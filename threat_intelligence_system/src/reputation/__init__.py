"""Threat Reputation Engine - additive extension of the Threat Intelligence
System. Nothing here modifies existing APIs or JSON contracts.

Usage::

    from src.reputation import ReputationEngine

    report = ReputationEngine().analyze("http://paypa1-verify.top/login")
    print(report["reputation_score"], report["reasons"])
"""

from .blacklists import (
    BlacklistConnector,
    BlacklistEngine,
    BlacklistResult,
    OpenPhishConnector,
    PhishTankConnector,
    URLHausConnector,
)
from .cache import TTLCache
from .cloud_hosting import CloudHostingDetector, CloudHostingResult
from .domain_analysis import DomainAnalysis, DomainAnalyzer
from .ioc import IOC, detect_ioc
from .normalizer import normalize_domain, normalize_url
from .fusion import ConfidenceFusion, FusionResult
from .indicators import IndicatorGenerator, ThreatIndicator
from .report import ReportGenerator, ThreatReport
from .reputation_engine import ReputationEngine

__all__ = [
    "ReputationEngine",
    "ReportGenerator",
    "ThreatReport",
    "ConfidenceFusion",
    "FusionResult",
    "IndicatorGenerator",
    "ThreatIndicator",
    "BlacklistEngine",
    "BlacklistConnector",
    "BlacklistResult",
    "OpenPhishConnector",
    "PhishTankConnector",
    "URLHausConnector",
    "TTLCache",
    "DomainAnalyzer",
    "CloudHostingDetector",
    "CloudHostingResult",
    "DomainAnalysis",
    "IOC",
    "detect_ioc",
    "normalize_url",
    "normalize_domain",
]
