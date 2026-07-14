"""Module 5 - Logo & Brand Detection for screenshot evidence."""

from .models import LogoDetection, LogoDetectionReport
from .registry import BrandDefinition, BrandRegistry
from .service import LogoDetectionService

__all__ = [
    "LogoDetection",
    "LogoDetectionReport",
    "BrandDefinition",
    "BrandRegistry",
    "LogoDetectionService",
]
