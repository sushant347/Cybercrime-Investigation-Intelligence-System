"""Adapter over the timeline reconstruction algorithm.

:mod:`.engine` owns timestamp resolution, ordering, de-duplication and event
classification, and stays framework-independent - it knows nothing about
configuration, storage or audit. This service only translates investigation
models, persists the frontend-compatible artifact, and records the audit entry.

The algorithm used to live in a separate top-level ``timeline_reconstruction/``
directory and was loaded by walking parent directories and exec'ing the file
through ``importlib``. It is a sibling module now, so a plain import does it.
"""

from __future__ import annotations

import time
from typing import Optional, Sequence

from backend.modules.evidence.logger import get_logger
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.core.data_access import CaseDataRepository, EvidenceContext
from ciis_correlation.core.repository import InvestigationReportRepository
from ciis_correlation.correlation.models import CorrelationAnalysis

from . import engine
from .models import TimelineAnalysis
from ciis_correlation.core.text import count_of

MODULE = "timeline"


class TimelineService:
    """Translate integrated evidence into the canonical timeline."""

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
        result = engine.build_timeline(
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
                f"{count_of(len(analysis.events), 'event')}, "
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
            # Creation timestamps from EXIF/PDF/Office metadata are a better
            # fallback than ingestion time. The standalone engine remains
            # framework-independent; it only receives this plain dictionary.
            "metadata": context.forensics.get("metadata_report", {}),
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
