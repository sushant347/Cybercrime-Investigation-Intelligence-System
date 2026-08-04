"""Correlation accuracy: does the engine link the *right* evidence pairs?

Ground truth is a set of evidence-id pairs that a human annotator judged to be
truly related. The engine's prediction is the set of pairs it scored as related
(``relationship_strength != "NO_RELATIONSHIP"``). We report Precision / Recall /
F1 over unordered pairs.

Pairs are order-independent: ``(A, B)`` == ``(B, A)`` (a ``frozenset``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, Set, Tuple

Pair = FrozenSet[str]


def _as_pair(a: str, b: str) -> Pair:
    return frozenset({a, b})


def to_pair_set(pairs: Iterable[Tuple[str, str]]) -> Set[Pair]:
    """Normalize an iterable of 2-tuples into a set of unordered pairs."""
    result: Set[Pair] = set()
    for a, b in pairs:
        if a != b:
            result.add(_as_pair(a, b))
    return result


def predicted_related_pairs(analysis: Any) -> Set[Pair]:
    """Extract the related pairs from a ``CorrelationAnalysis`` object.

    A pair is 'predicted related' when its ``relationship_strength`` is not
    ``"NO_RELATIONSHIP"``. Works with either dataclass pairs (attributes) or
    plain dicts (loaded from the JSON artifact).
    """
    related: Set[Pair] = set()
    pairs = getattr(analysis, "pairs", None)
    if pairs is None and isinstance(analysis, dict):
        pairs = analysis.get("pairs", [])
    for pair in pairs or []:
        if isinstance(pair, dict):
            a, b = pair.get("evidence_a"), pair.get("evidence_b")
            strength = pair.get("relationship_strength")
        else:
            a, b = getattr(pair, "evidence_a", None), getattr(pair, "evidence_b", None)
            strength = getattr(pair, "relationship_strength", None)
        if a and b and strength and strength != "NO_RELATIONSHIP":
            related.add(_as_pair(a, b))
    return related


@dataclass
class CorrelationEval:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


def evaluate_correlation(
    gold_related: Iterable[Tuple[str, str]],
    predicted_related: Iterable[Tuple[str, str]] | Set[Pair],
) -> CorrelationEval:
    """P/R/F1 of predicted related pairs against the gold related pairs."""
    gold = to_pair_set(gold_related)
    if isinstance(predicted_related, set):
        pred = {p if isinstance(p, frozenset) else _as_pair(*p) for p in predicted_related}
    else:
        pred = to_pair_set(predicted_related)
    return CorrelationEval(
        tp=len(gold & pred),
        fp=len(pred - gold),
        fn=len(gold - pred),
    )
