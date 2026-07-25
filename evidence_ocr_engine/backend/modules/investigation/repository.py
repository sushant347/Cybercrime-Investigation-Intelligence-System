"""Case-level JSON repository for all Phase-2 outputs.

**One file per (case, report type).** Re-analysis replaces the stored artifact
instead of accumulating ``<name>_v2.json``, ``<name>_v3.json``… A monotonic
``report_version`` counter is still carried *inside* the document, so a report
can say which analysis run produced it even though only the latest is kept.

Trade-off, recorded deliberately: superseded reports are no longer retained, so
a report can no longer be compared against the exact artifact of an earlier
run. Provenance within a single run is unaffected - each report still hashes
the artifacts it was built from.

Writes stay atomic (temp file + rename), so an interrupted run can never leave
a half-written report in place of a good one. Text (Markdown) and binary (PDF)
artefacts follow the same rules.
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
        """Persist a report, replacing any previously stored one."""
        directory = self._cfg.case_dir(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        version = self._next_version(case_id, report_name, ".json")
        path = directory / f"{report_name}.json"
        document = {
            "report_type": report_name,
            "report_version": version,
            "schema_version": self._cfg.report_schema_version,
            "case_id": case_id,
            "generated_at": utc_now_iso(),
            "report": payload,
        }
        self._atomic_write_json(path, document)
        self._discard_superseded(case_id, report_name, ".json", path)
        self._log.info("saved %s v%d for %s", report_name, version, case_id)
        return path

    def save_text(self, case_id: str, report_name: str, text: str,
                  suffix: str = ".md") -> Path:
        """Persist a text artefact, replacing any previously stored one."""
        directory = self._cfg.case_dir(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{report_name}{suffix}"
        tmp = path.with_suffix(suffix + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write report '{path}': {exc}") from exc
        self._discard_superseded(case_id, report_name, suffix, path)
        return path

    def save_binary(self, case_id: str, report_name: str, payload: bytes,
                    suffix: str = ".pdf") -> Path:
        """Persist a binary artefact (e.g. the PDF report twin), replacing any
        previously stored one. Writes stay atomic."""
        directory = self._cfg.case_dir(case_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{report_name}{suffix}"
        tmp = path.with_suffix(suffix + ".tmp")
        try:
            tmp.write_bytes(payload)
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write report '{path}': {exc}") from exc
        self._discard_superseded(case_id, report_name, suffix, path)
        self._log.info("saved %s (%s) for %s", report_name, suffix, case_id)
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
        """Generation counter for the *next* save.

        Only one file is kept, so the counter is read from the stored document
        rather than from file names - otherwise every re-analysis would reset
        it to 1 and the report could not say which run produced it. Falls back
        to the highest ``_vN`` file name so counters carry over from artifacts
        written before single-file storage.
        """
        existing = self.list_versions(case_id, report_name, suffix)
        if not existing:
            return 1
        highest = 0
        for path in existing:
            stem = path.name[: -len(suffix)]
            match = _VERSION_RE.search(stem)
            highest = max(highest, int(match.group(1)) if match else 1)
        if suffix == ".json":
            try:
                with open(existing[-1], "r", encoding="utf-8") as handle:
                    stored = int(json.load(handle).get("report_version", 0) or 0)
                highest = max(highest, stored)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass  # unreadable/old artifact: the file-name count still applies
        return highest + 1

    def _discard_superseded(self, case_id: str, report_name: str, suffix: str,
                            keep: Path) -> None:
        """Remove older ``_vN`` artifacts once the single file is written.

        Runs *after* the atomic write, so a failed save leaves the previous
        report intact. Only files this repository itself named are touched.
        """
        for path in self.list_versions(case_id, report_name, suffix):
            if path == keep:
                continue
            try:
                path.unlink()
            except OSError as exc:  # noqa: BLE001 - cleanup must not fail a save
                self._log.warning("could not remove superseded %s: %s", path, exc)

    @staticmethod
    def _atomic_write_json(path: Path, document: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2, default=str)
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write report '{path}': {exc}") from exc
