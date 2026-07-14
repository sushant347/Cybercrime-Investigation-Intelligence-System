"""Module 6 - Investigation Analytics Engine.

Aggregates every dimension of the case into machine-readable statistics:
entities, threats, brands, wallets, URLs, devices, metadata, campaigns,
timeline and evidence quality. Consumes only stored findings (Phase-1
reports + Phase-2 module outputs) - it computes nothing speculative.

Outputs: ``analytics.json`` (complete), plus the focused projections
``case_statistics.json`` and ``entity_statistics.json``.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Dict, List, Optional, Sequence

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..campaigns.models import CampaignAnalysis
from ..config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from ..timeline.models import TimelineAnalysis
from .models import CaseAnalytics, ValueCount

MODULE = "analytics"


class AnalyticsService:
    """Case-level aggregation of all forensic and investigative findings."""

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
        self._log = get_logger("investigation.analytics")

    # ------------------------------------------------------------------ public

    def generate(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        correlation: Optional[CorrelationAnalysis] = None,
        campaigns: Optional[CampaignAnalysis] = None,
        timeline: Optional[TimelineAnalysis] = None,
        *,
        persist: bool = True,
    ) -> CaseAnalytics:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)
        top_n = self._cfg.analytics_top_n

        entity_counts: Counter = Counter()
        values_by_type: Dict[str, Counter] = {}
        for context in items:
            for entity in context.entities:
                entity_counts[entity.entity_type] += 1
                values_by_type.setdefault(entity.entity_type, Counter())[
                    (entity.normalized or entity.value).lower()
                ] += 1

        analytics = CaseAnalytics(
            case_id=case_id,
            evidence_count=len(items),
            entity_statistics=dict(sorted(entity_counts.items())),
            top_entities={
                entity_type: _top(counter, top_n)
                for entity_type, counter in sorted(values_by_type.items())
            },
            threat_statistics=self._threat_statistics(items),
            brand_statistics=self._brand_statistics(items, top_n),
            wallet_statistics=_top(values_by_type.get("wallets", Counter()), top_n),
            url_statistics=_top(values_by_type.get("urls", Counter()), top_n),
            device_statistics=self._device_statistics(items, top_n),
            metadata_statistics=self._metadata_statistics(items),
            campaign_statistics=self._campaign_statistics(campaigns),
            timeline_statistics=dict(timeline.statistics) if timeline else {},
            evidence_quality_statistics=self._quality_statistics(items),
            correlation_statistics=self._correlation_statistics(correlation),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(case_id, self._cfg.analytics_report_name,
                            analytics.model_dump())
            self._repo.save(case_id, self._cfg.case_statistics_name, {
                "case_id": case_id,
                "evidence_count": analytics.evidence_count,
                "threat_statistics": analytics.threat_statistics,
                "campaign_statistics": analytics.campaign_statistics,
                "timeline_statistics": analytics.timeline_statistics,
                "evidence_quality_statistics": analytics.evidence_quality_statistics,
                "correlation_statistics": analytics.correlation_statistics,
                "metadata_statistics": analytics.metadata_statistics,
            })
            self._repo.save(case_id, self._cfg.entity_statistics_name, {
                "case_id": case_id,
                "entity_statistics": analytics.entity_statistics,
                "top_entities": {
                    k: [v.model_dump() for v in vs]
                    for k, vs in analytics.top_entities.items()
                },
            })
            self._audit.record(
                case_id, MODULE, "generated",
                f"{sum(entity_counts.values())} entities across "
                f"{len(entity_counts)} type(s)",
                duration_ms=analytics.analysis_time_ms,
            )
        return analytics

    # ---------------------------------------------------------------- internal

    def _threat_statistics(self, items: Sequence[EvidenceContext]) -> Dict[str, float]:
        intel = self._data.threat_intel
        flagged_values: set = set()
        flagged_evidence: set = set()
        checked = 0
        for context in items:
            for value in context.entity_values("urls") + context.entity_values("domains"):
                checked += 1
                if intel.available and intel.is_malicious(value):
                    flagged_values.add(value.lower())
                    flagged_evidence.add(context.evidence_id)
        return {
            "intel_available": 1.0 if intel.available else 0.0,
            "indicators_checked": float(checked),
            "malicious_indicators": float(len(flagged_values)),
            "evidence_with_threats": float(len(flagged_evidence)),
            "threat_evidence_ratio": round(
                len(flagged_evidence) / len(items), 4
            ) if items else 0.0,
        }

    @staticmethod
    def _brand_statistics(items: Sequence[EvidenceContext], top_n: int
                          ) -> List[ValueCount]:
        counter: Counter = Counter()
        for context in items:
            logos = context.forensics.get("logo_detections", {}) or {}
            for brand in logos.get("detected_brands", []):
                counter[str(brand)] += 1
        return _top(counter, top_n)

    @staticmethod
    def _device_statistics(items: Sequence[EvidenceContext], top_n: int
                           ) -> List[ValueCount]:
        counter: Counter = Counter()
        for context in items:
            image = (context.forensics.get("metadata_report", {}) or {}).get("image") or {}
            device = str(image.get("device", "") or "").strip()
            if device:
                counter[device] += 1
        return _top(counter, top_n)

    @staticmethod
    def _metadata_statistics(items: Sequence[EvidenceContext]) -> Dict[str, float]:
        with_exif = with_gps = with_software = have_report = 0
        for context in items:
            metadata = context.forensics.get("metadata_report")
            if not metadata:
                continue
            have_report += 1
            image = metadata.get("image") or {}
            if image.get("has_exif"):
                with_exif += 1
            if image.get("software"):
                with_software += 1
            gps = image.get("gps") or {}
            if gps.get("latitude") is not None:
                with_gps += 1
        return {
            "evidence_with_metadata_report": float(have_report),
            "evidence_with_exif": float(with_exif),
            "evidence_with_gps": float(with_gps),
            "evidence_with_editing_software": float(with_software),
        }

    @staticmethod
    def _campaign_statistics(campaigns: Optional[CampaignAnalysis]) -> Dict[str, float]:
        if campaigns is None:
            return {}
        sizes = [len(c.members) for c in campaigns.campaigns]
        return {
            "campaign_count": float(campaigns.campaign_count),
            "largest_campaign_size": float(max(sizes) if sizes else 0),
            "clustered_evidence": float(sum(sizes)),
            "unclustered_evidence": float(len(campaigns.unclustered_evidence)),
            "mean_campaign_confidence": round(
                sum(c.campaign_confidence for c in campaigns.campaigns)
                / len(campaigns.campaigns), 4
            ) if campaigns.campaigns else 0.0,
        }

    @staticmethod
    def _quality_statistics(items: Sequence[EvidenceContext]) -> Dict[str, float]:
        quality_scores: List[float] = []
        confidence_scores: List[float] = []
        forgery_scores: List[float] = []
        for context in items:
            quality = context.forensics.get("quality_report") or {}
            if "overall_score" in quality:
                quality_scores.append(float(quality["overall_score"]))
            confidence = context.forensics.get("evidence_confidence") or {}
            if "confidence_score" in confidence:
                confidence_scores.append(float(confidence["confidence_score"]))
            forgery = context.forensics.get("forgery_report") or {}
            if "forgery_score" in forgery:
                forgery_scores.append(float(forgery["forgery_score"]))

        def mean(values: List[float]) -> float:
            return round(sum(values) / len(values), 2) if values else 0.0

        return {
            "mean_image_quality": mean(quality_scores),
            "mean_evidence_confidence": mean(confidence_scores),
            "mean_forgery_score": mean(forgery_scores),
            "max_forgery_score": round(max(forgery_scores), 2) if forgery_scores else 0.0,
            "mean_ocr_confidence": mean([c.ocr_confidence for c in items]),
            "hash_verified_count": float(
                sum(1 for c in items if c.hash_verified is True)
            ),
        }

    @staticmethod
    def _correlation_statistics(correlation: Optional[CorrelationAnalysis]
                                ) -> Dict[str, float]:
        if correlation is None:
            return {}
        confidences = [p.correlation_confidence for p in correlation.pairs]
        return {
            "pair_count": float(correlation.pair_count),
            "related_pair_count": float(correlation.related_pair_count),
            "mean_confidence": round(
                sum(confidences) / len(confidences), 4
            ) if confidences else 0.0,
            "max_confidence": round(max(confidences), 4) if confidences else 0.0,
        }


def _top(counter: Counter, n: int) -> List[ValueCount]:
    return [ValueCount(value=value, count=count)
            for value, count in counter.most_common(n)]
