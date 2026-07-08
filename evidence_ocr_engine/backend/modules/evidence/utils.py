"""Shared utilities and the module-wide exception hierarchy.

Every custom error raised by the evidence engine derives from
:class:`EvidenceError` so callers can catch one base class for graceful
recovery while still being able to branch on specific failure modes.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class EvidenceError(Exception):
    """Base class for all evidence-engine errors."""


class UnsupportedFormatError(EvidenceError):
    """The uploaded file extension is not supported."""


class FileTooLargeError(EvidenceError):
    """The uploaded file exceeds the configured size limit."""


class PermissionDeniedError(EvidenceError):
    """The engine lacks read permission for the uploaded file."""


class InvalidImageError(EvidenceError):
    """The file claims to be an image but cannot be decoded."""


class CorruptedPDFError(EvidenceError):
    """The PDF is damaged or cannot be parsed."""


class EmptyOCRError(EvidenceError):
    """OCR produced no text (raised only in strict mode)."""


class OCRTimeoutError(EvidenceError):
    """OCR exceeded the configured timeout."""


class HashVerificationError(EvidenceError):
    """Evidence integrity check failed - hashes do not match."""


class StorageError(EvidenceError):
    """CSV/JSON persistence failed."""


# --------------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------------- #


def utc_now() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp suitable for CSV/JSON storage."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# --------------------------------------------------------------------------- #
# Identifier / filename helpers
# --------------------------------------------------------------------------- #

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def format_sequential_id(prefix: str, sequence: int, width: int = 4) -> str:
    """``format_sequential_id("CASE", 1) -> "CASE_0001"``."""
    return f"{prefix}_{sequence:0{width}d}"


def sanitize_filename(name: str) -> str:
    """Strip characters that are unsafe in filenames, preserving extension."""
    cleaned = _SAFE_CHARS.sub("_", name.strip())
    return cleaned or "evidence"


def unique_filename(original_name: str, evidence_id: str) -> str:
    """Collision-free stored filename: ``EVID_00001__a1b2c3d4__original.png``.

    The uuid fragment guarantees uniqueness even if the same evidence file is
    submitted twice under the same name.
    """
    token = uuid.uuid4().hex[:8]
    return f"{evidence_id}__{token}__{sanitize_filename(original_name)}"


def file_extension(path: Path | str) -> str:
    """Lower-case file extension including the dot (``".png"``)."""
    return Path(path).suffix.lower()


def human_size(num_bytes: int) -> str:
    """Human-readable size string for logging (e.g. ``"1.4 MB"``)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} GB"
