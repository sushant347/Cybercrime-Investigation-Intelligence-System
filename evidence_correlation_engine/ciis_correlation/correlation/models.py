"""Pydantic models for the Advanced Evidence Correlation Engine (Module 1)."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class SharedValueDetail(BaseModel):
    """Why one shared value counted as much (or as little) as it did."""

    value: str
    specificity: float = Field(
        ge=0.0, le=1.0,
        description="Multiplier applied to the type weight; 1.0 = fingerprint-like",
    )
    document_frequency: int = Field(
        default=0, ge=0,
        description="Distinct evidence items in the corpus carrying this value",
    )
    corpus_size: int = Field(
        default=0, ge=0, description="Distinct evidence items in the corpus"
    )
    reason: str = ""


class CorrelationFactor(BaseModel):
    """One weighted factor contributing to an evidence-pair correlation."""

    factor: str = Field(description="e.g. 'phones', 'file_hash', 'timeline_proximity'")
    weight: float = Field(ge=0.0, description="Configured factor weight")
    matches: int = Field(ge=0, description="Number of counted matches (capped)")
    contribution: float = Field(ge=0.0, description="weight x summed specificity")
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="The concrete shared values / observations behind the match",
    )
    reason: str = Field(description="Human-readable justification")
    #: Per-value breakdown for entity factors. Empty for factors that are not
    #: value-based (file hash, timeline proximity, ...). Additive and optional,
    #: so correlation artifacts stored before this existed still validate.
    value_details: List[SharedValueDetail] = Field(default_factory=list)
    #: Summed specificity of the counted values. Equals ``matches`` when every
    #: shared value is fingerprint-like, and approaches zero when they are all
    #: corpus-wide noise - the number that separates a real link from
    #: "both mention a round amount".
    effective_matches: float = Field(
        default=0.0, ge=0.0,
        description="Specificity-weighted match count behind the contribution",
    )


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


# --------------------------------------------------------------------------- #
# Cross-case correlation (Module 1, persistent-index extension)
# --------------------------------------------------------------------------- #


class CrossCaseEntityMatch(BaseModel):
    """One normalized entity shared between the subject case and another case."""

    entity_type: str
    value: str = Field(description="Normalized value that matched across cases")
    weight: float = Field(ge=0.0, description="Configured weight of this entity type")
    specificity: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="How identifying this value is corpus-wide; scales the weight",
    )
    document_frequency: int = Field(
        default=0, ge=0,
        description="Distinct evidence items across all cases carrying this value",
    )
    specificity_reason: str = ""
    this_evidence_ids: List[str] = Field(
        default_factory=list, description="Evidence in the subject case carrying it"
    )
    other_evidence_ids: List[str] = Field(
        default_factory=list, description="Evidence in the other case carrying it"
    )


class CrossCaseLink(BaseModel):
    """Explainable link between the subject case and one other case."""

    other_case_id: str
    match_confidence: float = Field(ge=0.0, le=1.0)
    relationship_strength: str = Field(
        description="VERY_STRONG | STRONG | MEDIUM | WEAK | NO_RELATIONSHIP"
    )
    matched_entities: List[CrossCaseEntityMatch] = Field(default_factory=list)
    this_evidence_ids: List[str] = Field(default_factory=list)
    other_evidence_ids: List[str] = Field(default_factory=list)
    match_reason: str = Field(default="", description="Human-readable justification")


class CrossCaseCorrelation(BaseModel):
    """Complete cross-case output stored as ``cross_case_correlation.json``."""

    case_id: str
    related_case_ids: List[str] = Field(default_factory=list)
    link_count: int = 0
    links: List[CrossCaseLink] = Field(default_factory=list)
    analysis_time_ms: float = 0.0

    def stable_payload(self) -> Dict:
        """Deterministic dump for change detection (excludes timing)."""
        data = self.model_dump()
        data.pop("analysis_time_ms", None)
        return data
