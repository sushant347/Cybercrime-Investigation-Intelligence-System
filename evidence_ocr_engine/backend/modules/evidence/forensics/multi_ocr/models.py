"""Pydantic models for the Multi-OCR Fusion Engine (Module 3)."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FusedLine(BaseModel):
    """One line of the fused output with provenance."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_engine: str


class EngineRun(BaseModel):
    """Independent output of a single OCR engine (always stored)."""

    engine: str
    available: bool
    succeeded: bool = False
    text: str = ""
    line_confidences: List[float] = Field(default_factory=list)
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    line_count: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None


class FusionResult(BaseModel):
    """Complete Module-3 output stored as ``ocr_fusion.json``.

    Field names follow the Phase-1 storage contract exactly:
    ``raw_text``, ``paddle_text``, ``easyocr_text``, ``tesseract_text``,
    ``merged_text``, ``final_text``.
    """

    evidence_id: str
    case_id: str
    page: int = 1

    raw_text: str = Field(
        default="", description="Verbatim output of the primary (Paddle) engine"
    )
    paddle_text: str = ""
    easyocr_text: str = ""
    tesseract_text: str = ""
    merged_text: str = ""
    final_text: str = ""

    engine_runs: List[EngineRun] = Field(default_factory=list)
    engine_confidences: Dict[str, float] = Field(default_factory=dict)
    selection_scores: Dict[str, float] = Field(default_factory=dict)
    pairwise_agreement: Dict[str, float] = Field(default_factory=dict)

    selected_engine: str = Field(default="", description="Engine whose output won")
    final_source: str = Field(
        default="", description="'selected' or 'merged' - what final_text is"
    )
    final_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    merge_applied: bool = False
    merged_lines: List[FusedLine] = Field(default_factory=list)
    total_time_ms: float = 0.0
