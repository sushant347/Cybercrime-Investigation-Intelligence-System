"""Module 8 - Evidence Confidence Scoring (final per-evidence trust score)."""

from .models import ConfidenceComponent, EvidenceConfidence
from .service import ConfidenceScoringService

__all__ = ["ConfidenceComponent", "EvidenceConfidence", "ConfidenceScoringService"]
