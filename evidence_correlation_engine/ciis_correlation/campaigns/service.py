"""Module 3 - Scam Campaign Clustering Engine.

Campaigns are connected components over the Module-1 correlation graph,
using only pairs whose confidence clears the configured threshold. The
clustering is therefore fully explainable: an item is in a campaign because
of concrete weighted links (shared wallets/phones/domains, threat-intel
corroboration, temporal proximity, metadata) - each membership carries the
exact links and reasons.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence, Set

from backend.modules.evidence.logger import get_logger
from ..core.audit import InvestigationAuditTrail
from ..core.config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis, EvidencePairCorrelation
from ..core.data_access import CaseDataRepository, EvidenceContext
from ..core.repository import InvestigationReportRepository
from .models import Campaign, CampaignAnalysis, CampaignMembership
from ..core.text import count_of

MODULE = "campaigns"


class CampaignService:
    """Explainable campaign clustering over correlated evidence."""

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
        self._log = get_logger("investigation.campaigns")

    # ------------------------------------------------------------------ public

    def cluster(
        self,
        case_id: str,
        correlation: CorrelationAnalysis,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> CampaignAnalysis:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)
        by_id = {e.evidence_id: e for e in items}

        strong_pairs = [
            p for p in correlation.pairs
            if p.correlation_confidence >= self._cfg.campaign_min_confidence
        ]
        components = self._connected_components(
            [e.evidence_id for e in items], strong_pairs
        )

        campaigns: List[Campaign] = []
        clustered: Set[str] = set()
        index = 0
        for component in components:
            if len(component) < self._cfg.campaign_min_members:
                continue
            index += 1
            campaign = self._build_campaign(
                case_id, index, sorted(component), strong_pairs, by_id
            )
            campaigns.append(campaign)
            clustered.update(component)

        analysis = CampaignAnalysis(
            case_id=case_id,
            campaign_count=len(campaigns),
            campaigns=campaigns,
            unclustered_evidence=sorted(
                e.evidence_id for e in items if e.evidence_id not in clustered
            ),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(case_id, self._cfg.campaign_report_name,
                            analysis.model_dump())
            self._audit.record(
                case_id, MODULE, "clustered",
                f"{count_of(analysis.campaign_count, 'campaign')}, "
                f"{count_of(len(analysis.unclustered_evidence), 'unclustered item')}",
                duration_ms=analysis.analysis_time_ms,
            )
        return analysis

    # ---------------------------------------------------------------- builders

    def _build_campaign(
        self,
        case_id: str,
        index: int,
        members: List[str],
        pairs: List[EvidencePairCorrelation],
        by_id: Dict[str, EvidenceContext],
    ) -> Campaign:
        member_set = set(members)
        internal = [p for p in pairs
                    if p.evidence_a in member_set and p.evidence_b in member_set]
        confidence = round(
            sum(p.correlation_confidence for p in internal) / len(internal), 4
        ) if internal else 0.0

        memberships = [
            self._membership(member, internal) for member in members
        ]
        signature = self._signature(members, by_id)
        brands = self._shared_values(
            members, by_id,
            lambda c: (c.forensics.get("logo_detections", {}) or {})
            .get("detected_brands", []),
        )
        domains = self._shared_values(
            members, by_id, lambda c: c.entity_values("domains")
        )
        times = sorted(
            t for t in (by_id[m].upload_time for m in members if m in by_id) if t
        )
        contexts = [by_id[m] for m in members if m in by_id]
        campaign = Campaign(
            campaign_id=f"{self._cfg.campaign_id_prefix}_{case_id}_{index:02d}",
            case_id=case_id,
            members=members,
            memberships=memberships,
            campaign_confidence=confidence,
            signature=signature,
            shared_brands=brands,
            shared_domains=domains,
            timeline_start=times[0] if times else "",
            timeline_end=times[-1] if times else "",
            statistics={
                "member_count": float(len(members)),
                "internal_links": float(len(internal)),
                "mean_link_confidence": confidence,
                "mean_ocr_confidence": round(
                    sum(c.ocr_confidence for c in contexts) / len(contexts), 4
                ) if contexts else 0.0,
            },
        )
        campaign.summary = self._summary(campaign)
        return campaign

    def _membership(self, member: str,
                    internal: List[EvidencePairCorrelation]) -> CampaignMembership:
        linked_via: List[str] = []
        reasons: List[str] = []
        for pair in internal:
            if member not in (pair.evidence_a, pair.evidence_b):
                continue
            other = pair.evidence_b if pair.evidence_a == member else pair.evidence_a
            linked_via.append(other)
            top = pair.correlation_reasons[0] if pair.correlation_reasons else \
                f"{pair.relationship_strength} correlation"
            reasons.append(f"linked to {other}: {top} "
                           f"(confidence {pair.correlation_confidence:.2f})")
        explanation = (
            f"{member} belongs to this campaign through "
            f"{count_of(len(linked_via), 'weighted correlation link')}: "
            + "; ".join(reasons[:3])
            + ("." if len(reasons) <= 3 else f"; and {len(reasons) - 3} more.")
        ) if linked_via else f"{member} has no internal links."
        return CampaignMembership(
            evidence_id=member,
            linked_via=sorted(set(linked_via)),
            link_reasons=reasons,
            membership_explanation=explanation,
        )

    def _signature(self, members: List[str],
                   by_id: Dict[str, EvidenceContext]) -> List[str]:
        """Entities appearing in at least two campaign members."""
        counts: Dict[str, int] = {}
        for member in members:
            context = by_id.get(member)
            if context is None:
                continue
            seen: Set[str] = set()
            for entity in context.entities:
                key = f"{entity.entity_type}:{(entity.normalized or entity.value).lower()}"
                if key not in seen:
                    seen.add(key)
                    counts[key] = counts.get(key, 0) + 1
        shared = [k for k, v in counts.items() if v >= 2]
        shared.sort(key=lambda k: (-counts[k], k))
        return shared[: self._cfg.campaign_signature_entities]

    @staticmethod
    def _shared_values(members, by_id, getter) -> List[str]:
        counts: Dict[str, int] = {}
        for member in members:
            context = by_id.get(member)
            if context is None:
                continue
            for value in {str(v).lower() for v in getter(context)}:
                counts[value] = counts.get(value, 0) + 1
        return sorted(v for v, n in counts.items() if n >= 2)

    @staticmethod
    def _summary(campaign: Campaign) -> str:
        parts = [
            f"Campaign {campaign.campaign_id} groups "
            f"{count_of(len(campaign.members), 'evidence item')} with mean link "
            f"confidence {campaign.campaign_confidence:.2f}."
        ]
        if campaign.signature:
            parts.append("Shared indicators: " + ", ".join(campaign.signature) + ".")
        if campaign.shared_brands:
            parts.append("Impersonated/used brands: "
                         + ", ".join(campaign.shared_brands) + ".")
        if campaign.timeline_start:
            parts.append(f"Active {campaign.timeline_start} to "
                         f"{campaign.timeline_end}.")
        return " ".join(parts)

    # ---------------------------------------------------------------- clustering

    @staticmethod
    def _connected_components(
        node_ids: List[str], pairs: List[EvidencePairCorrelation]
    ) -> List[Set[str]]:
        adjacency: Dict[str, Set[str]] = {n: set() for n in node_ids}
        for pair in pairs:
            if pair.evidence_a in adjacency and pair.evidence_b in adjacency:
                adjacency[pair.evidence_a].add(pair.evidence_b)
                adjacency[pair.evidence_b].add(pair.evidence_a)
        seen: Set[str] = set()
        components: List[Set[str]] = []
        for start in node_ids:
            if start in seen:
                continue
            stack, component = [start], set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                component.add(node)
                stack.extend(adjacency[node] - seen)
            components.append(component)
        return components
