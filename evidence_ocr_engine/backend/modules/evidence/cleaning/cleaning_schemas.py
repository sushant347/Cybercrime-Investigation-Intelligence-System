"""Pydantic output contract of the cleaning + entity extraction engine.

``raw_text`` is carried through unmodified (forensic invariant);
``cleaned_text`` is the working representation for downstream modules.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class EntityRecord(BaseModel):
    """One extracted entity (verbatim value + canonical form)."""

    value: str
    normalized: str


class CleaningStatistics(BaseModel):
    """Quality metrics of the cleaning run."""

    characters: int = 0
    words: int = 0
    lines: int = 0
    average_line_length: float = 0.0
    languages_detected: List[str] = Field(default_factory=list)
    entity_count: int = 0
    cleaning_operations: List[str] = Field(default_factory=list)
    ocr_corrections: List[str] = Field(default_factory=list)
    protected_entities: int = 0


class CleaningResult(BaseModel):
    """Complete result for one evidence item's OCR text."""

    case_id: str = ""
    evidence_id: str = ""
    raw_text: str = Field(description="Original OCR output - never modified")
    cleaned_text: str = Field(default="", description="Cleaned working copy")
    language: str = Field(default="unknown",
                          description="Document-level language label")
    line_languages: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-line detection: {'1': 'english', '2': 'roman_nepali'}",
    )
    entities: Dict[str, List[EntityRecord]] = Field(default_factory=dict)
    keywords: Dict[str, int] = Field(default_factory=dict)
    risk_signals: Dict[str, int] = Field(default_factory=dict)
    statistics: CleaningStatistics = Field(default_factory=CleaningStatistics)
    processing_time_ms: float = 0.0
