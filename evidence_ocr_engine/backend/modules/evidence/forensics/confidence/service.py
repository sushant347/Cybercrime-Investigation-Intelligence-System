"""Module 8 - Evidence Confidence Scoring service.

Aggregates the outputs of Modules 1-7 (plus the legacy chain-of-custody
verification) into one final 0-100 confidence score per evidence item:

* Image quality        (Module 1 overall score)
* Forgery detection    (Module 4 - inverted: low forgery => high confidence)
* Metadata consistency (Module 6 - penalty per consistency note)
* Hash verification    (legacy SHA-256 chain of custody + Module 7 cross-check)
* OCR confidence       (Module 3 fusion final confidence, or legacy Paddle)
* Processing success   (did every pipeline stage complete)

Weights are configuration-driven and renormalised over the components that
are actually available, so the score degrades gracefully when an analysis
was skipped (e.g. non-image evidence has no quality/forgery component).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ...logger import get_logger
from ...utils import utc_now_iso
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import ConfidenceComponent, EvidenceConfidence

import csv

MODULE = "confidence_scoring"


class ConfidenceScoringService:
    """Final trust score for one evidence item."""

    csv_fields = (
        "computed_at", "evidence_id", "case_id",
        "confidence_score", "confidence_level",
    )

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._log = get_logger("forensics.confidence")
        self._ensure_index()

    # ------------------------------------------------------------------ public

    def score(
        self,
        *,
        evidence_id: str,
        case_id: str,
        image_quality_score: Optional[float] = None,
        forgery_score: Optional[float] = None,
        metadata_consistency_notes: Optional[int] = None,
        hash_verified: Optional[bool] = None,
        fingerprint_hash_match: Optional[bool] = None,
        ocr_confidence: Optional[float] = None,
        processing_success: Optional[bool] = None,
        persist: bool = True,
    ) -> EvidenceConfidence:
        """Compute, explain and store the final Evidence Confidence Score.

        Every input is optional; missing analyses simply drop out of the
        weighted average (weights renormalised).
        """
        components = self._components(
            image_quality_score, forgery_score, metadata_consistency_notes,
            hash_verified, fingerprint_hash_match, ocr_confidence,
            processing_success,
        )
        available = [c for c in components if c.available]
        total_weight = sum(c.weight for c in available)
        score = (
            sum(c.score * c.weight for c in available) / total_weight
            if total_weight > 0 else 0.0
        )
        level = self._level(score)
        result = EvidenceConfidence(
            evidence_id=evidence_id,
            case_id=case_id,
            components=components,
            confidence_score=round(score, 1),
            confidence_level=level,
            explanation=self._explanation(score, level, available),
            computed_at=utc_now_iso(),
        )
        if persist:
            self._repo.save(
                evidence_id, case_id, self._cfg.confidence_report_name,
                result.model_dump(),
            )
            self._append_index(result)
            self._audit.record(
                case_id, evidence_id, MODULE, "scored",
                f"score={result.confidence_score} level={level} "
                f"components={len(available)}/{len(components)}",
            )
        return result

    # ------------------------------------------------------------- components

    def _components(
        self,
        image_quality_score: Optional[float],
        forgery_score: Optional[float],
        metadata_notes: Optional[int],
        hash_verified: Optional[bool],
        fingerprint_hash_match: Optional[bool],
        ocr_confidence: Optional[float],
        processing_success: Optional[bool],
    ) -> List[ConfidenceComponent]:
        weights: Dict[str, float] = self._cfg.confidence_weights
        components: List[ConfidenceComponent] = []

        def add(name: str, score: Optional[float], explanation: str) -> None:
            components.append(ConfidenceComponent(
                name=name,
                score=round(min(100.0, max(0.0, score)), 1) if score is not None else 0.0,
                weight=weights.get(name, 0.0),
                available=score is not None,
                explanation=explanation if score is not None else "analysis not available",
            ))

        add("image_quality", image_quality_score,
            f"Module-1 overall image quality {image_quality_score}")

        forgery_component = None if forgery_score is None else 100.0 - forgery_score
        add("forgery", forgery_component,
            f"inverted Module-4 forgery score ({forgery_score})")

        metadata_component = None
        if metadata_notes is not None:
            metadata_component = max(0.0, 100.0 - 20.0 * metadata_notes)
        add("metadata", metadata_component,
            f"{metadata_notes} metadata consistency finding(s), -20 each")

        hash_component: Optional[float] = None
        hash_note = ""
        if hash_verified is not None or fingerprint_hash_match is not None:
            checks = [c for c in (hash_verified, fingerprint_hash_match) if c is not None]
            hash_component = 100.0 if all(checks) else 0.0
            hash_note = (
                "chain-of-custody SHA-256 "
                + ("verified" if all(checks) else "MISMATCH")
                + (f" ({len(checks)} independent check(s))")
            )
        add("hash_verification", hash_component, hash_note)

        ocr_component = None if ocr_confidence is None else ocr_confidence * 100.0
        add("ocr_confidence", ocr_component,
            f"OCR confidence {ocr_confidence}")

        processing_component = None
        if processing_success is not None:
            processing_component = 100.0 if processing_success else 30.0
        add("processing", processing_component,
            "all pipeline stages completed" if processing_success
            else "one or more stages failed or were skipped")
        return components

    def _level(self, score: float) -> str:
        for level, ceiling in self._cfg.confidence_bands.items():
            if score < ceiling:
                return level
        return "VERY_HIGH"

    @staticmethod
    def _explanation(
        score: float, level: str, available: List[ConfidenceComponent]
    ) -> str:
        strongest = max(available, key=lambda c: c.score * c.weight, default=None)
        weakest = min(available, key=lambda c: c.score, default=None)
        count = len(available)
        parts = [
            f"Evidence confidence is {score:.1f}/100 ({level}), "
            f"derived from {count} verified "
            f"dimension{'' if count == 1 else 's'}."
        ]
        if strongest is not None:
            parts.append(f"Strongest signal: {strongest.name} ({strongest.score:.0f}/100).")
        if weakest is not None and weakest is not strongest:
            parts.append(f"Weakest signal: {weakest.name} ({weakest.score:.0f}/100).")
        return " ".join(parts)

    # ------------------------------------------------------------------- index

    def _ensure_index(self) -> None:
        index = self._cfg.confidence_csv
        if index.exists():
            return
        index.parent.mkdir(parents=True, exist_ok=True)
        with open(index, "w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=list(self.csv_fields)).writeheader()

    def _append_index(self, result: EvidenceConfidence) -> None:
        try:
            with open(self._cfg.confidence_csv, "a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=list(self.csv_fields)).writerow({
                    "computed_at": result.computed_at,
                    "evidence_id": result.evidence_id,
                    "case_id": result.case_id,
                    "confidence_score": f"{result.confidence_score:.1f}",
                    "confidence_level": result.confidence_level,
                })
        except OSError as exc:  # pragma: no cover
            self._log.error("could not append confidence index: %s", exc)
