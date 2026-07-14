"""Module 7 - Advanced File Integrity Analysis service.

Extends (never replaces) the existing SHA-256 chain-of-custody verification:

* MD5 / SHA-1 / SHA-256 / SHA-512 / CRC32 - computed in a single streaming
  pass over the file
* Shannon entropy (bits/byte)
* Magic-number identification and extension/MIME cross-check
* Duplicate detection against (a) the existing evidence register
  (``evidence.csv``, read-only) and (b) the forensics fingerprint index
* Cross-verification against the acquisition-time SHA-256 when provided

Output: a complete File Fingerprint Report per evidence item, plus a row in
``storage/forensics/file_fingerprints.csv`` for fast duplicate lookups.
"""

from __future__ import annotations

import csv
import hashlib
import math
import mimetypes
import time
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...logger import get_logger
from ...utils import StorageError, file_extension, utc_now_iso
from ..audit import ForensicAuditTrail
from ..config import ForensicsConfig
from ..repository import ForensicReportRepository
from .models import DuplicateHit, FileFingerprint

MODULE = "file_integrity"

#: Magic-number table (prefix bytes -> format name). Configuration-adjacent:
#: extend freely; detection picks the longest matching prefix.
MAGIC_NUMBERS: Dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "PNG image",
    b"\xff\xd8\xff": "JPEG image",
    b"%PDF-": "PDF document",
    b"PK\x03\x04": "ZIP container (OOXML/office or archive)",
    b"GIF87a": "GIF image",
    b"GIF89a": "GIF image",
    b"BM": "BMP image",
    b"II*\x00": "TIFF image (little-endian)",
    b"MM\x00*": "TIFF image (big-endian)",
    b"\x1f\x8b": "GZIP archive",
    b"7z\xbc\xaf\x27\x1c": "7-Zip archive",
    b"Rar!\x1a\x07": "RAR archive",
}

#: Extensions consistent with each detected magic format.
_FORMAT_EXTENSIONS: Dict[str, Tuple[str, ...]] = {
    "PNG image": (".png",),
    "JPEG image": (".jpg", ".jpeg"),
    "PDF document": (".pdf",),
    "ZIP container (OOXML/office or archive)": (".docx", ".xlsx", ".pptx", ".zip"),
    "GIF image": (".gif",),
    "BMP image": (".bmp",),
}


class FileIntegrityService:
    """Multi-hash fingerprinting and duplicate detection."""

    fingerprint_fields = (
        "recorded_at", "evidence_id", "case_id", "file_name",
        "sha256", "md5", "file_size_bytes",
    )

    def __init__(
        self,
        config: ForensicsConfig,
        repository: ForensicReportRepository,
        audit: ForensicAuditTrail,
        evidence_register_csv: Optional[Path] = None,
    ) -> None:
        """``evidence_register_csv`` points at the existing (read-only)
        ``storage/evidence.csv`` for cross-evidence duplicate detection."""
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._evidence_csv = evidence_register_csv
        self._log = get_logger("forensics.integrity")
        self._ensure_index()

    # ------------------------------------------------------------------ public

    def fingerprint(
        self,
        source_path: Path,
        *,
        evidence_id: str,
        case_id: str,
        acquisition_sha256: str = "",
        persist: bool = True,
    ) -> FileFingerprint:
        """Produce the complete fingerprint report for one evidence file."""
        started = time.perf_counter()
        digests, size, entropy, head = self._stream_analyze(source_path)
        magic_hex, magic_format = self._identify_magic(head)
        extension = file_extension(source_path)
        mime_type = mimetypes.guess_type(str(source_path))[0] or "application/octet-stream"

        matches_magic = True
        if magic_format and magic_format in _FORMAT_EXTENSIONS:
            matches_magic = extension in _FORMAT_EXTENSIONS[magic_format]

        duplicates = self._find_duplicates(digests["sha256"], evidence_id)
        report = FileFingerprint(
            evidence_id=evidence_id,
            case_id=case_id,
            source_file=source_path.name,
            md5=digests["md5"],
            sha1=digests["sha1"],
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            crc32=digests["crc32"],
            file_size_bytes=size,
            entropy_bits_per_byte=round(entropy, 4),
            high_entropy=entropy >= self._cfg.entropy_high_threshold,
            magic_number_hex=magic_hex,
            magic_format=magic_format,
            declared_extension=extension,
            mime_type=mime_type,
            extension_matches_magic=matches_magic,
            sha256_matches_acquisition=(
                digests["sha256"].lower() == acquisition_sha256.lower()
                if acquisition_sha256 else None
            ),
            duplicates=duplicates,
            is_duplicate=bool(duplicates),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )

        if persist:
            self._repo.save(
                evidence_id, case_id, self._cfg.fingerprint_report_name,
                report.model_dump(),
            )
            self._append_index(report)
            level = "INFO"
            message = (
                f"sha256={report.sha256[:16]}... entropy={report.entropy_bits_per_byte} "
                f"magic={report.magic_format or 'unknown'} duplicate={report.is_duplicate}"
            )
            if report.sha256_matches_acquisition is False:
                level = "ERROR"
                message += " ACQUISITION-HASH MISMATCH"
            if not report.extension_matches_magic:
                level = "WARNING"
                message += " extension/magic mismatch"
            self._audit.record(
                case_id, evidence_id, MODULE, "fingerprinted", message,
                level=level, duration_ms=report.analysis_time_ms,
            )
        return report

    # ---------------------------------------------------------------- analysis

    def _stream_analyze(
        self, path: Path
    ) -> Tuple[Dict[str, str], int, float, bytes]:
        """Single pass: all hashes + CRC32 + byte histogram (for entropy)."""
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        sha512 = hashlib.sha512()
        crc = 0
        histogram = [0] * 256
        size = 0
        head = b""
        try:
            with open(path, "rb") as handle:
                while True:
                    chunk = handle.read(self._cfg.hash_chunk_bytes)
                    if not chunk:
                        break
                    if not head:
                        head = chunk[:16]
                    md5.update(chunk)
                    sha1.update(chunk)
                    sha256.update(chunk)
                    sha512.update(chunk)
                    crc = zlib.crc32(chunk, crc)
                    size += len(chunk)
                    for byte in chunk:
                        histogram[byte] += 1
        except OSError as exc:
            raise StorageError(f"Cannot read evidence file '{path}': {exc}") from exc

        entropy = 0.0
        if size > 0:
            for count in histogram:
                if count:
                    p = count / size
                    entropy -= p * math.log2(p)
        digests = {
            "md5": md5.hexdigest(),
            "sha1": sha1.hexdigest(),
            "sha256": sha256.hexdigest(),
            "sha512": sha512.hexdigest(),
            "crc32": f"{crc & 0xFFFFFFFF:08x}",
        }
        return digests, size, entropy, head

    @staticmethod
    def _identify_magic(head: bytes) -> Tuple[str, str]:
        best: Tuple[str, str] = (head[:8].hex(), "")
        best_len = 0
        for prefix, format_name in MAGIC_NUMBERS.items():
            if head.startswith(prefix) and len(prefix) > best_len:
                best = (head[:max(8, len(prefix))].hex(), format_name)
                best_len = len(prefix)
        return best

    # -------------------------------------------------------------- duplicates

    def _find_duplicates(self, sha256: str, own_evidence_id: str) -> List[DuplicateHit]:
        hits: List[DuplicateHit] = []
        limit = self._cfg.duplicate_scope_limit
        # (a) existing chain-of-custody register - read-only access
        if self._evidence_csv is not None and self._evidence_csv.exists():
            try:
                with open(self._evidence_csv, "r", newline="", encoding="utf-8") as handle:
                    for i, row in enumerate(csv.DictReader(handle)):
                        if i >= limit:
                            break
                        if row.get("sha256_before", "").lower() == sha256.lower() \
                                and row.get("evidence_id") != own_evidence_id:
                            hits.append(DuplicateHit(
                                evidence_id=row.get("evidence_id", ""),
                                case_id=row.get("case_id", ""),
                                source="evidence_register",
                            ))
            except OSError as exc:
                self._log.warning("could not read evidence register: %s", exc)
        # (b) forensics fingerprint index
        index = self._cfg.fingerprint_csv
        if index.exists():
            try:
                with open(index, "r", newline="", encoding="utf-8") as handle:
                    known = {h.evidence_id for h in hits}
                    for i, row in enumerate(csv.DictReader(handle)):
                        if i >= limit:
                            break
                        if row.get("sha256", "").lower() == sha256.lower() \
                                and row.get("evidence_id") != own_evidence_id \
                                and row.get("evidence_id") not in known:
                            hits.append(DuplicateHit(
                                evidence_id=row.get("evidence_id", ""),
                                case_id=row.get("case_id", ""),
                                source="fingerprint_index",
                            ))
            except OSError as exc:
                self._log.warning("could not read fingerprint index: %s", exc)
        return hits

    # ------------------------------------------------------------------- index

    def _ensure_index(self) -> None:
        index = self._cfg.fingerprint_csv
        if index.exists():
            return
        index.parent.mkdir(parents=True, exist_ok=True)
        with open(index, "w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=list(self.fingerprint_fields)).writeheader()

    def _append_index(self, report: FileFingerprint) -> None:
        try:
            with open(self._cfg.fingerprint_csv, "a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=list(self.fingerprint_fields)).writerow({
                    "recorded_at": utc_now_iso(),
                    "evidence_id": report.evidence_id,
                    "case_id": report.case_id,
                    "file_name": report.source_file,
                    "sha256": report.sha256,
                    "md5": report.md5,
                    "file_size_bytes": str(report.file_size_bytes),
                })
        except OSError as exc:  # pragma: no cover
            self._log.error("could not append fingerprint index: %s", exc)
