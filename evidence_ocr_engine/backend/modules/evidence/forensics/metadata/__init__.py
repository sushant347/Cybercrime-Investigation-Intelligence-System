"""Module 6 - Forensic Metadata Extraction (images, PDFs, Office documents)."""

from .models import MetadataReport
from .service import MetadataExtractionService

__all__ = ["MetadataReport", "MetadataExtractionService"]
