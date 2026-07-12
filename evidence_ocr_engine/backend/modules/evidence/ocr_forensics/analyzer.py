"""OCR forensic analyzer facade + timing recorder.

Ties the additive analyzers together into a single ``OCRForensicMetadata``
object attachable alongside existing OCR output. It consumes the OCR ``pages``
already produced by the pipeline (with text/confidence/bbox) plus the image
path - it never re-runs OCR and never mutates existing output.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from ..logger import get_logger
from .chat_reconstruction import ChatReconstructor
from .confidence import ConfidenceAnalyzer
from .config import OCRForensicConfig
from .duplicate import DuplicateDetector
from .image_quality import ImageQualityAnalyzer
from .language import OCRLanguageDetector
from .schemas import OCRForensicMetadata, TimingMetrics


class TimingRecorder:
    """Accumulates per-stage durations (milliseconds); safe to reuse."""

    def __init__(self) -> None:
        self._stages: dict[str, float] = {}

    def record(self, stage: str, milliseconds: float) -> None:
        self._stages[stage] = round(self._stages.get(stage, 0.0) + milliseconds, 2)

    def to_metrics(self) -> TimingMetrics:
        s = self._stages
        total = round(sum(s.values()), 2) if s else 0.0
        return TimingMetrics(
            preprocessing_ms=s.get("preprocessing", 0.0),
            ocr_ms=s.get("ocr", 0.0),
            cleaning_ms=s.get("cleaning", 0.0),
            enhancement_ms=s.get("enhancement", 0.0),
            semantic_ms=s.get("semantic", 0.0),
            forensic_analysis_ms=s.get("forensic_analysis", 0.0),
            total_ms=s.get("total", total),
        )


class OCRForensicAnalyzer:
    """Produces additive forensic metadata for one OCR'd evidence image."""

    def __init__(
        self,
        config: Optional[OCRForensicConfig] = None,
        confidence: Optional[ConfidenceAnalyzer] = None,
        image_quality: Optional[ImageQualityAnalyzer] = None,
        language: Optional[OCRLanguageDetector] = None,
        duplicate: Optional[DuplicateDetector] = None,
        chat: Optional[ChatReconstructor] = None,
    ) -> None:
        self._cfg = config or OCRForensicConfig()
        self._confidence = confidence or ConfidenceAnalyzer(self._cfg)
        self._quality = image_quality or ImageQualityAnalyzer(self._cfg)
        self._language = language or OCRLanguageDetector()
        self._duplicate = duplicate or DuplicateDetector(self._cfg)
        self._chat = chat or ChatReconstructor()
        self._log = get_logger("ocr_forensics")

    def analyze(
        self,
        ocr_pages: Sequence[Mapping[str, Any]],
        image_path: Optional[Path | str] = None,
        evidence_id: str = "",
        timing: Optional[TimingRecorder] = None,
        ocr_engine: str = "paddleocr-v5",
        ocr_version: str = "PP-OCRv5",
    ) -> OCRForensicMetadata:
        """Build the forensic metadata block (never raises for valid input)."""
        started = time.perf_counter()
        warnings: list[str] = []

        lines, conf_stats = self._confidence.analyze(ocr_pages)
        language = self._language.detect(ocr_pages)

        if image_path is not None:
            quality = self._quality.analyze_path(image_path)
            duplicate = self._duplicate.check(image_path, evidence_id)
        else:
            from .schemas import DuplicateInfo, ImageQualityMetrics
            quality = ImageQualityMetrics(
                recommendations=["No image path supplied; quality not assessed."])
            duplicate = DuplicateInfo()

        chat = self._chat.reconstruct(ocr_pages, image_width=quality.width or None)

        # Confidence-driven warnings (helps investigators hit high confidence).
        if conf_stats.count and conf_stats.average < self._cfg.confidence_medium:
            warnings.append(
                f"Low average OCR confidence ({conf_stats.average:.2f}); "
                "review flagged lines and image quality.")
        if conf_stats.medium_count:
            warnings.append(
                f"{conf_stats.medium_count} line(s) are medium-confidence "
                "(uncertain) and should be reviewed.")
        warnings.extend(
            r for r in quality.recommendations if r != "Image quality is adequate for OCR.")

        timing = timing or TimingRecorder()
        timing.record("forensic_analysis", (time.perf_counter() - started) * 1000.0)

        metadata = OCRForensicMetadata(
            ocr_engine=ocr_engine,
            ocr_version=ocr_version,
            detected_language=language.detected,
            image_sha256=duplicate.image_sha256,
            confidence_statistics=conf_stats,
            lines=lines,
            image_quality=quality,
            language=language,
            timing=timing.to_metrics(),
            duplicate=duplicate,
            chat=chat,
            warnings=warnings,
        )
        self._log.info(
            "forensic metadata: lang=%s conf(avg=%.2f min=%.2f) quality(blur=%.0f) "
            "chat=%s dup=%s",
            language.detected, conf_stats.average, conf_stats.minimum,
            quality.blur_score, chat.is_chat_screenshot, duplicate.is_duplicate,
        )
        return metadata
