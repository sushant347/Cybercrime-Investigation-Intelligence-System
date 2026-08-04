"""Phase-2 orchestrator: runs all eight investigation modules for one case.

Dependency order::

    load evidence (read-only)
      -> M1 correlation
      -> M5 timeline            (canonical standalone reconstruction)
           -> M2 graph          (uses correlation + reconstructed events)
           -> M3 campaigns      (clusters over strong correlations)
           -> M4 suspects       (uses correlation for relationship strength)
      -> M6 analytics           (uses correlation, campaigns, timeline)
      -> M8 priority            (uses analytics, correlation, campaigns, timeline)
      -> M7 report              (references every stored finding, incl. priority)

Each module is failure-isolated (one broken analysis never aborts the case)
and everything is audited. All collaborators are injected; use
:func:`build_default_pipeline` as the composition root.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.logger import get_logger
from backend.modules.evidence.utils import EvidenceError
from .analytics.service import AnalyticsService
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.campaigns.service import CampaignService
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.correlation.service import CorrelationService
from ciis_correlation.core.data_access import CaseDataRepository, ThreatIntelProvider
from .graph.service import GraphService
from .prioritization.service import PrioritizationService
from .reporting.service import InvestigationReportService
from ciis_correlation.core.repository import InvestigationReportRepository
from ciis_correlation.suspects.service import SuspectService
from .timeline.service import TimelineService
from ciis_correlation.core.text import count_of

MODULE = "phase2_pipeline"


class InvestigationPipeline:
    """End-to-end Phase-2 analysis for one case."""

    def __init__(
        self,
        config: InvestigationConfig,
        *,
        data: CaseDataRepository,
        correlation: CorrelationService,
        graph: GraphService,
        campaigns: CampaignService,
        suspects: SuspectService,
        timeline: TimelineService,
        analytics: AnalyticsService,
        reporting: InvestigationReportService,
        prioritization: PrioritizationService,
        audit: InvestigationAuditTrail,
    ) -> None:
        self._cfg = config
        self._data = data
        self._correlation = correlation
        self._graph = graph
        self._campaigns = campaigns
        self._suspects = suspects
        self._timeline = timeline
        self._analytics = analytics
        self._reporting = reporting
        self._prioritization = prioritization
        self._audit = audit
        self._log = get_logger("investigation.pipeline")

    # ------------------------------------------------------------------ public

    def analyze_case(self, case_id: str) -> Dict[str, Any]:
        """Run all eight modules; returns every result keyed by module."""
        started = time.perf_counter()
        if not self._data.case_exists(case_id):
            raise EvidenceError(f"Unknown case '{case_id}'")
        evidence = self._data.load_case_evidence(case_id)
        self._audit.record(case_id, MODULE, "started",
                           f"{count_of(len(evidence), 'evidence item')}")

        results: Dict[str, Any] = {}
        failures: List[str] = []

        def safe(name: str, action: Callable[[], Any]) -> Any:
            try:
                return action()
            except Exception as exc:  # noqa: BLE001 - isolation by design
                failures.append(f"{name}: {exc}")
                self._audit.record(case_id, MODULE, name,
                                   f"failed: {exc}", level="ERROR")
                self._log.exception("module '%s' failed for %s", name, case_id)
                return None

        # Persist this case's entities to the cross-case index *before* any
        # correlation, so a case analysed later can match against them.
        safe("cross_case_index",
             lambda: self._correlation.index_case_entities(case_id, evidence))

        results["correlation"] = safe(
            "correlation",
            lambda: self._correlation.analyze_case(case_id, evidence))
        results["cross_case"] = safe(
            "cross_case",
            lambda: self._run_cross_case(case_id, evidence))
        results["timeline"] = safe(
            "timeline",
            lambda: self._timeline.analyze(
                case_id, evidence, results["correlation"]
            ))
        results["graph"] = safe(
            "graph",
            lambda: self._graph.build(
                case_id,
                results["correlation"],
                evidence,
                timeline=results["timeline"],
                cross_case=results["cross_case"],
            ))
        if results["correlation"] is not None:
            results["campaigns"] = safe(
                "campaigns",
                lambda: self._campaigns.cluster(case_id, results["correlation"],
                                                evidence))
        else:
            results["campaigns"] = None
        results["suspects"] = safe(
            "suspects",
            lambda: self._suspects.assess(case_id, results["correlation"], evidence))
        results["analytics"] = safe(
            "analytics",
            lambda: self._analytics.generate(
                case_id, evidence, results["correlation"],
                results["campaigns"], results["timeline"]))
        results["priority"] = safe(
            "priority",
            lambda: self._prioritization.prioritize(
                case_id,
                analytics=results["analytics"],
                correlation=results["correlation"],
                campaigns=results["campaigns"],
                timeline=results["timeline"]))
        results["report"] = safe(
            "report",
            lambda: self._reporting.generate(
                case_id,
                evidence=evidence,
                correlation=results["correlation"],
                cross_case=results["cross_case"],
                campaigns=results["campaigns"],
                suspects=results["suspects"],
                timeline=results["timeline"],
                analytics=results["analytics"],
                priority=(results["priority"].model_dump()
                          if results["priority"] is not None else None)))

        # Bidirectional propagation: refresh the cross-case artifact and report
        # of every case this one now links to, so links appear on both sides.
        safe("cross_case_propagation",
             lambda: self._propagate_cross_case(case_id, results["cross_case"]))

        total_ms = round((time.perf_counter() - started) * 1000.0, 1)
        self._audit.record(
            case_id, MODULE, "completed",
            f"modules_ok={sorted(k for k, v in results.items() if v is not None)} "
            f"failures={failures or 'none'}",
            level="WARNING" if failures else "INFO",
            duration_ms=total_ms,
        )
        results["failures"] = failures
        return results

    def refresh_timeline_graph(self, case_id: str) -> Dict[str, Any]:
        """Refresh only entity relationships, timeline and graph artifacts.

        This focused path is used immediately after evidence enrichment.  It
        deliberately does not invoke campaigns, suspects, analytics, priority,
        report generation, or cross-case report propagation.
        """
        if not self._data.case_exists(case_id):
            raise EvidenceError(f"Unknown case '{case_id}'")
        evidence = self._data.load_case_evidence(case_id)
        self._correlation.index_case_entities(case_id, evidence)
        correlation = self._correlation.analyze_case(case_id, evidence)
        cross_case = self._run_cross_case(case_id, evidence)
        timeline = self._timeline.analyze(case_id, evidence, correlation)
        graph = self._graph.build(
            case_id,
            correlation,
            evidence,
            timeline=timeline,
            cross_case=cross_case,
        )
        self._audit.record(
            case_id,
            MODULE,
            "timeline_graph_refreshed",
            f"{count_of(len(evidence), 'evidence item')}, {count_of(len(timeline.events), 'event')}, "
            f"{count_of(len(graph.nodes), 'graph node')}",
        )
        return {
            "correlation": correlation,
            "cross_case": cross_case,
            "timeline": timeline,
            "graph": graph,
        }

    # ------------------------------------------------------------ cross-case

    def _run_cross_case(self, case_id, evidence):
        """Compute and persist this case's cross-case correlation."""
        correlation = self._correlation.correlate_cross_case(case_id, evidence)
        self._correlation.persist_cross_case(case_id, correlation)
        return correlation

    def _propagate_cross_case(self, case_id, cross_case) -> List[str]:
        """Update every case newly linked to this one (one hop, no recursion).

        For each linked case we recompute its cross-case artifact from the
        shared index; only when that artifact actually changes do we regenerate
        that case's report. This makes a new match appear on both cases while
        preventing duplicate correlations and runaway report versions.
        """
        if cross_case is None:
            return []
        updated: List[str] = []
        for other_case_id in cross_case.related_case_ids:
            other = self._correlation.correlate_cross_case(other_case_id)
            if self._correlation.persist_cross_case(other_case_id, other):
                self._reporting.regenerate_with_cross_case(other_case_id, other)
                updated.append(other_case_id)
        if updated:
            self._audit.record(
                case_id, MODULE, "cross_case_propagated",
                f"updated {count_of(len(updated), 'linked case')}: {', '.join(updated)}")
        return updated

    def analyze_all_cases(self) -> Dict[str, Dict[str, Any]]:
        """Convenience: run the full analysis for every known case."""
        return {case_id: self.analyze_case(case_id)
                for case_id in self._data.list_case_ids()}


# --------------------------------------------------------------------------- #
# Composition root
# --------------------------------------------------------------------------- #


def build_default_pipeline(
    evidence_config: Optional[EvidenceConfig] = None,
    investigation_config: Optional[InvestigationConfig] = None,
    *,
    threat_intel: Optional[ThreatIntelProvider] = None,
) -> InvestigationPipeline:
    """Wire every Phase-2 service with production defaults (DI root)."""
    ecfg = evidence_config or EvidenceConfig.from_env()
    icfg = investigation_config or InvestigationConfig.from_env(ecfg)
    icfg.ensure_directories()

    data = CaseDataRepository(icfg, threat_intel=threat_intel)
    repository = InvestigationReportRepository(icfg)
    audit = InvestigationAuditTrail(icfg)
    return InvestigationPipeline(
        icfg,
        data=data,
        correlation=CorrelationService(icfg, data, repository, audit),
        graph=GraphService(icfg, data, repository, audit),
        campaigns=CampaignService(icfg, data, repository, audit),
        suspects=SuspectService(icfg, data, repository, audit),
        timeline=TimelineService(icfg, data, repository, audit),
        analytics=AnalyticsService(icfg, data, repository, audit),
        reporting=InvestigationReportService(icfg, data, repository, audit),
        prioritization=PrioritizationService(icfg, repository, audit),
        audit=audit,
    )
