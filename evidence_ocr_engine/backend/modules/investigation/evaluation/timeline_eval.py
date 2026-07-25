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
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence


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


# --------------------------------------------------------------------------- #
# Timestamp accuracy (Table 6.5) — how close resolved timestamps are to truth
# --------------------------------------------------------------------------- #
#
# Definition (proposed for approval):
#
#   For each evidence item that has a human-annotated TRUE timestamp, we take
#   the timestamp the engine resolved for that item and compute the absolute
#   error in seconds |t_pred - t_true|. We report:
#
#     * mae_seconds      — mean absolute error over resolved items
#     * median_ae_seconds
#     * within_tolerance — fraction of items whose error <= each tolerance
#                          window (default 60 s, 1 h, 24 h)
#     * unresolved_rate  — fraction of gold items the engine produced NO
#                          timestamp for (it could not resolve them)
#
# An item is "resolved" if the engine emitted an event for it with a parseable
# timestamp. Items the engine skipped count toward unresolved_rate and are
# excluded from the error statistics (you cannot measure the error of a
# timestamp that was never produced) — this keeps MAE honest rather than
# rewarding non-answers.

_DEFAULT_TOLERANCES = (60.0, 3600.0, 86400.0)  # 1 min, 1 hour, 1 day


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def predicted_timestamps(analysis: Any) -> Dict[str, str]:
    """Map ``evidence_id -> resolved timestamp`` from a ``TimelineAnalysis``.

    Uses the first event emitted for each evidence id (events are chronological
    upstream), matching :func:`predicted_order`.
    """
    events = getattr(analysis, "events", None)
    if events is None and isinstance(analysis, dict):
        events = analysis.get("events", [])
    resolved: Dict[str, str] = {}
    for event in events or []:
        if isinstance(event, dict):
            eid, ts = event.get("evidence_id"), event.get("timestamp")
        else:
            eid, ts = getattr(event, "evidence_id", None), getattr(event, "timestamp", None)
        if eid and ts and eid not in resolved:
            resolved[eid] = ts
    return resolved


@dataclass
class TimestampEval:
    resolved: int = 0
    unresolved: int = 0
    mae_seconds: float = 0.0
    median_ae_seconds: float = 0.0
    within_tolerance: Dict[str, float] = field(default_factory=dict)
    per_item_seconds: Dict[str, float] = field(default_factory=dict)

    @property
    def unresolved_rate(self) -> float:
        total = self.resolved + self.unresolved
        return self.unresolved / total if total else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "resolved": self.resolved,
            "unresolved": self.unresolved,
            "unresolved_rate": round(self.unresolved_rate, 4),
            "mae_seconds": round(self.mae_seconds, 3),
            "median_ae_seconds": round(self.median_ae_seconds, 3),
            "within_tolerance": {k: round(v, 4) for k, v in self.within_tolerance.items()},
        }


def evaluate_timestamp_accuracy(
    gold_timestamps: Dict[str, str],
    predicted: Dict[str, str],
    tolerances_seconds: Sequence[float] = _DEFAULT_TOLERANCES,
) -> TimestampEval:
    """Mean/median absolute error + within-tolerance rates + unresolved rate.

    Args:
        gold_timestamps: ``evidence_id -> true ISO-8601 timestamp`` (human).
        predicted: ``evidence_id -> resolved ISO-8601 timestamp`` (engine).
        tolerances_seconds: windows for the within-tolerance fractions.
    """
    errors: Dict[str, float] = {}
    unresolved = 0
    for eid, true_ts in gold_timestamps.items():
        gold_dt = _parse_iso(true_ts)
        pred_dt = _parse_iso(predicted.get(eid, ""))
        if gold_dt is None:
            continue  # a gold item with no parseable truth cannot be scored
        if pred_dt is None:
            unresolved += 1
            continue
        errors[eid] = abs((pred_dt - gold_dt).total_seconds())

    values = sorted(errors.values())
    n = len(values)
    mae = sum(values) / n if n else 0.0
    if n:
        mid = n // 2
        median = values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2
    else:
        median = 0.0
    within = {
        f"<= {int(tol)}s": (sum(1 for v in values if v <= tol) / n if n else 0.0)
        for tol in tolerances_seconds
    }
    return TimestampEval(
        resolved=n,
        unresolved=unresolved,
        mae_seconds=mae,
        median_ae_seconds=median,
        within_tolerance=within,
        per_item_seconds={k: round(v, 3) for k, v in errors.items()},
    )
