"""Pydantic models for the Investigation Analytics Engine (Module 6)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class ValueCount(BaseModel):
    value: str
    count: int = Field(ge=0)


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
    top_entities: Dict[str, List[ValueCount]] = Field(
        default_factory=dict, description="entity_type -> most frequent values"
    )
    threat_statistics: Dict[str, float] = Field(default_factory=dict)
    brand_statistics: List[ValueCount] = Field(default_factory=list)
    wallet_statistics: List[ValueCount] = Field(default_factory=list)
    url_statistics: List[ValueCount] = Field(default_factory=list)
    device_statistics: List[ValueCount] = Field(default_factory=list)
    metadata_statistics: Dict[str, float] = Field(default_factory=dict)
    campaign_statistics: Dict[str, float] = Field(default_factory=dict)
    timeline_statistics: Dict[str, float] = Field(default_factory=dict)
    evidence_quality_statistics: Dict[str, float] = Field(default_factory=dict)
    correlation_statistics: Dict[str, float] = Field(default_factory=dict)
    analysis_time_ms: float = 0.0
