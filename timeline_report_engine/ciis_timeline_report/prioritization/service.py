"""Module 8 - Case Prioritization Engine.

Deterministic weighted priority over six dimensions (evidence confidence,
threat intelligence, forgery risk, campaign size, correlation strength,
timeline criticality). Missing dimensions drop out with weight
renormalisation, mirroring the Phase-1 confidence engine. Fully explainable:
each component carries its own justification and the final score comes with
high-risk indicators plus an investigation recommendation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.modules.evidence.logger import get_logger
from backend.modules.evidence.utils import utc_now_iso
from ..analytics.models import CaseAnalytics
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.campaigns.models import CampaignAnalysis
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.correlation.models import CorrelationAnalysis
from ciis_correlation.core.repository import InvestigationReportRepository
from ..timeline.models import TimelineAnalysis
from .models import CasePriority, PriorityComponent

MODULE = "prioritization"


class PrioritizationService:
    """Explainable weighted case priority."""

    def __init__(
        self,
        config: InvestigationConfig,
        repository: InvestigationReportRepository,
        audit: InvestigationAuditTrail,
    ) -> None:
        self._cfg = config
        self._repo = repository
        self._audit = audit
        self._log = get_logger("investigation.priority")

    # ------------------------------------------------------------------ public

    def prioritize(
        self,
        case_id: str,
        *,
        analytics: Optional[CaseAnalytics] = None,
        correlation: Optional[CorrelationAnalysis] = None,
        campaigns: Optional[CampaignAnalysis] = None,
        timeline: Optional[TimelineAnalysis] = None,
        persist: bool = True,
    ) -> CasePriority:
        cfg = self._cfg
        quality = analytics.evidence_quality_statistics if analytics else {}
        threat = analytics.threat_statistics if analytics else {}
        components: List[PriorityComponent] = []
        indicators: List[str] = []

        def add(name: str, score: Optional[float], explanation: str) -> None:
            components.append(PriorityComponent(
                name=name,
                score=round(min(100.0, max(0.0, score)), 1) if score is not None else 0.0,
                weight=cfg.priority_weights.get(name, 0.0),
                available=score is not None,
                explanation=explanation if score is not None
                else "input not available",
            ))

        mean_conf = quality.get("mean_evidence_confidence")
        add("evidence_confidence",
            mean_conf if mean_conf else None,
            f"mean Phase-1 evidence confidence {mean_conf}" if mean_conf else "")

        threat_score = None
        if threat.get("intel_available"):
            ratio = float(threat.get("threat_evidence_ratio", 0.0))
            threat_score = ratio * 100.0
            if threat.get("malicious_indicators", 0) > 0:
                indicators.append(
                    f"{int(threat['malicious_indicators'])} threat-flagged "
                    "indicator(s) present in the evidence"
                )
        add("threat_intelligence", threat_score,
            f"{threat.get('threat_evidence_ratio', 0):.0%} of evidence touches "
            "flagged indicators" if threat_score is not None else "")

        forgery_score = None
        max_forgery = quality.get("max_forgery_score")
        if max_forgery is not None and quality:
            forgery_score = float(max_forgery)
            if forgery_score >= 50.0:
                indicators.append(
                    f"possible evidence tampering (max forgery score "
                    f"{forgery_score:.0f}/100)"
                )
        add("forgery_risk", forgery_score,
            f"max Phase-1 forgery score {max_forgery}"
            if forgery_score is not None else "")

        campaign_score = None
        if campaigns is not None:
            sizes = [len(c.members) for c in campaigns.campaigns]
            largest = max(sizes) if sizes else 0
            campaign_score = min(100.0,
                                 largest / cfg.priority_campaign_full_size * 100.0)
            if largest >= cfg.priority_campaign_full_size:
                indicators.append(
                    f"large coordinated campaign of {largest} evidence item(s)"
                )
        add("campaign_size", campaign_score,
            f"largest campaign groups "
            f"{max((len(c.members) for c in campaigns.campaigns), default=0)} "
            "item(s)" if campaigns is not None else "")

        correlation_score = None
        if correlation is not None and correlation.pairs:
            confidences = [p.correlation_confidence for p in correlation.pairs]
            correlation_score = max(confidences) * 100.0
        add("correlation_strength", correlation_score,
            f"strongest evidence-pair confidence "
            f"{max((p.correlation_confidence for p in correlation.pairs), default=0):.2f}"
            if correlation is not None and correlation.pairs else "")

        timeline_score = None
        if timeline is not None:
            critical = len(timeline.critical_events)
            timeline_score = min(100.0,
                                 critical / cfg.priority_critical_events_full * 100.0)
            if critical:
                indicators.append(
                    f"{critical} critical event(s) involving OTP/financial entities"
                )
        add("timeline_criticality", timeline_score,
            f"{len(timeline.critical_events)} critical timeline event(s)"
            if timeline is not None else "")

        available = [c for c in components if c.available]
        total_weight = sum(c.weight for c in available)
        score = round(
            sum(c.score * c.weight for c in available) / total_weight, 1
        ) if total_weight > 0 else 0.0
        level = self._band(score)

        priority = CasePriority(
            case_id=case_id,
            components=components,
            priority_score=score,
            priority_level=level,
            high_risk_indicators=indicators,
            investigation_recommendation=self._recommendation(level, indicators),
            explanation=self._explanation(score, level, available),
            computed_at=utc_now_iso(),
        )
        if persist:
            self._repo.save(case_id, self._cfg.priority_report_name,
                            priority.model_dump())
            self._audit.record(
                case_id, MODULE, "prioritized",
                f"score={score} level={level} indicators={len(indicators)}",
            )
        return priority

    # ---------------------------------------------------------------- helpers

    def _band(self, score: float) -> str:
        for level, ceiling in self._cfg.priority_bands.items():
            if score < ceiling:
                return level
        return "CRITICAL"

    @staticmethod
    def _recommendation(level: str, indicators: List[str]) -> str:
        if level == "CRITICAL":
            return ("Immediate escalation recommended: assign a lead "
                    "investigator and initiate legal preservation requests now.")
        if level == "HIGH":
            return ("Expedite: schedule active investigation within 48 hours; "
                    "high-risk indicators warrant prompt action.")
        if level == "MEDIUM":
            return ("Standard queue: process in normal rotation while "
                    "monitoring for new linked evidence.")
        return ("Low urgency: archive-ready unless new evidence raises the "
                "correlation or threat picture.")

    @staticmethod
    def _explanation(score: float, level: str,
                     available: List[PriorityComponent]) -> str:
        parts = [
            f"Case priority is {score:.1f}/100 ({level}), computed from "
            f"{len(available)} available dimension(s) with renormalised weights."
        ]
        for component in sorted(available, key=lambda c: c.score * c.weight,
                                reverse=True):
            parts.append(
                f"{component.name.replace('_', ' ').capitalize()}: "
                f"{component.score:.0f}/100 (weight {component.weight:.2f})"
                + (f" - {component.explanation}" if component.explanation else "")
                + "."
            )
        return " ".join(parts)
