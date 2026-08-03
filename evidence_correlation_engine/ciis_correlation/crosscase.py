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

from backend.modules.evidence.logger import get_logger


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

    When ``evidence_csv`` is supplied it is treated as **authoritative** for
    which evidence exists and which case owns it, because it is the
    chain-of-custody register; ``entities.csv`` is derived from it. Two classes
    of stale row are therefore neutralised at read time:

    * **Orphaned** - the entity's evidence item no longer exists (a delete that
      failed part-way, an externally edited CSV, a restored backup). The row is
      dropped, so a deleted item can never reappear in another case's
      correlation, graph or report.
    * **Mis-attributed** - the row names a different case than the register
      does for that evidence id. This happens when an evidence id is reused
      across cases, and it is the more dangerous of the two: correlation would
      report the *wrong case* as the source of a shared entity. The occurrence
      is re-attributed to the owning case from the register rather than being
      discarded, so the entity still correlates - just against the correct case.

    Enforcing this at read time makes the whole class of failure impossible
    regardless of how the row got stale, instead of relying on every writer to
    clean up after itself.
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
        #: Corpus size, computed once per load (see ``total_documents``).
        self._document_total: Optional[int] = None

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

    def _live_evidence(self) -> Optional[Dict[str, str]]:
        """``{evidence_id: owning_case_id}`` from the register, or ``None``.

        ``None`` means "do not filter" - returned when no register path was
        supplied or the file is unreadable, so a transient I/O error degrades
        to the old behaviour instead of silently reporting that every case is
        gone.
        """
        if self._evidence_path is None:
            return None
        try:
            with open(self._evidence_path, "r", newline="", encoding="utf-8") as handle:
                return {
                    (row.get("evidence_id") or "").strip():
                        (row.get("case_id") or "").strip()
                    for row in csv.DictReader(handle)
                    if (row.get("evidence_id") or "").strip()
                }
        except OSError:
            return None

    def _ensure_loaded(self) -> None:
        """(Re)build the in-memory index when entities.csv has changed."""
        stamp = self._current_stamp()
        if stamp[0] is not None and stamp == self._stamp and self._buckets:
            return
        buckets: Dict[str, List[EntityOccurrence]] = {}
        live = self._live_evidence()
        skipped = 0
        reattributed = 0
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
                        if live is not None:
                            owner = live.get(evidence_id)
                            if owner is None:
                                skipped += 1        # evidence item is gone
                                continue
                            if owner != case_id:
                                # The register wins: correlating this entity
                                # against the case named in entities.csv would
                                # cite the wrong case as its source.
                                reattributed += 1
                                case_id = owner
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
                "ignored %d entity row(s) whose evidence item no longer exists; "
                "run maintenance to purge them from %s", skipped, self._path.name)
        if reattributed:
            self._log.warning(
                "re-attributed %d entity row(s) to the case named in the "
                "chain-of-custody register; %s disagreed with evidence.csv",
                reattributed, self._path.name)
        self._buckets = buckets
        self._stamp = stamp
        self._document_total = None   # recomputed lazily against the new load

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

    # ------------------------------------------------------ corpus statistics
    #
    # Correlation weights a shared value by how rare it is, which needs two
    # counts over the whole corpus. Both are derived from the index that is
    # already in memory, so they cost a dict lookup rather than a file read.

    def document_frequency(self, entity_type: str, normalized: str) -> int:
        """Distinct evidence items carrying this value, corpus-wide.

        Counts *items*, not occurrences: a value repeated twelve times inside
        one screenshot is one item's worth of evidence, and counting the
        repeats would make a value look widespread on the strength of a single
        noisy OCR pass.
        """
        with self._lock:
            self._ensure_loaded()
            occurrences = self._buckets.get(bucket_key(entity_type, normalized), [])
            return len({occ.evidence_id for occ in occurrences})

    def total_documents(self) -> int:
        """Distinct evidence items that contributed any entity at all."""
        with self._lock:
            self._ensure_loaded()
            if self._document_total is None:
                self._document_total = len({
                    occ.evidence_id
                    for occurrences in self._buckets.values()
                    for occ in occurrences
                })
            return self._document_total

    # ------------------------------------------------------------------ write
    #
    # There is nothing to write: entities.csv is owned by the cleaning stage.
    # These remain so callers (pipeline, maintenance) keep a stable API.

    def refresh(self) -> None:
        """Force the next lookup to re-read entities.csv."""
        with self._lock:
            self._stamp = None
            self._buckets = {}
            self._document_total = None

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
