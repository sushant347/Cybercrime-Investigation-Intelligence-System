"""Module 1 - Advanced Evidence Correlation Engine.

Upgrades exact entity matching into an explainable weighted framework. For
every evidence pair inside a case the engine evaluates twelve factor types
(shared phones/URLs/domains/emails/wallets/bank accounts/social accounts,
device & image metadata, file hashes, timeline proximity, threat-intel
corroboration), producing a weight, a bounded confidence, a relationship
level and a complete narrative explanation with the concrete supporting
values.

Scoring is  type weight x value specificity, summed over shared values and
squashed into a bounded confidence. The type weight says how identifying a
*kind* of entity is; the specificity - learned from the corpus, see
``specificity.py`` - says how identifying *this particular value* is. Without
the second term, "both items mention NPR 2,000" scored exactly like "both
items mention the same wallet address", which linked essentially every case
in a corpus to every other one on round amounts alone.

On the absence of a supervised model: correlation has no ground truth to
train against. Nobody has labelled which evidence pairs are genuinely related,
and manufacturing those labels would produce a classifier whose confident
output means nothing. The learning that *is* justified by the available data
is unsupervised - estimating how common each value is across the corpus - and
that is what runs here. A supervised ranker would become appropriate once
investigators have confirmed or rejected enough links for those decisions to
serve as labels; the per-factor breakdown persisted in every artifact is
already the feature vector such a model would consume.
"""

from __future__ import annotations

import math
import time
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from backend.modules.evidence.logger import get_logger
from ..core.audit import InvestigationAuditTrail
from ..core.config import InvestigationConfig
from ..crosscase import CrossCaseEntityIndex
from ..core.data_access import CaseDataRepository, EvidenceContext
from ..core.repository import InvestigationReportRepository
from .models import (
    CorrelationAnalysis,
    CorrelationFactor,
    CrossCaseCorrelation,
    CrossCaseEntityMatch,
    CrossCaseLink,
    EvidencePairCorrelation,
    SharedValueDetail,
)
from .specificity import EntitySpecificityModel

MODULE = "correlation"
CROSS_CASE_MODULE = "cross_case_correlation"


class CorrelationService:
    """Explainable weighted correlation across all evidence of a case."""

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
        self._log = get_logger("investigation.correlation")
        self._index = CrossCaseEntityIndex(
            config.entities_csv,
            legacy_index_path=config.cross_case_index_path,
            # Ignore entity rows whose case has no evidence left, so a stale
            # row can never resurrect a deleted case in cross-correlation.
            evidence_csv=config.evidence_csv,
        )
        # Reads corpus statistics straight off the index above, so rarity is
        # always judged against the same entity view correlation matches on.
        self._specificity = EntitySpecificityModel(config, self._index)

    # ------------------------------------------------------------------ public

    def analyze_case(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> CorrelationAnalysis:
        """Correlate every evidence pair of a case."""
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        pairs: List[EvidencePairCorrelation] = []
        for a, b in combinations(items, 2):
            pairs.append(self.correlate_pair(a, b))
        pairs.sort(key=lambda p: p.correlation_confidence, reverse=True)

        distribution: Dict[str, int] = {}
        for pair in pairs:
            distribution[pair.relationship_strength] = \
                distribution.get(pair.relationship_strength, 0) + 1

        analysis = CorrelationAnalysis(
            case_id=case_id,
            evidence_ids=[e.evidence_id for e in items],
            pair_count=len(pairs),
            related_pair_count=sum(
                1 for p in pairs if p.relationship_strength != "NO_RELATIONSHIP"
            ),
            pairs=pairs,
            strength_distribution=distribution,
            strongest_pair=(
                f"{pairs[0].evidence_a}|{pairs[0].evidence_b}" if pairs else ""
            ),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if persist:
            self._repo.save(case_id, self._cfg.correlation_report_name,
                            analysis.model_dump())
            self._audit.record(
                case_id, MODULE, "analyzed",
                f"{analysis.related_pair_count}/{analysis.pair_count} related pairs, "
                f"strongest={analysis.strongest_pair or 'none'}",
                duration_ms=analysis.analysis_time_ms,
            )
        return analysis

    # ------------------------------------------------------- cross-case (M1+)

    @property
    def index(self) -> CrossCaseEntityIndex:
        """The persistent cross-case entity index this service maintains."""
        return self._index

    def index_case_entities(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
    ) -> int:
        """Ensure this case's entities are visible to cross-case lookups.

        Entities are written once by the cleaning stage into the single
        ``entities.csv``; there is no second index to populate. This refreshes
        the cached view so a case analysed moments ago is immediately matchable,
        and returns the number of entity occurrences the case contributes.
        """
        self._index.refresh()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)
        return sum(len(context.entities) for context in items)

    def correlate_cross_case(
        self,
        case_id: str,
        evidence: Optional[Sequence[EvidenceContext]] = None,
    ) -> CrossCaseCorrelation:
        """Link this case to every other case that shares normalized entities.

        Pure computation over the persistent index (no persistence here). Only
        entity types with a configured correlation weight participate, so the
        cross-case confidence sits on the same explainable scale as within-case
        correlation. Call :meth:`persist_cross_case` to store the result.
        """
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        # (entity_type, normalized) -> set of this-case evidence ids
        entity_types = set(self._cfg.correlation_entity_types)
        own: Dict[Tuple[str, str], set] = {}
        for context in items:
            for entity in context.entities:
                if entity.entity_type not in entity_types:
                    continue  # dates/times/... are not actor identifiers
                normalized = (entity.normalized or entity.value or "").strip().lower()
                if not normalized:
                    continue
                own.setdefault((entity.entity_type, normalized), set()).add(
                    context.evidence_id
                )

        # other_case_id -> {(type, value): {"this": set, "other": set}}
        grouped: Dict[str, Dict[Tuple[str, str], Dict[str, set]]] = {}
        for (entity_type, normalized), this_ids in own.items():
            for occ in self._index.occurrences_in_other_cases(
                entity_type, normalized, case_id
            ):
                slot = grouped.setdefault(occ.case_id, {}).setdefault(
                    (entity_type, normalized), {"this": set(), "other": set()}
                )
                slot["this"].update(this_ids)
                slot["other"].add(occ.evidence_id)

        links: List[CrossCaseLink] = []
        dropped = 0
        for other_case_id, matches in grouped.items():
            if len(matches) < self._cfg.cross_case_min_shared_entities:
                continue
            link = self._build_cross_case_link(other_case_id, matches)
            # A link resting entirely on values the whole corpus shares is not
            # a link. Reporting it named an unrelated case in this one's report
            # and dragged its own analysis into that case's re-analysis, so the
            # noise propagated. The shared values are still visible in the
            # correlation artifact - they are simply not grounds for a link.
            if link.relationship_strength == "NO_RELATIONSHIP":
                dropped += 1
                continue
            links.append(link)
        links.sort(key=lambda link: link.match_confidence, reverse=True)
        if dropped:
            self._log.info(
                "cross-case: dropped %d candidate link(s) for %s supported only "
                "by corpus-wide values", dropped, case_id,
            )

        return CrossCaseCorrelation(
            case_id=case_id,
            related_case_ids=[link.other_case_id for link in links],
            link_count=len(links),
            links=links,
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )

    def persist_cross_case(
        self, case_id: str, correlation: CrossCaseCorrelation
    ) -> bool:
        """Store the cross-case artifact, but only if it actually changed.

        Returns ``True`` when a new version was written. Skipping unchanged
        results prevents duplicate correlations and runaway report versions
        during bidirectional propagation.
        """
        latest = self._repo.load_latest(case_id, self._cfg.cross_case_report_name)
        if latest is not None:
            previous = CrossCaseCorrelation.model_validate(latest["report"])
            if previous.stable_payload() == correlation.stable_payload():
                return False
        self._repo.save(case_id, self._cfg.cross_case_report_name,
                        correlation.model_dump())
        self._audit.record(
            case_id, CROSS_CASE_MODULE, "linked",
            f"{correlation.link_count} related case(s): "
            f"{', '.join(correlation.related_case_ids) or 'none'}",
            duration_ms=correlation.analysis_time_ms,
        )
        return True

    def _build_cross_case_link(
        self,
        other_case_id: str,
        matches: Dict[Tuple[str, str], Dict[str, set]],
    ) -> CrossCaseLink:
        cfg = self._cfg
        matched_entities: List[CrossCaseEntityMatch] = []
        this_ids: set = set()
        other_ids: set = set()

        # Specificity-weighted sum with a per-type cap, mirroring within-case
        # scoring. Ordering by specificity matters here for the same reason it
        # does within a case: two cases that share one scammer wallet and four
        # round amounts must be linked on the wallet, and the cap must not
        # spend itself on the amounts.
        scored = sorted(
            (
                (key, sides, self._specificity.specificity(key[0], key[1]))
                for key, sides in matches.items()
            ),
            key=lambda item: (-item[2].specificity, item[0]),
        )

        per_type_count: Dict[str, int] = {}
        weight_sum = 0.0
        for (entity_type, normalized), sides, score in scored:
            weight = cfg.correlation_weights.get(entity_type, 0.0)
            matched_entities.append(CrossCaseEntityMatch(
                entity_type=entity_type,
                value=normalized,
                weight=weight,
                specificity=score.specificity,
                document_frequency=score.document_frequency,
                specificity_reason=score.reason,
                this_evidence_ids=sorted(sides["this"]),
                other_evidence_ids=sorted(sides["other"]),
            ))
            this_ids.update(sides["this"])
            other_ids.update(sides["other"])
            if per_type_count.get(entity_type, 0) < cfg.correlation_factor_cap:
                weight_sum += weight * score.specificity
                per_type_count[entity_type] = per_type_count.get(entity_type, 0) + 1

        confidence = round(
            1.0 - math.exp(-weight_sum / cfg.correlation_confidence_normaliser), 4
        ) if weight_sum > 0 else 0.0
        return CrossCaseLink(
            other_case_id=other_case_id,
            match_confidence=confidence,
            relationship_strength=self._strength(confidence),
            matched_entities=matched_entities,
            this_evidence_ids=sorted(this_ids),
            other_evidence_ids=sorted(other_ids),
            match_reason=self._cross_case_reason(other_case_id, matched_entities),
        )

    @staticmethod
    def _cross_case_reason(
        other_case_id: str, matched: List[CrossCaseEntityMatch]
    ) -> str:
        # `matched` is ordered most-identifying first, so the values named here
        # are the ones actually carrying the link, not an alphabetical sample.
        shown = ", ".join(
            f"{m.entity_type.replace('_', ' ').rstrip('s')} {m.value}"
            for m in matched[:3]
        )
        extra = f" (+{len(matched) - 3} more)" if len(matched) > 3 else ""
        reason = (
            f"Shares {len(matched)} entity(ies) with {other_case_id}: "
            f"{shown}{extra}"
        )
        carrying = [m for m in matched if m.specificity >= 0.5]
        if not carrying:
            return (
                reason
                + ". Every shared value is common across the corpus, so this "
                "link rests on weak grounds."
            )
        weak = len(matched) - len(carrying)
        if weak:
            reason += (
                f". {len(carrying)} of these are distinctive; the other {weak} "
                "are common across the corpus and were discounted"
            )
        return reason

    def correlate_pair(
        self, a: EvidenceContext, b: EvidenceContext
    ) -> EvidencePairCorrelation:
        """Weighted, explainable correlation between two evidence items."""
        cfg = self._cfg
        factors: List[CorrelationFactor] = []

        for entity_type in cfg.correlation_entity_types:
            factor = self._shared_entity_factor(a, b, entity_type)
            if factor is not None:
                factors.append(factor)

        for builder in (self._file_hash_factor, self._device_metadata_factor,
                        self._image_metadata_factor, self._timeline_factor,
                        self._threat_intel_factor):
            factor = builder(a, b)
            if factor is not None:
                factors.append(factor)

        weight = round(sum(f.contribution for f in factors), 4)
        confidence = round(
            1.0 - math.exp(-weight / cfg.correlation_confidence_normaliser), 4
        ) if weight > 0 else 0.0
        strength = self._strength(confidence)
        reasons = [f.reason for f in factors]
        return EvidencePairCorrelation(
            evidence_a=a.evidence_id,
            evidence_b=b.evidence_id,
            correlation_weight=weight,
            correlation_confidence=confidence,
            relationship_strength=strength,
            factors=factors,
            correlation_reasons=reasons,
            explanation=self._explanation(a, b, strength, confidence, factors),
        )

    # ----------------------------------------------------------------- factors

    def _shared_entity_factor(
        self, a: EvidenceContext, b: EvidenceContext, entity_type: str
    ) -> Optional[CorrelationFactor]:
        values_a = {v.lower() for v in a.entity_values(entity_type) if v}
        values_b = {v.lower() for v in b.entity_values(entity_type) if v}
        shared = sorted(values_a & values_b)
        if not shared:
            return None

        cfg = self._cfg
        # Score the most identifying values first, so the per-factor cap keeps
        # the strongest evidence rather than whatever sorted first
        # alphabetically - a case sharing one rare wallet and five round
        # amounts must be scored on the wallet.
        scored = sorted(
            (self._specificity.specificity(entity_type, value) for value in shared),
            key=lambda s: s.specificity,
            reverse=True,
        )
        counted = scored[: cfg.correlation_factor_cap]
        effective = sum(score.specificity for score in counted)

        weight = cfg.correlation_weights.get(entity_type, 0.0)
        label = entity_type.replace("_", " ")
        discounted = [s for s in counted if s.is_common]

        headline = (
            f"Both items reference the same {label}: "
            f"{', '.join(s.value for s in counted[:3])}"
            + (f" (+{len(shared) - len(counted[:3])} more)"
               if len(shared) > len(counted[:3]) else "")
        )
        if discounted:
            headline += (
                f" - but {len(discounted)} of these are common across the "
                f"corpus and were discounted"
            )

        return CorrelationFactor(
            factor=entity_type,
            weight=weight,
            matches=len(counted),
            contribution=round(weight * effective, 4),
            supporting_evidence=[s.value for s in scored[: cfg.correlation_factor_cap * 2]],
            reason=headline,
            effective_matches=round(effective, 4),
            value_details=[
                SharedValueDetail(
                    value=s.value,
                    specificity=s.specificity,
                    document_frequency=s.document_frequency,
                    corpus_size=s.corpus_size,
                    reason=s.reason,
                )
                for s in counted
            ],
        )

    def _file_hash_factor(self, a: EvidenceContext, b: EvidenceContext
                          ) -> Optional[CorrelationFactor]:
        if not a.sha256 or a.sha256.lower() != b.sha256.lower():
            return None
        return self._factor(
            "file_hash", 1, [a.sha256],
            "Identical SHA-256 content hash - the files are byte-for-byte copies",
        )

    def _device_metadata_factor(self, a: EvidenceContext, b: EvidenceContext
                                ) -> Optional[CorrelationFactor]:
        device_a = self._device_of(a)
        device_b = self._device_of(b)
        if not device_a or device_a != device_b:
            return None
        return self._factor(
            "device_metadata", 1, [device_a],
            f"Both files carry EXIF metadata from the same device '{device_a}'",
        )

    def _image_metadata_factor(self, a: EvidenceContext, b: EvidenceContext
                               ) -> Optional[CorrelationFactor]:
        software_a = self._software_of(a)
        software_b = self._software_of(b)
        if not software_a or software_a != software_b:
            return None
        return self._factor(
            "image_metadata", 1, [software_a],
            f"Both images were processed by the same software '{software_a}'",
        )

    def _timeline_factor(self, a: EvidenceContext, b: EvidenceContext
                         ) -> Optional[CorrelationFactor]:
        time_a, time_b = a.upload_datetime, b.upload_datetime
        if time_a is None or time_b is None:
            return None
        hours = abs((time_a - time_b).total_seconds()) / 3600.0
        if hours > self._cfg.timeline_proximity_hours:
            return None
        return self._factor(
            "timeline_proximity", 1, [f"{hours:.1f}h apart"],
            f"Acquired {hours:.1f} hours apart "
            f"(within the {self._cfg.timeline_proximity_hours:.0f}h proximity window)",
        )

    def _threat_intel_factor(self, a: EvidenceContext, b: EvidenceContext
                             ) -> Optional[CorrelationFactor]:
        intel = self._data.threat_intel
        if not intel.available:
            return None
        flagged_a = self._flagged_indicators(a)
        flagged_b = self._flagged_indicators(b)
        shared = sorted(set(flagged_a) & set(flagged_b))
        if not shared:
            return None
        return self._factor(
            "threat_intelligence", len(shared), shared,
            "Threat intelligence flags the same malicious indicator(s) in both "
            f"items: {', '.join(shared[:3])}",
        )

    # ---------------------------------------------------------------- helpers

    def _factor(self, name: str, matches: int, supporting: List[str],
                reason: str) -> CorrelationFactor:
        """Non-entity factors: hash identity, metadata, proximity, intel.

        These carry no per-value rarity because they are not drawn from the
        entity corpus - a matching SHA-256 is unique by construction, and a
        proximity window is an observation rather than a value - so the
        specificity-weighted count is simply the counted matches.
        """
        cfg = self._cfg
        weight = cfg.correlation_weights.get(name, 0.0)
        counted = min(matches, cfg.correlation_factor_cap)
        return CorrelationFactor(
            factor=name,
            weight=weight,
            matches=counted,
            contribution=round(weight * counted, 4),
            supporting_evidence=supporting[: cfg.correlation_factor_cap * 2],
            reason=reason,
            effective_matches=float(counted),
        )

    def _flagged_indicators(self, context: EvidenceContext) -> List[str]:
        intel = self._data.threat_intel
        flagged = []
        for entity_type in ("urls", "domains"):
            for value in context.entity_values(entity_type):
                if intel.is_malicious(value):
                    flagged.append(value.lower())
        return flagged

    @staticmethod
    def _device_of(context: EvidenceContext) -> str:
        metadata = context.forensics.get("metadata_report", {})
        image = metadata.get("image") or {}
        return str(image.get("device", "") or "").strip()

    @staticmethod
    def _software_of(context: EvidenceContext) -> str:
        metadata = context.forensics.get("metadata_report", {})
        image = metadata.get("image") or {}
        return str(image.get("software", "") or "").strip()

    def _strength(self, confidence: float) -> str:
        for level, ceiling in self._cfg.relationship_bands.items():
            if confidence < ceiling:
                return level
        return "VERY_STRONG"

    @staticmethod
    def _explanation(
        a: EvidenceContext, b: EvidenceContext,
        strength: str, confidence: float,
        factors: List[CorrelationFactor],
    ) -> str:
        if not factors:
            return (
                f"No shared entities, metadata, temporal proximity or threat "
                f"indicators were found between {a.evidence_id} "
                f"({a.file_name}) and {b.evidence_id} ({b.file_name})."
            )
        parts = [
            f"{a.evidence_id} ({a.file_name}) and {b.evidence_id} "
            f"({b.file_name}) show a {strength.replace('_', ' ').lower()} "
            f"relationship (confidence {confidence:.2f}) based on "
            f"{len(factors)} independent factor(s)."
        ]
        for factor in factors:
            parts.append(f"{factor.reason} [weight {factor.contribution:.2f}].")
        return " ".join(parts)
