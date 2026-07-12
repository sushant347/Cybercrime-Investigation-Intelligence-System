"""Additive OCR forensic-metadata layer (PP-OCRv5).

A self-contained, backward-compatible layer that enriches existing OCR output
with forensic metadata: confidence statistics/filtering, image-quality
diagnostics, language detection, duplicate detection, chat reconstruction,
timing and batch processing. It consumes the OCR ``pages`` the pipeline
already produces (text/confidence/bbox) and never re-runs OCR, mutates any
existing field, or changes any existing schema/API.

Usage::

    from backend.modules.evidence.ocr_forensics import OCRForensicAnalyzer

    meta = OCRForensicAnalyzer().analyze(ocr_pages, image_path="evidence.png")
    print(meta.confidence_statistics.average, meta.image_quality.recommendations)
"""

from .analyzer import OCRForensicAnalyzer, TimingRecorder
from .batch import BatchItemResult, BatchProcessor, BatchReport
from .chat_reconstruction import ChatReconstructor
from .confidence import ConfidenceAnalyzer
from .config import OCRForensicConfig
from .duplicate import DuplicateDetector
from .image_quality import ImageQualityAnalyzer
from .language import OCRLanguageDetector
from .schemas import (
    ChatMessage,
    ChatReconstruction,
    ConfidenceStatistics,
    DuplicateInfo,
    ImageQualityMetrics,
    LanguageInfo,
    LineConfidence,
    OCRForensicMetadata,
    TimingMetrics,
)

__all__ = [
    "OCRForensicAnalyzer",
    "TimingRecorder",
    "OCRForensicConfig",
    "ConfidenceAnalyzer",
    "ImageQualityAnalyzer",
    "OCRLanguageDetector",
    "DuplicateDetector",
    "ChatReconstructor",
    "BatchProcessor",
    "BatchReport",
    "BatchItemResult",
    "OCRForensicMetadata",
    "ConfidenceStatistics",
    "LineConfidence",
    "ImageQualityMetrics",
    "LanguageInfo",
    "TimingMetrics",
    "DuplicateInfo",
    "ChatMessage",
    "ChatReconstruction",
]
