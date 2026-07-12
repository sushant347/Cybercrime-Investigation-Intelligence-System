"""Threat intelligence package with external data source connectors."""

from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.intelligence.aggregator import IntelligenceAggregator

__all__ = ["BaseConnector", "IntelligenceResult", "IntelligenceAggregator"]

from src.intelligence.brand_intelligence import (
    BrandFinding,
    BrandIntelligenceEngine,
    BrandIntelligenceResult,
)

__all__ = list(globals().get("__all__", [])) + [
    "BrandIntelligenceEngine",
    "BrandIntelligenceResult",
    "BrandFinding",
]
