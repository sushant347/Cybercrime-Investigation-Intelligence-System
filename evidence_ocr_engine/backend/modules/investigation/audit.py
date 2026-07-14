"""Case-level audit trail for every Phase-2 module.

Appends to ``storage/investigation/investigation_audit_log.csv`` - the legacy
``processing_log.csv`` and Phase-1 ``forensics_audit_log.csv`` are untouched.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from ..evidence.logger import get_logger
from ..evidence.utils import StorageError, utc_now_iso
from .config import InvestigationConfig


class InvestigationAuditTrail:
    """Append-only CSV audit log shared by all Phase-2 services."""

    fieldnames: Sequence[str] = (
        "timestamp", "case_id", "module", "action", "level", "message", "duration_ms",
    )

    def __init__(self, config: InvestigationConfig) -> None:
        self._path: Path = config.audit_csv
        self._log = get_logger("investigation.audit")
        self._ensure_file()

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        case_id: str,
        module: str,
        action: str,
        message: str = "",
        *,
        level: str = "INFO",
        duration_ms: float = 0.0,
    ) -> None:
        """Append one audit entry; audit failure never breaks an analysis."""
        row = {
            "timestamp": utc_now_iso(),
            "case_id": case_id,
            "module": module,
            "action": action,
            "level": level,
            "message": message,
            "duration_ms": f"{duration_ms:.1f}",
        }
        try:
            with open(self._path, "a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=list(self.fieldnames)).writerow(row)
        except OSError as exc:  # pragma: no cover - disk failure path
            self._log.error("audit write failed (%s): %s", self._path, exc)
        self._log.log(
            {"INFO": 20, "WARNING": 30, "ERROR": 40}.get(level, 20),
            "[%s] %s %s: %s", module, case_id, action, message,
        )

    def _ensure_file(self) -> None:
        if self._path.exists():
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=list(self.fieldnames)).writeheader()
        except OSError as exc:
            raise StorageError(f"Cannot create audit log '{self._path}': {exc}") from exc
