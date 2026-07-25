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


def reset_engine_storage() -> dict[str, Any]:
    """Testing aid: wipe every case and entity from the engine's storage.

    Clears the case registry, evidence/entity/OCR CSVs, stored originals and
    OCR JSON, Phase-1 forensics, all Phase-2 artifacts, and the persistent
    cross-case entity index. Django workflow rows are cleared by the caller.
    """
    from backend.modules.investigation.maintenance import reset_all

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
    from backend.modules.investigation.maintenance import delete_case, linked_case_ids

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
    from backend.modules.investigation.maintenance import evidence_processing_state

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
    from backend.modules.investigation.maintenance import delete_evidence

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
    from backend.modules.investigation.audit import InvestigationAuditTrail
    from backend.modules.investigation.data_access import CaseDataRepository
    from backend.modules.investigation.pipeline import build_default_pipeline
    from backend.modules.investigation.reporting.service import (
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

    # Multi-OCR fusion is the one Phase-1 module that can add tens of seconds
    # per upload, because EasyOCR and Tesseract are separate OCR stacks (and
    # EasyOCR downloads its weights on first use). Nothing downstream reads the
    # fusion report today, so an interactive upload uses the OCR engine that is
    # already resident; the other engines are opt-in per deployment.
    engines = [PaddleOCRAdapter(ecfg, engine=_ocr_engine())]
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
        from backend.modules.investigation.pipeline import build_default_pipeline

        return build_default_pipeline(
            threat_intel=_threat_intel_provider()
        ).refresh_timeline_graph(case_id)
    except Exception:  # noqa: BLE001 - evidence processing remains recoverable
        log.exception("Live timeline/graph refresh failed for %s", case_id)
        return None


def submit_evidence_job(job_id: int, tmp_path: str, case_id: str,
                        notes: str, username: str) -> None:
    """Queue Phase-1 processing of an uploaded file (runs in a worker)."""

    def work() -> None:
        from .store import jobs, notifications
        from .constants import NotificationType

        jobs.update(job_id, status="running")
        detail = ""
        try:
            with _pipeline_lock:  # engine CSV storage is not concurrent-safe
                result = _evidence_pipeline().process_file(
                    tmp_path, case_id=case_id, notes=notes
                )
                # Full Phase-1 chain: cleaning -> enhancement -> semantic ->
                # entity extraction, for THIS item only (previously the whole
                # case was re-processed per upload). Kept inside the SAME lock
                # because these stages append to shared CSVs (entities.csv,
                # keyword_*.csv). Best-effort: a failure here does not discard
                # the OCR result.
                summary = _enrich_evidence(case_id, result.evidence_id)
                # Phase-1 forensics on the stored original: integrity, EXIF /
                # metadata, image quality, forgery indicators, brand logos and
                # the composite evidence-confidence score. Runs inside the same
                # lock (it appends to the forensic CSV registers).
                forensics = _run_forensics(result.evidence_id)
                # Entities are now durable, so regenerate only the timeline and
                # relationship graph.  Other Phase-2/report modules are not run.
                live_artifacts = _refresh_timeline_graph(case_id)
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
            if forensics is not None:
                detail += "; forensic reports generated"
            if live_artifacts is not None:
                detail += "; timeline and graph refreshed"
            else:
                detail += "; timeline/graph refresh pending"
            jobs.finish(job_id, "completed", detail=detail,
                        evidence_id=result.evidence_id)
            notifications.broadcast(
                type=NotificationType.PROCESSING_COMPLETE,
                title=f"Evidence {result.evidence_id} processed",
                message=f"{result.file_name} processed for {case_id}.",
                case_id=case_id, evidence_id=result.evidence_id,
            )
        except Exception as exc:  # noqa: BLE001 - report, never crash worker
            log.exception("Evidence processing failed (job %s)", job_id)
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
    from backend.modules.investigation.data_access import ThreatIntelProvider
    from backend.modules.investigation.threat_heuristics import (
        ChainedThreatIntelProvider,
        HeuristicThreatIntelProvider,
    )

    providers = [ThreatIntelProvider(investigation_config().threat_intel_json)]

    if getattr(settings, "ML_THREAT_INTEL_ENABLED", False):
        from backend.modules.investigation.ml_threat_intel import MLThreatIntelProvider

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


def _backfill_forensics(case_id: str) -> int:
    """Generate missing Phase-1 reports for a case; returns items repaired.

    Only items with no forensics directory are touched, so this is cheap on a
    healthy case and self-limiting on a repeat run. The caller must hold
    ``_pipeline_lock``.
    """
    if not getattr(settings, "ENGINE_RUN_FORENSICS", True):
        return 0
    root = investigation_config().forensics_dir
    repaired = 0
    for row in list_evidence(case_id):
        evidence_id = row.get("evidence_id", "")
        if not evidence_id or (root / evidence_id).is_dir():
            continue
        if _run_forensics(evidence_id) is not None:
            repaired += 1
    if repaired:
        log.info("backfilled Phase-1 forensics for %d item(s) in %s",
                 repaired, case_id)
    return repaired


def submit_analysis_job(job_id: int, case_id: str, username: str) -> None:
    """Queue the full Phase-2 pipeline for a case (runs in a worker)."""

    def work() -> None:
        from .store import jobs, notifications
        from .constants import NotificationType

        jobs.update(job_id, status="running")
        detail = ""
        try:
            from backend.modules.investigation.pipeline import build_default_pipeline

            with _pipeline_lock:
                # Evidence captured before forensics ran on upload has no
                # Phase-1 reports, which would leave this case's quality,
                # brand and forgery statistics at zero forever. Analysis is
                # the natural place to repair that: it is explicit, already
                # long-running, and the reports are what the analysis reads.
                backfilled = _backfill_forensics(case_id)
                results = build_default_pipeline(
                    threat_intel=_threat_intel_provider()
                ).analyze_case(case_id)
            failures = results.get("failures") or []
            detail = f"failures={failures or 'none'}"
            if backfilled:
                detail += f"; forensics backfilled for {backfilled} item(s)"
            jobs.finish(job_id, "completed", detail=detail)
            notifications.broadcast(
                type=NotificationType.REPORT_GENERATED,
                title=f"Investigation analysis completed for {case_id}",
                message="All Phase-2 artifacts regenerated.", case_id=case_id,
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
