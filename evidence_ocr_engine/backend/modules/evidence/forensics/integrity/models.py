"""Pydantic models for Advanced File Integrity Analysis (Module 7)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DuplicateHit(BaseModel):
    """Another evidence item sharing the same SHA-256 content hash."""

    evidence_id: str
    case_id: str = ""
    source: str = Field(description="'evidence_register' or 'fingerprint_index'")


class FileFingerprint(BaseModel):
    """Complete Module-7 output stored as ``file_fingerprint.json``."""

    evidence_id: str
    case_id: str
    source_file: str

    md5: str
    sha1: str
    sha256: str
    sha512: str
    crc32: str

    file_size_bytes: int = Field(ge=0)
    entropy_bits_per_byte: float = Field(ge=0.0, le=8.0)
    high_entropy: bool = Field(
        default=False,
        description="Entropy above threshold - compressed/encrypted content",
    )
    magic_number_hex: str = ""
    magic_format: str = Field(default="", description="Format implied by magic bytes")
    declared_extension: str = ""
    mime_type: str = ""
    extension_matches_magic: bool = True

    sha256_matches_acquisition: bool | None = Field(
        default=None,
        description="Cross-check against the chain-of-custody sha256_before",
    )
    duplicates: List[DuplicateHit] = Field(default_factory=list)
    is_duplicate: bool = False
    analysis_time_ms: float = 0.0
