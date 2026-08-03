"""Gold-label schema + loaders for the correlation (6.4) and timeline (6.5)
evaluations.

These are the data structures a human annotator fills in; the runner scripts
score the live services against them. This module builds and validates the
structures — it holds **no** labels itself. Real numbers require real labels
supplied by a human (see ``samples/ground_truth/*_gold_template.json``).

Correlation gold (``correlation_gold.json``)::

    {
      "within_case": {
        "CASE_0021": {"related_pairs": [["EVID_00001", "EVID_00002"], ...]}
      },
      "cross_case": {
        "related_pairs": [["EVID_00001", "EVID_00099"], ...]
      }
    }

Timeline gold (``timeline_gold.json``)::

    {
      "CASE_0021": {
        "order": ["EVID_00001", "EVID_00003", "EVID_00002"],
        "timestamps": {"EVID_00001": "2026-01-04T09:12:00Z", ...}
      }
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

Pair = Tuple[str, str]


@dataclass
class CorrelationGold:
    """Human-labelled related evidence pairs, split within- vs cross-case."""

    within_case: Dict[str, List[Pair]] = field(default_factory=dict)
    cross_case: List[Pair] = field(default_factory=list)

    def is_template(self) -> bool:
        """True if no real labels have been filled in yet."""
        return not any(self.within_case.values()) and not self.cross_case


@dataclass
class TimelineGold:
    """Human-labelled true order + true timestamps, per case."""

    order: Dict[str, List[str]] = field(default_factory=dict)
    timestamps: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def is_template(self) -> bool:
        return not any(self.order.values())


def _pairs(raw: object, where: str) -> List[Pair]:
    if not isinstance(raw, list):
        raise ValueError(f"{where}: expected a list of [a, b] pairs")
    out: List[Pair] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"{where}: each pair must be [evidence_a, evidence_b], got {item!r}")
        a, b = str(item[0]), str(item[1])
        if a and b and a != b:
            out.append((a, b))
    return out


def load_correlation_gold(path: str | Path) -> CorrelationGold:
    """Parse + validate a correlation gold file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    within_raw = data.get("within_case", {}) or {}
    within: Dict[str, List[Pair]] = {}
    for case_id, block in within_raw.items():
        within[case_id] = _pairs((block or {}).get("related_pairs", []),
                                 f"within_case.{case_id}.related_pairs")
    cross = _pairs((data.get("cross_case", {}) or {}).get("related_pairs", []),
                   "cross_case.related_pairs")
    return CorrelationGold(within_case=within, cross_case=cross)


def load_timeline_gold(path: str | Path) -> TimelineGold:
    """Parse + validate a timeline gold file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    order: Dict[str, List[str]] = {}
    timestamps: Dict[str, Dict[str, str]] = {}
    for case_id, block in data.items():
        if case_id.startswith("_"):
            continue  # skip meta keys like "_README"
        block = block or {}
        seq = block.get("order", [])
        if not isinstance(seq, list):
            raise ValueError(f"{case_id}.order must be a list of evidence ids")
        order[case_id] = [str(e) for e in seq]
        ts = block.get("timestamps", {}) or {}
        if not isinstance(ts, dict):
            raise ValueError(f"{case_id}.timestamps must be an object")
        timestamps[case_id] = {str(k): str(v) for k, v in ts.items()}
    return TimelineGold(order=order, timestamps=timestamps)
