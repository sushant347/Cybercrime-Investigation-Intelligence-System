"""Module 7 - Advanced Report Generation.

Produces a professional forensic investigation report (Markdown + a JSON
twin) assembled *exclusively* from stored/computed findings passed in by the
pipeline. Every sentence is templated over concrete values (evidence ids,
scores, entity values, timestamps) - the generator has no free-text
capability, so it cannot hallucinate. Missing inputs produce an explicit
"not available" statement instead of invented content.

The legacy ``report generation`` module is untouched; this report is stored
independently as ``investigation_report.md`` / ``investigation_report.json``.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from ...evidence.logger import get_logger
from ...evidence.utils import utc_now_iso
from ..audit import InvestigationAuditTrail
from ..campaigns.models import CampaignAnalysis
from ..config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis, CrossCaseCorrelation
from ..analytics.models import CaseAnalytics
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from ..suspects.models import SuspectAssessment
from ..timeline.models import TimelineAnalysis
from . import pdf_renderer

MODULE = "reporting"


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

        sections: Dict[str, Any] = {
            "executive_summary": self._executive_summary(
                case_id, items, correlation, campaigns, suspects, timeline,
                cross_case),
            "scope_and_methodology": self._scope_section(items),
            "case_overview": self._case_overview(case_id, items),
            "evidence_summary": self._evidence_summary(items),
            "correlation_analysis": self._correlation_section(correlation),
            "cross_case_correlation": self._cross_case_section(cross_case),
            "campaign_analysis": self._campaign_section(campaigns),
            "timeline_analysis": self._timeline_section(timeline),
            "suspect_assessment": self._suspect_section(suspects),
            "threat_intelligence_summary": self._threat_section(analytics),
            "model_predictions": self._model_predictions(items),
            "evidence_quality_summary": self._quality_section(analytics, items),
            "metadata_summary": self._metadata_section(items),
            "investigation_statistics": self._statistics_section(analytics),
            "confidence_analysis": self._confidence_section(items),
            "investigation_conclusion": self._conclusion(
                items, correlation, campaigns, suspects, timeline),
            "recommendations": self._recommendations(
                campaigns, suspects, timeline, priority),
            "report_provenance": self._provenance(
                case_id, items, report_id, generated_at),
            "appendix": self._appendix(items),
        }
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
        lines = [
            f"Case {case_id} contains {len(items)} evidence item(s), each "
            "acquired under SHA-256 chain-of-custody verification."
        ]
        if cross_case is not None and cross_case.link_count:
            lines.append(
                f"This case is linked to {cross_case.link_count} other case(s) "
                f"through shared entities: "
                f"{', '.join(cross_case.related_case_ids)} "
                "[cross_case_correlation.json]."
            )
        if correlation is not None:
            lines.append(
                f"The weighted correlation engine found "
                f"{correlation.related_pair_count} related evidence pair(s) "
                f"out of {correlation.pair_count} analysed [correlation_analysis.json]."
            )
        if campaigns is not None and campaigns.campaign_count:
            largest = max(campaigns.campaigns, key=lambda c: len(c.members))
            lines.append(
                f"{campaigns.campaign_count} coordinated campaign(s) were "
                f"identified; the largest ({largest.campaign_id}) groups "
                f"{len(largest.members)} item(s) [campaign_analysis.json]."
            )
        if suspects is not None and suspects.suspect_count:
            top = suspects.suspects[0]
            lines.append(
                f"The strongest suspect anchor is '{top.identity_value}' "
                f"({top.identity_type}) with confidence "
                f"{top.confidence_score:.0f}/100 [suspect_assessment.json]."
            )
        if timeline is not None and timeline.stage_progression:
            lines.append(
                "Observed attack progression: "
                + " -> ".join(timeline.stage_progression)
                + " [timeline_analysis.json]."
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
    def _correlation_section(correlation) -> Any:
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
        return {
            "summary": timeline.summary,
            "stage_progression": timeline.stage_progression,
            "progression_consistent": timeline.progression_consistent,
            "milestones": [
                {"timestamp": m.timestamp, "description": m.description}
                for m in timeline.milestones
            ],
            "critical_events": [
                {"timestamp": e.timestamp, "evidence_id": e.evidence_id,
                 "reasons": e.critical_reasons}
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
                "(suspect anchors, campaigns, cross-case links) strictly "
                "from stored, hash-verified artifacts."),
            "evidence_scope": (
                f"{len(items)} evidence item(s) acquired through the CIIS "
                "intake pipeline under SHA-256 chain-of-custody control."),
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
                "reproduces every figure herein; artifacts are versioned "
                "and never overwritten."),
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
    def _statistics_section(analytics) -> Any:
        if analytics is None:
            return "Analytics not available."
        return {
            "entity_statistics": analytics.entity_statistics,
            "campaign_statistics": analytics.campaign_statistics,
            "timeline_statistics": analytics.timeline_statistics,
            "correlation_statistics": analytics.correlation_statistics,
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
    def _conclusion(items, correlation, campaigns, suspects, timeline) -> List[str]:
        lines: List[str] = []
        verified = sum(1 for c in items if c.hash_verified is True)
        lines.append(
            f"{verified}/{len(items)} evidence item(s) passed SHA-256 "
            "chain-of-custody verification."
        )
        if correlation is not None and correlation.related_pair_count:
            lines.append(
                "The evidence set is internally connected "
                f"({correlation.related_pair_count} weighted relationship(s)), "
                "consistent with related activity rather than isolated incidents."
            )
        if campaigns is not None and campaigns.campaign_count:
            lines.append(
                f"{campaigns.campaign_count} campaign cluster(s) indicate "
                "coordinated operation."
            )
        if suspects is not None and suspects.suspect_count:
            top = suspects.suspects[0]
            lines.append(
                f"Investigation should focus on anchor '{top.identity_value}' "
                f"({top.confidence_score:.0f}/100 confidence)."
            )
        if timeline is not None and not timeline.progression_consistent:
            lines.append(
                "Observed stage order deviates from the canonical scam "
                "sequence; evidence acquisition order should be reviewed."
            )
        return lines

    @staticmethod
    def _recommendations(campaigns, suspects, timeline, priority) -> List[str]:
        recommendations: List[str] = []
        if suspects is not None:
            for s in suspects.suspects[:3]:
                if s.threat_flagged or s.confidence_score >= 60:
                    recommendations.append(
                        f"Pursue subscriber/KYC records for "
                        f"{s.identity_type[:-1] if s.identity_type.endswith('s') else s.identity_type} "
                        f"'{s.identity_value}' (suspect confidence "
                        f"{s.confidence_score:.0f}/100)."
                    )
        if campaigns is not None:
            for c in campaigns.campaigns:
                if c.shared_domains:
                    recommendations.append(
                        f"Request takedown/registrar data for campaign "
                        f"{c.campaign_id} domain(s): "
                        + ", ".join(c.shared_domains) + "."
                    )
        if timeline is not None and timeline.critical_events:
            recommendations.append(
                f"Prioritise the {len(timeline.critical_events)} critical "
                "event(s) involving OTP/financial entities for victim-impact "
                "assessment."
            )
        if priority is not None:
            recommendations.append(
                f"Case priority: {priority.get('priority_level', 'N/A')} "
                f"({priority.get('priority_score', 'N/A')}/100) - "
                f"{priority.get('investigation_recommendation', '')}"
            )
        return recommendations or [
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
        titles = {
            "executive_summary": "Executive Summary",
            "scope_and_methodology": "Scope & Methodology",
            "case_overview": "Case Overview",
            "evidence_summary": "Evidence Summary",
            "correlation_analysis": "Correlation Analysis",
            "cross_case_correlation": "Cross-Case Correlation",
            "campaign_analysis": "Campaign Analysis",
            "timeline_analysis": "Timeline Analysis",
            "suspect_assessment": "Suspect Assessment",
            "threat_intelligence_summary": "Threat Intelligence Summary",
            "model_predictions": "Model Prediction Results",
            "evidence_quality_summary": "Evidence Quality Summary",
            "metadata_summary": "Metadata Summary",
            "investigation_statistics": "Investigation Statistics",
            "confidence_analysis": "Confidence Analysis",
            "investigation_conclusion": "Investigation Conclusion",
            "recommendations": "Recommendations",
            "report_provenance": "Report Provenance & Integrity",
            "appendix": "Appendix",
        }
        out: List[str] = [
            f"# Forensic Investigation Report - {case_id}",
            "",
            f"Generated: {utc_now_iso()}  ",
            "System: Cybercrime Investigation Intelligence System (CIIS), Phase 2  ",
            "Basis: every statement below references stored forensic findings; "
            "no content is generated outside computed results.",
            "",
        ]
        for key, title in titles.items():
            out.append(f"## {title}")
            out.append("")
            out.extend(_to_markdown(sections.get(key)))
            out.append("")
        return "\n".join(out)


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
