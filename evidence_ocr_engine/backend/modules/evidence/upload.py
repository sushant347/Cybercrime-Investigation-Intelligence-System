"""Forensic evidence acquisition (upload) service.

Responsibilities:
    1. Validate the submitted file (existence, permission, format, size).
    2. Compute the pre-processing SHA-256 hash of the original.
    3. Copy the file into ``storage/originals/`` under a unique name -
       the submitted original is **never** moved, altered or deleted.
    4. Verify the stored copy's hash matches the original (acquisition
       integrity), then persist the chain-of-custody row to ``evidence.csv``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import EvidenceConfig
from .csv_storage import EvidenceRepository, ProcessingLogRepository
from .hash_service import HashService
from .logger import StageTimer, get_logger
from .models import EvidenceRecord
from .utils import (
    FileTooLargeError,
    HashVerificationError,
    PermissionDeniedError,
    UnsupportedFormatError,
    file_extension,
    human_size,
    unique_filename,
    utc_now_iso,
)


class EvidenceUploader:
    """Acquires evidence files with full integrity guarantees."""

    def __init__(
        self,
        config: EvidenceConfig,
        hash_service: HashService,
        evidence_repo: EvidenceRepository,
        log_repo: ProcessingLogRepository,
    ) -> None:
        self._cfg = config
        self._hash = hash_service
        self._evidence = evidence_repo
        self._audit = log_repo
        self._log = get_logger("upload")
        config.ensure_directories()

    def upload(self, source: Path | str, case_id: str, notes: str = "") -> EvidenceRecord:
        """Acquire one evidence file for ``case_id``.

        Args:
            source: Path to the submitted evidence file.
            case_id: Investigation case the evidence belongs to.
            notes: Optional investigator notes (empty by default).

        Returns:
            The persisted :class:`EvidenceRecord` (status ``"uploaded"``).

        Raises:
            UnsupportedFormatError, FileTooLargeError, PermissionDeniedError,
            HashVerificationError: On validation / integrity failures.
        """
        source_path = Path(source)
        with StageTimer(self._log, "upload") as timer:
            self._validate(source_path)

            evidence_id = self._evidence.next_evidence_id()
            sha_before = self._hash.sha256_file(source_path)
            stored_name = unique_filename(source_path.name, evidence_id)
            stored_path = self._cfg.originals_dir / stored_name

            # copy2 preserves timestamps; the original file is left untouched.
            shutil.copy2(source_path, stored_path)

            # Acquisition integrity: the stored copy must be bit-identical.
            if not self._hash.verify(stored_path, sha_before):
                stored_path.unlink(missing_ok=True)
                raise HashVerificationError(
                    f"Stored copy of '{source_path.name}' does not match original hash"
                )

            record = EvidenceRecord(
                evidence_id=evidence_id,
                case_id=case_id,
                original_file_name=source_path.name,
                stored_file_name=stored_name,
                file_extension=file_extension(source_path),
                file_size_bytes=source_path.stat().st_size,
                sha256_before=sha_before,
                upload_time=utc_now_iso(),
                status="uploaded",
                investigator_notes=notes,
            )
            self._evidence.add(record)

        self._audit.log_stage(
            case_id, record.evidence_id, "upload",
            f"acquired '{source_path.name}' ({human_size(record.file_size_bytes)}), "
            f"sha256={record.sha256_before[:16]}...",
            duration_ms=timer.elapsed_ms,
        )
        self._log.info(
            "evidence %s acquired for %s (%s)",
            record.evidence_id, case_id, human_size(record.file_size_bytes),
        )
        return record

    def stored_path(self, record: EvidenceRecord) -> Path:
        """Absolute path of the preserved working copy for ``record``."""
        return self._cfg.originals_dir / record.stored_file_name

    # ---------------------------------------------------------------- internal

    def _validate(self, path: Path) -> None:
        """All upfront validations with specific, actionable errors."""
        if not path.exists() or not path.is_file():
            raise PermissionDeniedError(f"Evidence file not found: '{path}'")
        if not os.access(path, os.R_OK):
            raise PermissionDeniedError(f"No read permission for '{path}'")

        extension = file_extension(path)
        if extension not in self._cfg.supported_extensions:
            supported = ", ".join(sorted(self._cfg.supported_extensions))
            raise UnsupportedFormatError(
                f"Unsupported evidence format '{extension}'. Supported: {supported}"
            )

        size = path.stat().st_size
        if size > self._cfg.max_file_size_bytes:
            raise FileTooLargeError(
                f"'{path.name}' is {human_size(size)}; limit is "
                f"{human_size(self._cfg.max_file_size_bytes)}"
            )
        if size == 0:
            raise UnsupportedFormatError(f"'{path.name}' is empty (0 bytes)")
