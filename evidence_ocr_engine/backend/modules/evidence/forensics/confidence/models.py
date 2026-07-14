"""Pydantic models for Evidence Confidence Scoring (Module 8)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ConfidenceComponent(BaseModel):
    """One input dimension of the final confidence score."""

    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    available: bool = True
    explanation: str = ""


class EvidenceConfidence(BaseModel):
    """Complete Module-8 output stored as ``evidence_confidence.json``.

    Also appended (one row) to ``storage/forensics/evidence_confidence.csv``
    so the score is attached to the evidence record without altering the
    existing ``evidence.csv`` schema (backward compatibility).
    """

    evidence_id: str
    case_id: str
    components: List[ConfidenceComponent] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=100.0)
    confidence_level: str = Field(
        description="VERY_LOW | LOW | MODERATE | HIGH | VERY_HIGH"
    )
    explanation: str = ""
    computed_at: str = ""
