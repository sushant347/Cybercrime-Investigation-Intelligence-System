"""Module 1 - Advanced Evidence Correlation Engine (explainable, weighted)."""

from .models import CorrelationAnalysis, CorrelationFactor, EvidencePairCorrelation
from .service import CorrelationService

__all__ = [
    "CorrelationAnalysis",
    "CorrelationFactor",
    "EvidencePairCorrelation",
    "CorrelationService",
]
