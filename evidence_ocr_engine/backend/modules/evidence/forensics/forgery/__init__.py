"""Module 4 - Image Forgery Detection (findings only - never rejects evidence)."""

from .models import ForgeryReport
from .service import ForgeryDetectionService

__all__ = ["ForgeryReport", "ForgeryDetectionService"]
