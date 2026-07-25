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
import json
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
    """Cases whose stored artifacts reference ``case_id`` (read before deletion).

    These are the cases that must be regenerated once ``case_id`` disappears,
    so no surviving artifact keeps citing a case that no longer exists.

    The obvious implementation - read the doomed case's own cross-case report
    and trust its ``related_case_ids`` - is not sufficient, and was the reason
    deleted cases kept showing up elsewhere:

    * that list is a **snapshot** taken when the doomed case was last analysed,
      so a case that linked to it *afterwards* is missing from it;
    * a case that was never analysed has no cross-case artifact at all, so the
      list is empty and nothing gets refreshed;
    * links are recorded per-case, so the relation is not symmetric on disk
      even when it is symmetric in fact.

    Instead this scans every case's stored cross-case and graph artifacts for
    an actual reference to ``case_id``. That is authoritative by construction:
    a case is refreshed precisely when something it stores names the case being
    deleted. Only the latest version of each artifact is inspected - older
    versions are immutable history and are deliberately left alone.
    """
    from .repository import InvestigationReportRepository

    repo = InvestigationReportRepository(investigation_config)
    linked: List[str] = []

    # Start from the doomed case's own view (cheap, and covers the common case
    # where the other side has not been re-analysed since the link formed).
    document = repo.load_latest(case_id, investigation_config.cross_case_report_name)
    if document:
        for other in (document.get("report") or {}).get("related_case_ids") or []:
            if str(other) != case_id:
                linked.append(str(other))

    # Then the authoritative sweep: who actually stores a reference to us?
    root = investigation_config.case_dir(case_id).parent
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            other = entry.name
            if not entry.is_dir() or other == case_id or other in linked:
                continue
            for report_name in (investigation_config.cross_case_report_name,
                                investigation_config.graph_report_name):
                try:
                    stored = repo.load_latest(other, report_name)
                except Exception:  # noqa: BLE001 - a corrupt artifact is not fatal
                    log.warning("could not read %s/%s while scanning for links",
                                other, report_name)
                    continue
                if stored and case_id in json.dumps(stored):
                    linked.append(other)
                    break
    return linked


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

    # Sweep any entity rows left behind by an *earlier* delete that did not
    # finish (or by storage edited outside the engine). Cross-case correlation
    # reads entities.csv directly, so an orphan row here keeps a long-gone case
    # alive in every other case's correlation, graph and report. Rows are only
    # dropped when their case has no evidence at all - a live case is untouched.
    if _guard(investigation_config.entities_csv):
        live_cases = set()
        if evidence_config.evidence_csv.is_file():
            with open(evidence_config.evidence_csv, "r", newline="",
                      encoding="utf-8") as handle:
                live_cases = {(r.get("case_id") or "").strip()
                              for r in csv.DictReader(handle)}
        orphans = _filter_csv_rows(
            investigation_config.entities_csv,
            lambda r: (r.get("case_id") or "").strip() in live_cases,
        )
        if orphans:
            log.warning("purged %d orphaned entity row(s) while deleting %s",
                        orphans, case_id)
            removed_rows["entities.csv (orphans)"] = orphans

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

    index = CrossCaseEntityIndex(
        investigation_config.entities_csv,
        legacy_index_path=investigation_config.cross_case_index_path,
        evidence_csv=investigation_config.evidence_csv,
    )
    # The case's rows were already removed from entities.csv above, so this
    # just invalidates the cached view (the single file is the only store).
    index_changed = index.remove_case(case_id)

    summary = {
        "case_id": case_id,
        "evidence_removed": len(evidence_ids),
        "csv_rows_removed": removed_rows,
        "paths_deleted": deleted_paths,
        "cross_case_index_updated": index_changed,
    }
    log.info("deleted case %s: %s", case_id, summary)
    return summary
