"""Domain models (dataclasses) used across the evidence engine.

These are internal, storage-agnostic value objects. Pydantic models used for
the public output contract live in :mod:`schemas`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

#: A bounding box is a polygon of four ``[x, y]`` corner points
#: (top-left, top-right, bottom-right, bottom-left) in pixel coordinates.
BoundingBox = List[List[float]]


@dataclass
class OCRLine:
    """One recognised text line, exactly as returned by the OCR engine.

    ``text`` is never translated, autocorrected or otherwise modified.
    """

    text: str
    confidence: float
    bbox: BoundingBox = field(default_factory=list)


@dataclass
class OCRPageResult:
    """OCR output for a single page (or single image)."""

    page_number: int
    lines: List[OCRLine] = field(default_factory=list)
    processing_time_ms: float = 0.0
    preprocessing_steps: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Raw page text: recognised lines joined by newlines, unmodified."""
        return "\n".join(line.text for line in self.lines)

    @property
    def average_confidence(self) -> float:
        """Mean line confidence, 0.0 when the page produced no text."""
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)


@dataclass
class ImageQualityReport:
    """Automatic quality assessment used to choose preprocessing steps."""

    width: int
    height: int
    blur_score: float        # Laplacian variance; low => blurry
    brightness: float        # mean grayscale intensity
    contrast: float          # grayscale standard deviation
    noise_level: float       # median-filter residual estimate
    skew_angle: float        # estimated document skew in degrees

    @property
    def is_blurry(self) -> bool:
        return self.blur_score < 120.0

    @property
    def is_low_contrast(self) -> bool:
        return self.contrast < 45.0


@dataclass
class CaseRecord:
    """A cybercrime investigation case."""

    case_id: str
    created_at: str
    title: str = ""
    investigator_notes: str = ""  # empty by default, filled by investigators
    evidence_count: int = 0


@dataclass
class EvidenceRecord:
    """One acquired evidence item (chain-of-custody row)."""

    evidence_id: str
    case_id: str
    original_file_name: str
    stored_file_name: str
    file_extension: str
    file_size_bytes: int
    sha256_before: str
    sha256_after: str = ""
    hash_verified: Optional[bool] = None
    upload_time: str = ""
    processing_time: str = ""
    status: str = "uploaded"  # uploaded | processed | failed
    investigator_notes: str = ""


@dataclass
class ProcessingLogEntry:
    """A single audit-trail entry written to ``processing_log.csv``."""

    timestamp: str
    case_id: str
    evidence_id: str
    stage: str          # upload | preprocessing | ocr | hashing | storage | pipeline
    level: str          # INFO | WARNING | ERROR
    message: str
    duration_ms: float = 0.0
