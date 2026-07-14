"""Versioned case-level JSON repository for all Phase-2 outputs.

Never overwrites: re-analysis produces ``<name>_v2.json``, ``<name>_v3.json``…
Writes are atomic (temp file + rename). Also supports versioned text
artefacts (the Module-7 Markdown report) with identical semantics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence.logger import get_logger
from ..evidence.utils import StorageError, utc_now_iso
from .config import InvestigationConfig

_VERSION_RE = re.compile(r"_v(\d+)$")


class InvestigationReportRepository:
    """One JSON document per (case, report type, version)."""

    def __init__(self, config: InvestigationConfig) -> None:
        self._cfg = config
        self._log = get_logger("investigation.repository")
        config.ensure_directories()

    # ------------------------------------------------------------------ write

    def save(self, case_id: str, report_name: str, payload: Dict[str, Any]) -> Path:
        """Persist a report as a new, never-overwriting version."""
        directory = self._cfg.case_dir(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        version = self._next_version(case_id, report_name, ".json")
        name = report_name if version == 1 else f"{report_name}_v{version}"
        path = directory / f"{name}.json"
        document = {
            "report_type": report_name,
            "report_version": version,
            "schema_version": self._cfg.report_schema_version,
            "case_id": case_id,
            "generated_at": utc_now_iso(),
            "report": payload,
        }
        self._atomic_write_json(path, document)
        self._log.info("saved %s v%d for %s", report_name, version, case_id)
        return path

    def save_text(self, case_id: str, report_name: str, text: str,
                  suffix: str = ".md") -> Path:
        """Persist a text artefact with the same versioning semantics."""
        directory = self._cfg.case_dir(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        version = self._next_version(case_id, report_name, suffix)
        name = report_name if version == 1 else f"{report_name}_v{version}"
        path = directory / f"{name}{suffix}"
        tmp = path.with_suffix(suffix + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write report '{path}': {exc}") from exc
        return path

    # ------------------------------------------------------------------- read

    def load_latest(self, case_id: str, report_name: str) -> Optional[Dict[str, Any]]:
        versions = self.list_versions(case_id, report_name, ".json")
        if not versions:
            return None
        try:
            with open(versions[-1], "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot read report '{versions[-1]}': {exc}") from exc

    def list_versions(self, case_id: str, report_name: str,
                      suffix: str = ".json") -> List[Path]:
        """All stored versions of one report, oldest first."""
        directory = self._cfg.case_dir(case_id)
        if not directory.is_dir():
            return []
        found: List[tuple[int, Path]] = []
        for path in directory.glob(f"{report_name}*{suffix}"):
            stem = path.name[: -len(suffix)]
            if stem == report_name:
                found.append((1, path))
            else:
                match = _VERSION_RE.search(stem)
                if match and stem == f"{report_name}_v{match.group(1)}":
                    found.append((int(match.group(1)), path))
        return [path for _, path in sorted(found)]

    # ---------------------------------------------------------------- internal

    def _next_version(self, case_id: str, report_name: str, suffix: str) -> int:
        existing = self.list_versions(case_id, report_name, suffix)
        if not existing:
            return 1
        stem = existing[-1].name[: -len(suffix)]
        match = _VERSION_RE.search(stem)
        return (int(match.group(1)) if match else 1) + 1

    @staticmethod
    def _atomic_write_json(path: Path, document: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2, default=str)
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write report '{path}': {exc}") from exc
