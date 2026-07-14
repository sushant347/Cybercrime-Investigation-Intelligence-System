"""Pydantic models for the Advanced Evidence Correlation Engine (Module 1)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class CorrelationFactor(BaseModel):
    """One weighted factor contributing to an evidence-pair correlation."""

    factor: str = Field(description="e.g. 'phones', 'file_hash', 'timeline_proximity'")
    weight: float = Field(ge=0.0, description="Configured factor weight")
    matches: int = Field(ge=0, description="Number of counted matches (capped)")
    contribution: float = Field(ge=0.0, description="weight x counted matches")
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="The concrete shared values / observations behind the match",
    )
    reason: str = Field(description="Human-readable justification")


class EvidencePairCorrelation(BaseModel):
    """Explainable correlation between two evidence items."""

    evidence_a: str
    evidence_b: str
    correlation_weight: float = Field(ge=0.0, description="Sum of contributions")
    correlation_confidence: float = Field(ge=0.0, le=1.0)
    relationship_strength: str = Field(
        description="VERY_STRONG | STRONG | MEDIUM | WEAK | NO_RELATIONSHIP"
    )
    factors: List[CorrelationFactor] = Field(default_factory=list)
    correlation_reasons: List[str] = Field(default_factory=list)
    explanation: str = Field(
        default="", description="Complete narrative of why the items are linked"
    )


class CorrelationAnalysis(BaseModel):
    """Complete Module-1 output stored as ``correlation_analysis.json``."""

    case_id: str
    evidence_ids: List[str] = Field(default_factory=list)
    pair_count: int = 0
    related_pair_count: int = Field(
        default=0, description="Pairs above NO_RELATIONSHIP"
    )
    pairs: List[EvidencePairCorrelation] = Field(default_factory=list)
    strength_distribution: Dict[str, int] = Field(default_factory=dict)
    strongest_pair: str = ""
    analysis_time_ms: float = 0.0
