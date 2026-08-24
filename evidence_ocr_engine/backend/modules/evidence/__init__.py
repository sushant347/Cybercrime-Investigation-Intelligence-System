"""Module 2 - Digital Evidence Acquisition and OCR Engine.

Public API for other CIIE modules::

    from backend.modules.evidence import EvidenceConfig, EvidencePipeline, PaddleOCRService

    config = EvidenceConfig.from_env()
    pipeline = EvidencePipeline(config, PaddleOCRService(config))
    result = pipeline.process_file("evidence/phishing_screenshot.png")
"""

from .config import EvidenceConfig
from .hash_service import HashService
from .json_storage import JSONCaseStorage
from .models import CaseRecord, EvidenceRecord, OCRLine, OCRPageResult
from .ocr_interface import BaseOCR, FutureOCRService
from .paddle_service import PaddleOCRService
from .pdf_processor import PDFProcessor
from .pipeline import EvidencePipeline
from .preprocessing import ImagePreprocessor, load_image
from .schemas import EvidenceOCRResult, LineResult, PageResult
from .upload import EvidenceUploader
from .utils import (
    CorruptedPDFError,
    EmptyOCRError,
    EvidenceError,
    FileTooLargeError,
    HashVerificationError,
    InvalidImageError,
    OCRTimeoutError,
    PermissionDeniedError,
    StorageError,
    UnsupportedFormatError,
)

__all__ = [
    "EvidenceConfig",
    "EvidencePipeline",
    "EvidenceUploader",
    "HashService",
    "ImagePreprocessor",
    "JSONCaseStorage",
    "PDFProcessor",
    "BaseOCR",
    "PaddleOCRService",
    "FutureOCRService",
    "load_image",
    "CaseRecord",
    "EvidenceRecord",
    "OCRLine",
    "OCRPageResult",
    "EvidenceOCRResult",
    "PageResult",
    "LineResult",
    "EvidenceError",
    "UnsupportedFormatError",
    "FileTooLargeError",
    "PermissionDeniedError",
    "InvalidImageError",
    "CorruptedPDFError",
    "EmptyOCRError",
    "OCRTimeoutError",
    "HashVerificationError",
    "StorageError",
]
