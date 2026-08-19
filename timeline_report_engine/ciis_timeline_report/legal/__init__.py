"""Statutory basis: which provisions the findings engage, and why.

Maps stored technical findings onto the Electronic Transactions Act, 2063
(2008) of Nepal. Deterministic and rule-based, like the rest of the scoring
path - and, like the rest of it, it explains every entry rather than asserting
a conclusion. It reports that the evidence contains the features a provision
describes; whether an offence is made out is for the investigating officer and
the prosecutor.
"""

from .models import (
    EngagedProvision,
    InvestigativeGuidance,
    LegalBasisAssessment,
    LegalSourceReference,
    UnassessedProvision,
)
from .provisions import (
    ACT_SHORT_NAME,
    ASSESSMENT_CAVEAT,
    MANUAL_REVIEW_PROVISIONS,
    PROVISIONS,
)
from .service import LegalBasisService

__all__ = [
    "EngagedProvision",
    "InvestigativeGuidance",
    "LegalBasisAssessment",
    "LegalSourceReference",
    "LegalBasisService",
    "UnassessedProvision",
    "PROVISIONS",
    "MANUAL_REVIEW_PROVISIONS",
    "ACT_SHORT_NAME",
    "ASSESSMENT_CAVEAT",
]
