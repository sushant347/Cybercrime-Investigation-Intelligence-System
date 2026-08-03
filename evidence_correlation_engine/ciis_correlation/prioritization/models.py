"""Pydantic models for the Case Prioritization Engine (Module 8)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class PriorityComponent(BaseModel):
    """One weighted dimension of the case priority score."""

    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    available: bool = True
    explanation: str = ""


class CasePriority(BaseModel):
    """Complete Module-8 output stored as ``case_priority.json``."""

    case_id: str
    components: List[PriorityComponent] = Field(default_factory=list)
    priority_score: float = Field(ge=0.0, le=100.0)
    priority_level: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    high_risk_indicators: List[str] = Field(default_factory=list)
    investigation_recommendation: str = ""
    explanation: str = ""
    computed_at: str = ""
