"""Phase-1 orchestrator: composes the existing pipeline with all 8 modules.

:class:`ForensicPhase1Pipeline` is a *wrapper*, not a replacement:

1. Acquisition, SHA-256 chain of custody, legacy preprocessing, PaddleOCR
   and all legacy storage run through the existing, unmodified
   :class:`~..pipeline.EvidencePipeline`.
2. The Phase-1 analyses then run on the pristine stored original:
   integrity -> metadata -> quality -> forgery -> advanced preprocessing ->
   multi-OCR fusion -> logo detection -> confidence scoring.

Each analysis is isolated: a failure produces an audited ERROR entry and the
run continues (forensic findings must never destroy the evidence trail).
Every collaborator is injected, so any module can be replaced or faked in
tests without touching this class.

Use :func:`build_default_pipeline` as the composition root.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..config import EvidenceConfig
from ..csv_storage import EvidenceRepository
from ..logger import get_logger
from ..models import OCRLine
from ..ocr_interface import BaseOCR
from ..pipeline import EvidencePipeline
from ..preprocessing import load_image
from ..schemas import EvidenceOCRResult
from ..utils import EvidenceError, file_extension
from .audit import ForensicAuditTrail
from .config import ForensicsConfig
from .repository import ForensicReportRepository
from .quality.service import QualityAssessmentService
from .advanced_preprocessing.service import AdvancedPreprocessingService
from .multi_ocr.engines import (
    EasyOCRAdapter,
    OCREngineAdapter,
    PaddleOCRAdapter,
    TesseractAdapter,
)
from .multi_ocr.fusion import MultiOCRFusionService
from .forgery.service import ForgeryDetectionService
from .logos.service import LogoDetectionService
from .metadata.service import MetadataExtractionService
from .integrity.service import FileIntegrityService
from .confidence.service import ConfidenceScoringService

MODULE = "phase1_pipeline"


class ForensicPhase1Pipeline:
    """End-to-end Phase-1 processing for one evidence file."""

    def __init__(
        self,
        evidence_config: EvidenceConfig,
        forensics_config: ForensicsConfig,
        *,
        evidence_pipeline: EvidencePipeline,
        quality: QualityAssessmentService,
        preprocessing: AdvancedPreprocessingService,
        fusion: MultiOCRFusionService,
        forgery: ForgeryDetectionService,
        logos: LogoDetectionService,
        metadata: MetadataExtractionService,
        integrity: FileIntegrityService,
        confidence: ConfidenceScoringService,
        audit: ForensicAuditTrail,
        evidence_repo: Optional[EvidenceRepository] = None,
    ) -> None:
        self._ecfg = evidence_config
        self._fcfg = forensics_config
        self._legacy = evidence_pipeline
        self._quality = quality
        self._preprocessing = preprocessing
        self._fusion = fusion
        self._forgery = forgery
        self._logos = logos
        self._metadata = metadata
        self._integrity = integrity
        self._confidence = confidence
        self._audit = audit
        self._evidence_repo = evidence_repo or EvidenceRepository(evidence_config)
        self._log = get_logger("forensics.pipeline")

    # ------------------------------------------------------------------ public

    def process_file(
        self,
        source: Path | str,
        case_id: Optional[str] = None,
        notes: str = "",
        case_title: str = "",
    ) -> Dict[str, Any]:
        """Acquire + OCR via the legacy pipeline, then run all Phase-1 modules.

        Returns a summary dict with the legacy result and every Phase-1
        report (each also persisted separately under storage/forensics/).
        """
        legacy_result = self._legacy.process_file(
            source, case_id=case_id, notes=notes, case_title=case_title
        )
        analyses = self.analyze_evidence(legacy_result.evidence_id,
                                         legacy_result=legacy_result)
        return {"legacy_result": legacy_result, **analyses}

    def analyze_evidence(
        self,
        evidence_id: str,
        legacy_result: Optional[EvidenceOCRResult] = None,
    ) -> Dict[str, Any]:
        """Run Phase-1 on already-acquired evidence (backward-compatible
        enrichment of the existing evidence base)."""
        started = time.perf_counter()
        record = self._evidence_repo.get(evidence_id)
        if record is None:
            raise EvidenceError(f"Unknown evidence '{evidence_id}'")
        case_id = record.get("case_id", "")
        stored_path = self._ecfg.originals_dir / record.get("stored_file_name", "")
        file_name = record.get("original_file_name", stored_path.name)
        acquisition_sha256 = record.get("sha256_before", "")
        is_image = file_extension(stored_path) in self._ecfg.image_extensions

        self._audit.record(case_id, evidence_id, MODULE, "started",
                           f"file={file_name} image={is_image}")

        results: Dict[str, Any] = {}
        failures: List[str] = []

        # --- Module 7: integrity (all file types) -------------------------
        results["fingerprint"] = self._safe(
            "integrity", case_id, evidence_id, failures,
            lambda: self._integrity.fingerprint(
                stored_path, evidence_id=evidence_id, case_id=case_id,
                acquisition_sha256=acquisition_sha256,
            ),
        )
        # --- Module 6: metadata (all file types) --------------------------
        results["metadata"] = self._safe(
            "metadata", case_id, evidence_id, failures,
            lambda: self._metadata.extract(
                stored_path, evidence_id=evidence_id, case_id=case_id,
            ),
        )

        image: Optional[np.ndarray] = None
        if is_image:
            try:
                image = load_image(stored_path)
            except EvidenceError as exc:
                failures.append(f"image_load: {exc}")
                self._audit.record(case_id, evidence_id, MODULE, "image_load",
                                   str(exc), level="ERROR")

        if image is not None:
            # --- Module 1: quality (pre-OCR, evidence untouched) ----------
            results["quality"] = self._safe(
                "quality", case_id, evidence_id, failures,
                lambda: self._quality.assess(
                    image, evidence_id=evidence_id, case_id=case_id,
                    source_file=file_name, source_path=stored_path,
                ),
            )
            # --- Module 4: forgery (pre-OCR authenticity) -----------------
            results["forgery"] = self._safe(
                "forgery", case_id, evidence_id, failures,
                lambda: self._forgery.analyze(
                    image, evidence_id=evidence_id, case_id=case_id,
                    source_file=file_name, source_path=stored_path,
                ),
            )
            # --- Modules 2+3: advanced preprocessing -> multi-OCR fusion --
            #
            # Both are skipped when no fusion engine is configured: the
            # enhanced copy exists solely as fusion's input, so producing it
            # would be pure cost. This is the single largest saving available
            # on an interactive upload (each fusion engine re-OCRs the whole
            # image the acquisition pipeline has already read).
            enhanced = image
            if getattr(self._fusion, "enabled", True):
                if results.get("quality") is not None:
                    preprocessing_out = self._safe(
                        "advanced_preprocessing", case_id, evidence_id, failures,
                        lambda: self._preprocessing.enhance(image, results["quality"]),
                    )
                    if preprocessing_out is not None:
                        enhanced, results["preprocessing"] = preprocessing_out
                results["fusion"] = self._safe(
                    "multi_ocr_fusion", case_id, evidence_id, failures,
                    lambda: self._fusion.run(
                        enhanced, evidence_id=evidence_id, case_id=case_id,
                    ),
                )
            # --- Module 5: logos (complements OCR) ------------------------
            ocr_lines = self._lines_for_logos(results.get("fusion"), legacy_result)
            results["logos"] = self._safe(
                "logo_detection", case_id, evidence_id, failures,
                lambda: self._logos.detect(
                    image, evidence_id=evidence_id, case_id=case_id,
                    source_file=file_name, ocr_lines=ocr_lines,
                ),
            )

        # --- Module 8: final confidence score ------------------------------
        results["confidence"] = self._safe(
            "confidence", case_id, evidence_id, failures,
            lambda: self._confidence.score(
                evidence_id=evidence_id,
                case_id=case_id,
                image_quality_score=(
                    results["quality"].overall_score
                    if results.get("quality") else None
                ),
                forgery_score=(
                    results["forgery"].forgery_score
                    if results.get("forgery") else None
                ),
                metadata_consistency_notes=(
                    len(results["metadata"].consistency_notes)
                    if results.get("metadata") else None
                ),
                hash_verified=_str_to_bool(record.get("hash_verified")),
                fingerprint_hash_match=(
                    results["fingerprint"].sha256_matches_acquisition
                    if results.get("fingerprint") else None
                ),
                ocr_confidence=self._best_ocr_confidence(results, legacy_result),
                processing_success=not failures,
            ),
        )

        total_ms = round((time.perf_counter() - started) * 1000.0, 1)
        self._audit.record(
            case_id, evidence_id, MODULE, "completed",
            f"analyses={sorted(k for k, v in results.items() if v is not None)} "
            f"failures={failures or 'none'}",
            level="WARNING" if failures else "INFO",
            duration_ms=total_ms,
        )
        results["failures"] = failures
        return results

    # ---------------------------------------------------------------- helpers

    def _safe(self, name: str, case_id: str, evidence_id: str,
              failures: List[str], action):
        """Isolation wrapper: one failing analysis never stops the others."""
        try:
            return action()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {exc}")
            self._audit.record(case_id, evidence_id, MODULE, name,
                               f"failed: {exc}", level="ERROR")
            self._log.exception("analysis '%s' failed for %s", name, evidence_id)
            return None

    @staticmethod
    def _lines_for_logos(fusion, legacy_result) -> List[OCRLine]:
        """Best available OCR lines to support keyword-based logo detection."""
        if fusion is not None and fusion.merged_lines:
            return [OCRLine(text=fl.text, confidence=fl.confidence)
                    for fl in fusion.merged_lines]
        if fusion is not None and fusion.final_text:
            return [OCRLine(text=line, confidence=fusion.final_confidence)
                    for line in fusion.final_text.splitlines() if line.strip()]
        if legacy_result is not None:
            return [
                OCRLine(text=ln.text, confidence=ln.confidence, bbox=ln.bbox)
                for page in legacy_result.pages for ln in page.lines
            ]
        return []

    @staticmethod
    def _best_ocr_confidence(results: Dict[str, Any],
                             legacy_result: Optional[EvidenceOCRResult]) -> Optional[float]:
        fusion = results.get("fusion")
        if fusion is not None and fusion.final_text:
            return fusion.final_confidence
        if legacy_result is not None:
            return legacy_result.average_confidence
        return None


def _str_to_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    return str(value).strip().lower() in {"true", "1", "yes"}


# --------------------------------------------------------------------------- #
# Composition root
# --------------------------------------------------------------------------- #


def build_default_pipeline(
    evidence_config: Optional[EvidenceConfig] = None,
    forensics_config: Optional[ForensicsConfig] = None,
    *,
    ocr_engine: Optional[BaseOCR] = None,
    fusion_engines: Optional[List[OCREngineAdapter]] = None,
) -> ForensicPhase1Pipeline:
    """Wire every Phase-1 service with production defaults.

    ``ocr_engine`` (a BaseOCR, e.g. the existing PaddleOCRService) drives the
    legacy pipeline; if omitted it is created lazily by PaddleOCRAdapter for
    fusion and by PaddleOCRService for the legacy path.
    """
    ecfg = evidence_config or EvidenceConfig.from_env()
    fcfg = forensics_config or ForensicsConfig.from_env(ecfg)
    ecfg.ensure_directories()
    fcfg.ensure_directories()

    if ocr_engine is None:
        from ..paddle_service import PaddleOCRService  # reuse, never modify
        ocr_engine = PaddleOCRService(ecfg)

    audit = ForensicAuditTrail(fcfg)
    repository = ForensicReportRepository(fcfg)
    # An explicit list - including an EMPTY one - is the caller's decision and
    # is honoured as given. Only when the argument is omitted entirely do the
    # config defaults apply. Treating `[]` as "unconfigured" meant a caller that
    # had deliberately switched fusion off still got the default engines back,
    # and so still paid for a complete second OCR pass over every image.
    if fusion_engines is not None:
        engines: List[OCREngineAdapter] = list(fusion_engines)
    else:
        engines = []
        if fcfg.fusion_enable_paddle:
            engines.append(PaddleOCRAdapter(ecfg, engine=ocr_engine))
        if fcfg.fusion_enable_easyocr:
            engines.append(EasyOCRAdapter(fcfg))
        if fcfg.fusion_enable_tesseract:
            engines.append(TesseractAdapter(fcfg))

    return ForensicPhase1Pipeline(
        ecfg, fcfg,
        evidence_pipeline=EvidencePipeline(ecfg, ocr_engine),
        quality=QualityAssessmentService(fcfg, repository, audit),
        preprocessing=AdvancedPreprocessingService(fcfg, repository, audit),
        fusion=MultiOCRFusionService(fcfg, repository, audit, engines),
        forgery=ForgeryDetectionService(fcfg, repository, audit),
        logos=LogoDetectionService(fcfg, repository, audit),
        metadata=MetadataExtractionService(fcfg, repository, audit),
        integrity=FileIntegrityService(
            fcfg, repository, audit, evidence_register_csv=ecfg.evidence_csv
        ),
        confidence=ConfidenceScoringService(fcfg, repository, audit),
        audit=audit,
    )
