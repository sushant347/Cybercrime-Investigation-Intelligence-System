"""Persistent cross-case entity index.

A single JSON file (``storage/investigation/cross_case_index.json``) records
every normalized entity ever extracted, attributed to the case and evidence it
came from. It is the substrate the correlation service queries to find entities
shared **across** cases.

This is a storage helper - the *pattern* of the existing ``repository.py`` and
``data_access.py`` - not a second correlation engine. All cross-case scoring and
link-building lives in the existing :class:`CorrelationService`.

Index layout::

    {
      "version": 1,
      "updated_at": "<iso>",
      "buckets": {
        "<entity_type>\\u001f<normalized_lower>": {
          "entity_type": "phones",
          "normalized": "9812345678",
          "occurrences": [
            {"case_id": "...", "evidence_id": "...", "value": "...",
             "source_location": "...", "confidence": 0.97,
             "first_seen": "<iso>", "last_seen": "<iso>"}
          ]
        }
      }
    }

Duplicate entity records are impossible: an occurrence is keyed by
``(case_id, evidence_id)`` inside its bucket, so re-processing a case updates
the existing occurrence in place instead of appending a copy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..evidence.logger import get_logger
from ..evidence.utils import StorageError, utc_now_iso

#: Unit separator - safe key delimiter that cannot occur in a normalized value.
_SEP = ""

INDEX_VERSION = 1


@dataclass(frozen=True)
class EntityOccurrence:
    """One (case, evidence) that a normalized entity was seen in."""

    entity_type: str
    normalized: str
    case_id: str
    evidence_id: str
    value: str
    source_location: str
    confidence: float
    first_seen: str
    last_seen: str


def bucket_key(entity_type: str, normalized: str) -> str:
    return f"{entity_type.strip().lower()}{_SEP}{normalized.strip().lower()}"


class CrossCaseEntityIndex:
    """Read/write access to the persistent cross-case entity index."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._log = get_logger("investigation.crosscase")
        self._data: Dict = {"version": INDEX_VERSION, "updated_at": "", "buckets": {}}
        self._loaded = False

    # ------------------------------------------------------------------- load

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                self._data.setdefault("buckets", {})
            except (OSError, json.JSONDecodeError) as exc:
                self._log.warning("cross-case index unreadable (%s): %s", self._path, exc)
                self._data = {"version": INDEX_VERSION, "updated_at": "", "buckets": {}}
        self._loaded = True

    # ------------------------------------------------------------------ write

    def upsert(
        self,
        *,
        entity_type: str,
        normalized: str,
        case_id: str,
        evidence_id: str,
        value: str = "",
        source_location: str = "",
        confidence: float = 0.0,
    ) -> bool:
        """Insert or update one occurrence. Returns True if the index changed.

        Idempotent per ``(entity_type, normalized, case_id, evidence_id)`` - a
        repeat call only refreshes ``last_seen``/metadata, never duplicates.
        """
        if not entity_type or not normalized:
            return False
        self._ensure_loaded()
        key = bucket_key(entity_type, normalized)
        now = utc_now_iso()
        bucket = self._data["buckets"].get(key)
        if bucket is None:
            bucket = {
                "entity_type": entity_type.strip().lower(),
                "normalized": normalized.strip().lower(),
                "occurrences": [],
            }
            self._data["buckets"][key] = bucket

        for occ in bucket["occurrences"]:
            if occ["case_id"] == case_id and occ["evidence_id"] == evidence_id:
                changed = (
                    occ.get("value") != value
                    or occ.get("source_location") != source_location
                    or float(occ.get("confidence") or 0.0) != float(confidence)
                )
                occ["last_seen"] = now
                occ["value"] = value
                occ["source_location"] = source_location
                occ["confidence"] = round(float(confidence), 4)
                return changed  # occurrence already present -> no new record

        bucket["occurrences"].append({
            "case_id": case_id,
            "evidence_id": evidence_id,
            "value": value,
            "source_location": source_location,
            "confidence": round(float(confidence), 4),
            "first_seen": now,
            "last_seen": now,
        })
        return True

    def remove_case(self, case_id: str) -> bool:
        """Drop every occurrence belonging to a case. True if anything changed."""
        self._ensure_loaded()
        changed = False
        empty_keys: List[str] = []
        for key, bucket in self._data["buckets"].items():
            before = len(bucket["occurrences"])
            bucket["occurrences"] = [
                o for o in bucket["occurrences"] if o["case_id"] != case_id
            ]
            if len(bucket["occurrences"]) != before:
                changed = True
            if not bucket["occurrences"]:
                empty_keys.append(key)
        for key in empty_keys:
            del self._data["buckets"][key]
        return changed

    def clear(self) -> None:
        """Wipe the entire index (used by the testing reset)."""
        self._data = {"version": INDEX_VERSION, "updated_at": "", "buckets": {}}
        self._loaded = True
        if self._path.exists():
            try:
                self._path.unlink()
            except OSError as exc:  # noqa: BLE001
                self._log.warning("could not delete index %s: %s", self._path, exc)

    def save(self) -> None:
        self._ensure_loaded()
        self._data["version"] = INDEX_VERSION
        self._data["updated_at"] = utc_now_iso()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        try:
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except OSError as exc:
            raise StorageError(f"Cannot write cross-case index '{self._path}': {exc}") from exc

    # ------------------------------------------------------------------- read

    def occurrences_for(self, entity_type: str, normalized: str) -> List[EntityOccurrence]:
        self._ensure_loaded()
        bucket = self._data["buckets"].get(bucket_key(entity_type, normalized))
        if not bucket:
            return []
        return [_to_occurrence(bucket, o) for o in bucket["occurrences"]]

    def occurrences_in_other_cases(
        self, entity_type: str, normalized: str, case_id: str
    ) -> List[EntityOccurrence]:
        return [
            occ for occ in self.occurrences_for(entity_type, normalized)
            if occ.case_id != case_id
        ]

    def case_ids(self) -> List[str]:
        self._ensure_loaded()
        seen: List[str] = []
        for bucket in self._data["buckets"].values():
            for occ in bucket["occurrences"]:
                if occ["case_id"] not in seen:
                    seen.append(occ["case_id"])
        return seen

    def entity_count(self) -> int:
        self._ensure_loaded()
        return sum(len(b["occurrences"]) for b in self._data["buckets"].values())


def _to_occurrence(bucket: Dict, occ: Dict) -> EntityOccurrence:
    return EntityOccurrence(
        entity_type=bucket["entity_type"],
        normalized=bucket["normalized"],
        case_id=occ["case_id"],
        evidence_id=occ["evidence_id"],
        value=occ.get("value", ""),
        source_location=occ.get("source_location", ""),
        confidence=float(occ.get("confidence") or 0.0),
        first_seen=occ.get("first_seen", ""),
        last_seen=occ.get("last_seen", ""),
    )
