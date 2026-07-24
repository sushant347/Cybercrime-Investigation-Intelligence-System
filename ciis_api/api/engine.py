"""Read-only bridge to the completed Phase 1/2 forensic engines.

This module is the ONLY place the platform touches the engine. It imports
the engine packages from ``settings.ENGINE_ROOT`` and exposes:

* CSV/JSON storage readers (cases, evidence, OCR results, forensics)
* Phase-2 artifact loaders (``storage/investigation/<CASE_ID>/*.json``)
* Background execution of engine work (evidence processing, case analysis)

No forensic logic lives here - only orchestration and data access.
"""
from __future__ import annotations

import csv
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Optional

from django.conf import settings
from django.utils import timezone

from .exceptions import EngineUnavailable

log = logging.getLogger("ciis.engine")

# --------------------------------------------------------------------- import
if str(settings.ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(settings.ENGINE_ROOT))

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from backend.modules.investigation.config import InvestigationConfig  # noqa: E402
from backend.modules.investigation.repository import (  # noqa: E402
    InvestigationReportRepository,
)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ciis-engine")
_pipeline_lock = threading.Lock()


@lru_cache(maxsize=1)
def evidence_config() -> EvidenceConfig:
    return EvidenceConfig.from_env()


@lru_cache(maxsize=1)
def investigation_config() -> InvestigationConfig:
    return InvestigationConfig.from_env(evidence_config())


@lru_cache(maxsize=1)
def report_repository() -> InvestigationReportRepository:
    return InvestigationReportRepository(investigation_config())


@lru_cache(maxsize=1)
def case_registry():
    """CSV registry mapping a case reference to its hashed case id."""
    from backend.modules.evidence.case_registry import CaseRegistry

    return CaseRegistry(evidence_config())


# ----------------------------------------------------------------- CSV access
def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def list_cases() -> list[dict[str, str]]:
    return _read_csv(evidence_config().cases_csv)


def get_case(case_id: str) -> Optional[dict[str, str]]:
    return next((c for c in list_cases() if c.get("case_id") == case_id), None)


def list_evidence(case_id: str | None = None) -> list[dict[str, str]]:
    rows = _read_csv(evidence_config().evidence_csv)
    return [r for r in rows if case_id is None or r.get("case_id") == case_id]


def get_evidence(evidence_id: str) -> Optional[dict[str, str]]:
    rows = _read_csv(evidence_config().evidence_csv)
    return next((r for r in rows if r.get("evidence_id") == evidence_id), None)


def processing_log(case_id: str | None = None) -> list[dict[str, str]]:
    rows = _read_csv(evidence_config().processing_log_csv)
    return [r for r in rows if case_id is None or r.get("case_id") == case_id]


def investigation_audit(case_id: str | None = None) -> list[dict[str, str]]:
    path = investigation_config().investigation_dir / investigation_config().audit_csv_name
    rows = _read_csv(path)
    return [r for r in rows if case_id is None or r.get("case_id") == case_id]


# ---------------------------------------------------------------- JSON access
def load_case_json(case_id: str) -> Optional[dict[str, Any]]:
    """Full Phase-1 OCR document for a case (pages, lines, confidences)."""
    from backend.modules.evidence.json_storage import JSONCaseStorage

    return JSONCaseStorage(evidence_config()).load_case(case_id)


def evidence_ocr(case_id: str, evidence_id: str) -> Optional[dict[str, Any]]:
    doc = load_case_json(case_id) or {}
    return next(
        (e for e in doc.get("evidence", []) if e.get("evidence_id") == evidence_id),
        None,
    )


def original_path(evidence_row: dict[str, str]) -> Path:
    return evidence_config().originals_dir / evidence_row["stored_file_name"]


# --------------------------------------------------------- Phase-2 artifacts
#: report_name -> API artifact key (Phase-2 storage spec, config.py docstring)
ARTIFACTS: dict[str, str] = {
    "correlation": "correlation_analysis",
    "graph": "graph",
    "graph_statistics": "graph_statistics",
    "graph_summary": "graph_summary",
    "campaigns": "campaign_analysis",
    "suspects": "suspect_assessment",
    "timeline": "timeline_analysis",
    "analytics": "analytics",
    "case_statistics": "case_statistics",
    "entity_statistics": "entity_statistics",
    "report": "investigation_report",
    "priority": "case_priority",
}


def load_artifact(case_id: str, key: str) -> dict[str, Any]:
    """Latest version of one Phase-2 artifact; 503 if not generated yet."""
    name = ARTIFACTS.get(key)
    if name is None:
        raise EngineUnavailable(f"Unknown artifact '{key}'.")
    document = report_repository().load_latest(case_id, name)
    if document is None:
        raise EngineUnavailable(
            f"Artifact '{key}' has not been generated for {case_id}. "
            "Run the investigation analysis first."
        )
    return document


def try_artifact(case_id: str, key: str) -> Optional[dict[str, Any]]:
    try:
        return load_artifact(case_id, key)
    except EngineUnavailable:
        return None


def report_versions(case_id: str, suffix: str = ".json") -> list[Path]:
    return report_repository().list_versions(case_id, "investigation_report", suffix)


def forensics_artifacts(case_id: str, evidence_id: str) -> dict[str, Any]:
    """Phase-1 forensic artifacts (forgery, metadata, logo, integrity, score).

    The forensics pipeline stores per-evidence JSON under
    ``storage/forensics/``; every file mentioning the evidence id is returned
    keyed by its stem so the UI can display all generated artifacts.
    """
    root = investigation_config().forensics_dir
    found: dict[str, Any] = {}
    if not root.is_dir():
        return found
    import json

    for path in sorted(root.rglob("*.json")):
        if evidence_id in path.name or evidence_id in str(path.parent):
            try:
                found[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return found


# ------------------------------------------------------------ engine actions
def create_case(title: str, notes: str = "", case_id: str | None = None) -> dict[str, str]:
    from backend.modules.evidence.csv_storage import CaseRepository

    record = CaseRepository(evidence_config()).create(
        title=title, notes=notes, case_id=case_id
    )
    return {
        "case_id": record.case_id,
        "created_at": record.created_at,
        "title": record.title,
        "investigator_notes": record.investigator_notes,
        "evidence_count": str(record.evidence_count),
    }


def intake_case(reference: str, title: str = "") -> tuple[dict[str, str], bool]:
    """Resolve a case reference to a case, creating it on first use.

    Returns ``(registry_record, created)``. The same reference always yields
    the same case id, so an investigator returns to their evidence and
    reports by typing the reference again - no account needed.
    """
    with _pipeline_lock:  # engine CSV storage is not concurrent-safe
        record, created = case_registry().resolve_or_create(reference, title)
        # Reconcile: the registry is the index, cases.csv is the engine's own
        # case list. Create the engine case if it is missing (first use, or a
        # registry entry whose case row was removed).
        if get_case(record["case_id"]) is None:
            create_case(
                title=record.get("title", ""),
                notes="",
                case_id=record["case_id"],
            )
    return record, created


@lru_cache(maxsize=1)
def _evidence_pipeline():
    """Phase-1 pipeline with the production OCR engine (heavy: lazy)."""
    from backend.modules.evidence.paddle_service import PaddleOCRService
    from backend.modules.evidence.pipeline import EvidencePipeline

    cfg = evidence_config()
    return EvidencePipeline(cfg, PaddleOCRService(cfg, lang=cfg.ocr_lang))


def submit_evidence_job(job_id: int, tmp_path: str, case_id: str,
                        notes: str, username: str) -> None:
    """Queue Phase-1 processing of an uploaded file (runs in a worker)."""

    def work() -> None:
        from .models import BackgroundJob, Notification, NotificationType

        job = BackgroundJob.objects.get(pk=job_id)
        job.status = "running"
        job.save(update_fields=["status"])
        try:
            with _pipeline_lock:  # engine CSV storage is not concurrent-safe
                result = _evidence_pipeline().process_file(
                    tmp_path, case_id=case_id, notes=notes
                )
            job.status = "completed"
            job.evidence_id = result.evidence_id
            job.detail = f"Processed as {result.evidence_id}"
            Notification.broadcast(
                type=NotificationType.PROCESSING_COMPLETE,
                title=f"Evidence {result.evidence_id} processed",
                message=f"{result.file_name} processed for {case_id}.",
                case_id=case_id, evidence_id=result.evidence_id,
            )
        except Exception as exc:  # noqa: BLE001 - report, never crash worker
            log.exception("Evidence processing failed (job %s)", job_id)
            job.status = "failed"
            job.error = str(exc)
            Notification.broadcast(
                type=NotificationType.SYSTEM_ERROR,
                title="Evidence processing failed",
                message=str(exc), case_id=case_id,
            )
        finally:
            job.finished_at = timezone.now()
            job.save()
            Path(tmp_path).unlink(missing_ok=True)

    _executor.submit(work)


def submit_analysis_job(job_id: int, case_id: str, username: str) -> None:
    """Queue the full Phase-2 pipeline for a case (runs in a worker)."""

    def work() -> None:
        from .models import BackgroundJob, Notification, NotificationType

        job = BackgroundJob.objects.get(pk=job_id)
        job.status = "running"
        job.save(update_fields=["status"])
        try:
            from backend.modules.investigation.pipeline import build_default_pipeline

            with _pipeline_lock:
                results = build_default_pipeline().analyze_case(case_id)
            failures = results.get("failures") or []
            job.status = "completed"
            job.detail = f"failures={failures or 'none'}"
            Notification.broadcast(
                type=NotificationType.REPORT_GENERATED,
                title=f"Investigation analysis completed for {case_id}",
                message="All Phase-2 artifacts regenerated.", case_id=case_id,
            )
            _emit_priority_notification(case_id)
        except Exception as exc:  # noqa: BLE001
            log.exception("Case analysis failed (job %s)", job_id)
            job.status = "failed"
            job.error = str(exc)
            Notification.broadcast(
                type=NotificationType.SYSTEM_ERROR,
                title=f"Analysis failed for {case_id}",
                message=str(exc), case_id=case_id,
            )
        finally:
            job.finished_at = timezone.now()
            job.save()

    _executor.submit(work)


def _emit_priority_notification(case_id: str) -> None:
    """High-priority alert sourced from the engine's own priority verdict."""
    from .models import Notification, NotificationType

    document = try_artifact(case_id, "priority")
    if not document:
        return
    payload = document.get("report", document)
    band = str(
        payload.get("priority_band")
        or payload.get("band")
        or payload.get("priority_level")
        or ""
    ).lower()
    if band in {"high", "critical", "urgent"}:
        score = payload.get("priority_score") or payload.get("score")
        Notification.broadcast(
            type=NotificationType.HIGH_PRIORITY,
            title=f"{case_id} flagged {band.upper()} priority",
            message=f"Engine priority score: {score}.", case_id=case_id,
        )


# ------------------------------------------------------------------- helpers
def engine_health() -> dict[str, Any]:
    cfg = evidence_config()
    return {
        "engine_root": str(settings.ENGINE_ROOT),
        "storage_ok": cfg.storage_dir.is_dir(),
        "cases_csv": cfg.cases_csv.is_file(),
        "evidence_csv": cfg.evidence_csv.is_file(),
        "investigation_dir": investigation_config().investigation_dir.is_dir(),
    }


def iter_case_artifact(case_ids: list[str], key: str) -> Iterator[tuple[str, dict]]:
    for cid in case_ids:
        doc = try_artifact(cid, key)
        if doc is not None:
            yield cid, doc.get("report", doc)
