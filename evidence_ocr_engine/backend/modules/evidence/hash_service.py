"""SHA-256 hashing for forensic evidence integrity.

Evidence is hashed **before** processing (at acquisition) and **after**
processing; both hashes must match, proving the original file was never
modified. Hashing streams the file in chunks so arbitrarily large evidence
is supported without loading it fully into memory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .logger import get_logger
from .utils import HashVerificationError

_CHUNK_SIZE = 1024 * 1024  # 1 MB


class HashService:
    """Computes and verifies SHA-256 digests of evidence files."""

    def __init__(self) -> None:
        self._log = get_logger("hash")

    def sha256_file(self, path: Path | str) -> str:
        """Stream-hash a file and return the hex digest.

        Args:
            path: File to hash. Must exist and be readable.

        Returns:
            64-character lowercase hexadecimal SHA-256 digest.
        """
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        hex_digest = digest.hexdigest()
        self._log.debug("sha256(%s) = %s", path, hex_digest)
        return hex_digest

    def verify(self, path: Path | str, expected: str) -> bool:
        """Re-hash ``path`` and compare with ``expected`` (case-insensitive)."""
        actual = self.sha256_file(path)
        matches = actual.lower() == expected.lower()
        if matches:
            self._log.info("hash verification OK for %s", path)
        else:
            self._log.error(
                "hash MISMATCH for %s: expected %s, got %s", path, expected, actual
            )
        return matches

    def verify_or_raise(self, path: Path | str, expected: str) -> None:
        """Like :meth:`verify` but raises :class:`HashVerificationError` on mismatch."""
        if not self.verify(path, expected):
            raise HashVerificationError(
                f"Evidence integrity violated: SHA-256 mismatch for '{path}'"
            )
