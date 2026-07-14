"""Pydantic models for Logo & Brand Detection (Module 5)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class LogoDetection(BaseModel):
    """One detected brand occurrence."""

    brand: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(
        default_factory=list, description="[x0, y0, x1, y1] in pixel coordinates"
    )
    detection_method: str = Field(
        description="template_match | colour_signature | ocr_keyword"
    )
    detected_at: str = Field(description="UTC ISO-8601 timestamp")
    detail: str = ""


class LogoDetectionReport(BaseModel):
    """Complete Module-5 output stored as ``logo_detections.json``."""

    evidence_id: str
    case_id: str
    source_file: str
    brands_checked: List[str] = Field(default_factory=list)
    detections: List[LogoDetection] = Field(default_factory=list)
    detected_brands: List[str] = Field(default_factory=list)
    template_assets_available: bool = False
    analysis_time_ms: float = 0.0
