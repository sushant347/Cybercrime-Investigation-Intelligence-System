"""Pydantic contracts for OCR forensic metadata (purely additive).

These models describe the ``ocr_forensics`` metadata block that can be
attached alongside the existing OCR output. No existing schema/field is
modified - this is metadata only.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

BoundingBox = List[List[float]]


class ConfidenceStatistics(BaseModel):
    """Document-level confidence summary derived from PP-OCRv5 line scores."""

    count: int = 0
    average: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0
    median: float = 0.0
    high_count: int = 0          # >= confidence_high
    medium_count: int = 0        # medium tier (uncertain)
    low_count: int = 0           # < medium
    discarded_count: int = 0     # dropped when discard_low is enabled
    tier_thresholds: Dict[str, float] = Field(default_factory=dict)


class LineConfidence(BaseModel):
    """One OCR line with its confidence tier and preserved geometry."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    tier: str = Field(description="high | medium | low | discarded")
    bbox: BoundingBox = Field(default_factory=list)
    page: int = 1


class ImageQualityMetrics(BaseModel):
    """Diagnostic image-quality metrics (never used to reject evidence)."""

    width: int = 0
    height: int = 0
    megapixels: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    blur_score: float = 0.0          # Laplacian variance; low => blurry
    sharpness: float = 0.0           # normalised sharpness proxy
    estimated_noise: float = 0.0
    low_resolution: bool = False
    is_blurry: bool = False
    is_dark: bool = False
    is_bright: bool = False
    is_low_contrast: bool = False
    is_noisy: bool = False
    recommendations: List[str] = Field(default_factory=list)


class LanguageInfo(BaseModel):
    """Detected script/language and the recommended PP-OCRv5 language code."""

    detected: str = "unknown"        # english | nepali | mixed | unknown
    recommended_paddle_lang: str = "ne"
    line_languages: Dict[str, str] = Field(default_factory=dict)


class TimingMetrics(BaseModel):
    """Per-stage wall-clock timing (milliseconds)."""

    preprocessing_ms: float = 0.0
    ocr_ms: float = 0.0
    cleaning_ms: float = 0.0
    enhancement_ms: float = 0.0
    semantic_ms: float = 0.0
    forensic_analysis_ms: float = 0.0
    total_ms: float = 0.0


class DuplicateInfo(BaseModel):
    """SHA-256 duplicate-evidence detection result."""

    image_sha256: str = ""
    is_duplicate: bool = False
    first_seen_evidence_id: Optional[str] = None
    reused_ocr: bool = False


class ChatMessage(BaseModel):
    """One reconstructed message from a chat-screenshot layout."""

    order: int
    sender: str = "unknown"          # sender name | "me" | "unknown"
    side: str = "unknown"            # left | right | unknown
    timestamp: str = ""
    text: str = ""
    bbox: BoundingBox = Field(default_factory=list)


class ChatReconstruction(BaseModel):
    """Structured conversation reconstructed from spatial layout."""

    is_chat_screenshot: bool = False
    app_hint: str = ""               # whatsapp | messenger | telegram | generic | ""
    messages: List[ChatMessage] = Field(default_factory=list)


class OCRForensicMetadata(BaseModel):
    """Complete additive forensic metadata for one OCR'd evidence image."""

    ocr_engine: str = "paddleocr-v5"
    ocr_version: str = "PP-OCRv5"
    detected_language: str = "unknown"
    image_sha256: str = ""
    confidence_statistics: ConfidenceStatistics = Field(default_factory=ConfidenceStatistics)
    lines: List[LineConfidence] = Field(default_factory=list)
    image_quality: ImageQualityMetrics = Field(default_factory=ImageQualityMetrics)
    language: LanguageInfo = Field(default_factory=LanguageInfo)
    timing: TimingMetrics = Field(default_factory=TimingMetrics)
    duplicate: DuplicateInfo = Field(default_factory=DuplicateInfo)
    chat: ChatReconstruction = Field(default_factory=ChatReconstruction)
    warnings: List[str] = Field(default_factory=list)
