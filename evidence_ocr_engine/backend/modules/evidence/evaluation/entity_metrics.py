"""Entity-extraction evaluation: Precision / Recall / F1 per entity type.

Compares a set of *predicted* entities against a *gold* (human-labelled) set.
Matching is **set-based per (type, value)** with a configurable normalization
so that, e.g., a trailing-slash URL or a spaced phone number is not counted as
a miss when it is semantically identical. The exact rule is recorded in the
report so scores are reproducible and not silently inflated/deflated.

Definitions (per type ``t``)::

    precision_t = TP_t / (TP_t + FP_t)
    recall_t    = TP_t / (TP_t + FN_t)
    F1_t        = 2 * P * R / (P + R)

Aggregates are reported **both** ways (a common type must not mask a weak one):
    * micro  - pool all types, then compute P/R/F1 (frequency-weighted).
    * macro  - average the per-type F1 (each type weighted equally).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple


# --------------------------------------------------------------- normalization
def default_normalizer(entity_type: str, value: str) -> str:
    """Reproducible per-type normalization used for matching.

    * lowercase + strip for everything;
    * URLs: drop a single trailing slash and a leading scheme is kept as-is;
    * phones/esewa ids: keep only leading ``+`` and digits.
    """
    value = value.strip().lower()
    etype = entity_type.lower()
    if etype in {"url", "urls"}:
        return value[:-1] if value.endswith("/") else value
    if etype in {"phone", "phones", "esewa_id", "esewa_ids"}:
        digits = "".join(ch for ch in value if ch.isdigit())
        return ("+" + digits) if value.startswith("+") else digits
    return value


Normalizer = Callable[[str, str], str]
EntitySet = Mapping[str, Iterable[str]]  # type -> iterable of values


# ----------------------------------------------------------------- data types
@dataclass
class PRF1:
    """Precision / Recall / F1 with the underlying confusion counts."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

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


@dataclass
class EntityScore:
    """Full per-type + aggregated entity-extraction result."""

    per_type: Dict[str, PRF1] = field(default_factory=dict)
    micro: PRF1 = field(default_factory=PRF1)
    macro_f1: float = 0.0
    normalization: str = "default"

    def to_dict(self) -> Dict[str, object]:
        return {
            "per_type": {t: s.to_dict() for t, s in sorted(self.per_type.items())},
            "micro": self.micro.to_dict(),
            "macro_f1": round(self.macro_f1, 4),
            "normalization": self.normalization,
        }


# --------------------------------------------------------------------- scoring
def _normalized_set(
    entities: EntitySet, entity_type: str, normalizer: Normalizer
) -> Set[str]:
    return {normalizer(entity_type, str(v)) for v in entities.get(entity_type, [])}


def entity_prf1(
    gold: EntitySet,
    predicted: EntitySet,
    *,
    normalizer: Optional[Normalizer] = None,
    normalization_name: str = "default",
) -> EntityScore:
    """Score predicted entities against gold, per type and aggregated.

    Args:
        gold: mapping ``entity_type -> values`` (human ground truth).
        predicted: mapping ``entity_type -> values`` (extractor output).
        normalizer: ``(type, value) -> canonical value`` used for matching;
            defaults to :func:`default_normalizer`.
        normalization_name: label recorded in the report.

    Returns:
        An :class:`EntityScore`.
    """
    normalizer = normalizer or default_normalizer
    types = set(gold) | set(predicted)
    result = EntityScore(normalization=normalization_name)
    f1s: List[float] = []
    for etype in types:
        gset = _normalized_set(gold, etype, normalizer)
        pset = _normalized_set(predicted, etype, normalizer)
        tp = len(gset & pset)
        score = PRF1(tp=tp, fp=len(pset - gset), fn=len(gset - pset))
        result.per_type[etype] = score
        result.micro.tp += score.tp
        result.micro.fp += score.fp
        result.micro.fn += score.fn
        f1s.append(score.f1)
    result.macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    return result


def micro_macro_average(scores: Iterable[EntityScore]) -> EntityScore:
    """Combine several per-document :class:`EntityScore` into a corpus score."""
    combined = EntityScore()
    per_type_f1: Dict[str, List[float]] = {}
    for score in scores:
        for etype, prf in score.per_type.items():
            agg = combined.per_type.setdefault(etype, PRF1())
            agg.tp += prf.tp
            agg.fp += prf.fp
            agg.fn += prf.fn
        combined.micro.tp += score.micro.tp
        combined.micro.fp += score.micro.fp
        combined.micro.fn += score.micro.fn
    for etype, prf in combined.per_type.items():
        per_type_f1.setdefault(etype, []).append(prf.f1)
    combined.macro_f1 = (
        sum(prf.f1 for prf in combined.per_type.values()) / len(combined.per_type)
        if combined.per_type
        else 0.0
    )
    return combined
