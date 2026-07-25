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


# --------------------------------------------------------------------------- #
# Single-case deletion (admin action)
# --------------------------------------------------------------------------- #


def _filter_csv_rows(path: Path, predicate) -> int:
    """Rewrite a CSV keeping only rows where ``predicate(row)`` is True.

    Returns the number of removed rows. No-op when the file is absent.
    """
    if not path.is_file():
        return 0
    try:
        with open(path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
        keep = [r for r in rows if predicate(r)]
        removed = len(rows) - len(keep)
        if removed:
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(keep)
            tmp.replace(path)
        return removed
    except OSError as exc:  # noqa: BLE001
        log.warning("could not filter %s: %s", path, exc)
        return 0


def linked_case_ids(
    investigation_config: InvestigationConfig, case_id: str
) -> List[str]:
    """Cases currently cross-linked to ``case_id`` (read before deletion).

    These are the cases whose cross-case artifacts and reports must be
    regenerated once ``case_id`` disappears, so no report keeps citing a case
    that no longer exists.
    """
    from .repository import InvestigationReportRepository

    repo = InvestigationReportRepository(investigation_config)
    document = repo.load_latest(case_id, investigation_config.cross_case_report_name)
    if not document:
        return []
    related = (document.get("report") or {}).get("related_case_ids") or []
    return [str(c) for c in related]


def delete_case(
    evidence_config: EvidenceConfig,
    investigation_config: InvestigationConfig,
    case_id: str,
) -> Dict[str, object]:
    """Purge one case from every store the engine owns.

    Removes its rows from the case registry and the evidence/entity/OCR/
    processing CSVs, deletes its OCR JSON, uploaded originals, Phase-1 forensic
    reports and all Phase-2 artifacts, and drops its entries from the persistent
    cross-case entity index.

    The caller is responsible for re-analysing the cases returned by
    :func:`linked_case_ids` (see ``api.engine.delete_case_cascade``), so their
    correlation/timeline/graph/report artifacts stop referencing this case.
    """
    storage = evidence_config.storage_dir.resolve()

    def _guard(path: Path) -> bool:
        try:
            path.resolve().relative_to(storage)
            return True
        except ValueError:
            log.error("refusing to touch path outside storage: %s", path)
            return False

    # 1. Which evidence belonged to this case (needed to delete originals)?
    evidence_ids: List[str] = []
    stored_files: List[str] = []
    if evidence_config.evidence_csv.is_file():
        with open(evidence_config.evidence_csv, "r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("case_id") == case_id:
                    if row.get("evidence_id"):
                        evidence_ids.append(row["evidence_id"])
                    if row.get("stored_file_name"):
                        stored_files.append(row["stored_file_name"])

    # 2. CSV rows keyed by case_id.
    removed_rows: Dict[str, int] = {}
    for path in (
        evidence_config.cases_csv,
        evidence_config.case_registry_csv,
        evidence_config.evidence_csv,
        evidence_config.processing_log_csv,
        investigation_config.entities_csv,
        investigation_config.audit_csv,
    ):
        if _guard(path):
            removed_rows[path.name] = _filter_csv_rows(
                path, lambda r: r.get("case_id") != case_id
            )

    # OCR results are keyed by evidence, not case.
    if _guard(evidence_config.ocr_results_csv) and evidence_ids:
        removed_rows[evidence_config.ocr_results_csv.name] = _filter_csv_rows(
            evidence_config.ocr_results_csv,
            lambda r: r.get("evidence_id") not in set(evidence_ids),
        )

    # 3. Per-case files and directories.
    deleted_paths: List[str] = []
    case_json = evidence_config.json_dir / f"{case_id}.json"
    if _guard(case_json) and case_json.is_file():
        case_json.unlink()
        deleted_paths.append(case_json.name)

    for stored in stored_files:
        original = evidence_config.originals_dir / stored
        if _guard(original) and original.is_file():
            original.unlink()
            deleted_paths.append(original.name)

    for evidence_id in evidence_ids:
        forensic_dir = investigation_config.forensics_dir / evidence_id
        if _guard(forensic_dir) and forensic_dir.is_dir():
            shutil.rmtree(forensic_dir, ignore_errors=True)
            deleted_paths.append(f"forensics/{evidence_id}")

    case_dir = investigation_config.case_dir(case_id)
    if _guard(case_dir) and case_dir.is_dir():
        shutil.rmtree(case_dir, ignore_errors=True)
        deleted_paths.append(f"investigation/{case_id}")

    # 4. Cross-case entity index.
    from .crosscase import CrossCaseEntityIndex

    index = CrossCaseEntityIndex(investigation_config.cross_case_index_path)
    index_changed = index.remove_case(case_id)
    if index_changed:
        index.save()

    summary = {
        "case_id": case_id,
        "evidence_removed": len(evidence_ids),
        "csv_rows_removed": removed_rows,
        "paths_deleted": deleted_paths,
        "cross_case_index_updated": index_changed,
    }
    log.info("deleted case %s: %s", case_id, summary)
    return summary
