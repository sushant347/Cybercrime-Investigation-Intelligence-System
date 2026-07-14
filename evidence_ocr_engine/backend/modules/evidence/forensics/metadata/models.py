"""Pydantic models for Forensic Metadata Extraction (Module 6)."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GPSData(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    raw: Dict[str, str] = Field(default_factory=dict)


class ImageMetadata(BaseModel):
    """EXIF-derived image metadata."""

    has_exif: bool = False
    camera_make: str = ""
    camera_model: str = ""
    device: str = Field(default="", description="'<make> <model>' when known")
    software: str = ""
    date_created: str = Field(default="", description="EXIF DateTimeOriginal")
    date_modified: str = Field(default="", description="EXIF DateTime")
    orientation: str = ""
    gps: Optional[GPSData] = None
    all_tags: Dict[str, str] = Field(default_factory=dict)


class PDFMetadata(BaseModel):
    author: str = ""
    producer: str = ""
    creator: str = ""
    title: str = ""
    subject: str = ""
    creation_date: str = ""
    modification_date: str = ""
    page_count: int = 0
    encrypted: bool = False


class OfficeMetadata(BaseModel):
    author: str = ""
    company: str = ""
    last_modified_by: str = ""
    revision_number: str = ""
    title: str = ""
    created: str = ""
    modified: str = ""
    application: str = ""


class FileSystemMetadata(BaseModel):
    file_size_bytes: int = 0
    created: str = ""
    modified: str = ""
    accessed: str = ""


class MetadataReport(BaseModel):
    """Complete Module-6 output stored as ``metadata_report.json``."""

    evidence_id: str
    case_id: str
    source_file: str
    file_type: str = Field(description="image | pdf | office | text | other")
    filesystem: FileSystemMetadata
    image: Optional[ImageMetadata] = None
    pdf: Optional[PDFMetadata] = None
    office: Optional[OfficeMetadata] = None
    consistency_notes: List[str] = Field(default_factory=list)
    extraction_errors: List[str] = Field(default_factory=list)
    analysis_time_ms: float = 0.0
