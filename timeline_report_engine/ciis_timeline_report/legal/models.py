"""Contracts for the statutory-basis assessment."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class EngagedProvision(BaseModel):
    """One statutory provision the findings engage, and why."""

    section: str
    title: str
    citation: str
    conduct: str
    penalty: str
    #: The concrete finding that engaged it, naming the evidence involved.
    basis: str
    #: Evidence items supporting the basis, so the reader can go and look.
    evidence_ids: List[str] = Field(default_factory=list)


class UnassessedProvision(BaseModel):
    """A potentially relevant provision the available signals cannot prove."""

    section: str
    title: str
    citation: str
    reason: str


class InvestigativeGuidance(BaseModel):
    """Source-backed preservation or regulatory follow-up, never an offence."""

    category: str
    control_ids: List[str] = Field(default_factory=list)
    title: str
    citation: str
    expectation: str
    basis: str
    recommended_action: str
    applicability: str
    status: str = "investigative_follow_up"
    evidence_ids: List[str] = Field(default_factory=list)
    source_id: str


class LegalSourceReference(BaseModel):
    """Primary-source provenance carried with every generated assessment."""

    source_id: str
    authority: str
    title: str
    url: str
    local_documents: List[str] = Field(default_factory=list)
    sha256: Dict[str, str] = Field(default_factory=dict)
    usage: str
    note: str = ""


class LegalBasisAssessment(BaseModel):
    """Which provisions the stored findings engage for one case."""

    case_id: str
    statute: str
    #: The Act as named in Nepali law, for filings in Nepali.
    statute_nepali: str = ""
    jurisdiction: str = ""
    #: Which language text the citations were taken from, and which governs.
    language_note: str = ""
    provisions: List[EngagedProvision] = Field(default_factory=list)
    #: Provisions present in the source set but withheld from automatic
    #: assessment because the current evidence model cannot establish an
    #: essential element such as authorisation or corporate responsibility.
    manual_review_provisions: List[UnassessedProvision] = Field(default_factory=list)
    #: Evidentiary and regulatory follow-up kept separate from offence mapping.
    investigative_guidance: List[InvestigativeGuidance] = Field(default_factory=list)
    sources: List[LegalSourceReference] = Field(default_factory=list)
    #: Mandatory wording; see ``provisions.ASSESSMENT_CAVEAT``.
    caveat: str = ""
    #: Present when nothing was engaged, so the section never renders empty.
    summary: str = ""
    analysis_time_ms: float = 0.0
