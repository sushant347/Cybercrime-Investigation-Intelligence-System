"""Pydantic schemas defining the public output contract of Module 2.

The JSON produced for every processed evidence item follows
:class:`EvidenceOCRResult`, matching the format required by the project
specification. Downstream modules (entity extraction, correlation, reporting)
consume this structure.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .models import OCRPageResult


class LineResult(BaseModel):
    """A single recognised text line (verbatim OCR output)."""

    text: str = Field(description="Exact recognised text - never modified")
    confidence: float = Field(ge=0.0, le=1.0, description="Recognition confidence 0-1")
    bbox: List[List[float]] = Field(
        default_factory=list,
        description="4-point polygon [[x,y] x4] in pixel coordinates",
    )


class PageResult(BaseModel):
    """OCR output for one page of the evidence file."""

    page: int = Field(ge=1, description="1-based page number (page order preserved)")
    confidence: float = Field(ge=0.0, le=1.0, description="Average line confidence")
    text: str = Field(default="", description="Raw page text, lines joined by newline")
    lines: List[LineResult] = Field(default_factory=list)
    bounding_boxes: List[List[List[float]]] = Field(
        default_factory=list, description="All line polygons, aligned with `lines`"
    )
    preprocessing_steps: List[str] = Field(
        default_factory=list, description="Image preprocessing steps applied to this page"
    )

    @classmethod
    def from_page(cls, page: OCRPageResult) -> "PageResult":
        """Convert an internal :class:`OCRPageResult` into the public schema."""
        return cls(
            page=page.page_number,
            confidence=round(page.average_confidence, 4),
            text=page.text,
            lines=[
                LineResult(text=ln.text, confidence=round(ln.confidence, 4), bbox=ln.bbox)
                for ln in page.lines
            ],
            bounding_boxes=[ln.bbox for ln in page.lines],
            preprocessing_steps=page.preprocessing_steps,
        )


class EvidenceOCRResult(BaseModel):
    """Complete machine-readable result for one evidence item."""

    case_id: str
    evidence_id: str
    file_name: str
    file_hash: str = Field(description="SHA-256 of the original evidence file")
    file_size: str = Field(description="File size in bytes (string per output spec)")
    upload_time: str
    processing_time_ms: float = 0.0
    pages: List[PageResult] = Field(default_factory=list)
    raw_text: str = Field(default="", description="All pages concatenated, page order kept")
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    hash_verified: bool = Field(default=False, description="Post-processing integrity check")
    ocr_engine: str = Field(default="", description="Name of the OCR engine used")

    def build_raw_text(self) -> None:
        """Populate ``raw_text`` and ``average_confidence`` from ``pages``."""
        self.raw_text = "\n".join(p.text for p in self.pages)
        if self.pages:
            self.average_confidence = round(
                sum(p.confidence for p in self.pages) / len(self.pages), 4
            )
