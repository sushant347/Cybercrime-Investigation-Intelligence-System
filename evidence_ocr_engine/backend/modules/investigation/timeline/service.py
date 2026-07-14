"""Module 5 - Timeline Intelligence Engine.

Extends the timeline from a plain chronological listing into an intelligent
view of the attack:

* events         - every evidence acquisition, chronologically ordered
* attack stages  - initial contact, social engineering, credential theft,
                   financial transaction, post-attack (config-driven keyword
                   rules over the verbatim OCR text; fully explainable)
* milestones     - first observation of each stage
* critical events - evidence containing OTPs, money amounts, wallets or
                    bank accounts (configurable entity types)
* progression check - whether the observed stage order follows the canonical
                      scam sequence (chronological integrity is preserved:
                      events are only ever sorted by timestamp, never edited)
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..config import InvestigationConfig
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from .models import AttackStage, TimelineAnalysis, TimelineEvent

MODULE = "timeline"


class TimelineService:
    """Attack-stage aware timeline intelligence for one case."""

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

    # ------------------------------------------------------------------ public

    def analyze(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> TimelineAnalysis:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)
        items = sorted(items, key=lambda c: c.upload_time or "")

        stage_hits: Dict[str, Dict[str, List[str]]] = {}
        events: List[TimelineEvent] = []
        for context in items:
            stages, keywords = self._classify(context)
            critical, reasons = self._critical(context)
            events.append(TimelineEvent(
                timestamp=context.upload_time,
                event_type="evidence_acquired",
                evidence_id=context.evidence_id,
                description=(
                    f"Evidence {context.evidence_id} ({context.file_name}) acquired"
                    + (f"; stages: {', '.join(stages)}" if stages else "")
                ),
                stages=stages,
                critical=critical,
                critical_reasons=reasons,
            ))
            for stage in stages:
                bucket = stage_hits.setdefault(stage, {})
                bucket[context.evidence_id] = keywords.get(stage, [])

        attack_stages = self._attack_stages(stage_hits, items)
        progression = self._progression(events)
        milestones = self._milestones(events)
        critical_events = [e for e in events if e.critical]

        analysis = TimelineAnalysis(
            case_id=case_id,
            events=events,
            attack_stages=attack_stages,
            stage_progression=progression,
            progression_consistent=self._is_consistent(progression),
            milestones=milestones,
            critical_events=critical_events,
            statistics=self._statistics(events, attack_stages, items),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        analysis.summary = self._summary(analysis)
        if persist:
            self._repo.save(case_id, self._cfg.timeline_report_name,
                            analysis.model_dump())
            self._audit.record(
                case_id, MODULE, "analyzed",
                f"{len(events)} event(s), stages={progression or 'none'}, "
                f"{len(critical_events)} critical",
                duration_ms=analysis.analysis_time_ms,
            )
        return analysis

    # ---------------------------------------------------------------- internal

    def _classify(self, context: EvidenceContext) -> tuple:
        """Stages present in one evidence item + the exact matched keywords."""
        text = (context.raw_text or "").lower()
        stages: List[str] = []
        matched: Dict[str, List[str]] = {}
        for stage in self._cfg.timeline_stage_order:
            keywords = self._cfg.timeline_stage_keywords.get(stage, ())
            hits = sorted({k.strip() for k in keywords if k in text})
            if hits:
                stages.append(stage)
                matched[stage] = hits
        return stages, matched

    def _critical(self, context: EvidenceContext) -> tuple:
        reasons: List[str] = []
        for entity_type in self._cfg.timeline_critical_entity_types:
            values = context.entity_values(entity_type)
            if values:
                reasons.append(
                    f"contains {entity_type} entity/entities: "
                    + ", ".join(sorted(set(values))[:3])
                )
        return bool(reasons), reasons

    def _attack_stages(self, stage_hits: Dict[str, Dict[str, List[str]]],
                       items: Sequence[EvidenceContext]) -> List[AttackStage]:
        upload = {c.evidence_id: c.upload_time for c in items}
        stages: List[AttackStage] = []
        for stage in self._cfg.timeline_stage_order:
            hits = stage_hits.get(stage)
            if not hits:
                continue
            evidence_ids = sorted(hits, key=lambda e: upload.get(e, ""))
            keywords = sorted({k for ks in hits.values() for k in ks})
            stages.append(AttackStage(
                stage=stage,
                evidence_ids=evidence_ids,
                first_seen=upload.get(evidence_ids[0], ""),
                last_seen=upload.get(evidence_ids[-1], ""),
                matched_keywords=keywords,
                explanation=(
                    f"Stage '{stage}' is evidenced by keyword matches "
                    f"({', '.join(keywords[:5])}) in the verbatim OCR text of "
                    + ", ".join(evidence_ids) + "."
                ),
            ))
        return stages

    @staticmethod
    def _progression(events: List[TimelineEvent]) -> List[str]:
        seen: List[str] = []
        for event in events:  # events are already chronological
            for stage in event.stages:
                if stage not in seen:
                    seen.append(stage)
        return seen

    def _is_consistent(self, progression: List[str]) -> bool:
        order = {s: i for i, s in enumerate(self._cfg.timeline_stage_order)}
        indices = [order[s] for s in progression if s in order]
        return indices == sorted(indices)

    def _milestones(self, events: List[TimelineEvent]) -> List[TimelineEvent]:
        milestones: List[TimelineEvent] = []
        seen_stages: set = set()
        if events:
            first = events[0]
            milestones.append(TimelineEvent(
                timestamp=first.timestamp, event_type="milestone",
                evidence_id=first.evidence_id,
                description="Investigation start - first evidence acquired",
            ))
        for event in events:
            for stage in event.stages:
                if stage in seen_stages:
                    continue
                seen_stages.add(stage)
                milestones.append(TimelineEvent(
                    timestamp=event.timestamp, event_type="milestone",
                    evidence_id=event.evidence_id, stages=[stage],
                    description=f"First observation of stage "
                                f"'{stage}' ({event.evidence_id})",
                ))
        return milestones

    @staticmethod
    def _statistics(events, attack_stages, items) -> Dict[str, float]:
        dts = sorted(d for d in (c.upload_datetime for c in items) if d)
        span_hours = ((dts[-1] - dts[0]).total_seconds() / 3600.0
                      if len(dts) >= 2 else 0.0)
        return {
            "event_count": float(len(events)),
            "stage_count": float(len(attack_stages)),
            "critical_event_count": float(sum(1 for e in events if e.critical)),
            "timeline_span_hours": round(span_hours, 2),
        }

    def _summary(self, analysis: TimelineAnalysis) -> str:
        parts = [
            f"{int(analysis.statistics.get('event_count', 0))} event(s) spanning "
            f"{analysis.statistics.get('timeline_span_hours', 0.0):.1f} hour(s)."
        ]
        if analysis.stage_progression:
            parts.append(
                "Observed scam progression: "
                + " -> ".join(analysis.stage_progression) + "."
            )
            parts.append(
                "The progression "
                + ("follows" if analysis.progression_consistent else
                   "deviates from")
                + " the canonical scam sequence."
            )
        if analysis.critical_events:
            parts.append(
                f"{len(analysis.critical_events)} critical event(s) involve "
                "OTP/financial entities."
            )
        return " ".join(parts)
