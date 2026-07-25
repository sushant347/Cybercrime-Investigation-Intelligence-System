"""Pydantic models for the Investigation Analytics Engine (Module 6)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class ValueCount(BaseModel):
    value: str
    count: int = Field(ge=0)


class ThreatIndicator(BaseModel):
    """One URL/domain the threat provider returned a non-benign verdict for.

    A verdict on its own is not evidence: a report has to name the indicator,
    say who judged it and on what grounds, and point at the evidence items it
    came from. All of that is recorded here so the analytics artifact - not
    just the narrative report - carries the justification.
    """

    value: str
    verdict: str = ""
    source: str = ""
    risk_score: float = 0.0
    confidence: float = 0.0
    brand_impersonated: str = ""
    reasons: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class CaseAnalytics(BaseModel):
    """Complete Module-6 output stored as ``analytics.json``.

    ``case_statistics.json`` and ``entity_statistics.json`` are focused
    projections of this document (stored independently per the spec).
    """

    case_id: str
    evidence_count: int = 0

    entity_statistics: Dict[str, int] = Field(
        default_factory=dict, description="entity_type -> total occurrences"
    )
    entity_types_supported: int = Field(
        default=0, description="How many entity types the extractor searches for"
    )
    entity_types_found: int = Field(
        default=0, description="How many of those types this case actually contains"
    )
    top_entities: Dict[str, List[ValueCount]] = Field(
        default_factory=dict, description="entity_type -> most frequent values"
    )
    threat_statistics: Dict[str, float] = Field(default_factory=dict)
    threat_indicators: List[ThreatIndicator] = Field(
        default_factory=list, description="Non-benign verdicts, with their grounds"
    )
    threat_source: str = Field(
        default="", description="Which provider produced the verdicts"
    )
    brand_statistics: List[ValueCount] = Field(default_factory=list)
    wallet_statistics: List[ValueCount] = Field(default_factory=list)
    wallet_statistics_by_rail: Dict[str, List[ValueCount]] = Field(
        default_factory=dict, description="payment entity type -> top values"
    )
    url_statistics: List[ValueCount] = Field(default_factory=list)
    device_statistics: List[ValueCount] = Field(default_factory=list)
    metadata_statistics: Dict[str, float] = Field(default_factory=dict)
    campaign_statistics: Dict[str, float] = Field(default_factory=dict)
    timeline_statistics: Dict[str, float] = Field(default_factory=dict)
    evidence_quality_statistics: Dict[str, float] = Field(default_factory=dict)
    correlation_statistics: Dict[str, float] = Field(default_factory=dict)
    analysis_time_ms: float = 0.0
