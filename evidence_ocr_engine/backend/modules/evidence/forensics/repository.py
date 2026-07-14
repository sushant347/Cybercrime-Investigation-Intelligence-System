"""Versioned JSON report repository for all Phase-1 modules.

Storage rule of the Phase-1 spec: *"Every new output must be stored
separately without replacing previous outputs."* This repository therefore
never overwrites: re-running an analysis produces ``<name>_v2.json``,
``<name>_v3.json``, ... while the newest version is discoverable via
:meth:`load_latest`.

Layout::

    storage/forensics/<EVIDENCE_ID>/quality_report.json
    storage/forensics/<EVIDENCE_ID>/quality_report_v2.json
    ...

Writes are atomic (temp file + rename), mirroring the guarantees of the
existing :class:`~..json_storage.JSONCaseStorage`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logger import get_logger
from ..utils import StorageError, utc_now_iso
from .config import ForensicsConfig

_VERSION_RE = re.compile(r"_v(\d+)$")


class ForensicReportRepository:
    """Stores one JSON document per (evidence, report type, version)."""

    def __init__(self, config: ForensicsConfig) -> None:
        self._cfg = config
        self._log = get_logger("forensics.repository")
        config.ensure_directories()

    # ------------------------------------------------------------------ write

    def save(
        self,
        evidence_id: str,
        case_id: str,
        report_name: str,
        payload: Dict[str, Any],
    ) -> Path:
        """Persist a report as a new, never-overwriting version.

        A standard envelope (evidence/case ids, timestamp, schema version,
        report version) is added around the payload.

        Returns:
            Path of the JSON file written.
        """
        directory = self._cfg.evidence_dir(evidence_id)
        directory.mkdir(parents=True, exist_ok=True)
        version = self._next_version(directory, report_name)
        name = report_name if version == 1 else f"{report_name}_v{version}"
        path = directory / f"{name}.json"

        document = {
            "report_type": report_name,
            "report_version": version,
            "schema_version": self._cfg.report_schema_version,
            "evidence_id": evidence_id,
            "case_id": case_id,
            "generated_at": utc_now_iso(),
            "report": payload,
        }
        self._atomic_write(path, document)
        self._log.info("saved %s v%d for %s", report_name, version, evidence_id)
        return path

    # ------------------------------------------------------------------- read

    def load_latest(self, evidence_id: str, report_name: str) -> Optional[Dict[str, Any]]:
        """Return the newest version of a report, or ``None`` if absent."""
        versions = self.list_versions(evidence_id, report_name)
        if not versions:
            return None
        return self._read(versions[-1])

    def list_versions(self, evidence_id: str, report_name: str) -> List[Path]:
        """All stored versions of a report, oldest first."""
        directory = self._cfg.evidence_dir(evidence_id)
        if not directory.is_dir():
            return []
        found: List[tuple[int, Path]] = []
        for path in directory.glob(f"{report_name}*.json"):
            stem = path.stem
            if stem == report_name:
                found.append((1, path))
            else:
                match = _VERSION_RE.search(stem)
                if match and stem == f"{report_name}_v{match.group(1)}":
                    found.append((int(match.group(1)), path))
        return [path for _, path in sorted(found)]

    # ---------------------------------------------------------------- internal

    def _next_version(self, directory: Path, report_name: str) -> int:
        existing = self.list_versions(directory.name, report_name) \
            if directory.name else []
        # list_versions derives the directory from evidence_id == directory.name
        if not existing:
            return 1
        last = existing[-1].stem
        match = _VERSION_RE.search(last)
        return (int(match.group(1)) if match else 1) + 1

    def _read(self, path: Path) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot read forensic report '{path}': {exc}") from exc

    @staticmethod
    def _atomic_write(path: Path, document: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2, default=str)
            tmp_path.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write forensic report '{path}': {exc}") from exc
