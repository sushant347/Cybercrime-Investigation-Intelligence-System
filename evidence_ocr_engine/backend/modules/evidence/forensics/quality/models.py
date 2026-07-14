"""Pydantic models for the OCR Quality Assessment Engine (Module 1)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class QualityMetrics(BaseModel):
    """Raw measurements taken from the (unmodified) evidence image."""

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    megapixels: float = Field(ge=0.0)
    blur_laplacian_variance: float = Field(ge=0.0, description="Low => blurry")
    brightness_mean: float = Field(ge=0.0, le=255.0)
    contrast_std: float = Field(ge=0.0)
    noise_residual: float = Field(ge=0.0, description="Median-filter residual")
    skew_angle_deg: float = Field(description="Estimated document skew")
    compression_quality: float = Field(
        ge=0.0, le=100.0,
        description="Estimated JPEG quality (100 for lossless sources)",
    )
    edge_density: float = Field(ge=0.0, le=1.0)
    text_like_components: int = Field(ge=0)


class QualityAssessment(BaseModel):
    """Complete Module-1 output stored as ``quality_report.json``."""

    evidence_id: str
    case_id: str
    source_file: str
    metrics: QualityMetrics
    #: Per-dimension normalised sub-scores, each 0-100.
    sub_scores: Dict[str, float] = Field(default_factory=dict)
    overall_score: float = Field(ge=0.0, le=100.0)
    quality_grade: str = Field(description="EXCELLENT | GOOD | FAIR | POOR | UNUSABLE")
    expected_ocr_accuracy: float = Field(ge=0.0, le=100.0)
    readability_score: float = Field(ge=0.0, le=100.0)
    recommended_operations: List[str] = Field(
        default_factory=list,
        description="Operation names understood by the Module-2 planner",
    )
    notes: List[str] = Field(default_factory=list)
    analysis_time_ms: float = 0.0
