"""Module 4 - Suspect Confidence Engine (explainable weighted scoring, no ML)."""

from .models import SuspectAssessment, SuspectProfile, SuspectScoreComponent
from .service import SuspectService

__all__ = ["SuspectAssessment", "SuspectProfile", "SuspectScoreComponent", "SuspectService"]
