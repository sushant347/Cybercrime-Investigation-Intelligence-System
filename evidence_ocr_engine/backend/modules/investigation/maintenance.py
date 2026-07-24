"""Engine storage reset - a testing convenience, not a production feature.

``reset_all`` wipes every case and every extracted entity so a fresh test run
starts from an empty engine: the case registry, evidence/entity/OCR CSVs, the
per-case OCR JSON, stored originals, Phase-1 forensic reports, all Phase-2
investigation artifacts, and the persistent cross-case entity index.

It is intentionally conservative: it only ever touches paths **inside** the
engine's own storage directory, truncates CSVs back to their header rather than
deleting them, and never raises on a missing path.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Dict, List

from ..evidence.config import EvidenceConfig
from ..evidence.logger import get_logger
from .config import InvestigationConfig

log = get_logger("investigation.maintenance")


def _truncate_csv_to_header(path: Path) -> bool:
    """Keep only the header row of a CSV (no-op if absent). True if it existed."""
    if not path.is_file():
        return False
    try:
        with open(path, "r", newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), None)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            if header:
                csv.writer(handle).writerow(header)
    except OSError as exc:  # noqa: BLE001
        log.warning("could not truncate %s: %s", path, exc)
    return True


def _empty_dir(path: Path) -> int:
    """Delete every child of a directory, keeping the directory. Returns count."""
    if not path.is_dir():
        return 0
    removed = 0
    for child in path.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed += 1
        except OSError as exc:  # noqa: BLE001
            log.warning("could not remove %s: %s", child, exc)
    return removed


def reset_all(
    evidence_config: EvidenceConfig,
    investigation_config: InvestigationConfig,
) -> Dict[str, object]:
    """Clear all cases and entities from engine storage. Returns a summary."""
    storage = evidence_config.storage_dir.resolve()

    def _guard(path: Path) -> bool:
        """Only ever act on paths inside the engine storage directory."""
        try:
            path.resolve().relative_to(storage)
            return True
        except ValueError:
            log.error("refusing to reset path outside storage: %s", path)
            return False

    cleared_csvs: List[str] = []
    for path in (
        evidence_config.cases_csv,
        evidence_config.case_registry_csv,
        evidence_config.evidence_csv,
        evidence_config.ocr_results_csv,
        evidence_config.processing_log_csv,
        investigation_config.entities_csv,
    ):
        if _guard(path) and _truncate_csv_to_header(path):
            cleared_csvs.append(path.name)

    emptied_dirs: Dict[str, int] = {}
    for path in (
        evidence_config.json_dir,
        evidence_config.originals_dir,
        investigation_config.forensics_dir,
    ):
        if _guard(path):
            emptied_dirs[path.name] = _empty_dir(path)

    # Investigation artifacts: remove per-case directories, the audit log, and
    # the cross-case index, but keep the investigation directory itself.
    investigation_removed = 0
    if _guard(investigation_config.investigation_dir):
        for child in investigation_config.investigation_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                investigation_removed += 1
        for path in (investigation_config.audit_csv,
                     investigation_config.cross_case_index_path):
            if path.is_file():
                try:
                    path.unlink()
                except OSError as exc:  # noqa: BLE001
                    log.warning("could not remove %s: %s", path, exc)

    summary = {
        "cleared_csvs": cleared_csvs,
        "emptied_dirs": emptied_dirs,
        "investigation_case_dirs_removed": investigation_removed,
    }
    log.info("engine storage reset: %s", summary)
    return summary
