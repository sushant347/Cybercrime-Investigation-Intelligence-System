"""Timeline accuracy: does the engine order events correctly?

Ground truth is the true chronological order of evidence ids (a human-annotated
sequence). The engine's prediction is the order its timeline produced. We report
**pairwise ordering accuracy** (a normalized Kendall's-tau-style score): the
fraction of evidence-id pairs placed in the correct relative order, which is
robust to length differences and easy to interpret.

    score = concordant_pairs / total_comparable_pairs      in [0, 1]

1.0 = identical ordering; 0.5 ≈ random; 0.0 = fully reversed. Also reported:
``exact_match`` (the whole sequence matches) and ``kendall_tau`` in [-1, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Sequence


def predicted_order(analysis: Any) -> List[str]:
    """Extract the ordered evidence-id sequence from a ``TimelineAnalysis``.

    Uses each event's ``evidence_id`` in the order the engine emitted them
    (events are sorted by timestamp upstream). De-duplicates while preserving
    first-seen order so multi-event evidence items appear once.
    """
    events = getattr(analysis, "events", None)
    if events is None and isinstance(analysis, dict):
        events = analysis.get("events", [])
    order: List[str] = []
    seen = set()
    for event in events or []:
        if isinstance(event, dict):
            eid = event.get("evidence_id")
        else:
            eid = getattr(event, "evidence_id", None)
        if eid and eid not in seen:
            seen.add(eid)
            order.append(eid)
    return order


@dataclass
class TimelineEval:
    pairwise_accuracy: float = 0.0
    kendall_tau: float = 0.0
    exact_match: bool = False
    comparable_pairs: int = 0
    concordant_pairs: int = 0
    per_item: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "pairwise_accuracy": round(self.pairwise_accuracy, 4),
            "kendall_tau": round(self.kendall_tau, 4),
            "exact_match": self.exact_match,
            "comparable_pairs": self.comparable_pairs,
            "concordant_pairs": self.concordant_pairs,
        }


def evaluate_timeline(
    gold_order: Sequence[str], predicted: Sequence[str]
) -> TimelineEval:
    """Pairwise ordering accuracy of ``predicted`` against ``gold_order``.

    Only pairs present in BOTH sequences are comparable (so missing/extra items
    don't crash the metric — they are simply not counted, which is reported via
    ``comparable_pairs``).
    """
    gold_rank = {eid: i for i, eid in enumerate(gold_order)}
    pred_rank = {eid: i for i, eid in enumerate(predicted)}
    common = [eid for eid in gold_order if eid in pred_rank]

    concordant = 0
    total = 0
    for a, b in combinations(common, 2):
        total += 1
        gold_before = gold_rank[a] < gold_rank[b]
        pred_before = pred_rank[a] < pred_rank[b]
        if gold_before == pred_before:
            concordant += 1

    accuracy = concordant / total if total else 1.0
    # Kendall tau = (concordant - discordant) / total = 2*acc - 1.
    tau = (2 * accuracy - 1) if total else 1.0
    exact = list(predicted) == list(gold_order)
    return TimelineEval(
        pairwise_accuracy=accuracy,
        kendall_tau=tau,
        exact_match=exact,
        comparable_pairs=total,
        concordant_pairs=concordant,
    )
