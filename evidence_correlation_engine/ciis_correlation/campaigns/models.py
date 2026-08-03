"""Pydantic models for the Scam Campaign Clustering Engine (Module 3)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class CampaignMembership(BaseModel):
    """Why one evidence item belongs to a campaign."""

    evidence_id: str
    linked_via: List[str] = Field(
        default_factory=list,
        description="Evidence ids this member is directly linked to",
    )
    link_reasons: List[str] = Field(default_factory=list)
    membership_explanation: str = ""


class Campaign(BaseModel):
    """One identified cybercrime campaign."""

    campaign_id: str
    case_id: str
    members: List[str] = Field(default_factory=list)
    memberships: List[CampaignMembership] = Field(default_factory=list)
    campaign_confidence: float = Field(ge=0.0, le=1.0)
    #: Distinguishing shared indicators (entities, brands, domains).
    signature: List[str] = Field(default_factory=list)
    shared_brands: List[str] = Field(default_factory=list)
    shared_domains: List[str] = Field(default_factory=list)
    timeline_start: str = ""
    timeline_end: str = ""
    statistics: Dict[str, float] = Field(default_factory=dict)
    summary: str = ""


class CampaignAnalysis(BaseModel):
    """Complete Module-3 output stored as ``campaign_analysis.json``."""

    case_id: str
    campaign_count: int = 0
    campaigns: List[Campaign] = Field(default_factory=list)
    unclustered_evidence: List[str] = Field(default_factory=list)
    analysis_time_ms: float = 0.0
