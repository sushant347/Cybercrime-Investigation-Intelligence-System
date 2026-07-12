"""Pydantic output contract for the Semantic Correction Engine.

Adds a *fourth* text representation, produced only after context validation::

    raw_text      (Prompt 1)   - verbatim OCR, never modified
    cleaned_text  (Prompt 2)   - cleaned copy, never modified
    enhanced_text (Prompt 2.5) - rule-corrected copy, never modified
    semantic_text (this module) - context-validated copy; the only field this
                                  module writes, and only accepted corrections
                                  reach it

The result is appended to the case JSON under ``semantic_correction`` without
touching any existing field.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class SemanticCorrection(BaseModel):
    """One candidate that was judged in context (accepted or rejected)."""

    original: str
    candidate: str
    accepted: bool
    confidence: float = Field(ge=0.0, le=1.0)
    validator: str = Field(description="Validator that produced the verdict")
    candidate_source: str = Field(default="", description="rule source of the candidate")
    reason: str = Field(default="", description="Why it was accepted/rejected")
    language: str = Field(default="")


class SemanticStatistics(BaseModel):
    """Quality metrics of one semantic-correction run."""

    suspicious_tokens: int = 0
    candidates_evaluated: int = 0
    accepted_corrections: int = 0
    rejected_corrections: int = 0
    average_confidence: float = 0.0
    protected_entities: int = 0
    validator: str = ""
    languages_detected: List[str] = Field(default_factory=list)


class EntityRef(BaseModel):
    """One entity extracted from ``semantic_text`` (verbatim + canonical)."""

    value: str
    normalized: str


class SemanticResult(BaseModel):
    """Complete result for one evidence item's semantic pass."""

    case_id: str = ""
    evidence_id: str = ""
    enhanced_text: str = Field(description="Input from Prompt 2.5 - never modified")
    semantic_text: str = Field(default="", description="Context-validated text")
    corrections: List[SemanticCorrection] = Field(default_factory=list)
    accepted_corrections: List[SemanticCorrection] = Field(default_factory=list)
    rejected_corrections: List[SemanticCorrection] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0,
                              description="Mean confidence of accepted corrections")
    #: Entities extracted from ``semantic_text`` by the EXISTING (unchanged)
    #: cleaning-module EntityExtractor. Append-only: this makes semantic_text
    #: the input to entity extraction as required by the merged pipeline,
    #: without altering the cleaning module or entities.csv.
    entities: Dict[str, List[EntityRef]] = Field(default_factory=dict)
    statistics: SemanticStatistics = Field(default_factory=SemanticStatistics)
    processing_time_ms: float = 0.0
