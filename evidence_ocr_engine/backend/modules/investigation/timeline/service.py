"""Integrated adapter for the standalone timeline reconstruction engine.

The standalone package owns timestamp resolution, ordering, de-duplication and
event classification.  This service only translates investigation models,
persists the frontend-compatible artifact, and records the audit entry.
"""

from __future__ import annotations

import importlib.util
import time
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Optional, Sequence

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from .models import TimelineAnalysis

MODULE = "timeline"


@lru_cache(maxsize=1)
def _standalone_engine() -> ModuleType:
    """Load the framework-independent engine without relying on cwd/sys.path."""
    current = Path(__file__).resolve()
    candidates = [
        parent / "timeline_reconstruction" / "timeline_reconstruction.py"
        for parent in current.parents
    ]
    engine_path = next((path for path in candidates if path.is_file()), None)
    if engine_path is None:
        raise RuntimeError("standalone timeline_reconstruction engine not found")
    spec = importlib.util.spec_from_file_location(
        "ciis_standalone_timeline_reconstruction", engine_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load standalone timeline engine: {engine_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TimelineService:
    """Translate integrated evidence into the canonical standalone timeline."""

    def __init__(
        self,
        config: InvestigationConfig,
        data: CaseDataRepository,
        repository: InvestigationReportRepository,
        audit: InvestigationAuditTrail,
    ) -> None:
        self._cfg = config
        self._data = data
        self._repo = repository
        self._audit = audit
        self._log = get_logger("investigation.timeline")

    def analyze(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        correlation: Optional[CorrelationAnalysis] = None,
        *,
        persist: bool = True,
    ) -> TimelineAnalysis:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)
        cases = [{
            "case_id": case_id,
            "evidence": [self._evidence_payload(item) for item in items],
        }]
        result = _standalone_engine().build_timeline(
            cases,
            self._correlation_payload(correlation),
            stage_keywords=self._cfg.timeline_stage_keywords,
            stage_order=self._cfg.timeline_stage_order,
            critical_entity_types=self._cfg.timeline_critical_entity_types,
        )
        result["analysis_time_ms"] = round(
            (time.perf_counter() - started) * 1000.0, 1
        )
        analysis = TimelineAnalysis.model_validate(result)
        if persist:
            self._repo.save(
                case_id, self._cfg.timeline_report_name, analysis.model_dump()
            )
            self._audit.record(
                case_id,
                MODULE,
                "analyzed",
                f"{len(analysis.events)} event(s), "
                f"resolved={int(analysis.statistics.get('resolved_event_count', 0))}, "
                f"inferred={int(analysis.statistics.get('inferred_event_count', 0))}",
                duration_ms=analysis.analysis_time_ms,
            )
        return analysis

    @staticmethod
    def _evidence_payload(context: EvidenceContext) -> dict:
        grouped: dict[str, list[dict[str, str]]] = {}
        for entity in context.entities:
            grouped.setdefault(entity.entity_type, []).append({
                "value": entity.value,
                "normalized": entity.normalized,
            })
        return {
            "evidence_id": context.evidence_id,
            "file_name": context.file_name,
            "upload_time": context.upload_time,
            "raw_text": context.raw_text,
            "cleaning": {"entities": grouped},
        }

    @staticmethod
    def _correlation_payload(
        correlation: Optional[CorrelationAnalysis],
    ) -> dict:
        if correlation is None:
            return {"nodes": [], "edges": []}
        return {
            "nodes": [],
            "edges": [
                {
                    "source": pair.evidence_a,
                    "target": pair.evidence_b,
                    "type": "behavioral_relationship",
                    "weight": pair.correlation_confidence,
                    "confidence": pair.correlation_confidence,
                }
                for pair in correlation.pairs
                if pair.relationship_strength != "NO_RELATIONSHIP"
            ],
        }
