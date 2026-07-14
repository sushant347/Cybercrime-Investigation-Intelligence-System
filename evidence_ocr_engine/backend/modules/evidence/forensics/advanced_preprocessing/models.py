"""Pydantic models for the Advanced Image Preprocessing module (Module 2)."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AppliedOperation(BaseModel):
    """Audit record of one preprocessing operation on the working copy."""

    name: str
    applied: bool
    reason: str = Field(description="Why the planner selected (or skipped) it")
    parameters: Dict[str, float] = Field(default_factory=dict)
    duration_ms: float = 0.0
    detail: str = ""


class PreprocessingReport(BaseModel):
    """Complete Module-2 output stored as ``preprocessing_report.json``."""

    evidence_id: str
    case_id: str
    driven_by_quality_score: float = Field(ge=0.0, le=100.0)
    planned_operations: List[str] = Field(default_factory=list)
    operations: List[AppliedOperation] = Field(default_factory=list)
    input_shape: List[int] = Field(default_factory=list)
    output_shape: List[int] = Field(default_factory=list)
    derived_image_file: Optional[str] = Field(
        default=None,
        description="Working-copy image saved under storage/forensics/<id>/derived/",
    )
    total_time_ms: float = 0.0
