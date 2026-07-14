"""Module 4 - Suspect Confidence Engine.

A *suspect* is anchored on an identity entity (phone, email, wallet, bank
account, social handle) observed in the evidence. For every anchor the
engine aggregates the evidence it appears in and produces an explainable
0-100 confidence score from six weighted components:

* identity strength      (a wallet is a stronger identifier than an email)
* evidence count         (breadth of appearances across the case)
* evidence confidence    (mean Phase-1 Evidence Confidence Score)
* threat intelligence    (anchor or its co-occurring URLs flagged malicious)
* correlation strength   (how tightly its evidence set is inter-linked, M1)
* timeline span          (sustained activity over days, not a single burst)

No machine learning is used - deterministic weighted scoring only, with a
complete narrative explanation per suspect.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from .models import SuspectAssessment, SuspectProfile, SuspectScoreComponent

MODULE = "suspects"


class SuspectService:
    """Explainable suspect assessment over identity anchors."""

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
        self._log = get_logger("investigation.suspects")

    # ------------------------------------------------------------------ public

    def assess(
        self,
        case_id: str,
        correlation: Optional[CorrelationAnalysis] = None,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> SuspectAssessment:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        anchors = self._collect_anchors(items)
        suspects = [
            self._profile(case_id, i + 1, anchor, appearances, items, correlation)
            for i, (anchor, appearances) in enumerate(sorted(anchors.items()))
        ]
        suspects.sort(key=lambda s: s.confidence_score, reverse=True)
        suspects = suspects[: self._cfg.suspect_max_results]

        assessment = SuspectAssessment(
            case_id=case_id,
            suspect_count=len(suspects),
            suspects=suspects,
            top_suspect=suspects[0].suspect_id if suspects else "",
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(case_id, self._cfg.suspect_report_name,
                            assessment.model_dump())
            self._audit.record(
                case_id, MODULE, "assessed",
                f"{assessment.suspect_count} suspect anchor(s), "
                f"top={assessment.top_suspect or 'none'}",
                duration_ms=assessment.analysis_time_ms,
            )
        return assessment

    # ---------------------------------------------------------------- internal

    def _collect_anchors(
        self, items: Sequence[EvidenceContext]
    ) -> Dict[tuple, List[EvidenceContext]]:
        """(entity_type, value) -> evidence items containing it."""
        anchors: Dict[tuple, List[EvidenceContext]] = {}
        for context in items:
            seen: set = set()
            for entity in context.entities:
                if entity.entity_type not in self._cfg.suspect_identity_types:
                    continue
                key = (entity.entity_type, (entity.normalized or entity.value).lower())
                if key in seen:
                    continue
                seen.add(key)
                anchors.setdefault(key, []).append(context)
        return anchors

    def _profile(
        self,
        case_id: str,
        index: int,
        anchor: tuple,
        appearances: List[EvidenceContext],
        all_items: Sequence[EvidenceContext],
        correlation: Optional[CorrelationAnalysis],
    ) -> SuspectProfile:
        cfg = self._cfg
        entity_type, value = anchor
        evidence_ids = sorted(c.evidence_id for c in appearances)
        components: List[SuspectScoreComponent] = []

        def add(name: str, score: float, explanation: str) -> None:
            components.append(SuspectScoreComponent(
                name=name,
                score=round(max(0.0, min(100.0, score)), 1),
                weight=cfg.suspect_weights.get(name, 0.0),
                explanation=explanation,
            ))

        identity_score = cfg.suspect_identity_type_scores.get(entity_type, 50.0)
        add("identity_strength", identity_score,
            f"'{value}' is a {entity_type[:-1] if entity_type.endswith('s') else entity_type} "
            f"- identity weight {identity_score:.0f}/100 for this anchor type")

        count_score = min(100.0, len(appearances) /
                          cfg.suspect_evidence_count_full_score * 100.0)
        add("evidence_count", count_score,
            f"appears in {len(appearances)} of {len(all_items)} evidence item(s)")

        ecs = [
            float((c.forensics.get("evidence_confidence", {}) or {})
                  .get("confidence_score", 0.0) or 0.0)
            for c in appearances
        ]
        ecs = [v for v in ecs if v > 0]
        mean_ecs = sum(ecs) / len(ecs) if ecs else 50.0
        add("evidence_confidence", mean_ecs,
            f"mean Phase-1 evidence confidence of its evidence set is {mean_ecs:.0f}/100"
            + ("" if ecs else " (no Phase-1 scores stored; neutral 50 assumed)"))

        threat_flagged, threat_detail = self._threat_signal(entity_type, value, appearances)
        add("threat_intelligence", 100.0 if threat_flagged else 0.0, threat_detail)

        rel_strength, rel_score, rel_detail = self._relationship(evidence_ids, correlation)
        add("correlation_strength", rel_score, rel_detail)

        times = sorted(t for t in (c.upload_time for c in appearances) if t)
        span_days = 0.0
        if len(times) >= 2:
            first = appearances[0].upload_datetime
            dts = sorted(d for d in (c.upload_datetime for c in appearances) if d)
            if len(dts) >= 2:
                span_days = (dts[-1] - dts[0]).total_seconds() / 86400.0
        span_score = min(100.0, span_days / cfg.suspect_timeline_span_full_days * 100.0)
        add("timeline_span", span_score,
            f"activity spans {span_days:.1f} day(s) across its evidence set")

        total_weight = sum(c.weight for c in components) or 1.0
        score = round(sum(c.score * c.weight for c in components) / total_weight, 1)

        profile = SuspectProfile(
            suspect_id=f"SUSPECT_{case_id}_{index:02d}",
            identity_type=entity_type,
            identity_value=value,
            aliases=self._aliases(anchor, appearances),
            evidence_ids=evidence_ids,
            evidence_count=len(evidence_ids),
            components=components,
            confidence_score=score,
            confidence_level=self._band(score, cfg.suspect_confidence_bands),
            relationship_strength=rel_strength,
            risk_level=self._band(score, cfg.suspect_risk_bands),
            threat_flagged=threat_flagged,
            first_seen=times[0] if times else "",
            last_seen=times[-1] if times else "",
        )
        profile.explanation = self._explanation(profile)
        return profile

    def _threat_signal(self, entity_type: str, value: str,
                       appearances: List[EvidenceContext]) -> tuple:
        intel = self._data.threat_intel
        if not intel.available:
            return False, "no threat-intelligence indicator file available"
        if intel.is_malicious(value):
            hit = intel.lookup(value) or {}
            return True, (f"anchor '{value}' is flagged "
                          f"{hit.get('verdict', 'malicious')} by threat intelligence")
        for context in appearances:
            for url in context.entity_values("urls") + context.entity_values("domains"):
                if intel.is_malicious(url):
                    return True, (
                        f"co-occurs with threat-flagged indicator '{url.lower()}' "
                        f"in {context.evidence_id}"
                    )
        return False, "no threat-intelligence hits for this anchor or its context"

    def _relationship(self, evidence_ids: List[str],
                      correlation: Optional[CorrelationAnalysis]) -> tuple:
        if correlation is None or len(evidence_ids) < 2:
            return ("N/A", 50.0,
                    "fewer than two evidence items (or no correlation input); neutral 50")
        ids = set(evidence_ids)
        internal = [p for p in correlation.pairs
                    if p.evidence_a in ids and p.evidence_b in ids]
        if not internal:
            return ("NO_RELATIONSHIP", 0.0,
                    "its evidence items show no internal correlation links")
        mean_conf = sum(p.correlation_confidence for p in internal) / len(internal)
        strength = max(internal,
                       key=lambda p: p.correlation_confidence).relationship_strength
        return (strength, mean_conf * 100.0,
                f"its {len(evidence_ids)} evidence items are inter-linked with mean "
                f"correlation confidence {mean_conf:.2f} (strongest: {strength})")

    def _aliases(self, anchor: tuple,
                 appearances: List[EvidenceContext]) -> List[str]:
        """Other identity entities consistently co-occurring with the anchor."""
        counts: Dict[str, int] = {}
        for context in appearances:
            seen: set = set()
            for entity in context.entities:
                if entity.entity_type not in self._cfg.suspect_identity_types:
                    continue
                key = (entity.entity_type, (entity.normalized or entity.value).lower())
                if key == anchor or key in seen:
                    continue
                seen.add(key)
                label = f"{key[0]}:{key[1]}"
                counts[label] = counts.get(label, 0) + 1
        threshold = max(1, len(appearances) - 0) if len(appearances) == 1 else 2
        return sorted(k for k, v in counts.items() if v >= min(threshold, 2))[:10]

    @staticmethod
    def _band(score: float, bands: Dict[str, float]) -> str:
        for level, ceiling in bands.items():
            if score < ceiling:
                return level
        return list(bands)[-1]

    @staticmethod
    def _explanation(profile: SuspectProfile) -> str:
        parts = [
            f"Suspect anchor '{profile.identity_value}' "
            f"({profile.identity_type}) scores "
            f"{profile.confidence_score:.1f}/100 "
            f"({profile.confidence_level}, risk {profile.risk_level}) across "
            f"{profile.evidence_count} evidence item(s): "
            + ", ".join(profile.evidence_ids) + "."
        ]
        for component in profile.components:
            parts.append(
                f"{component.name.replace('_', ' ').capitalize()}: "
                f"{component.score:.0f}/100 (weight {component.weight:.2f}) - "
                f"{component.explanation}."
            )
        if profile.aliases:
            parts.append("Co-occurring identity entities: "
                         + ", ".join(profile.aliases) + ".")
        return " ".join(parts)
