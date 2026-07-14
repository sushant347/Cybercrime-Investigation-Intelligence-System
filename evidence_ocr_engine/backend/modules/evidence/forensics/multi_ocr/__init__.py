"""Module 3 - Multi-OCR Fusion Engine (PaddleOCR + EasyOCR + Tesseract)."""

from .engines import (
    EasyOCRAdapter,
    OCREngineAdapter,
    PaddleOCRAdapter,
    TesseractAdapter,
)
from .models import EngineRun, FusionResult
from .fusion import MultiOCRFusionService

__all__ = [
    "OCREngineAdapter",
    "PaddleOCRAdapter",
    "EasyOCRAdapter",
    "TesseractAdapter",
    "EngineRun",
    "FusionResult",
    "MultiOCRFusionService",
]
