"""Pydantic models for the Suspect Confidence Engine (Module 4)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class SuspectScoreComponent(BaseModel):
    """One dimension of the explainable weighted suspect score."""

    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class SuspectProfile(BaseModel):
    """One suspect identity anchor and its assessment."""

    suspect_id: str
    identity_type: str = Field(description="phones | emails | wallets | ...")
    identity_value: str
    aliases: List[str] = Field(
        default_factory=list,
        description="Other identity entities co-occurring with this anchor",
    )
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    components: List[SuspectScoreComponent] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=100.0)
    confidence_level: str = ""
    relationship_strength: str = Field(
        default="", description="Strength of internal links among its evidence"
    )
    risk_level: str = ""
    threat_flagged: bool = False
    first_seen: str = ""
    last_seen: str = ""
    explanation: str = ""


class SuspectAssessment(BaseModel):
    """Complete Module-4 output stored as ``suspect_assessment.json``."""

    case_id: str
    suspect_count: int = 0
    suspects: List[SuspectProfile] = Field(default_factory=list)
    top_suspect: str = ""
    analysis_time_ms: float = 0.0
    methodology: str = (
        "Deterministic weighted scoring over identity anchors "
        "(no machine learning); every component carries its own explanation."
    )
