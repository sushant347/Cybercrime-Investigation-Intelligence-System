"""CSV persistence layer (Repository pattern).

Per the project's design decisions, this research prototype stores structured
records in CSV files (no PostgreSQL / MongoDB / Neo4j / Redis) to keep the
system reproducible on any machine.

Repositories:
    * :class:`CaseRepository`          -> ``storage/cases.csv``
    * :class:`EvidenceRepository`      -> ``storage/evidence.csv``
    * :class:`OCRResultRepository`     -> ``storage/ocr_results.csv``
    * :class:`ProcessingLogRepository` -> ``storage/processing_log.csv``
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import EvidenceConfig
from .logger import get_logger
from .models import CaseRecord, EvidenceRecord, ProcessingLogEntry
from .utils import StorageError, format_sequential_id, utc_now_iso

Row = Dict[str, str]


class BaseCSVRepository:
    """Common CSV read/append behaviour shared by all repositories."""

    #: Column order for the underlying CSV file (subclasses override).
    fieldnames: Sequence[str] = ()

    def __init__(self, path: Path) -> None:
        self._path = path
        self._log = get_logger(f"csv.{path.stem}")
        self._ensure_file()

    @property
    def path(self) -> Path:
        return self._path

    def read_all(self) -> List[Row]:
        """Return every row as a dict (header excluded)."""
        try:
            with open(self._path, "r", newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
        except OSError as exc:
            raise StorageError(f"Cannot read '{self._path}': {exc}") from exc

    def append(self, row: Row) -> None:
        """Append a single row, keeping only known columns."""
        filtered = {key: str(row.get(key, "")) for key in self.fieldnames}
        try:
            with open(self._path, "a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=list(self.fieldnames)).writerow(filtered)
        except OSError as exc:
            raise StorageError(f"Cannot write '{self._path}': {exc}") from exc

    def overwrite_all(self, rows: List[Row]) -> None:
        """Atomically rewrite the file (used for record updates)."""
        tmp_path = self._path.with_suffix(".csv.tmp")
        try:
            with open(tmp_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(self.fieldnames))
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: str(row.get(key, "")) for key in self.fieldnames})
            tmp_path.replace(self._path)
        except OSError as exc:
            raise StorageError(f"Cannot rewrite '{self._path}': {exc}") from exc

    def count(self) -> int:
        return len(self.read_all())

    def delete_where(self, **match: str) -> int:
        """Remove every row whose columns all equal ``match``; returns count.

        Used to make re-processing idempotent: callers that re-derive rows for
        a key (e.g. an ``evidence_id``) clear the stale rows first so a second
        run replaces rather than duplicates them. No-op when the file is empty
        or nothing matches.
        """
        if not match:
            return 0
        rows = self.read_all()
        keep = [
            row for row in rows
            if not all(str(row.get(k, "")) == str(v) for k, v in match.items())
        ]
        removed = len(rows) - len(keep)
        if removed:
            self.overwrite_all(keep)
        return removed

    def _ensure_file(self) -> None:
        """Create the CSV with its header if it does not exist yet."""
        if self._path.exists():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=list(self.fieldnames)).writeheader()
        self._log.info("created %s", self._path.name)


class CaseRepository(BaseCSVRepository):
    """Repository for investigation cases."""

    fieldnames = ("case_id", "created_at", "title", "investigator_notes", "evidence_count")

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.cases_csv)
        self._prefix = config.case_id_prefix

    def next_case_id(self) -> str:
        """Sequential case identifier: CASE_0001, CASE_0002, ..."""
        return format_sequential_id(self._prefix, self.count() + 1, width=4)

    def create(
        self, title: str = "", notes: str = "", case_id: Optional[str] = None
    ) -> CaseRecord:
        """Create a case, optionally with a caller-supplied identifier.

        ``case_id`` lets the case registry store a hash-derived id (so a case
        reference always resolves to the same case); omitting it keeps the
        original sequential ``CASE_0001`` behaviour.
        """
        record = CaseRecord(
            case_id=case_id or self.next_case_id(),
            created_at=utc_now_iso(),
            title=title,
            investigator_notes=notes,
        )
        self.append({k: str(v) for k, v in asdict(record).items()})
        self._log.info("created case %s", record.case_id)
        return record

    def get(self, case_id: str) -> Optional[Row]:
        return next((r for r in self.read_all() if r["case_id"] == case_id), None)

    def increment_evidence_count(self, case_id: str) -> None:
        rows = self.read_all()
        for row in rows:
            if row["case_id"] == case_id:
                row["evidence_count"] = str(int(row.get("evidence_count") or 0) + 1)
        self.overwrite_all(rows)


class EvidenceRepository(BaseCSVRepository):
    """Repository for acquired evidence items (chain of custody)."""

    fieldnames = (
        "evidence_id", "case_id", "original_file_name", "stored_file_name",
        "file_extension", "file_size_bytes", "sha256_before", "sha256_after",
        "hash_verified", "upload_time", "processing_time", "status",
        "investigator_notes",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.evidence_csv)
        self._prefix = config.evidence_id_prefix

    def next_evidence_id(self) -> str:
        """Sequential evidence identifier: EVID_00001, EVID_00002, ..."""
        return format_sequential_id(self._prefix, self.count() + 1, width=5)

    def add(self, record: EvidenceRecord) -> None:
        self.append({k: str(v) for k, v in asdict(record).items()})
        self._log.info("stored evidence row %s", record.evidence_id)

    def get(self, evidence_id: str) -> Optional[Row]:
        return next((r for r in self.read_all() if r["evidence_id"] == evidence_id), None)

    def update(self, record: EvidenceRecord) -> None:
        """Replace the row matching ``record.evidence_id`` (atomic rewrite)."""
        rows = self.read_all()
        payload = {k: str(v) for k, v in asdict(record).items()}
        for index, row in enumerate(rows):
            if row["evidence_id"] == record.evidence_id:
                rows[index] = payload
                break
        else:
            rows.append(payload)
        self.overwrite_all(rows)


class OCRResultRepository(BaseCSVRepository):
    """Summary of OCR output per evidence item (full detail lives in JSON)."""

    fieldnames = (
        "evidence_id", "case_id", "ocr_engine", "page_count", "line_count",
        "average_confidence", "processing_time_ms", "raw_text_preview",
        "json_file", "created_at",
    )

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.ocr_results_csv)

    def add_summary(
        self,
        evidence_id: str,
        case_id: str,
        ocr_engine: str,
        page_count: int,
        line_count: int,
        average_confidence: float,
        processing_time_ms: float,
        raw_text: str,
        json_file: str,
    ) -> None:
        preview = raw_text[:200].replace("\n", " ")
        self.append(
            {
                "evidence_id": evidence_id,
                "case_id": case_id,
                "ocr_engine": ocr_engine,
                "page_count": str(page_count),
                "line_count": str(line_count),
                "average_confidence": f"{average_confidence:.4f}",
                "processing_time_ms": f"{processing_time_ms:.1f}",
                "raw_text_preview": preview,
                "json_file": json_file,
                "created_at": utc_now_iso(),
            }
        )


class ProcessingLogRepository(BaseCSVRepository):
    """Structured, queryable audit trail of every processing stage."""

    fieldnames = ("timestamp", "case_id", "evidence_id", "stage", "level", "message", "duration_ms")

    def __init__(self, config: EvidenceConfig) -> None:
        super().__init__(config.processing_log_csv)

    def log(self, entry: ProcessingLogEntry) -> None:
        self.append({k: str(v) for k, v in asdict(entry).items()})

    def log_stage(
        self,
        case_id: str,
        evidence_id: str,
        stage: str,
        message: str,
        level: str = "INFO",
        duration_ms: float = 0.0,
    ) -> None:
        """Convenience wrapper building the entry with a fresh timestamp."""
        self.log(
            ProcessingLogEntry(
                timestamp=utc_now_iso(),
                case_id=case_id,
                evidence_id=evidence_id,
                stage=stage,
                level=level,
                message=message,
                duration_ms=round(duration_ms, 1),
            )
        )
