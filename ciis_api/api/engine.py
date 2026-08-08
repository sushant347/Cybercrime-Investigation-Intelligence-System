"""Read-only bridge to the forensic engines.

This module is the ONLY place the platform touches the engines. It imports
them from the three engine roots in settings (OCR, correlation, timeline+report)
and exposes:

* CSV/JSON storage readers (cases, evidence, OCR results, forensics)
* Phase-2 artifact loaders (``storage/investigation/<CASE_ID>/*.json``)
* Background execution of engine work (evidence processing, case analysis)

No forensic logic lives here - only orchestration and data access.
"""
from __future__ import annotations

import csv
import importlib.metadata
import importlib.util
import logging
import platform
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Optional

from django.conf import settings

from .exceptions import EngineUnavailable

log = logging.getLogger("ciis.engine")

# --------------------------------------------------------------------- import
# All three engine roots go on the path before any of them is imported. Each
# engine also bootstraps the one upstream of it, so order here is not
# load-bearing - but listing them in pipeline order matches the data flow.
for _root in (settings.ENGINE_ROOT, settings.CORRELATION_ROOT,
              settings.TIMELINE_REPORT_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from backend.modules.evidence.hash_service import HashService  # noqa: E402
from ciis_correlation.core.config import InvestigationConfig  # noqa: E402
from ciis_correlation.core.repository import (  # noqa: E402
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
#
# The register CSVs (cases, evidence, processing log) are read on essentially
# every request the platform serves — the case header alone triggers three of
# them — and each read re-parsed the whole file from disk. An mtime-keyed
# cache makes repeat reads free while staying exactly as fresh as the file:
# every engine write goes through the filesystem, so a change always bumps
# mtime and invalidates the entry. Entries are copied out so a caller mutating
# a row (several views decorate rows in place) cannot poison the cache.
_csv_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
_csv_cache_lock = threading.Lock()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    key = str(path)
    mtime = path.stat().st_mtime
    with _csv_cache_lock:
        cached = _csv_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return [dict(r) for r in cached[1]]
    with open(path, "r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with _csv_cache_lock:
        _csv_cache[key] = (mtime, rows)
    return [dict(r) for r in rows]


def list_cases() -> list[dict[str, str]]:
    return _read_csv(evidence_config().cases_csv)


def get_case(case_id: str) -> Optional[dict[str, str]]:
    return next((c for c in list_cases() if c.get("case_id") == case_id), None)


#: How far an evidence row has progressed. Used to pick the surviving row when
#: the register briefly holds more than one row for the same id.
_EVIDENCE_STATUS_RANK = {"processed": 3, "failed": 2, "uploaded": 1}


def _collapse_evidence_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return one row per evidence id, keeping the most-progressed one.

    The chain-of-custody register is append-then-rewrite, so an interleaved
    write can leave a stale ``uploaded`` row (empty ``sha256_after``,
    ``hash_verified`` unset) beside the real ``processed`` row. Serving both
    shows the investigator a phantom duplicate that reads as "integrity not
    verified" and cannot be deleted, because the deletion gate keys on the
    *id* - which is processed - not on the row.

    The engine now self-heals on the next write (``EvidenceRepository.update``
    collapses duplicates), but the read path must not display a phantom in the
    meantime. First occurrence wins ties, so display order is stable.
    """
    best: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        key = row.get("evidence_id", "")
        current = best.get(key)
        if current is None:
            best[key] = row
            order.append(key)
            continue
        if (_EVIDENCE_STATUS_RANK.get(row.get("status", ""), 0)
                > _EVIDENCE_STATUS_RANK.get(current.get("status", ""), 0)):
            best[key] = row
    return [best[key] for key in order]


def list_evidence(case_id: str | None = None) -> list[dict[str, str]]:
    rows = _read_csv(evidence_config().evidence_csv)
    return _collapse_evidence_rows(
        [r for r in rows if case_id is None or r.get("case_id") == case_id]
    )


def get_evidence(evidence_id: str) -> Optional[dict[str, str]]:
    rows = _read_csv(evidence_config().evidence_csv)
    matches = [r for r in rows if r.get("evidence_id") == evidence_id]
    if not matches:
        return None
    return max(
        matches,
        key=lambda r: _EVIDENCE_STATUS_RANK.get(r.get("status", ""), 0),
    )


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
    "cross_case": "cross_case_correlation",
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
    "analysis_manifest": "analysis_manifest",
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


def artifact_exists(case_id: str, key: str) -> bool:
    """Does this artifact exist, without reading or parsing it?

    The availability map asked ``try_artifact(...) is not None`` for all
    thirteen artifacts, which deserialised every one of them - including the
    relationship graph and the full report, the two largest documents in the
    system - to answer a yes/no question. On a case with a rich graph that is
    megabytes of JSON parsed on every page load.
    """
    name = ARTIFACTS.get(key)
    if name is None:
        return False
    return bool(report_repository().list_versions(case_id, name, ".json"))


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

    # The reports for an item live in ``forensics/<EVIDENCE_ID>/``. This used
    # to ``rglob("*.json")`` the entire forensics tree and filter by name, so
    # opening one evidence item walked every report of every item in the
    # system — cost grew with the corpus, not with the request. Scan the
    # item's own directory, and only fall back to the walk for legacy layouts
    # where reports were written beside each other.
    directory = root / evidence_id
    candidates = (
        sorted(directory.glob("*.json"))
        if directory.is_dir()
        else [p for p in sorted(root.glob("*.json")) if evidence_id in p.name]
    )
    for path in candidates:
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


def reset_engine_storage() -> dict[str, Any]:
    """Testing aid: wipe every case and entity from the engine's storage.

    Clears the case registry, evidence/entity/OCR CSVs, stored originals and
    OCR JSON, Phase-1 forensics, all Phase-2 artifacts, and the persistent
    cross-case entity index. Django workflow rows are cleared by the caller.
    """
    from ciis_correlation.core.maintenance import reset_all

    with _pipeline_lock:  # serialize against any in-flight engine write
        summary = reset_all(evidence_config(), investigation_config())
        # Drop cached singletons so nothing holds a handle to cleared state.
        for cached in (evidence_config, investigation_config, report_repository,
                       case_registry):
            cached.cache_clear()
    return summary


def delete_case_cascade(case_id: str) -> dict[str, Any]:
    """Delete one case and re-analyse every case that was linked to it.

    Admin action. Two halves:

    1. **Purge** - the engine drops the case from every store it owns (registry,
       evidence/entity/OCR/processing CSVs, OCR JSON, uploaded originals,
       Phase-1 forensics, all Phase-2 artifacts, cross-case entity index).
    2. **Re-analyse** - each case that was cross-linked to the deleted one gets
       its cross-case correlation recomputed and its report regenerated, so no
       surviving artifact still cites a case that no longer exists. The
       correlation/timeline/graph of those cases are refreshed too, because the
       report is rebuilt from their latest stored artifacts.
    """
    from ciis_correlation.core.maintenance import delete_case, linked_case_ids

    ecfg, icfg = evidence_config(), investigation_config()
    with _pipeline_lock:  # engine CSV storage is not concurrent-safe
        # Read the links BEFORE the case disappears.
        linked = linked_case_ids(icfg, case_id)
        purge = delete_case(ecfg, icfg, case_id)
        for cached in (evidence_config, investigation_config, report_repository,
                       case_registry):
            cached.cache_clear()

    refreshed = _refresh_linked_cases(linked)
    return {**purge, "linked_cases": linked, "refreshed_cases": refreshed}


def evidence_state(evidence_id: str) -> dict[str, Any]:
    """Whether an evidence item produced any findings yet (deletion gate)."""
    from ciis_correlation.core.maintenance import evidence_processing_state

    return evidence_processing_state(
        evidence_config(), investigation_config(), evidence_id
    )


def delete_evidence_item(case_id: str, evidence_id: str) -> dict[str, Any]:
    """Delete one evidence item, then refresh the case's live artifacts.

    The purge itself is the engine's; what belongs here is the follow-up. A
    case's correlation, timeline and graph are derived artifacts, so leaving
    them untouched would keep an item visible in the graph and on the timeline
    after its record had been removed - a discrepancy that is much worse in a
    chain-of-custody product than a slow delete.
    """
    from ciis_correlation.core.maintenance import delete_evidence

    with _pipeline_lock:  # engine CSV storage is not concurrent-safe
        summary = delete_evidence(
            evidence_config(), investigation_config(), evidence_id
        )
    if not summary.get("deleted"):
        return summary

    remaining = len(list_evidence(case_id))
    refreshed = _refresh_timeline_graph(case_id) if remaining else None
    return {
        **summary,
        "remaining_evidence": remaining,
        "artifacts_refreshed": refreshed is not None,
    }


def _refresh_linked_cases(case_ids: list[str]) -> list[str]:
    """Rebuild the artifacts of every case that referenced a deleted case.

    Cross-case correlation is not the only place a case id appears: the
    relationship **graph** embeds cross-case nodes too, and the report is
    assembled from both. Refreshing only the cross-case artifact left the graph
    (and therefore the investigation view) still showing the deleted case.

    So this reuses ``refresh_timeline_graph`` - the same path evidence
    enrichment already uses - which recomputes correlation, cross-case,
    timeline and graph from live storage, and then regenerates the report on
    top of the fresh cross-case result.

    The report is regenerated unconditionally rather than only when the
    cross-case artifact changed: these cases were selected *because* something
    they store names the deleted case, so there is always something to rewrite.
    """
    if not case_ids:
        return []
    from ciis_correlation.core.audit import InvestigationAuditTrail
    from ciis_correlation.core.data_access import CaseDataRepository
    from ciis_timeline_report.pipeline import build_default_pipeline
    from ciis_timeline_report.reporting.service import (
        InvestigationReportService,
    )

    icfg = investigation_config()
    data = CaseDataRepository(icfg)
    reporting = InvestigationReportService(
        icfg, data, report_repository(), InvestigationAuditTrail(icfg)
    )
    pipeline = build_default_pipeline(threat_intel=_threat_intel_provider())

    refreshed: list[str] = []
    with _pipeline_lock:
        for other in case_ids:
            if not data.case_exists(other):
                continue  # that case is gone too
            try:
                result = pipeline.refresh_timeline_graph(other)
                reporting.regenerate_with_cross_case(other, result["cross_case"])
                refreshed.append(other)
            except Exception:  # noqa: BLE001 - one bad case must not abort
                log.exception("Could not refresh linked case %s", other)
    return refreshed


@lru_cache(maxsize=1)
def _evidence_pipeline():
    """Acquisition + OCR pipeline with the production OCR engine (lazy)."""
    from backend.modules.evidence.pipeline import EvidencePipeline

    return EvidencePipeline(evidence_config(), _ocr_engine())


@lru_cache(maxsize=1)
def _forensics_pipeline():
    """Phase-1 forensic analyses, sharing the already-built OCR engine.

    Built lazily and cached: the services themselves are cheap, but the OCR
    adapters they compose are not, so the engine instance from
    ``_evidence_pipeline`` is injected rather than a second one created.
    """
    from backend.modules.evidence.forensics.config import ForensicsConfig
    from backend.modules.evidence.forensics.multi_ocr.engines import (
        EasyOCRAdapter,
        PaddleOCRAdapter,
        TesseractAdapter,
    )
    from backend.modules.evidence.forensics.pipeline import build_default_pipeline

    ecfg = evidence_config()
    fcfg = ForensicsConfig.from_env(ecfg)

    # Multi-OCR fusion is by far the most expensive Phase-1 module: every
    # engine listed here performs a *complete second OCR pass* over the image
    # the acquisition pipeline has already read, and EasyOCR/Tesseract are
    # whole extra stacks (EasyOCR downloads weights on first use). Nothing
    # downstream consumes the fusion report today, so it is off by default —
    # that alone roughly halves the forensic cost of an upload. Each engine is
    # opt-in per deployment.
    engines = []
    if getattr(settings, "FORENSICS_FUSION_PADDLE", False):
        engines.append(PaddleOCRAdapter(ecfg, engine=_ocr_engine()))
    if getattr(settings, "FORENSICS_FUSION_EASYOCR", False):
        engines.append(EasyOCRAdapter(fcfg))
    if getattr(settings, "FORENSICS_FUSION_TESSERACT", False):
        engines.append(TesseractAdapter(fcfg))

    return build_default_pipeline(
        ecfg, fcfg, ocr_engine=_ocr_engine(), fusion_engines=engines,
    )


def _run_forensics(evidence_id: str) -> Optional[dict[str, Any]]:
    """Run the Phase-1 forensic chain on one already-acquired item.

    The upload path used to stop after OCR + entity extraction, so
    ``storage/forensics/`` was never created and *no* case in the system had a
    quality score, EXIF/metadata report, forgery assessment, logo/brand
    detection or evidence-confidence score. Everything downstream that reads
    those reports - the analytics quality panel, brand statistics, device
    statistics, the forgery component of the priority score, and the evidence
    confidence the suspect scorer uses - was therefore permanently zero.

    ``analyze_evidence`` re-uses the stored original and the existing evidence
    row, so nothing is re-acquired or re-hashed for custody. Failure-isolated:
    a forensic analysis that cannot run must never discard captured evidence.
    """
    if not getattr(settings, "ENGINE_RUN_FORENSICS", True):
        log.info("Phase-1 forensics disabled (ENGINE_RUN_FORENSICS=0)")
        return None
    try:
        results = _forensics_pipeline().analyze_evidence(evidence_id)
        failures = results.get("failures") or []
        log.info("Phase-1 forensics for %s: failures=%s", evidence_id,
                 failures or "none")
        return results
    except Exception:  # noqa: BLE001 - best-effort, never fatal
        log.exception("Phase-1 forensics failed for %s", evidence_id)
        return None


def _failure_modules(failures: list[Any]) -> str:
    """Compact failure details to module names safe for job-facing messages."""
    return ", ".join(sorted({str(item).split(":", 1)[0] for item in failures}))


@lru_cache(maxsize=1)
def _ocr_engine():
    """The single PaddleOCR instance shared by every pipeline (heavy: lazy)."""
    from backend.modules.evidence.paddle_service import PaddleOCRService

    cfg = evidence_config()
    return PaddleOCRService(cfg, lang=cfg.ocr_lang)


@lru_cache(maxsize=1)
def _evidence_orchestrator():
    """Post-OCR text chain (cleaning -> enhancement -> semantic -> entities).

    Reuses the engine's ``EvidenceProcessingOrchestrator`` unchanged. Built
    lazily and cached (mirrors ``_evidence_pipeline``) because the semantic
    knowledge base / dictionaries are non-trivial to load. Runs fully offline:
    the semantic stage falls back to its heuristic path when the optional
    transformer weights are absent.
    """
    from backend.modules.evidence.semantic.orchestrator import (
        EvidenceProcessingOrchestrator,
    )

    return EvidenceProcessingOrchestrator(evidence_config())


def _enrich_evidence(case_id: str,
                     evidence_id: str | None = None) -> Optional[dict[str, Any]]:
    """Run the full post-OCR chain; failure-isolated.

    When ``evidence_id`` is given, only that item is cleaned/enhanced/
    corrected — the incremental path used on upload. Re-processing the whole
    case on every upload made the n-th upload re-do all n items (quadratic
    over a case's lifetime), which is why multi-evidence cases slowed to a
    crawl. Without ``evidence_id`` the whole case is processed (used when a
    normalization rule changes and stored entities must be recomputed).

    Returns the orchestrator summary on success, or ``None`` when the chain is
    disabled or fails. A failure here never discards the already-captured OCR
    evidence: the upload has succeeded regardless, so we log/report but do not
    re-raise. The caller must hold ``_pipeline_lock`` (engine CSV storage is
    not concurrency-safe and several stages append to shared CSVs).
    """
    if not getattr(settings, "ENGINE_RUN_FULL_PIPELINE", True):
        log.info("Full Phase-1 chain disabled (ENGINE_RUN_FULL_PIPELINE=0)")
        return None
    try:
        orchestrator = _evidence_orchestrator()
        if evidence_id:
            summary = orchestrator.process_evidence(case_id, evidence_id)
        else:
            summary = orchestrator.process_case(case_id)
        log.info(
            "Post-OCR chain for %s: clean=%s enhance=%s semantic=%s in %s ms",
            case_id,
            summary.get("stages", {}).get("cleaning"),
            summary.get("stages", {}).get("enhancement"),
            summary.get("stages", {}).get("semantic"),
            summary.get("duration_ms"),
        )
        return summary
    except Exception:  # noqa: BLE001 - enrichment is best-effort, never fatal
        log.exception("Post-OCR enrichment chain failed for %s", case_id)
        return None


def _entity_count(summary: Optional[dict[str, Any]]) -> Optional[int]:
    """Total entities extracted across the case's evidence, if available."""
    if not summary:
        return None
    total = 0
    for res in summary.get("semantic_results", []) or []:
        entities = getattr(res, "entities", None)
        if isinstance(entities, dict):
            total += sum(len(v) for v in entities.values())
    return total


def _refresh_timeline_graph(case_id: str) -> Optional[dict[str, Any]]:
    """Regenerate live artifacts after OCR/entity enrichment, failure-isolated."""
    try:
        from ciis_timeline_report.pipeline import build_default_pipeline

        return build_default_pipeline(
            threat_intel=_threat_intel_provider()
        ).refresh_timeline_graph(case_id)
    except Exception:  # noqa: BLE001 - evidence processing remains recoverable
        log.exception("Live timeline/graph refresh failed for %s", case_id)
        return None


#: Evidence jobs still queued or running, per case. Guarded by its own lock so
#: a worker can read it without waiting on the (long-held) pipeline lock.
_pending_uploads: dict[str, int] = {}
_pending_lock = threading.Lock()


def _upload_queued(case_id: str) -> None:
    with _pending_lock:
        _pending_uploads[case_id] = _pending_uploads.get(case_id, 0) + 1


def _upload_finished(case_id: str) -> int:
    """Mark one upload done; returns how many are still outstanding."""
    with _pending_lock:
        remaining = max(0, _pending_uploads.get(case_id, 1) - 1)
        if remaining:
            _pending_uploads[case_id] = remaining
        else:
            _pending_uploads.pop(case_id, None)
        return remaining


def submit_evidence_job(job_id: int, tmp_path: str, case_id: str,
                        notes: str, username: str) -> None:
    """Queue Phase-1 processing of an uploaded file (runs in a worker)."""
    _upload_queued(case_id)

    def work() -> None:
        from .store import jobs, notifications
        from .constants import EvidenceStage, NotificationType

        jobs.update(job_id, status="running")
        detail = ""
        still_pending: Optional[int] = None   # set once this item is accounted for

        def report(key: str, note: str = "") -> None:
            """Publish the engine's real step onto the job the UI is polling."""
            jobs.stage(job_id, key, EvidenceStage.LABELS.get(key, key), note)

        try:
            with _pipeline_lock:  # engine CSV storage is not concurrent-safe
                result = _evidence_pipeline().process_file(
                    tmp_path, case_id=case_id, notes=notes, on_stage=report,
                )
                # Full Phase-1 chain: cleaning -> enhancement -> semantic ->
                # entity extraction, for THIS item only (previously the whole
                # case was re-processed per upload). Kept inside the SAME lock
                # because these stages append to shared CSVs (entities.csv,
                # keyword_*.csv). Best-effort: a failure here does not discard
                # the OCR result.
                report(EvidenceStage.ENRICH, "cleaning text, extracting entities")
                summary = _enrich_evidence(case_id, result.evidence_id)
                # Phase-1 forensics on the stored original: integrity, EXIF /
                # metadata, image quality, forgery indicators, brand logos and
                # the composite evidence-confidence score. Runs inside the same
                # lock (it appends to the forensic CSV registers).
                report(EvidenceStage.FORENSICS,
                       "metadata, quality, forgery and logo checks")
                forensics = _run_forensics(result.evidence_id)
                # Entities are durable now, so only the timeline and graph need
                # regenerating — and only once per *burst*. Rebuilding them per
                # item made a batch of n uploads recompute correlation over the
                # whole case n times (O(n²) pairs on the last item alone), which
                # is what made multi-file uploads crawl. When more uploads for
                # this case are still queued, the last one to finish does it.
                still_pending = _upload_finished(case_id)
                if still_pending == 0:
                    report(EvidenceStage.CORRELATE,
                           "rebuilding correlation, timeline and graph")
                    live_artifacts = _refresh_timeline_graph(case_id)
                else:
                    live_artifacts = None
            entities = _entity_count(summary)
            if summary is None:
                detail = f"Processed as {result.evidence_id} (OCR only)"
            elif entities is None:
                detail = f"Processed as {result.evidence_id} (full pipeline)"
            else:
                detail = (
                    f"Processed as {result.evidence_id}; "
                    f"{entities} entities extracted"
                )
            warnings: list[str] = []
            if summary is None and getattr(settings, "ENGINE_RUN_FULL_PIPELINE", True):
                warnings.append("entity enrichment did not complete")
            if forensics is None:
                if getattr(settings, "ENGINE_RUN_FORENSICS", True):
                    warnings.append("Phase-1 forensic processing did not complete")
            else:
                forensic_failures = forensics.get("failures") or []
                if forensic_failures:
                    warnings.append(
                        "Phase-1 warnings in "
                        f"{_failure_modules(forensic_failures)}"
                    )
                    detail += "; forensic reports generated with warnings"
                else:
                    detail += "; forensic reports generated"
            if live_artifacts is not None:
                detail += "; timeline and graph refreshed"
            elif still_pending:
                detail += (
                    f"; timeline/graph refresh deferred "
                    f"({still_pending} upload(s) still queued)"
                )
            else:
                detail += "; timeline/graph refresh pending"
                warnings.append("timeline/graph refresh did not complete")
            if warnings:
                detail += f"; warnings={'; '.join(warnings)}"
            outcome = "completed_with_warnings" if warnings else "completed"
            jobs.finish(job_id, outcome, detail=detail,
                        evidence_id=result.evidence_id)
            notifications.broadcast(
                type=NotificationType.PROCESSING_COMPLETE,
                title=(
                    f"Evidence {result.evidence_id} processed with warnings"
                    if warnings else f"Evidence {result.evidence_id} processed"
                ),
                message=(
                    f"{result.file_name} processed for {case_id} with "
                    f"{len(warnings)} warning(s)."
                    if warnings else f"{result.file_name} processed for {case_id}."
                ),
                case_id=case_id, evidence_id=result.evidence_id,
            )
        except Exception as exc:  # noqa: BLE001 - report, never crash worker
            log.exception("Evidence processing failed (job %s)", job_id)
            # A failed item must not hold the burst counter open, or a queued
            # sibling would never trigger the refresh. Only decrement if this
            # item was not already accounted for before the failure.
            if still_pending is None and _upload_finished(case_id) == 0:
                _refresh_timeline_graph(case_id)
            jobs.finish(job_id, "failed", error=str(exc))
            notifications.broadcast(
                type=NotificationType.SYSTEM_ERROR,
                title="Evidence processing failed",
                message=str(exc), case_id=case_id,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    _executor.submit(work)


@lru_cache(maxsize=1)
def _threat_intel_provider():
    """Threat-intel provider chain for Phase-2 analysis.

    Curated indicator file -> ML classifier (when its dependencies are
    installed and the model loads) -> rule-based heuristics. The chain keeps
    the most serious *explained* verdict, so a deployment with no indicator
    file and no ML stack still scores every link instead of reporting
    "intelligence unavailable" - which is what happened before, on every case,
    because the indicator file is not shipped and the ML dependencies live in a
    separate virtualenv.
    """
    from ciis_correlation.core.data_access import ThreatIntelProvider
    from ciis_correlation.threat.heuristics import (
        ChainedThreatIntelProvider,
        HeuristicThreatIntelProvider,
    )

    providers = [ThreatIntelProvider(investigation_config().threat_intel_json)]

    if getattr(settings, "ML_THREAT_INTEL_ENABLED", False):
        from ciis_correlation.threat.ml_provider import MLThreatIntelProvider

        ml = MLThreatIntelProvider(
            settings.ML_THREAT_INTEL_ROOT,
            model_type=getattr(settings, "ML_THREAT_INTEL_MODEL", "xgboost"),
            use_intelligence=getattr(settings, "ML_THREAT_INTEL_LIVE", False),
        )
        if ml.available:
            log.info("ML threat-intel active (model=%s)", settings.ML_THREAT_INTEL_MODEL)
            providers.append(ml)
        else:
            log.warning(
                "ML threat-intel enabled but the classifier did not load; "
                "continuing with indicator file + heuristics"
            )

    providers.append(HeuristicThreatIntelProvider())
    chain = ChainedThreatIntelProvider(*providers)
    log.info("threat-intel chain: %s", chain.source_name)
    return chain


def _has_forensic_report(directory: Path, report_name: str) -> bool:
    """Return whether ``directory`` contains any version of a report."""
    return any(directory.glob(f"{report_name}*.json"))


def _forensics_complete(evidence_row: dict[str, str]) -> bool:
    """Check the minimum Phase-1 reports expected for this evidence type.

    Directory existence alone is not sufficient: a failed run can persist a
    metadata or confidence report before integrity/image loading fails. Such a
    directory must remain eligible for repair on a later analysis.
    """
    from backend.modules.evidence.forensics.config import ForensicsConfig

    ecfg = evidence_config()
    fcfg = ForensicsConfig.from_env(ecfg)
    directory = fcfg.evidence_dir(evidence_row.get("evidence_id", ""))
    required = {
        fcfg.fingerprint_report_name,
        fcfg.metadata_report_name,
        fcfg.confidence_report_name,
    }
    suffix = Path(evidence_row.get("stored_file_name", "")).suffix.lower()
    if suffix in ecfg.image_extensions:
        required.update({
            fcfg.quality_report_name,
            fcfg.forgery_report_name,
            fcfg.logo_report_name,
        })
    return directory.is_dir() and all(
        _has_forensic_report(directory, name) for name in required
    )


def _backfill_forensics(case_id: str) -> dict[str, Any]:
    """Generate missing Phase-1 reports and return repairs plus warnings.

    Every registered original is validated before analysis. Missing originals
    are not sent through Phase 1, because doing so creates low-information
    confidence scores that look authoritative despite integrity failure. The
    caller must hold ``_pipeline_lock``.
    """
    summary: dict[str, Any] = {"repaired": 0, "warnings": []}
    if not getattr(settings, "ENGINE_RUN_FORENSICS", True):
        return summary
    ecfg = evidence_config()
    originals_root = ecfg.originals_dir.resolve()
    hash_service = HashService()
    missing_originals: list[str] = []
    for row in list_evidence(case_id):
        evidence_id = row.get("evidence_id", "")
        if not evidence_id:
            continue
        stored_name = row.get("stored_file_name", "").strip()
        if not stored_name:
            summary["warnings"].append(
                f"{evidence_id}: stored original filename is missing"
            )
            continue
        stored_path = (originals_root / stored_name).resolve()
        try:
            stored_path.relative_to(originals_root)
        except ValueError:
            summary["warnings"].append(
                f"{evidence_id}: stored original path is outside evidence storage"
            )
            continue
        if not stored_path.is_file():
            missing_originals.append(evidence_id)
            continue
        acquisition_hash = row.get("sha256_before", "").strip().lower()
        if not acquisition_hash:
            summary["warnings"].append(
                f"{evidence_id}: acquisition SHA-256 is missing"
            )
            continue
        if hash_service.sha256_file(stored_path).lower() != acquisition_hash:
            summary["warnings"].append(
                f"{evidence_id}: original evidence SHA-256 no longer matches acquisition"
            )
            continue
        if _forensics_complete(row):
            continue

        result = _run_forensics(evidence_id)
        if result is None:
            summary["warnings"].append(
                f"{evidence_id}: Phase-1 forensic processing did not complete"
            )
            continue
        failures = result.get("failures") or []
        if failures:
            summary["warnings"].append(
                f"{evidence_id}: Phase-1 warnings in {_failure_modules(failures)}"
            )
            continue
        if not _forensics_complete(row):
            summary["warnings"].append(
                f"{evidence_id}: required forensic reports remain incomplete"
            )
            continue
        summary["repaired"] += 1
    if missing_originals:
        summary["warnings"].insert(
            0,
            f"Original evidence files unavailable for {len(missing_originals)} "
            f"item(s): {', '.join(missing_originals)}",
        )
    if summary["repaired"]:
        log.info("backfilled Phase-1 forensics for %d item(s) in %s",
                 summary["repaired"], case_id)
    if summary["warnings"]:
        log.warning("Phase-1 validation warnings for %s: %s",
                    case_id, "; ".join(summary["warnings"]))
    return summary


def _save_analysis_manifest(
    case_id: str,
    *,
    status: str,
    warnings: list[str],
    threat_provider: Any,
) -> None:
    """Persist the runtime/configuration provenance behind an analysis run."""
    health = engine_health()

    def version(distribution: str) -> str:
        try:
            return importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            return "not-installed"

    icfg = investigation_config()
    rows = list_evidence(case_id)
    report_repository().save(
        case_id,
        icfg.analysis_manifest_name,
        {
            "status": status,
            "input_quality": "partial" if warnings else "complete",
            "warnings": warnings,
            "evidence_ids": [row.get("evidence_id", "") for row in rows],
            "evidence_count": len(rows),
            "semantic_validator": health.get("semantic_validator", "unknown"),
            "threat_provider": getattr(threat_provider, "source_name", "unknown"),
            "graph_analytics": f"networkx-{version('networkx')}",
            "runtime": {
                "python": platform.python_version(),
                "pydantic": version("pydantic"),
                "networkx": version("networkx"),
            },
            "correlation_configuration": {
                "confidence_normaliser": icfg.correlation_confidence_normaliser,
                "relationship_bands": icfg.relationship_bands,
                "timeline_proximity_weight": icfg.correlation_weights.get(
                    "timeline_proximity", 0.0
                ),
            },
            "timeline_configuration": {
                "proximity_hours": icfg.timeline_proximity_hours,
                "stage_order": list(icfg.timeline_stage_order),
            },
        },
    )


def submit_analysis_job(job_id: int, case_id: str, username: str) -> None:
    """Queue the full Phase-2 pipeline for a case (runs in a worker)."""

    def work() -> None:
        from .store import jobs, notifications
        from .constants import NotificationType

        jobs.update(job_id, status="running")
        detail = ""
        try:
            from ciis_timeline_report.pipeline import build_default_pipeline

            with _pipeline_lock:
                # Evidence captured before forensics ran on upload has no
                # Phase-1 reports, which would leave this case's quality,
                # brand and forgery statistics at zero forever. Analysis is
                # the natural place to repair that: it is explicit, already
                # long-running, and the reports are what the analysis reads.
                backfill = _backfill_forensics(case_id)
                threat_provider = _threat_intel_provider()
                if (
                    backfill["warnings"]
                    and getattr(settings, "ANALYSIS_INPUT_POLICY", "warn") == "strict"
                ):
                    _save_analysis_manifest(
                        case_id,
                        status="failed_quality_gate",
                        warnings=list(backfill["warnings"]),
                        threat_provider=threat_provider,
                    )
                    raise RuntimeError(
                        "Analysis quality gate blocked Phase 2: "
                        + "; ".join(backfill["warnings"])
                    )
                results = build_default_pipeline(
                    threat_intel=threat_provider
                ).analyze_case(case_id)
            phase2_failures = results.get("failures") or []
            warnings = list(backfill["warnings"])
            warnings.extend(f"Phase-2 {failure}" for failure in phase2_failures)
            detail = f"phase2_failures={phase2_failures or 'none'}"
            if backfill["repaired"]:
                detail += (
                    f"; forensics backfilled for {backfill['repaired']} item(s)"
                )
            if warnings:
                detail += f"; warnings={'; '.join(warnings)}"
            outcome = "completed_with_warnings" if warnings else "completed"
            _save_analysis_manifest(
                case_id,
                status=outcome,
                warnings=warnings,
                threat_provider=threat_provider,
            )
            jobs.finish(job_id, outcome, detail=detail)
            notifications.broadcast(
                type=NotificationType.REPORT_GENERATED,
                title=(
                    f"Investigation analysis completed with warnings for {case_id}"
                    if warnings else
                    f"Investigation analysis completed for {case_id}"
                ),
                message=(
                    f"Phase-2 artifacts regenerated with {len(warnings)} warning(s)."
                    if warnings else "All Phase-2 artifacts regenerated."
                ),
                case_id=case_id,
            )
            _emit_priority_notification(case_id)
        except Exception as exc:  # noqa: BLE001
            log.exception("Case analysis failed (job %s)", job_id)
            jobs.finish(job_id, "failed", error=str(exc))
            notifications.broadcast(
                type=NotificationType.SYSTEM_ERROR,
                title=f"Analysis failed for {case_id}",
                message=str(exc), case_id=case_id,
            )

    _executor.submit(work)


def _emit_priority_notification(case_id: str) -> None:
    """High-priority alert sourced from the engine's own priority verdict."""
    from .store import notifications
    from .constants import NotificationType

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
        notifications.broadcast(
            type=NotificationType.HIGH_PRIORITY,
            title=f"{case_id} flagged {band.upper()} priority",
            message=f"Engine priority score: {score}.", case_id=case_id,
        )


# ------------------------------------------------------------------- warm-up
_warmed = threading.Event()


def warm_start() -> None:
    """Build the expensive singletons ahead of the first upload.

    ``PaddleOCRService`` loads three models on construction and the semantic
    orchestrator loads its dictionaries; together that is the bulk of the wait
    on the first piece of evidence processed after a restart. Nothing about it
    is upload-specific, so it does not belong on the investigator's clock.

    Runs once, on a daemon thread, and is failure-isolated: a warm-up that
    cannot complete (missing optional dependency, no model cache) must leave
    the server perfectly usable — the lazy ``lru_cache`` path still applies,
    it just pays the cost later, exactly as before.
    """
    if not getattr(settings, "ENGINE_WARM_START", True):
        return
    if _warmed.is_set():
        return
    _warmed.set()

    def preload() -> None:
        import time

        started = time.perf_counter()
        for name, build in (("OCR engine", _ocr_engine),
                            ("evidence pipeline", _evidence_pipeline),
                            ("text/entity chain", _evidence_orchestrator)):
            try:
                build()
            except Exception:  # noqa: BLE001 - warm-up is an optimisation only
                log.exception("warm-up of the %s failed; it will load on demand",
                              name)
        log.info("engine warm-up finished in %.1fs",
                 time.perf_counter() - started)

    threading.Thread(target=preload, name="ciis-warmup", daemon=True).start()


# ------------------------------------------------------------------- helpers
def engine_health() -> dict[str, Any]:
    cfg = evidence_config()
    return {
        "engine_root": str(settings.ENGINE_ROOT),
        "correlation_root": str(settings.CORRELATION_ROOT),
        "timeline_report_root": str(settings.TIMELINE_REPORT_ROOT),
        "storage_ok": cfg.storage_dir.is_dir(),
        "cases_csv": cfg.cases_csv.is_file(),
        "evidence_csv": cfg.evidence_csv.is_file(),
        "investigation_dir": investigation_config().investigation_dir.is_dir(),
        **_optional_capabilities(),
    }


def _optional_capabilities() -> dict[str, Any]:
    """Which optional analysis capabilities this deployment can actually run.

    Both degrade silently by design - the pipeline works without them - but a
    forensic deployment has to be able to state which mode it is in *before*
    evidence is processed, not infer it afterwards from per-item fields. A
    report that says "semantically corrected" means something different when
    the corrector was a multilingual language model than when it was the
    dictionary fallback.

    Neither probe loads a model, and neither imports an engine package.
    ``find_spec`` resolves a module without executing it, which keeps this
    cheap and - more importantly - keeps it off the import graph: warm-up runs
    in a background thread, and a probe that imported the semantic package
    could observe it half-initialised and report "unknown" for no real reason.

    ``MLThreatIntelProvider.available`` is deliberately *not* called: it loads
    the classifier, which is far too expensive for a health endpoint.
    """
    capabilities: dict[str, Any] = {}

    # Mirrors SemanticCorrectionPipeline._default_validator: XLM-R is used when
    # transformers is present, otherwise the heuristic fallback. The
    # authoritative per-item record stays on each semantic result
    # (``validator=`` in the stored artifact); this is the deployment-level view.
    semantic_ml = importlib.util.find_spec("transformers") is not None
    capabilities["semantic_ml_available"] = semantic_ml
    capabilities["semantic_validator"] = "xlm-roberta-base" if semantic_ml else "heuristic"

    enabled = bool(getattr(settings, "ML_THREAT_INTEL_ENABLED", False))
    model = getattr(settings, "ML_THREAT_INTEL_MODEL", "xgboost")
    root = getattr(settings, "ML_THREAT_INTEL_ROOT", None)
    checkpoint = Path(root) / "checkpoints" / f"{model}.pkl" if root else None
    capabilities["threat_ml_enabled"] = enabled
    capabilities["threat_ml_checkpoint"] = bool(checkpoint and checkpoint.is_file())

    return capabilities


def iter_case_artifact(case_ids: list[str], key: str) -> Iterator[tuple[str, dict]]:
    for cid in case_ids:
        doc = try_artifact(cid, key)
        if doc is not None:
            yield cid, doc.get("report", doc)


def iter_case_artifacts(case_ids: list[str], keys: tuple[str, ...]
                        ) -> Iterator[tuple[str, dict[str, dict]]]:
    """Several artifacts per case in **one** pass over the case ids.

    The dashboard needs priority, campaigns and analytics for every case;
    calling :func:`iter_case_artifact` once per key walked the case list three
    times and re-globbed each case directory three times. Reading them together
    keeps the directory listing warm and cuts the syscalls by two thirds.
    """
    for cid in case_ids:
        found: dict[str, dict] = {}
        for key in keys:
            doc = try_artifact(cid, key)
            if doc is not None:
                found[key] = doc.get("report", doc)
        if found:
            yield cid, found
