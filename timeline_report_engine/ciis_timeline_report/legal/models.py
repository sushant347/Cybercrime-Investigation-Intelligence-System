"""Contracts for the statutory-basis assessment."""

from __future__ import annotations

from typing import List

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


class LegalBasisAssessment(BaseModel):
    """Which provisions the stored findings engage for one case."""

    case_id: str
    statute: str
    jurisdiction: str
    provisions: List[EngagedProvision] = Field(default_factory=list)
    #: Mandatory wording; see ``provisions.ASSESSMENT_CAVEAT``.
    caveat: str = ""
    #: Present when nothing was engaged, so the section never renders empty.
    summary: str = ""
    analysis_time_ms: float = 0.0
