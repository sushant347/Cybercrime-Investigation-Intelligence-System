"""Cross-case entity lookup over the **single** entity file.

Every extracted entity in the system lives in exactly one place:

    storage/entities.csv
      case_id, evidence_id, entity_type, value, normalized, extracted_at

written once by the cleaning stage. Cross-case correlation reads *that* file and
nothing else, so there is no second store to keep in sync and no way for the two
to disagree. Deleting a case's rows from ``entities.csv`` removes it from
cross-case correlation automatically.

(Historically this module maintained a duplicate ``cross_case_index.json``. That
file is obsolete; :meth:`CrossCaseEntityIndex.clear` deletes it if present.)

Lookups are served from a small in-memory index built from the CSV and
invalidated by the file's mtime+size, so repeated queries during one analysis
do not re-read the file, while a fresh write is always picked up.
"""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..evidence.logger import get_logger


def normalize_value(value: str) -> str:
    """Canonical form used for cross-case matching (case/space-insensitive)."""
    return (value or "").strip().lower()


def bucket_key(entity_type: str, normalized: str) -> str:
    """Stable key for one (type, value) pair."""
    return f"{(entity_type or '').strip().lower()}\x1f{normalize_value(normalized)}"


@dataclass(frozen=True)
class EntityOccurrence:
    """One (case, evidence) that a normalized entity was seen in."""

    entity_type: str
    normalized: str
    case_id: str
    evidence_id: str
    value: str = ""
    source_location: str = ""
    confidence: float = 0.0
    first_seen: str = ""
    last_seen: str = ""


class CrossCaseEntityIndex:
    """Read-through view of ``entities.csv`` for cross-case lookups.

    Constructed with the path to the *entities CSV*. The legacy JSON index path
    may still be passed for cleanup purposes via ``legacy_index_path``.

    When ``evidence_csv`` is supplied, occurrences belonging to a case that has
    no evidence left are ignored. An entity row can outlive its case - a delete
    that failed part-way, an externally edited CSV, a restored backup - and
    without this guard a single orphaned row silently resurrects a deleted case
    in every other case's cross-case correlation, graph and report. Filtering
    at read time makes that whole class of failure impossible regardless of how
    the row got orphaned, instead of relying on every writer to clean up.
    """

    def __init__(self, entities_csv: Path,
                 legacy_index_path: Optional[Path] = None,
                 evidence_csv: Optional[Path] = None) -> None:
        self._path = Path(entities_csv)
        self._evidence_path = Path(evidence_csv) if evidence_csv else None
        self._legacy_path = Path(legacy_index_path) if legacy_index_path else None
        self._log = get_logger("investigation.crosscase")
        self._lock = threading.Lock()
        self._buckets: Dict[str, List[EntityOccurrence]] = {}
        self._stamp: Optional[Tuple[Optional[Tuple[float, int]], ...]] = None

    # ------------------------------------------------------------------ load

    @staticmethod
    def _file_stamp(path: Optional[Path]) -> Optional[Tuple[float, int]]:
        if path is None:
            return None
        try:
            stat = path.stat()
            return (stat.st_mtime, stat.st_size)
        except OSError:
            return None

    def _current_stamp(self):
        """Cache key: both files matter, so deleting a case invalidates too."""
        return (self._file_stamp(self._path), self._file_stamp(self._evidence_path))

    def _live_case_ids(self) -> Optional[set]:
        """Cases that still have evidence, or None when not filtering.

        Mirrors ``CaseDataRepository.case_exists``: a case is live exactly when
        evidence.csv still has a row for it.
        """
        if self._evidence_path is None:
            return None
        try:
            with open(self._evidence_path, "r", newline="", encoding="utf-8") as handle:
                return {(row.get("case_id") or "").strip()
                        for row in csv.DictReader(handle)}
        except OSError:
            # Unreadable evidence file: fall back to not filtering rather than
            # silently reporting that every case is gone.
            return None

    def _ensure_loaded(self) -> None:
        """(Re)build the in-memory index when entities.csv has changed."""
        stamp = self._current_stamp()
        if stamp[0] is not None and stamp == self._stamp and self._buckets:
            return
        buckets: Dict[str, List[EntityOccurrence]] = {}
        live = self._live_case_ids()
        skipped = 0
        if stamp[0] is not None:
            try:
                with open(self._path, "r", newline="", encoding="utf-8") as handle:
                    for row in csv.DictReader(handle):
                        entity_type = (row.get("entity_type") or "").strip().lower()
                        raw = row.get("normalized") or row.get("value") or ""
                        normalized = normalize_value(raw)
                        case_id = (row.get("case_id") or "").strip()
                        evidence_id = (row.get("evidence_id") or "").strip()
                        if not (entity_type and normalized and case_id and evidence_id):
                            continue
                        if live is not None and case_id not in live:
                            skipped += 1   # orphaned row: its case is gone
                            continue
                        seen = row.get("extracted_at", "")
                        buckets.setdefault(bucket_key(entity_type, normalized), []).append(
                            EntityOccurrence(
                                entity_type=entity_type,
                                normalized=normalized,
                                case_id=case_id,
                                evidence_id=evidence_id,
                                value=row.get("value", "") or normalized,
                                source_location=evidence_id,
                                first_seen=seen,
                                last_seen=seen,
                            )
                        )
            except OSError as exc:
                self._log.warning("entities.csv unreadable (%s): %s", self._path, exc)
        if skipped:
            self._log.warning(
                "ignored %d entity row(s) whose case no longer has evidence; "
                "run maintenance to purge them from %s", skipped, self._path.name)
        self._buckets = buckets
        self._stamp = stamp

    # ------------------------------------------------------------------- read

    def occurrences_for(self, entity_type: str, normalized: str) -> List[EntityOccurrence]:
        with self._lock:
            self._ensure_loaded()
            return list(self._buckets.get(bucket_key(entity_type, normalized), []))

    def occurrences_in_other_cases(
        self, entity_type: str, normalized: str, case_id: str
    ) -> List[EntityOccurrence]:
        """Every occurrence of this entity that belongs to a *different* case."""
        return [occ for occ in self.occurrences_for(entity_type, normalized)
                if occ.case_id != case_id]

    def case_ids(self) -> List[str]:
        with self._lock:
            self._ensure_loaded()
            seen: List[str] = []
            for occurrences in self._buckets.values():
                for occ in occurrences:
                    if occ.case_id not in seen:
                        seen.append(occ.case_id)
            return seen

    def entity_count(self) -> int:
        """Total entity occurrences currently recorded (across all cases)."""
        with self._lock:
            self._ensure_loaded()
            return sum(len(v) for v in self._buckets.values())

    # ------------------------------------------------------------------ write
    #
    # There is nothing to write: entities.csv is owned by the cleaning stage.
    # These remain so callers (pipeline, maintenance) keep a stable API.

    def refresh(self) -> None:
        """Force the next lookup to re-read entities.csv."""
        with self._lock:
            self._stamp = None
            self._buckets = {}

    def save(self) -> None:
        """No-op: the single entity file is written by the cleaning stage."""
        return None

    def remove_case(self, case_id: str) -> bool:
        """Report whether ``case_id`` still has entities.

        Actual removal happens when the case's rows are deleted from
        ``entities.csv`` (see ``maintenance.delete_case``); this just drops the
        cached view so the next lookup reflects that.
        """
        had = case_id in self.case_ids()
        self.refresh()
        return had

    def clear(self) -> None:
        """Drop the cache and delete the obsolete legacy JSON index, if any."""
        self.refresh()
        if self._legacy_path and self._legacy_path.exists():
            try:
                self._legacy_path.unlink()
            except OSError as exc:  # noqa: BLE001
                self._log.warning("could not delete legacy index %s: %s",
                                  self._legacy_path, exc)
