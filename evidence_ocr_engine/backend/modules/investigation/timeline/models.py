"""Pydantic models for the Timeline Intelligence Engine (Module 5)."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """One chronologically ordered investigation event."""

    timestamp: str = Field(default="", description="ISO-8601 UTC; empty when unresolved")
    event_type: str = Field(description="evidence_acquired | stage_marker | milestone")
    evidence_id: str = ""
    case_id: str = ""
    file_name: str = ""
    description: str = ""
    time_source: str = "unresolved"
    confidence: str = "low"
    timestamp_inferred: bool = False
    source_evidence_ids: List[str] = Field(default_factory=list)
    correlated_with: List[Dict[str, Any]] = Field(default_factory=list)
    text_preview: str = ""
    risk_signals: Dict[str, Any] = Field(default_factory=dict)
    stages: List[str] = Field(
        default_factory=list, description="Attack stages detected in this event"
    )
    critical: bool = False
    critical_reasons: List[str] = Field(default_factory=list)


class AttackStage(BaseModel):
    """One detected attack stage with its supporting evidence."""

    stage: str
    evidence_ids: List[str] = Field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    matched_keywords: List[str] = Field(default_factory=list)
    explanation: str = ""


class TimelineAnalysis(BaseModel):
    """Complete Module-5 output stored as ``timeline_analysis.json``."""

    case_id: str
    events: List[TimelineEvent] = Field(default_factory=list)
    attack_stages: List[AttackStage] = Field(default_factory=list)
    stage_progression: List[str] = Field(
        default_factory=list,
        description="Stages in the order first observed (chronological)",
    )
    progression_consistent: bool = Field(
        default=True,
        description="Whether observed order follows the canonical scam sequence",
    )
    milestones: List[TimelineEvent] = Field(default_factory=list)
    critical_events: List[TimelineEvent] = Field(default_factory=list)
    summary: str = ""
    statistics: Dict[str, float] = Field(default_factory=dict)
    analysis_time_ms: float = 0.0
