"""Baseline related-pair predictors for Table 6.4.

The table compares the live weighted correlation engine against two simpler
baselines. Both produce a *set of related evidence-id pairs* that
``correlation_eval.evaluate_correlation`` scores against the gold pairs — the
same currency as the live service's predictions, so the comparison is apples-
to-apples.

* ``exact_match_pairs``  — two items are "related" iff they share an entity
  **value with exact string equality** (no normalization at all). This is the
  naive string-matching baseline: it misses ``+977 9812345678`` vs
  ``9812345678`` and other trivially-different spellings.

* ``unweighted_shared_entity_pairs`` — two items are "related" iff they share
  at least one **normalized** entity of a linkable type, with **no weighting
  and no temporal-proximity fallback**. This isolates the contribution of the
  live engine's weighting + temporal reasoning: anything the live engine links
  *only* via time-proximity (no shared entity) is not linked here.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, List, Sequence, Set, Tuple

from ..data_access import EvidenceContext

Pair = Tuple[str, str]


def _linkable_types(config) -> Set[str]:
    return set(getattr(config, "correlation_entity_types", ()) or ())


def exact_match_pairs(evidence: Sequence[EvidenceContext]) -> Set[Pair]:
    """Pairs sharing an entity value by EXACT string equality (unnormalized)."""
    # evidence_id -> set of raw entity values (case-sensitive, unnormalized).
    values = {
        ctx.evidence_id: {e.value for e in ctx.entities if e.value}
        for ctx in evidence
    }
    related: Set[Pair] = set()
    for a, b in combinations(evidence, 2):
        if values[a.evidence_id] & values[b.evidence_id]:
            related.add((a.evidence_id, b.evidence_id))
    return related


def unweighted_shared_entity_pairs(
    evidence: Sequence[EvidenceContext], config
) -> Set[Pair]:
    """Pairs sharing >=1 normalized linkable entity; no weights, no temporal."""
    types = _linkable_types(config)

    def norm_set(ctx: EvidenceContext) -> Set[Tuple[str, str]]:
        out: Set[Tuple[str, str]] = set()
        for e in ctx.entities:
            if e.entity_type not in types:
                continue
            value = (e.normalized or e.value or "").strip().lower()
            if value:
                out.add((e.entity_type, value))
        return out

    sets = {ctx.evidence_id: norm_set(ctx) for ctx in evidence}
    related: Set[Pair] = set()
    for a, b in combinations(evidence, 2):
        if sets[a.evidence_id] & sets[b.evidence_id]:
            related.add((a.evidence_id, b.evidence_id))
    return related


def as_tuple_list(pairs: Iterable[Pair]) -> List[Pair]:
    """Convenience for feeding evaluate_correlation (which wants 2-tuples)."""
    return list(pairs)
