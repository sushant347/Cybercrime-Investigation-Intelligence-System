"""Module 1 - Advanced Evidence Correlation Engine.

Upgrades exact entity matching into an explainable weighted framework. For
every evidence pair inside a case the engine evaluates twelve factor types
(shared phones/URLs/domains/emails/wallets/bank accounts/social accounts,
device & image metadata, file hashes, timeline proximity, threat-intel
corroboration), producing a weight, a bounded confidence, a relationship
level and a complete narrative explanation with the concrete supporting
values. No machine learning - deterministic weighted scoring only.
"""

from __future__ import annotations

import math
import time
from itertools import combinations
from typing import Dict, List, Optional, Sequence

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..config import InvestigationConfig
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from .models import CorrelationAnalysis, CorrelationFactor, EvidencePairCorrelation

MODULE = "correlation"

#: Entity types compared value-for-value between two evidence items.
_SHARED_ENTITY_FACTORS = (
    "phones", "emails", "urls", "domains",
    "wallets", "bank_accounts", "social_accounts",
)


class CorrelationService:
    """Explainable weighted correlation across all evidence of a case."""

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
        self._log = get_logger("investigation.correlation")

    # ------------------------------------------------------------------ public

    def analyze_case(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> CorrelationAnalysis:
        """Correlate every evidence pair of a case."""
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        pairs: List[EvidencePairCorrelation] = []
        for a, b in combinations(items, 2):
            pairs.append(self.correlate_pair(a, b))
        pairs.sort(key=lambda p: p.correlation_confidence, reverse=True)

        distribution: Dict[str, int] = {}
        for pair in pairs:
            distribution[pair.relationship_strength] = \
                distribution.get(pair.relationship_strength, 0) + 1

        analysis = CorrelationAnalysis(
            case_id=case_id,
            evidence_ids=[e.evidence_id for e in items],
            pair_count=len(pairs),
            related_pair_count=sum(
                1 for p in pairs if p.relationship_strength != "NO_RELATIONSHIP"
            ),
            pairs=pairs,
            strength_distribution=distribution,
            strongest_pair=(
                f"{pairs[0].evidence_a}|{pairs[0].evidence_b}" if pairs else ""
            ),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(case_id, self._cfg.correlation_report_name,
                            analysis.model_dump())
            self._audit.record(
                case_id, MODULE, "analyzed",
                f"{analysis.related_pair_count}/{analysis.pair_count} related pairs, "
                f"strongest={analysis.strongest_pair or 'none'}",
                duration_ms=analysis.analysis_time_ms,
            )
        return analysis

    def correlate_pair(
        self, a: EvidenceContext, b: EvidenceContext
    ) -> EvidencePairCorrelation:
        """Weighted, explainable correlation between two evidence items."""
        cfg = self._cfg
        factors: List[CorrelationFactor] = []

        for entity_type in _SHARED_ENTITY_FACTORS:
            factor = self._shared_entity_factor(a, b, entity_type)
            if factor is not None:
                factors.append(factor)

        for builder in (self._file_hash_factor, self._device_metadata_factor,
                        self._image_metadata_factor, self._timeline_factor,
                        self._threat_intel_factor):
            factor = builder(a, b)
            if factor is not None:
                factors.append(factor)

        weight = round(sum(f.contribution for f in factors), 4)
        confidence = round(
            1.0 - math.exp(-weight / cfg.correlation_confidence_normaliser), 4
        ) if weight > 0 else 0.0
        strength = self._strength(confidence)
        reasons = [f.reason for f in factors]
        return EvidencePairCorrelation(
            evidence_a=a.evidence_id,
            evidence_b=b.evidence_id,
            correlation_weight=weight,
            correlation_confidence=confidence,
            relationship_strength=strength,
            factors=factors,
            correlation_reasons=reasons,
            explanation=self._explanation(a, b, strength, confidence, factors),
        )

    # ----------------------------------------------------------------- factors

    def _shared_entity_factor(
        self, a: EvidenceContext, b: EvidenceContext, entity_type: str
    ) -> Optional[CorrelationFactor]:
        values_a = {v.lower() for v in a.entity_values(entity_type) if v}
        values_b = {v.lower() for v in b.entity_values(entity_type) if v}
        shared = sorted(values_a & values_b)
        if not shared:
            return None
        return self._factor(
            entity_type, len(shared), shared,
            f"Both items reference the same {entity_type.replace('_', ' ')}: "
            f"{', '.join(shared[:3])}"
            + (f" (+{len(shared) - 3} more)" if len(shared) > 3 else ""),
        )

    def _file_hash_factor(self, a: EvidenceContext, b: EvidenceContext
                          ) -> Optional[CorrelationFactor]:
        if not a.sha256 or a.sha256.lower() != b.sha256.lower():
            return None
        return self._factor(
            "file_hash", 1, [a.sha256],
            "Identical SHA-256 content hash - the files are byte-for-byte copies",
        )

    def _device_metadata_factor(self, a: EvidenceContext, b: EvidenceContext
                                ) -> Optional[CorrelationFactor]:
        device_a = self._device_of(a)
        device_b = self._device_of(b)
        if not device_a or device_a != device_b:
            return None
        return self._factor(
            "device_metadata", 1, [device_a],
            f"Both files carry EXIF metadata from the same device '{device_a}'",
        )

    def _image_metadata_factor(self, a: EvidenceContext, b: EvidenceContext
                               ) -> Optional[CorrelationFactor]:
        software_a = self._software_of(a)
        software_b = self._software_of(b)
        if not software_a or software_a != software_b:
            return None
        return self._factor(
            "image_metadata", 1, [software_a],
            f"Both images were processed by the same software '{software_a}'",
        )

    def _timeline_factor(self, a: EvidenceContext, b: EvidenceContext
                         ) -> Optional[CorrelationFactor]:
        time_a, time_b = a.upload_datetime, b.upload_datetime
        if time_a is None or time_b is None:
            return None
        hours = abs((time_a - time_b).total_seconds()) / 3600.0
        if hours > self._cfg.timeline_proximity_hours:
            return None
        return self._factor(
            "timeline_proximity", 1, [f"{hours:.1f}h apart"],
            f"Acquired {hours:.1f} hours apart "
            f"(within the {self._cfg.timeline_proximity_hours:.0f}h proximity window)",
        )

    def _threat_intel_factor(self, a: EvidenceContext, b: EvidenceContext
                             ) -> Optional[CorrelationFactor]:
        intel = self._data.threat_intel
        if not intel.available:
            return None
        flagged_a = self._flagged_indicators(a)
        flagged_b = self._flagged_indicators(b)
        shared = sorted(set(flagged_a) & set(flagged_b))
        if not shared:
            return None
        return self._factor(
            "threat_intelligence", len(shared), shared,
            "Threat intelligence flags the same malicious indicator(s) in both "
            f"items: {', '.join(shared[:3])}",
        )

    # ---------------------------------------------------------------- helpers

    def _factor(self, name: str, matches: int, supporting: List[str],
                reason: str) -> CorrelationFactor:
        cfg = self._cfg
        weight = cfg.correlation_weights.get(name, 0.0)
        counted = min(matches, cfg.correlation_factor_cap)
        return CorrelationFactor(
            factor=name,
            weight=weight,
            matches=counted,
            contribution=round(weight * counted, 4),
            supporting_evidence=supporting[: cfg.correlation_factor_cap * 2],
            reason=reason,
        )

    def _flagged_indicators(self, context: EvidenceContext) -> List[str]:
        intel = self._data.threat_intel
        flagged = []
        for entity_type in ("urls", "domains"):
            for value in context.entity_values(entity_type):
                if intel.is_malicious(value):
                    flagged.append(value.lower())
        return flagged

    @staticmethod
    def _device_of(context: EvidenceContext) -> str:
        metadata = context.forensics.get("metadata_report", {})
        image = metadata.get("image") or {}
        return str(image.get("device", "") or "").strip()

    @staticmethod
    def _software_of(context: EvidenceContext) -> str:
        metadata = context.forensics.get("metadata_report", {})
        image = metadata.get("image") or {}
        return str(image.get("software", "") or "").strip()

    def _strength(self, confidence: float) -> str:
        for level, ceiling in self._cfg.relationship_bands.items():
            if confidence < ceiling:
                return level
        return "VERY_STRONG"

    @staticmethod
    def _explanation(
        a: EvidenceContext, b: EvidenceContext,
        strength: str, confidence: float,
        factors: List[CorrelationFactor],
    ) -> str:
        if not factors:
            return (
                f"No shared entities, metadata, temporal proximity or threat "
                f"indicators were found between {a.evidence_id} "
                f"({a.file_name}) and {b.evidence_id} ({b.file_name})."
            )
        parts = [
            f"{a.evidence_id} ({a.file_name}) and {b.evidence_id} "
            f"({b.file_name}) show a {strength.replace('_', ' ').lower()} "
            f"relationship (confidence {confidence:.2f}) based on "
            f"{len(factors)} independent factor(s)."
        ]
        for factor in factors:
            parts.append(f"{factor.reason} [weight {factor.contribution:.2f}].")
        return " ".join(parts)
