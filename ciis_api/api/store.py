"""File-backed platform store — replaces the Django ORM/SQLite entirely.

The forensic engine has always kept its records in CSV/JSON; this module brings
the *platform's* workflow state (background jobs, notifications, activity audit,
case metadata and case history) onto the same footing, so the project contains
no predefined database of any kind.

Layout (all under ``storage/platform/``)::

    jobs.json            background jobs (upload / analysis) - needs ids
    notifications.json   engine-wide notifications           - needs ids
    activity_log.csv     user/system activity audit          - append-only
    case_meta.csv        per-case workflow state (status, tags, ...)
    case_history.csv     immutable trail of case changes

JSON is used where records are updated in place and need an auto-increment id;
CSV where the data is a flat, append-mostly log (matching the engine's own
audit CSVs). Every write is atomic (temp file + rename) and guarded by a
per-file lock, because the API writes from a background worker thread.
"""

from __future__ import annotations

import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ----------------------------------------------------------------- utilities


def utc_now() -> str:
    """ISO-8601 UTC timestamp, matching the engine's format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _storage_root() -> Path:
    """``<engine storage>/platform`` — resolved lazily so tests can repoint it."""
    from . import engine  # local import: avoids a cycle at module load

    root = engine.evidence_config().storage_dir / "platform"
    root.mkdir(parents=True, exist_ok=True)
    return root


class _Collection:
    """Base: a single file plus the lock that serialises access to it."""

    filename: str = ""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return _storage_root() / self.filename

    def clear(self) -> None:
        with self._lock:
            path = self.path
            if path.exists():
                path.unlink()


class JsonCollection(_Collection):
    """Records with an auto-increment ``id``, updated in place."""

    def _read(self) -> List[Dict[str, Any]]:
        path = self.path
        if not path.is_file():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _write(self, rows: List[Dict[str, Any]]) -> None:
        path = self.path
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._read()

    def create(self, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            rows = self._read()
            next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
            record = {"id": next_id, "created_at": utc_now(), **fields}
            rows.append(record)
            self._write(rows)
            return record

    def get(self, record_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return next((r for r in self._read() if int(r.get("id", 0)) == int(record_id)), None)

    def update(self, record_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            rows = self._read()
            for row in rows:
                if int(row.get("id", 0)) == int(record_id):
                    row.update(fields)
                    self._write(rows)
                    return row
            return None


class CsvCollection(_Collection):
    """Flat rows keyed by column names; append-mostly."""

    fieldnames: tuple = ()

    def _read(self) -> List[Dict[str, str]]:
        path = self.path
        if not path.is_file():
            return []
        try:
            with open(path, "r", newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
        except OSError:
            return []

    def _write(self, rows: List[Dict[str, Any]]) -> None:
        path = self.path
        tmp = path.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.fieldnames))
            writer.writeheader()
            for row in rows:
                writer.writerow({k: ("" if row.get(k) is None else str(row.get(k, "")))
                                 for k in self.fieldnames})
        tmp.replace(path)

    def all(self) -> List[Dict[str, str]]:
        with self._lock:
            return self._read()

    def append(self, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            rows = self._read()
            record = {"id": len(rows) + 1, "created_at": utc_now(), **fields}
            rows.append(record)
            self._write(rows)
            return record


# ------------------------------------------------------------------- jobs


class Jobs(JsonCollection):
    """Background jobs for evidence processing and case analysis."""

    filename = "jobs.json"

    def start(self, job_type: str, case_id: str = "", detail: str = "",
              created_by: str = "") -> Dict[str, Any]:
        return self.create(job_type=job_type, status="queued", case_id=case_id,
                           evidence_id="", detail=detail, error="",
                           created_by=created_by, finished_at=None)

    def list(self, case_id: str = "", job_type: str = "",
             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = [r for r in self.all()
                if (not case_id or r.get("case_id") == case_id)
                and (not job_type or r.get("job_type") == job_type)]
        rows.sort(key=lambda r: int(r.get("id", 0)), reverse=True)
        return rows[:limit] if limit else rows

    def active(self, job_type: str, case_id: str) -> Optional[Dict[str, Any]]:
        return next((r for r in self.list(case_id=case_id, job_type=job_type)
                     if r.get("status") in ("queued", "running")), None)

    def finish(self, job_id: int, status: str, detail: str = "",
               error: str = "", evidence_id: str = "") -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {"status": status, "finished_at": utc_now()}
        if detail:
            fields["detail"] = detail
        if error:
            fields["error"] = error
        if evidence_id:
            fields["evidence_id"] = evidence_id
        return self.update(job_id, **fields)

    def delete_case(self, case_id: str) -> int:
        with self._lock:
            rows = self._read()
            keep = [r for r in rows if r.get("case_id") != case_id]
            removed = len(rows) - len(keep)
            if removed:
                self._write(keep)
            return removed


# ---------------------------------------------------------- notifications


class Notifications(JsonCollection):
    """Engine-wide notifications (no accounts, so no per-user inbox)."""

    filename = "notifications.json"

    def broadcast(self, *, type: str, title: str, message: str = "",
                  case_id: str = "", evidence_id: str = "") -> Dict[str, Any]:
        return self.create(type=type, title=title, message=message,
                           case_id=case_id, evidence_id=evidence_id, read=False)

    def list(self, unread: bool = False, type: str = "") -> List[Dict[str, Any]]:
        rows = [r for r in self.all()
                if (not unread or not r.get("read"))
                and (not type or r.get("type") == type)]
        rows.sort(key=lambda r: int(r.get("id", 0)), reverse=True)
        return rows

    def unread_count(self) -> int:
        return sum(1 for r in self.all() if not r.get("read"))

    def mark_read(self, ids: Optional[List[int]] = None) -> int:
        with self._lock:
            rows = self._read()
            marked = 0
            for row in rows:
                if row.get("read"):
                    continue
                if ids is None or int(row.get("id", 0)) in {int(i) for i in ids}:
                    row["read"] = True
                    marked += 1
            if marked:
                self._write(rows)
            return marked

    def delete_case(self, case_id: str) -> int:
        with self._lock:
            rows = self._read()
            keep = [r for r in rows if r.get("case_id") != case_id]
            removed = len(rows) - len(keep)
            if removed:
                self._write(keep)
            return removed


# --------------------------------------------------------------- activity


class ActivityLogStore(CsvCollection):
    """Platform-side activity audit (merged with the engine's own audit log)."""

    filename = "activity_log.csv"
    fieldnames = ("id", "created_at", "username", "module", "action", "case_id", "detail")

    def record(self, *, username: str = "", module: str, action: str,
               case_id: str = "", detail: str = "") -> Dict[str, Any]:
        return self.append(username=username, module=module, action=action,
                           case_id=case_id, detail=detail)

    def list(self, case_id: str = "", module: str = "",
             limit: Optional[int] = None) -> List[Dict[str, str]]:
        rows = [r for r in self.all()
                if (not case_id or r.get("case_id") == case_id)
                and (not module or r.get("module") == module)]
        rows.sort(key=lambda r: int(r.get("id", 0) or 0), reverse=True)
        return rows[:limit] if limit else rows


# -------------------------------------------------------------- case meta


class CaseMetaStore(CsvCollection):
    """Per-case workflow state: status, description, tags, priority override."""

    filename = "case_meta.csv"
    fieldnames = ("id", "created_at", "case_id", "title", "description", "status",
                  "priority_override", "tags", "updated_at")

    DEFAULT_STATUS = "open"

    def get(self, case_id: str) -> Optional[Dict[str, Any]]:
        row = next((r for r in self.all() if r.get("case_id") == case_id), None)
        return self._decode(row) if row else None

    def all_decoded(self) -> List[Dict[str, Any]]:
        return [self._decode(r) for r in self.all()]

    @staticmethod
    def _decode(row: Dict[str, str]) -> Dict[str, Any]:
        data = dict(row)
        raw = data.get("tags") or ""
        try:
            data["tags"] = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            data["tags"] = [t for t in raw.split("|") if t]
        return data

    def upsert(self, case_id: str, **fields: Any) -> Dict[str, Any]:
        if "tags" in fields and not isinstance(fields["tags"], str):
            fields["tags"] = json.dumps(list(fields["tags"]))
        with self._lock:
            rows = self._read()
            for row in rows:
                if row.get("case_id") == case_id:
                    row.update({k: v for k, v in fields.items() if v is not None})
                    row["updated_at"] = utc_now()
                    self._write(rows)
                    return self._decode(row)
            now = utc_now()
            record = {"id": len(rows) + 1, "created_at": now, "case_id": case_id,
                      "title": "", "description": "", "status": self.DEFAULT_STATUS,
                      "priority_override": "", "tags": "[]", "updated_at": now}
            record.update({k: v for k, v in fields.items() if v is not None})
            rows.append(record)
            self._write(rows)
            return self._decode(record)

    def delete_case(self, case_id: str) -> bool:
        with self._lock:
            rows = self._read()
            keep = [r for r in rows if r.get("case_id") != case_id]
            if len(keep) == len(rows):
                return False
            self._write(keep)
            return True


# ------------------------------------------------------------ case history


class CaseHistoryStore(CsvCollection):
    """Immutable trail of workflow changes on a case."""

    filename = "case_history.csv"
    fieldnames = ("id", "created_at", "case_id", "username", "action", "detail")

    def add(self, *, case_id: str, action: str, username: str = "",
            detail: str = "") -> Dict[str, Any]:
        return self.append(case_id=case_id, username=username, action=action, detail=detail)

    def list(self, case_id: str = "") -> List[Dict[str, str]]:
        rows = [r for r in self.all() if not case_id or r.get("case_id") == case_id]
        rows.sort(key=lambda r: int(r.get("id", 0) or 0), reverse=True)
        return rows

    def delete_case(self, case_id: str) -> int:
        with self._lock:
            rows = self._read()
            keep = [r for r in rows if r.get("case_id") != case_id]
            removed = len(rows) - len(keep)
            if removed:
                self._write(keep)
            return removed


# ------------------------------------------------------------- singletons

jobs = Jobs()
notifications = Notifications()
activity = ActivityLogStore()
case_meta = CaseMetaStore()
case_history = CaseHistoryStore()

ALL_COLLECTIONS = (jobs, notifications, activity, case_meta, case_history)


def clear_all() -> None:
    """Wipe every platform record (used by the testing reset)."""
    for collection in ALL_COLLECTIONS:
        collection.clear()


def delete_case_everywhere(case_id: str) -> Dict[str, int]:
    """Remove all platform records belonging to one case."""
    return {
        "jobs": jobs.delete_case(case_id),
        "notifications": notifications.delete_case(case_id),
        "case_meta": int(case_meta.delete_case(case_id)),
        "case_history": case_history.delete_case(case_id),
    }
