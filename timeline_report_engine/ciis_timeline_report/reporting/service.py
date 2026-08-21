"""Module 7 - Advanced Report Generation.

Produces a professional forensic investigation report (Markdown + a JSON
twin) assembled *exclusively* from stored/computed findings passed in by the
pipeline. Every sentence is templated over concrete values (evidence ids,
scores, entity values, timestamps) - the generator has no free-text
capability, so it cannot hallucinate. Missing inputs produce an explicit
"not available" statement instead of invented content.

The retired ``report generation`` prototype has been removed; this report is stored
independently as ``investigation_report.md`` / ``investigation_report.json``.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from backend.modules.evidence.logger import get_logger
from backend.modules.evidence.utils import utc_now_iso
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.campaigns.models import CampaignAnalysis
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.correlation.models import CorrelationAnalysis, CrossCaseCorrelation
from ..analytics.models import CaseAnalytics
from ciis_correlation.core.data_access import CaseDataRepository, EvidenceContext
from ciis_correlation.core.repository import InvestigationReportRepository
from ciis_correlation.suspects.models import SuspectAssessment
from ..timeline.models import TimelineAnalysis
from . import pdf_renderer
from ciis_correlation.core.text import count_of

MODULE = "reporting"

#: Section key -> heading, in the order every renderer must emit them.
#:
#: The order follows the pipeline that produced the findings, so the report
#: reads in the sequence the analysis actually ran rather than an arbitrary
#: one: evidence is gathered, placed on a timeline, then correlated, clustered
#: into campaigns and attributed to suspects, and only then summarised and
#: acted on. Timeline precedes correlation here because a reader needs to know
#: *when* things happened before *how* they connect.
#:
#: This is the single definition. The Markdown writer, the JSON section map and
#: :mod:`.pdf_renderer` all derive their order from it, so the three exports
#: cannot drift apart.
SECTION_ORDER: List[tuple] = [
    ("executive_summary", "Executive Summary"),
    ("scope_and_methodology", "Scope & Methodology"),
    ("case_overview", "Case Overview"),
    ("evidence_summary", "Evidence Summary"),
    ("timeline_analysis", "Timeline Analysis"),
    ("correlation_analysis", "Correlation Analysis"),
    ("cross_case_correlation", "Cross-Case Correlation"),
    ("campaign_analysis", "Campaign Analysis"),
    ("suspect_assessment", "Suspect Assessment"),
    ("threat_intelligence_summary", "Threat Intelligence Summary"),
    ("model_predictions", "Model Prediction Results"),
    ("evidence_quality_summary", "Evidence Quality Summary"),
    ("metadata_summary", "Metadata Summary"),
    ("investigation_statistics", "Investigation Statistics"),
    ("confidence_analysis", "Confidence Analysis"),
    ("limitations", "Statement of Limitations"),
    ("investigation_conclusion", "Investigation Conclusion"),
    # Statutory basis sits between the conclusion and the actions: it reads as
    # "this is what the evidence shows, this is the law it engages, this is
    # what to do next", which is the order an investigating officer works in.
    ("legal_basis", "Statutory Basis"),
    ("recommendations", "Recommendations"),
    ("report_provenance", "Report Provenance & Integrity"),
    ("appendix", "Appendix"),
]


def _url_host(value: str) -> str:
    """Bare host of a URL or domain, for de-duplicating indicators.

    ``https://www.x.top/login`` and ``www.x.top`` are the same site and must
    not be reported as two separate findings.
    """
    text = (value or "").strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    host = text.split("/", 1)[0].split("?", 1)[0]
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    return host.split(":", 1)[0]


class InvestigationReportService:
    """Finding-referenced professional investigation report."""

    def __init__(
        self,
        config: InvestigationConfig,
        data: CaseDataRepository,
        repository: InvestigationReportRepository,
        audit: InvestigationAuditTrail,
    ) -> None:
        self._cfg = config
        self._data = data
        self._repo = repository
        self._audit = audit
        self._log = get_logger("investigation.reporting")

    # ------------------------------------------------------------------ public

    def generate(
        self,
        case_id: str,
        *,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        correlation: Optional[CorrelationAnalysis] = None,
        campaigns: Optional[CampaignAnalysis] = None,
        suspects: Optional[SuspectAssessment] = None,
        timeline: Optional[TimelineAnalysis] = None,
        analytics: Optional[CaseAnalytics] = None,
        priority: Optional[Dict[str, Any]] = None,
        cross_case: Optional[CrossCaseCorrelation] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Build the report; returns ``{"markdown": ..., "sections": ...}``."""
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        generated_at = utc_now_iso()
        report_id = (
            f"RPT-{case_id.replace('CASE_', '')}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )

        # Built in SECTION_ORDER sequence: dicts preserve insertion order, so
        # the stored JSON, the Markdown and the PDF all present the findings
        # in the same order without any renderer re-sorting them.
        built = {
            "executive_summary": lambda: self._executive_summary(
                case_id, items, correlation, campaigns, suspects, timeline,
                cross_case),
            "scope_and_methodology": lambda: self._scope_section(items),
            "case_overview": lambda: self._case_overview(case_id, items),
            "evidence_summary": lambda: self._evidence_summary(items),
            "timeline_analysis": lambda: self._timeline_section(timeline),
            "correlation_analysis": lambda: self._correlation_section(correlation),
            "cross_case_correlation": lambda: self._cross_case_section(cross_case),
            "campaign_analysis": lambda: self._campaign_section(campaigns),
            "suspect_assessment": lambda: self._suspect_section(suspects),
            "threat_intelligence_summary": lambda: self._threat_section(analytics),
            "model_predictions": lambda: self._model_predictions(items),
            "evidence_quality_summary": lambda: self._quality_section(
                analytics, items),
            "metadata_summary": lambda: self._metadata_section(items),
            "investigation_statistics": lambda: self._statistics_section(
                analytics, timeline
            ),
            "confidence_analysis": lambda: self._confidence_section(items),
            "limitations": lambda: self._limitations(timeline),
            "investigation_conclusion": lambda: self._conclusion(
                items, correlation, campaigns, suspects, timeline),
            "legal_basis": lambda: self._legal_section(
                case_id, items, campaigns, cross_case, analytics),
            "recommendations": lambda: self._recommendations(
                campaigns, suspects, timeline, priority, analytics),
            "report_provenance": lambda: self._provenance(
                case_id, items, report_id, generated_at),
            "appendix": lambda: self._appendix(items),
        }
        sections: Dict[str, Any] = {key: built[key]() for key, _ in SECTION_ORDER}
        markdown = self._render_markdown(case_id, sections)
        duration = round((time.perf_counter() - started) * 1000.0, 1)

        if persist:
            saved = self._repo.save(
                case_id, self._cfg.investigation_report_name, {
                    "report_id": report_id,
                    "sections": sections,
                    "generated_from": {
                        "correlation": correlation is not None,
                        "cross_case": cross_case is not None,
                        "campaigns": campaigns is not None,
                        "suspects": suspects is not None,
                        "timeline": timeline is not None,
                        "analytics": analytics is not None,
                        "priority": priority is not None,
                    },
                })
            self._repo.save_text(case_id, self._cfg.investigation_report_name,
                                 markdown, ".md")
            self._persist_pdf(case_id, sections, report_id, generated_at, saved)
            self._audit.record(case_id, MODULE, "generated",
                               f"{len(sections)} sections", duration_ms=duration)
        return {"markdown": markdown, "sections": sections,
                "report_id": report_id}

    def _persist_pdf(self, case_id, sections, report_id, generated_at,
                     saved_json_path) -> None:
        """Render + store the native PDF twin; never aborts the pipeline."""
        try:
            version = 1
            try:  # derive version from the just-saved JSON name (…_vN.json)
                stem = saved_json_path.stem
                if "_v" in stem:
                    version = int(stem.rsplit("_v", 1)[1])
            except (ValueError, AttributeError, IndexError):
                pass
            payload = pdf_renderer.render_pdf(
                case_id, sections, report_id=report_id,
                generated_at=generated_at, report_version=version)
            if payload is None:
                self._log.info("reportlab not installed; PDF twin skipped")
                return
            self._repo.save_binary(
                case_id, self._cfg.investigation_report_name, payload, ".pdf")
        except Exception as exc:  # noqa: BLE001 - PDF must never kill analysis
            self._log.warning("PDF rendering failed for %s: %s", case_id, exc)

    def regenerate_with_cross_case(
        self, case_id: str, cross_case: CrossCaseCorrelation
    ) -> Dict[str, Any]:
        """Rebuild a case's report from its stored artifacts + new cross-case data.

        Used for bidirectional propagation: when a newly analysed case links to
        an *already analysed* case, that other case's report must reflect the
        link without re-running its full Phase-2 analysis. Every module input is
        reloaded from its latest stored artifact, so no analysis is recomputed -
        only the report is regenerated.
        """
        correlation = self._load_model(case_id, self._cfg.correlation_report_name,
                                       CorrelationAnalysis)
        campaigns = self._load_model(case_id, self._cfg.campaign_report_name,
                                     CampaignAnalysis)
        suspects = self._load_model(case_id, self._cfg.suspect_report_name,
                                    SuspectAssessment)
        timeline = self._load_model(case_id, self._cfg.timeline_report_name,
                                    TimelineAnalysis)
        analytics = self._load_model(case_id, self._cfg.analytics_report_name,
                                     CaseAnalytics)
        priority_doc = self._repo.load_latest(case_id, self._cfg.priority_report_name)
        priority = priority_doc["report"] if priority_doc else None

        return self.generate(
            case_id,
            correlation=correlation,
            campaigns=campaigns,
            suspects=suspects,
            timeline=timeline,
            analytics=analytics,
            priority=priority,
            cross_case=cross_case,
        )

    def _load_model(self, case_id: str, report_name: str, model_cls):
        """Reconstruct a typed model from its latest stored artifact, or None."""
        document = self._repo.load_latest(case_id, report_name)
        if document is None:
            return None
        try:
            return model_cls.model_validate(document["report"])
        except Exception as exc:  # noqa: BLE001 - tolerate schema drift
            self._log.warning("could not reload %s for %s: %s",
                              report_name, case_id, exc)
            return None

    # ---------------------------------------------------------------- sections

    @staticmethod
    def _executive_summary(case_id, items, correlation, campaigns,
                           suspects, timeline, cross_case=None) -> List[str]:
        verified = sum(1 for item in items if item.hash_verified is True)
        lines = [
            f"Case {case_id} contains {count_of(len(items), 'evidence item')}; "
            f"{verified}/{len(items)} passed the stored SHA-256 integrity check."
        ]
        if cross_case is not None and cross_case.link_count:
            lines.append(
                "This case was automatically linked to "
                f"{count_of(cross_case.link_count, 'other case')}; these are "
                "candidate shared-entity associations: "
                f"{', '.join(cross_case.related_case_ids)} "
                "[cross_case_correlation.json]."
            )
        if correlation is not None:
            lines.append(
                f"The weighted correlation engine found "
                f"{count_of(correlation.related_pair_count, 'related evidence pair')} "
                f"out of {correlation.pair_count} analysed [correlation_analysis.json]."
            )
        if campaigns is not None and campaigns.campaign_count:
            largest = max(campaigns.campaigns, key=lambda c: len(c.members))
            lines.append(
                f"Clustering produced {count_of(campaigns.campaign_count, 'candidate campaign')}"
                f"; the largest ({largest.campaign_id}) groups "
                f"{count_of(len(largest.members), 'item')} for investigator review "
                "[campaign_analysis.json]."
            )
        if suspects is not None and suspects.suspect_count:
            top = suspects.suspects[0]
            lines.append(
                f"The highest-scoring identity lead is '{top.identity_value}' "
                f"({top.identity_type}), supported by "
                f"{count_of(len(top.evidence_ids), 'evidence item')} and scored "
                f"{top.confidence_score:.0f}/100; this is a lead, not identity "
                "attribution [suspect_assessment.json]."
            )
        if timeline is not None:
            inferred = int(timeline.statistics.get("inferred_event_count", 0))
            fallback = int(timeline.statistics.get("acquisition_fallback_count", 0))
            unresolved = int(timeline.statistics.get("unresolved_event_count", 0))
            event_times = max(0, len(timeline.events) - fallback - unresolved)
            inferred_event_times = max(0, inferred - fallback)
            lines.append(
                f"Chronology contains {count_of(event_times, 'evidence-derived event time')} "
                f"({inferred_event_times} inferred), {count_of(fallback, 'acquisition-only record')} "
                f"and {count_of(unresolved, 'unresolved record')} "
                "[timeline_analysis.json]."
            )
        if timeline is not None and timeline.stage_progression:
            assessable = bool(timeline.statistics.get(
                "progression_assessable", False
            ))
            if assessable:
                lines.append(
                    "Evidence-timed stage order: "
                    + " -> ".join(timeline.stage_progression)
                    + " [timeline_analysis.json]."
                )
            else:
                lines.append(
                    "Evidence-timed stage order is incomplete because one or "
                    "more detected stages has acquisition time only "
                    "[timeline_analysis.json]."
                )
        elif (
            timeline is not None
            and timeline.attack_stages
            and not bool(timeline.statistics.get("progression_assessable", False))
        ):
            lines.append(
                "Attack stages were detected, but no evidence-derived event "
                "times were available to order them [timeline_analysis.json]."
            )
        return lines

    @staticmethod
    def _case_overview(case_id, items) -> Dict[str, Any]:
        times = sorted(t for t in (c.upload_time for c in items) if t)
        return {
            "case_id": case_id,
            "evidence_count": len(items),
            "first_evidence": times[0] if times else "not available",
            "last_evidence": times[-1] if times else "not available",
            "file_types": sorted({c.file_name.rsplit('.', 1)[-1].lower()
                                  for c in items if '.' in c.file_name}),
        }

    @staticmethod
    def _evidence_summary(items) -> List[Dict[str, Any]]:
        summary = []
        for c in items:
            confidence = c.forensics.get("evidence_confidence") or {}
            summary.append({
                "evidence_id": c.evidence_id,
                "file_name": c.file_name,
                "upload_time": c.upload_time,
                "sha256": c.sha256,
                "hash_verified": c.hash_verified,
                "ocr_confidence": c.ocr_confidence,
                "evidence_confidence_score": confidence.get("confidence_score",
                                                            "not available"),
                "entity_count": len(c.entities),
            })
        return summary

    @staticmethod
    def _factor_rows(pair) -> List[Dict[str, Any]]:
        """The pair's factors as rows, so renderers need not parse the prose.

        ``explanation`` states every factor in one paragraph that ends each
        clause with ``[weight 0.66]``. As a table cell that is a wall of text,
        and the bracketed number is unlabelled - a reader cannot tell that it
        is this factor's share of the pair's total, nor that the total is what
        the confidence is computed from. The same factors are already carried
        structured on the pair, so they are passed through as rows here and laid
        out by each renderer. Nothing is recomputed: every number below is read
        straight off the stored factor.
        """
        rows: List[Dict[str, Any]] = []
        for factor in pair.factors:
            label = factor.factor.replace("_", " ")
            # The engine builds entity reasons as "Both items reference the
            # same <label>: <values>". With the label in its own column that
            # prefix repeats on every row, so the known template is dropped and
            # anything else is passed through untouched.
            prefix = f"Both items reference the same {label}: "
            reason = factor.reason
            detail = reason[len(prefix):] if reason.startswith(prefix) else reason
            rows.append({
                "factor": factor.factor,
                "label": label,
                "detail": detail,
                "contribution": factor.contribution,
                "type_weight": factor.weight,
                "matches": factor.matches,
            })
        return rows

    @classmethod
    def _correlation_section(cls, correlation) -> Any:
        if correlation is None:
            return "Correlation analysis not available for this case."
        return {
            "pair_count": correlation.pair_count,
            "related_pair_count": correlation.related_pair_count,
            "strength_distribution": correlation.strength_distribution,
            "top_relationships": [
                {
                    "pair": f"{p.evidence_a} <-> {p.evidence_b}",
                    "strength": p.relationship_strength,
                    "confidence": p.correlation_confidence,
                    "explanation": p.explanation,
                    # Additive: reports stored before these existed still
                    # render, from ``explanation`` alone.
                    "weight": p.correlation_weight,
                    "factors": cls._factor_rows(p),
                }
                for p in correlation.pairs[:5]
                if p.relationship_strength != "NO_RELATIONSHIP"
            ],
        }

    @staticmethod
    def _cross_case_section(cross_case) -> Any:
        if cross_case is None:
            return "Cross-case correlation was not evaluated for this case."
        if not cross_case.links:
            return "No cross-case correlations were found for this case."
        return {
            "related_case_count": len(cross_case.related_case_ids),
            "related_case_ids": cross_case.related_case_ids,
            "links": [
                {
                    "other_case_id": link.other_case_id,
                    "relationship_strength": link.relationship_strength,
                    "match_confidence": link.match_confidence,
                    "match_reason": link.match_reason,
                    "matched_entities": [
                        {
                            "entity_type": m.entity_type,
                            "value": m.value,
                            "this_evidence_ids": m.this_evidence_ids,
                            "other_evidence_ids": m.other_evidence_ids,
                        }
                        for m in link.matched_entities
                    ],
                }
                for link in cross_case.links
            ],
        }

    @staticmethod
    def _campaign_section(campaigns) -> Any:
        if campaigns is None:
            return "Campaign analysis not available for this case."
        return {
            "campaign_count": campaigns.campaign_count,
            "unclustered_evidence": campaigns.unclustered_evidence,
            "campaigns": [
                {
                    "campaign_id": c.campaign_id,
                    "members": c.members,
                    "confidence": c.campaign_confidence,
                    "signature": c.signature,
                    "summary": c.summary,
                }
                for c in campaigns.campaigns
            ],
        }

    @staticmethod
    def _timeline_section(timeline) -> Any:
        if timeline is None:
            return "Timeline analysis not available for this case."
        inferred = int(timeline.statistics.get("inferred_event_count", 0))
        fallback = int(timeline.statistics.get("acquisition_fallback_count", 0))
        unresolved = int(timeline.statistics.get("unresolved_event_count", 0))
        if fallback or unresolved:
            reliability = (
                "Chronology is provisional: acquisition time is an intake "
                "timestamp, not proof of when the underlying event occurred. "
                "Every fallback and unresolved value must be checked against "
                "the source exhibit."
            )
        elif inferred:
            reliability = (
                "Chronology includes inferred values. Date-only values are "
                "normalised to 00:00 UTC and do not establish an exact time."
            )
        else:
            reliability = (
                "All events have non-inferred content or metadata timestamps; "
                "their accuracy still depends on the source exhibit and clock."
            )
        chronological_events = [
            {
                "timestamp": event.timestamp or "unresolved",
                "evidence_id": event.evidence_id,
                "file_name": event.file_name,
                "event_type": event.event_type,
                "description": event.description,
                "timestamp_source": event.time_source,
                "timestamp_confidence": event.confidence,
                "timestamp_inferred": event.timestamp_inferred,
                "stages": event.stages,
                "critical": event.critical,
                "critical_reasons": event.critical_reasons,
            }
            for event in timeline.events
        ]
        event_time_events = [
            event for event in chronological_events
            if event["timestamp"] != "unresolved"
            and event["timestamp_source"] != "upload_time_fallback"
        ]
        acquisition_records = [
            event for event in chronological_events
            if event["timestamp_source"] == "upload_time_fallback"
        ]
        unresolved_records = [
            event for event in chronological_events
            if event["timestamp"] == "unresolved"
        ]

        return {
            "summary": timeline.summary,
            "timestamp_quality": {
                "event_count": len(timeline.events),
                "non_inferred_count": int(timeline.statistics.get(
                    "non_inferred_event_count", len(timeline.events) - inferred
                )),
                "inferred_count": inferred,
                "acquisition_fallback_count": fallback,
                "unresolved_count": unresolved,
                "reliability_note": reliability,
            },
            "stage_progression": timeline.stage_progression,
            "progression_consistent": timeline.progression_consistent,
            "progression_assessable": bool(timeline.statistics.get(
                "progression_assessable", not fallback and not unresolved
            )),
            # The complete compatibility view remains available to API clients,
            # while formal renderers can keep incident chronology separate from
            # intake provenance and unresolved records.
            "chronological_events": chronological_events,
            "event_time_events": event_time_events,
            "acquisition_records": acquisition_records,
            "unresolved_records": unresolved_records,
            "milestones": [
                {
                    "timestamp": m.timestamp or "unresolved",
                    "timestamp_source": m.time_source,
                    "timestamp_confidence": m.confidence,
                    "timestamp_inferred": m.timestamp_inferred,
                    "description": m.description,
                }
                for m in timeline.milestones
            ],
            "critical_events": [
                {
                    "timestamp": e.timestamp or "unresolved",
                    "timestamp_source": e.time_source,
                    "timestamp_confidence": e.confidence,
                    "timestamp_inferred": e.timestamp_inferred,
                    "evidence_id": e.evidence_id,
                    "reasons": e.critical_reasons,
                }
                for e in timeline.critical_events
            ],
        }

    @staticmethod
    def _suspect_section(suspects) -> Any:
        if suspects is None or not suspects.suspect_count:
            return "No suspect anchors were derived from the evidence."
        return [
            {
                "suspect_id": s.suspect_id,
                "identity": f"{s.identity_type}:{s.identity_value}",
                "confidence_score": s.confidence_score,
                "confidence_level": s.confidence_level,
                "risk_level": s.risk_level,
                "evidence_ids": s.evidence_ids,
                "explanation": s.explanation,
            }
            for s in suspects.suspects[:10]
        ]

    @staticmethod
    def _threat_section(analytics) -> Any:
        if analytics is None:
            return "Threat statistics not available."
        stats = analytics.threat_statistics
        if not stats.get("intel_available"):
            return ("No threat-intelligence indicator file was provided; "
                    "threat corroboration was skipped (not an absence of threat).")
        return stats

    @staticmethod
    def _scope_section(items) -> Dict[str, Any]:
        """SWGDE-style scope & methodology statement (tools + reproducibility).

        Report-writing best practice requires the methodology to be recorded
        in enough detail that the process is reproducible; this section names
        every module that contributed findings and the storage layout needed
        to re-derive them.
        """
        return {
            "objective": (
                "Acquire, verify, correlate and reconstruct the digital "
                "evidence for this case, and derive investigative leads "
                "(identity anchors, candidate clusters and cross-case links) "
                "from stored artifacts while preserving each item's recorded "
                "integrity status."),
            "evidence_scope": (
                f"{count_of(len(items), 'evidence item')} acquired through the CIIS "
                "intake pipeline with a recorded SHA-256 digest."),
            "methodology": [
                "Phase 1 - Acquisition & OCR: PaddleOCR PP-OCRv5 text "
                "extraction with per-item confidence scoring; SHA-256 "
                "fingerprint recorded at intake and re-verified at read.",
                "Phase 1 - Forensics: metadata/EXIF consistency, forgery "
                "signals, logo detection and evidence-confidence scoring "
                "stored per item under storage/forensics/.",
                "Phase 2 - Correlation: weighted entity-overlap engine "
                "scoring every evidence pair; results in "
                "correlation_analysis.json.",
                "Phase 2 - Cross-case: shared-entity matching against every "
                "other analysed case (cross_case_correlation.json).",
                "Phase 2 - Campaigns / Suspects / Timeline: clustering, "
                "anchor derivation and event reconstruction over the "
                "correlated evidence set.",
                "Threat intelligence: URL/domain indicators scored by the "
                "configured provider (static indicator file, or the trained "
                "phishing classifier when CIIS_ML_THREAT_INTEL=1); "
                "per-indicator results in 'Model Prediction Results'.",
                "Reporting: this document is assembled exclusively from the "
                "stored outputs above; it contains no free-text generation.",
            ],
            "reproducibility": (
                "Re-running the analysis against the same stored evidence "
                "recomputes the canonical artifacts; report control records "
                "the evidence-set digest and the stored JSON companion retains "
                "the complete source-artifact hash register."),
        }

    def _model_predictions(self, items) -> Any:
        """Per-indicator threat-model predictions (URL/domain classifier).

        Surfaces the *individual* verdicts behind the aggregate threat
        statistics: indicator, verdict, risk score, model confidence and the
        model that produced it. With the ML provider enabled these are live
        XGBoost classifications; with the static provider they are feed
        lookups; with neither, an explicit unavailability statement.
        """
        intel = getattr(self._data, "threat_intel", None)
        if intel is None or not getattr(intel, "available", False):
            return ("No threat-intelligence provider was active during this "
                    "analysis; indicator-level model predictions were not "
                    "produced (this is a coverage gap, not an absence of "
                    "threat).")
        predictions: List[Dict[str, Any]] = []
        seen: set = set()
        # Entity extraction emits both the full URL and its bare host, so the
        # same site would otherwise be classified twice - and the schemeless
        # host scores worse ("does not use HTTPS") purely because it has no
        # scheme. Classify the full URL and skip a domain already covered by
        # one; URLs are listed first so the host is always seen after it.
        hosts_covered: set = set()
        for context in items:
            urls, domains = [], []
            try:
                urls = list(context.entity_values("urls"))
                domains = list(context.entity_values("domains"))
            except Exception:  # noqa: BLE001 - malformed entity lists
                pass
            for value in urls + domains:
                key = value.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                host = _url_host(key)
                if host in hosts_covered:
                    continue
                hosts_covered.add(host)
                try:
                    hit = intel.lookup(value)
                except Exception:  # noqa: BLE001 - one bad value can't abort
                    hit = None
                if hit is None:
                    continue
                row = {
                    "indicator": value,
                    "evidence_id": context.evidence_id,
                    "verdict": hit.get("verdict", "unknown"),
                    "risk_score": hit.get("risk_score"),
                    "confidence": hit.get("confidence"),
                    "risk_level": hit.get("risk_level", ""),
                    "source": hit.get("source", "indicator-file"),
                    "model_version": hit.get("model_version", ""),
                }
                # Carry through the investigator-facing detail when the
                # provider supplies it (the ML adapter does; the static
                # indicator file does not). Empty values are dropped so the
                # report never shows a blank "Registrar:" line.
                for key in ("domain", "trust_score", "brand_impersonated",
                            "official_domain", "ssl_status", "domain_age_days",
                            "registrar", "spf_present", "dmarc_present",
                            "ssl_days_left", "hosting", "ip_address",
                            "reasons", "threat_signals", "trust_signals"):
                    if key in hit and hit[key] not in ("", None, []):
                        row[key] = hit[key]
                predictions.append(row)
        if not predictions:
            return ("The active threat-intelligence provider returned no "
                    "classification for any URL/domain indicator in this "
                    "case's evidence.")
        malicious = sum(1 for p in predictions
                        if p["verdict"] in ("malicious", "phishing"))
        predictions.sort(
            key=lambda p: (p.get("risk_score") or 0), reverse=True)
        return {
            "indicators_classified": len(predictions),
            "flagged_malicious": malicious,
            "predictions": predictions,
        }

    def _provenance(self, case_id, items, report_id, generated_at) -> Dict[str, Any]:
        """SHA-256 digests tying this report to its exact source artifacts.

        Ported from the retired Module-6 prototype, which hashed its source
        timeline.json; here every contributing stored artifact is hashed so
        the report can always be re-tied to the precise inputs it was built
        from (evidentiary traceability).
        """
        hashes: Dict[str, str] = {}
        artifact_names = (
            self._cfg.correlation_report_name,
            self._cfg.cross_case_report_name,
            self._cfg.campaign_report_name,
            self._cfg.suspect_report_name,
            self._cfg.timeline_report_name,
            self._cfg.analytics_report_name,
            self._cfg.priority_report_name,
            self._cfg.graph_report_name,
        )
        for name in artifact_names:
            try:
                versions = self._repo.list_versions(case_id, name, ".json")
                if versions:
                    digest = hashlib.sha256(
                        versions[-1].read_bytes()).hexdigest()
                    hashes[versions[-1].name] = digest
            except OSError:
                continue
        evidence_digest = hashlib.sha256(
            "".join(sorted(c.sha256 or "" for c in items)).encode("utf-8")
        ).hexdigest()
        return {
            "report_id": report_id,
            "generated_at": generated_at,
            "generator": ("CIIS Phase-2 reporting module "
                          "(template-over-data; no free-text generation)"),
            "evidence_set_digest": evidence_digest,
            "evidence_set_digest_note": (
                "SHA-256 over the sorted SHA-256 digests of every evidence "
                "item; any change to the evidence set changes this value."),
            "source_artifact_hashes": hashes,
        }

    @staticmethod
    def _quality_section(analytics, items) -> Any:
        if analytics is not None and analytics.evidence_quality_statistics:
            return analytics.evidence_quality_statistics
        return {"hash_verified_count":
                sum(1 for c in items if c.hash_verified is True)}

    @staticmethod
    def _metadata_section(items) -> List[Dict[str, Any]]:
        rows = []
        for c in items:
            metadata = c.forensics.get("metadata_report")
            if not metadata:
                continue
            image = metadata.get("image") or {}
            rows.append({
                "evidence_id": c.evidence_id,
                "has_exif": image.get("has_exif", False),
                "device": image.get("device", ""),
                "software": image.get("software", ""),
                "consistency_notes": metadata.get("consistency_notes", []),
            })
        return rows or [{"note": "No Phase-1 metadata reports stored for this case."}]

    @staticmethod
    def _statistics_section(analytics, timeline=None) -> Any:
        if analytics is None and timeline is None:
            return "Analytics not available."
        return {
            "entity_statistics": (
                analytics.entity_statistics if analytics is not None
                else "not available"
            ),
            "campaign_statistics": (
                analytics.campaign_statistics if analytics is not None
                else "not available"
            ),
            # Reporting receives the current TimelineAnalysis directly. Use it
            # instead of a previously persisted analytics snapshot so a focused
            # timeline/report refresh cannot publish contradictory statistics.
            "timeline_statistics": (
                timeline.statistics if timeline is not None
                else analytics.timeline_statistics
            ),
            "correlation_statistics": (
                analytics.correlation_statistics if analytics is not None
                else "not available"
            ),
        }

    @staticmethod
    def _confidence_section(items) -> List[Dict[str, Any]]:
        rows = []
        for c in items:
            confidence = c.forensics.get("evidence_confidence")
            if confidence:
                rows.append({
                    "evidence_id": c.evidence_id,
                    "score": confidence.get("confidence_score"),
                    "level": confidence.get("confidence_level"),
                    "explanation": confidence.get("explanation", ""),
                })
        return rows or [{"note": "No Phase-1 confidence scores stored for this case."}]

    @staticmethod
    def _limitations(timeline) -> List[str]:
        """Interpretive boundaries that must travel with every report format."""
        lines = [
            "This automated report organises submitted material and computed "
            "leads. It does not determine guilt or attribute an offence to a "
            "person.",
            "OCR and entity extraction can omit, merge or misclassify text. "
            "Identifiers, amounts and names must be verified in the original "
            "exhibit before operational use.",
            "Correlation and cross-case scores measure shared features, not "
            "causation, common ownership or identity.",
            "Campaign clusters and identity-anchor scores are prioritisation "
            "aids that require independent corroboration.",
            "Threat-intelligence verdicts reflect the configured provider and "
            "its coverage at analysis time; no match does not prove safety.",
            "New evidence or corrected extraction may change any finding in "
            "this report.",
        ]
        if timeline is None:
            lines.insert(2, "Timeline coverage was unavailable for this report.")
        else:
            inferred = int(timeline.statistics.get("inferred_event_count", 0))
            fallback = int(timeline.statistics.get(
                "acquisition_fallback_count", 0
            ))
            unresolved = int(timeline.statistics.get(
                "unresolved_event_count", 0
            ))
            lines.insert(
                2,
                f"Timeline quality: {inferred} inferred timestamp(s), including "
                f"{fallback} acquisition-time fallback(s), and {unresolved} "
                "unresolved timestamp(s). Date-only values use 00:00 UTC; "
                "fallbacks describe intake time rather than event time.",
            )
        return lines

    def _legal_section(self, case_id, items, campaigns, cross_case,
                       analytics) -> Dict[str, Any]:
        """Which provisions of the Electronic Transactions Act the findings engage.

        Built here rather than in the pipeline because it is derived purely from
        findings the report already holds - no new storage, no new artifact, and
        nothing to keep in sync.
        """
        from ..legal.service import LegalBasisService

        assessment = LegalBasisService(self._cfg, self._audit).assess(
            case_id, items, campaigns=campaigns, cross_case=cross_case,
            analytics=analytics,
        )
        return assessment.model_dump()

    @staticmethod
    def _conclusion(items, correlation, campaigns, suspects, timeline) -> List[str]:
        lines: List[str] = []
        verified = sum(1 for c in items if c.hash_verified is True)
        lines.append(
            f"{verified}/{count_of(len(items), 'evidence item')} passed SHA-256 "
            "integrity verification; this establishes stored-file integrity, "
            "not the truth of its content."
        )
        if correlation is not None and correlation.related_pair_count:
            lines.append(
                f"The engine identified {count_of(correlation.related_pair_count, 'weighted association')} "
                "for manual corroboration; shared features alone do not prove "
                "that the items have a common actor or cause."
            )
        if campaigns is not None and campaigns.campaign_count:
            verb = "requires" if campaigns.campaign_count == 1 else "require"
            lines.append(
                f"{count_of(campaigns.campaign_count, 'candidate campaign cluster')} "
                f"met the configured clustering criteria and {verb} investigator "
                "review before being treated as coordinated activity."
            )
        if suspects is not None and suspects.suspect_count:
            top = suspects.suspects[0]
            lines.append(
                f"Validate the ownership and role of identity lead "
                f"'{top.identity_value}' ({top.confidence_score:.0f}/100 model "
                f"score; {count_of(len(top.evidence_ids), 'supporting evidence item')}) "
                "against provider records and the original exhibits."
            )
        if timeline is not None:
            fallback = int(timeline.statistics.get(
                "acquisition_fallback_count", 0
            ))
            unresolved = int(timeline.statistics.get(
                "unresolved_event_count", 0
            ))
            assessable = bool(timeline.statistics.get(
                "progression_assessable", not fallback and not unresolved
            ))
            if not assessable:
                lines.append(
                    "The keyword-derived stage order is provisional because "
                    "one or more stage-bearing items lack a reliable event time."
                )
            elif not timeline.progression_consistent:
                lines.append(
                    "The keyword-derived stage order differs from the configured "
                    "reference sequence and should be checked against the exhibits."
                )
        return lines

    #: Where each payment rail's records actually live - so a recommendation
    #: names the institution to serve, not just "the provider".
    #: Each entry names the institution that holds the relevant records and the
    #: record class to request. KYC is retained because it appears on provider
    #: request forms; it is paired with a plain-language description.
    _RAIL_AUTHORITIES = {
        "esewa_ids": ("eSewa", "subscriber/KYC ownership and transaction history"),
        "khalti_ids": ("Khalti", "subscriber/KYC ownership and transaction history"),
        "imepay_ids": ("IME Pay", "subscriber/KYC ownership and transaction history"),
        "bank_accounts": ("the relevant bank", "account-holder identity and statements"),
        "card_numbers": ("the card issuer", "cardholder and transaction records"),
        "eth_wallets": ("a crypto-tracing specialist", "transaction tracing"),
        "btc_wallets": ("a crypto-tracing specialist", "transaction tracing"),
    }

    #: How a brand name is written in a report ("esewa" is a matcher key).
    _BRAND_NAMES = {
        "esewa": "eSewa", "khalti": "Khalti", "imepay": "IME Pay",
        "connectips": "ConnectIPS", "fonepay": "Fonepay",
        "nabil": "Nabil Bank", "nicasia": "NIC Asia Bank",
        "globalime": "Global IME Bank", "machhapuchchhre": "Machhapuchchhre Bank",
        "nepalbank": "Nepal Bank", "rastriyabanijya": "Rastriya Banijya Bank",
        "nrb": "Nepal Rastra Bank", "ntc": "Nepal Telecom", "ncell": "Ncell",
        "facebook": "Facebook", "instagram": "Instagram",
        "whatsapp": "WhatsApp", "gmail": "Gmail", "google": "Google",
    }

    #: Hard cap on one action line. A recommendation an investigator cannot
    #: read in a glance does not get acted on; detail lives in the sections
    #: above, which this list points at.
    _MAX_ACTION_CHARS = 150

    @classmethod
    def _recommendations(cls, campaigns, suspects, timeline, priority,
                         analytics=None) -> List[str]:
        """One concise, operationally formal action per line.

        Each line is a single sentence naming what to do and to which
        identifier, capped at ~150 characters. No rationale and no repetition:
        the evidence behind each action is in the report sections above it.
        """
        actions: List[str] = []

        # -- 1. Take down the infrastructure -------------------------------
        flagged = list(getattr(analytics, "threat_indicators", None) or [])
        hosts: List[str] = []
        for indicator in flagged:
            host = _url_host(indicator.value)
            if host and host not in hosts:
                hosts.append(host)
        if hosts:
            shown = ", ".join(hosts[:2])
            more = f" (+{len(hosts) - 2} more)" if len(hosts) > 2 else ""
            actions.append(
                "Issue preservation requests to the relevant hosting providers, "
                f"then seek suspension of the suspected domains: {shown}{more}."
            )
        brands = sorted({i.brand_impersonated for i in flagged
                         if i.brand_impersonated})
        if brands:
            named = ", ".join(cls._BRAND_NAMES.get(b, b.title())
                              for b in brands[:3])
            actions.append(
                f"Notify {named} of suspected brand impersonation and request "
                "preservation of any related abuse records."
            )

        # -- 2. Follow the money -------------------------------------------
        by_rail = dict(getattr(analytics, "wallet_statistics_by_rail", None) or {})
        for rail, values in by_rail.items():
            if not values:
                continue
            authority, records = cls._RAIL_AUTHORITIES.get(
                rail, ("the operating institution", "account records"))
            ids = ", ".join(v.value for v in values[:2])
            extra = f" (+{len(values) - 2} more)" if len(values) > 2 else ""
            actions.append(
                f"Request {records} from {authority} for: {ids}{extra}."
            )
        transaction_ids = (getattr(analytics, "top_entities", None) or {}
                           ).get("transaction_ids") or []
        if transaction_ids:
            codes = ", ".join(v.value.upper() for v in transaction_ids[:3])
            actions.append(
                "Verify these extracted payment references against the source "
                f"exhibits before including them in record requests: {codes}."
            )

        # -- 3. Identify the actor -------------------------------------------
        anchors = [s for s in (getattr(suspects, "suspects", None) or [])[:2]
                   if s.threat_flagged or s.confidence_score >= 60]
        if anchors:
            named = ", ".join(s.identity_value for s in anchors)
            actions.append(
                "Ask the relevant provider to verify registration, ownership "
                f"and transaction records for {named}; confirm each party's role."
            )
        clustered = [c for c in (getattr(campaigns, "campaigns", None) or [])
                     if c.shared_domains]
        if clustered:
            total = sum(len(c.members) for c in clustered)
            actions.append(
                f"Review {total} items as a candidate cluster because they share "
                "a website; corroborate the link before combining incidents."
            )

        # -- 4. Victim care & handling ----------------------------------------
        if (getattr(analytics, "entity_statistics", None) or {}).get("otp"):
            actions.append(
                "Advise the complainant to reset affected credentials and ask "
                "the relevant bank or wallet provider to monitor the account."
            )
        critical = len([
            event for event in (getattr(timeline, "critical_events", None) or [])
            if event.time_source != "upload_time_fallback"
        ])
        if critical:
            actions.append(
                f"Review the {count_of(critical, 'flagged event')} with the source "
                "exhibits; confirm each event's time, participants and any loss "
                "with the "
                "complainant."
            )
        if priority is not None:
            level = str(priority.get("priority_level", "")).lower()
            score = priority.get("priority_score")
            urgency = {
                "critical": "Assign immediate queue priority",
                "high": "Assign high queue priority",
                "medium": "Assign standard queue priority",
                "low": "Assign low queue priority",
            }.get(level, "Assign standard queue priority")
            scored = f" (rated {float(score):.0f} out of 100)" \
                if isinstance(score, (int, float)) else ""
            actions.append(f"{urgency}{scored}.")

        # Presentation (numbering, bullets) belongs to the renderers - the
        # markdown writer prefixes "- " and the report view prefixes "N." so
        # numbering here produced "1. 1. ...".
        deduped: List[str] = []
        for text in actions:
            cleaned = " ".join(text.split())
            if len(cleaned) > cls._MAX_ACTION_CHARS:
                cleaned = cleaned[: cls._MAX_ACTION_CHARS - 3].rsplit(" ", 1)[0] + "..."
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped or [
            "No specific action items derived; continue standard processing."
        ]

    @staticmethod
    def _appendix(items) -> Dict[str, Any]:
        return {
            "chain_of_custody": [
                {"evidence_id": c.evidence_id, "sha256": c.sha256,
                 "upload_time": c.upload_time, "status": c.status}
                for c in items
            ],
            "stored_artifacts_root": "storage/investigation/<CASE_ID>/",
            "phase1_artifacts_root": "storage/forensics/<EVIDENCE_ID>/",
        }

    # ---------------------------------------------------------------- renderer

    @staticmethod
    def _render_markdown(case_id: str, sections: Dict[str, Any]) -> str:
        titles = dict(SECTION_ORDER)
        out: List[str] = [
            f"# Forensic Investigation Report - {case_id}",
            "",
            f"Generated: {utc_now_iso()}  ",
            "Produced by: Cybercrime Investigation Intelligence Engine (CIIS), "
            "Phase 2  ",
            "Status: Automated analytical draft - investigator review required  ",
            "Basis: every statement below references stored forensic findings; "
            "accuracy depends on the source evidence and upstream extraction.",
            "",
        ]
        for key, title in titles.items():
            out.append(f"## {title}")
            out.append("")
            if key == "legal_basis":
                out.extend(_legal_markdown(sections.get(key)))
            elif key == "scope_and_methodology":
                out.extend(_scope_markdown(sections.get(key)))
            elif key == "case_overview":
                out.extend(_case_overview_markdown(sections.get(key)))
            elif key == "evidence_summary":
                out.extend(_evidence_markdown(sections.get(key)))
            elif key == "timeline_analysis":
                out.extend(_timeline_markdown(sections.get(key)))
            elif key == "correlation_analysis":
                out.extend(_correlation_markdown(sections.get(key)))
            elif key == "cross_case_correlation":
                out.extend(_cross_case_markdown(sections.get(key)))
            elif key == "campaign_analysis":
                out.extend(_campaign_markdown(sections.get(key)))
            elif key == "suspect_assessment":
                out.extend(_suspect_markdown(sections.get(key)))
            elif key == "metadata_summary":
                out.extend(_metadata_markdown(sections.get(key)))
            elif key == "confidence_analysis":
                out.extend(_confidence_markdown(sections.get(key)))
            elif key in {
                "executive_summary", "limitations",
                "investigation_conclusion", "recommendations",
            }:
                label = {
                    "executive_summary": "Finding",
                    "limitations": "Review boundary",
                    "investigation_conclusion": "Conclusion",
                    "recommendations": "Investigator action",
                }[key]
                out.extend(_numbered_markdown(sections.get(key), label))
            else:
                out.extend(_to_markdown(sections.get(key)))
            out.append("")
        return "\n".join(out)


def _markdown_cell(value: Any) -> str:
    """Keep generated Markdown tables valid when evidence text contains pipes."""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value) or "none"
    return str(value if value not in (None, "") else "none").replace("|", "\\|")


def _short(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0] + "…"


def _markdown_table(headers: List[str], rows: List[List[Any]]) -> List[str]:
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend(
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in rows
    )
    if not rows:
        output.append("| " + " | ".join("none" for _ in headers) + " |")
    return output


def _numbered_markdown(section: Any, label: str) -> List[str]:
    if not isinstance(section, list):
        return _to_markdown(section)
    return _markdown_table(
        ["#", label],
        [[index, item] for index, item in enumerate(section, start=1)],
    )


def _case_overview_markdown(section: Any) -> List[str]:
    if not isinstance(section, dict):
        return _to_markdown(section)
    return _markdown_table(
        ["Case field", "Recorded value"],
        [[str(key).replace("_", " ").title(), value]
         for key, value in section.items()],
    )


def _scope_markdown(section: Any) -> List[str]:
    if not isinstance(section, dict):
        return _to_markdown(section)
    out = _markdown_table(
        ["Scope", "Recorded basis"],
        [["Objective", section.get("objective", "not available")],
         ["Evidence scope", section.get("evidence_scope", "not available")],
         ["Reproducibility", section.get("reproducibility", "not available")]],
    )
    out += ["", "### Processing stages", ""]
    rows = []
    for method in section.get("methodology") or []:
        stage, separator, detail = str(method).partition(":")
        rows.append([stage, detail.strip() if separator else method])
    out += _markdown_table(["Stage", "Method and stored output"], rows)
    return out


def _evidence_markdown(section: Any) -> List[str]:
    if not isinstance(section, list) or not section or not isinstance(section[0], dict):
        return _to_markdown(section)
    return _markdown_table(
        ["Evidence", "File", "Acquired", "OCR confidence", "Entities", "Integrity"],
        [[row.get("evidence_id", ""), row.get("file_name", ""),
          row.get("upload_time", ""), row.get("ocr_confidence", ""),
          row.get("entity_count", 0),
          "VERIFIED" if row.get("hash_verified") else "FAILED"]
         for row in section],
    )


def _metadata_markdown(section: Any) -> List[str]:
    if not isinstance(section, list) or not section or "evidence_id" not in section[0]:
        return _to_markdown(section)
    return _markdown_table(
        ["Evidence", "EXIF", "Device", "Software", "Consistency notes"],
        [[row.get("evidence_id", ""), row.get("has_exif", False),
          row.get("device", ""), row.get("software", ""),
          row.get("consistency_notes", [])] for row in section],
    )


def _confidence_markdown(section: Any) -> List[str]:
    if not isinstance(section, list) or not section or "evidence_id" not in section[0]:
        return _to_markdown(section)
    return _markdown_table(
        ["Evidence", "Score", "Level", "Computed explanation"],
        [[row.get("evidence_id", ""), row.get("score", ""),
          row.get("level", ""), _short(row.get("explanation", ""))]
         for row in section],
    )


def _correlation_basis_cell(row: Dict[str, Any]) -> str:
    """One pair's factors as a compact cell.

    Falls back to the prose explanation for reports stored before the
    structured factors were carried through.
    """
    factors = row.get("factors") or []
    if not factors:
        return _short(row.get("explanation", ""))
    parts = [
        f"**{str(factor.get('label', '')).title()}** (+"
        f"{float(factor.get('contribution') or 0):.2f}): "
        f"{_short(str(factor.get('detail', '')), 90)}"
        for factor in factors
    ]
    return "<br>".join(parts)


def _correlation_markdown(section: Any) -> List[str]:
    if not isinstance(section, dict):
        return _to_markdown(section)
    out = [
        f"{section.get('related_pair_count', 0)} of "
        f"{section.get('pair_count', 0)} analysed pairs met a configured "
        "relationship threshold.",
        "",
        "Each factor below contributes points. The points sum to the pair's "
        "total weight, and the confidence is that total put through a "
        "saturating curve - so more corroborating factors raise confidence, "
        "but no single factor can carry a pair to certainty on its own.",
        "",
    ]
    out += _markdown_table(
        ["Evidence pair", "Strength", "Weight", "Confidence", "Contributing factors"],
        [[
            row.get("pair", ""),
            row.get("strength", ""),
            (f"{float(row['weight']):.2f}" if row.get("weight") is not None else "-"),
            row.get("confidence", ""),
            _correlation_basis_cell(row),
        ] for row in section.get("top_relationships") or []],
    )
    return out


def _cross_case_markdown(section: Any) -> List[str]:
    if not isinstance(section, dict):
        return _to_markdown(section)
    rows = []
    for link in section.get("links") or []:
        matches = link.get("matched_entities") or []
        indicators = [
            f"{match.get('entity_type', '')}:{match.get('value', '')}"
            for match in matches[:5]
        ]
        if len(matches) > 5:
            indicators.append(f"+{len(matches) - 5} more")
        rows.append([
            link.get("other_case_id", ""),
            link.get("relationship_strength", ""),
            link.get("match_confidence", ""),
            indicators,
            _short(link.get("match_reason", ""), 180),
        ])
    out = [
        "These are automated shared-entity associations and require "
        "independent corroboration.",
        "",
    ]
    out += _markdown_table(
        ["Other case", "Strength", "Confidence", "Matched indicators", "Basis"],
        rows,
    )
    return out


def _campaign_markdown(section: Any) -> List[str]:
    if not isinstance(section, dict):
        return _to_markdown(section)
    rows = [[
        campaign.get("campaign_id", ""),
        campaign.get("members", []),
        campaign.get("confidence", ""),
        (campaign.get("signature") or [])[:5],
    ] for campaign in section.get("campaigns") or []]
    out = [
        "Clusters are candidate groupings produced by configured thresholds; "
        "they do not by themselves establish coordination.",
        "",
    ]
    out += _markdown_table(
        ["Candidate cluster", "Evidence", "Confidence", "Shared signature"],
        rows,
    )
    if section.get("unclustered_evidence"):
        out += [
            "",
            "**Unclustered evidence:** "
            + ", ".join(section["unclustered_evidence"]),
        ]
    return out


def _suspect_markdown(section: Any) -> List[str]:
    if not isinstance(section, list):
        return _to_markdown(section)
    out = [
        "> Identity anchors are investigative leads, not legal attribution. "
        "Verify ownership and role using original exhibits and independent records.",
        "",
    ]
    out += _markdown_table(
        ["Identity lead", "Score", "Confidence", "Risk", "Supporting evidence"],
        [[
            row.get("identity", ""),
            row.get("confidence_score", ""),
            row.get("confidence_level", ""),
            row.get("risk_level", ""),
            row.get("evidence_ids", []),
        ] for row in section],
    )
    return out


def _timeline_markdown(section: Any) -> List[str]:
    """Render chronology as an investigator-readable table, not a dict dump."""
    if not isinstance(section, dict):
        return _to_markdown(section)

    out: List[str] = []
    if section.get("summary"):
        out += [str(section["summary"]), ""]
    quality = section.get("timestamp_quality") or {}
    if quality.get("reliability_note"):
        out += [f"> {quality['reliability_note']}", ""]
    out += [
        "| Events | Non-inferred | Inferred | Acquisition fallback | Unresolved |",
        "| ---: | ---: | ---: | ---: | ---: |",
        "| {event_count} | {non_inferred_count} | {inferred_count} | "
        "{acquisition_fallback_count} | {unresolved_count} |".format(
            event_count=quality.get("event_count", 0),
            non_inferred_count=quality.get("non_inferred_count", 0),
            inferred_count=quality.get("inferred_count", 0),
            acquisition_fallback_count=quality.get(
                "acquisition_fallback_count", 0
            ),
            unresolved_count=quality.get("unresolved_count", 0),
        ),
        "",
        "### Chronological Events",
        "",
        "| Timestamp (UTC) | Evidence | File | Source | Confidence | Inferred | Stages |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for event in section.get("chronological_events") or []:
        out.append(
            "| " + " | ".join(_markdown_cell(event.get(key)) for key in (
                "timestamp", "evidence_id", "file_name", "timestamp_source",
                "timestamp_confidence", "timestamp_inferred", "stages",
            )) + " |"
        )
    if not section.get("chronological_events"):
        out.append("| none | none | none | none | none | none | none |")

    stages = section.get("stage_progression") or []
    out += [
        "",
        "### Stage Assessment",
        "",
        f"- **Keyword-derived order:** {_markdown_cell(stages)}",
        f"- **Order assessable:** {section.get('progression_assessable', False)}",
        f"- **Matches configured sequence:** "
        f"{section.get('progression_consistent', False)}",
        "",
        "### Critical Events",
        "",
    ]
    critical = section.get("critical_events") or []
    if not critical:
        out.append("- none")
    for event in critical:
        reasons = "; ".join(event.get("reasons") or []) or "no reason recorded"
        out.append(
            f"- **{event.get('evidence_id', 'unknown')}** at "
            f"{event.get('timestamp', 'unresolved')} "
            f"({event.get('timestamp_source', 'unresolved')}, "
            f"{event.get('timestamp_confidence', 'unknown')}, "
            f"inferred={event.get('timestamp_inferred', False)}): {reasons}"
        )
    return out


def _legal_markdown(section: Any) -> List[str]:
    """Statutory basis as prose, not as a flattened key/value dump.

    The generic renderer emits every provision's fields as sibling bullets, so
    a reader cannot see where one section of the Act ends and the next begins -
    which is exactly the distinction that matters here.
    """
    if not isinstance(section, dict):
        return _to_markdown(section)

    out: List[str] = []
    if section.get("summary"):
        out += [section["summary"], ""]
    out += [
        f"**Statute:** {section.get('statute', 'not available')}  ",
    ]
    if section.get("statute_nepali"):
        out.append(f"**ऐन:** {section['statute_nepali']}  ")
    out += [
        f"**Jurisdiction:** {section.get('jurisdiction', 'not available')}",
        "",
    ]
    if section.get("language_note"):
        out += [f"*{section['language_note']}*", ""]
    for provision in section.get("provisions") or []:
        out.append(f"### Section {provision['section']} — {provision['title']}")
        out += ["", f"*{provision['citation']}*", ""]
        out += _markdown_table(
            ["Field", "Recorded value"],
            [["Conduct", provision["conduct"]],
             ["Penalty", provision["penalty"]],
             ["Evidence-based match", provision["basis"]],
             ["Supporting evidence", provision.get("evidence_ids") or ["none"]]],
        )
        out.append("")

    guidance = section.get("investigative_guidance") or []
    if guidance:
        out += ["### Evidentiary and regulatory follow-up", ""]
        out += [
            "These entries are preservation or investigative actions, not findings "
            "that an institution violated a rule.",
            "",
        ]
        for item in guidance:
            out += [f"#### {item['title']}", "", f"*{item['citation']}*", ""]
            out += _markdown_table(
                ["Field", "Recorded value"],
                [["Status", item.get("status", "investigative_follow_up")],
                 ["Expectation", item["expectation"]],
                 ["Why relevant", item["basis"]],
                 ["Recommended action", item["recommended_action"]],
                 ["Applicability", item["applicability"]],
                 ["Supporting evidence", item.get("evidence_ids") or ["none"]]],
            )
            out.append("")

    manual = section.get("manual_review_provisions") or []
    if manual:
        out += ["### Provisions requiring manual review", ""]
        out += [
            "The current evidence model does not automatically assess these "
            "provisions:",
            "",
        ]
        for item in manual:
            out.append(
                f"- **Section {item['section']} — {item['title']}:** {item['reason']}"
            )
        out.append("")

    sources = section.get("sources") or []
    if sources:
        out += ["### Primary sources", ""]
        for source in sources:
            out += [
                f"- **{source['authority']} — {source['title']}**  ",
                f"  {source['url']}  ",
                f"  Used for: {source['usage']}",
            ]
            if source.get("note"):
                out.append(f"  Note: {source['note']}")
        out.append("")
    if section.get("caveat"):
        out += [f"> {section['caveat']}", ""]
    return out


def _to_markdown(value: Any, indent: int = 0) -> List[str]:
    pad = "  " * indent
    if value is None:
        return [f"{pad}- not available"]
    if isinstance(value, str):
        return [f"{pad}{value}" if indent == 0 else f"{pad}- {value}"]
    if isinstance(value, (int, float, bool)):
        return [f"{pad}- {value}"]
    if isinstance(value, list):
        lines: List[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.extend(_to_markdown(item, indent))
            else:
                lines.append(f"{pad}- {item}")
        return lines or [f"{pad}- none"]
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            label = str(key).replace("_", " ")
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}- **{label}**:")
                lines.extend(_to_markdown(item, indent + 1))
            else:
                lines.append(f"{pad}- **{label}**: {item}")
        return lines
    return [f"{pad}- {value}"]
