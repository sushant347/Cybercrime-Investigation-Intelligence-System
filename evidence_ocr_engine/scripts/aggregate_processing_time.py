"""Table 6.7 (End-to-End) — aggregate real per-stage timings for one case.

Per-stage ``duration_ms`` is already recorded by the engine into two logs:

* ``storage/processing_log.csv``               (Phase-1 acquisition/OCR stages)
* ``storage/investigation/investigation_audit_log.csv``  (Phase-2 modules)

This script sums those durations into a single processing-time figure for the
"Implemented System" cell of Table 6.7, with full provenance (which case, which
files, timestamp range, per-stage breakdown). It computes nothing new — it only
sums measurements the engine already took.

It deliberately produces **no** "Manual workflow" figure: no such measurement
exists in the codebase, so that cell must be an explicitly-cited estimate or SME
interview, not a number derived here. The "Report correctness" row likewise
requires a human review pass and is out of scope for this script.

Usage::

    python scripts/aggregate_processing_time.py --case CASE_2CF24DBA5F
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Dict, List, Optional, Tuple


def _read_csv(path: str) -> List[Dict[str, str]]:
    if not os.path.isfile(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_ms(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


#: The engine logs a per-evidence umbrella row ("pipeline") whose duration
#: already includes its sub-stages (upload/preprocessing/ocr/hashing), and a
#: per-case umbrella row ("phase2_pipeline") that wraps the Phase-2 modules.
#: Summing an umbrella together with its leaves would double-count, so the
#: umbrella is the authoritative total and the leaves are an informational
#: breakdown only.
PHASE1_UMBRELLA = "pipeline"
PHASE2_UMBRELLA = "phase2_pipeline"


def aggregate_processing_time(
    processing_rows: List[Dict[str, str]],
    audit_rows: List[Dict[str, str]],
    case_id: str,
    *,
    phase1_umbrella: str = PHASE1_UMBRELLA,
    phase2_umbrella: str = PHASE2_UMBRELLA,
) -> Dict[str, object]:
    """Sum authoritative ``duration_ms`` for one case across the two engine logs.

    The Phase-1 total is the sum of the per-evidence umbrella rows
    (``phase1_umbrella``); the Phase-2 total is the umbrella row
    (``phase2_umbrella``). Leaf stages/modules are reported as a breakdown but
    NOT added to the total (they are already inside the umbrella). If a phase
    has no umbrella row, its leaf sum is used instead and flagged.
    """
    phase1_leaves: Dict[str, float] = {}
    phase2_leaves: Dict[str, float] = {}
    phase1_umbrella_ms = 0.0
    phase2_umbrella_ms = 0.0
    phase1_has_umbrella = phase2_has_umbrella = False
    timestamps: List[str] = []
    rows_used = 0

    for row in processing_rows:
        if row.get("case_id") != case_id:
            continue
        ms = _to_ms(row.get("duration_ms", "0"))
        stage = row.get("stage") or "unknown"
        if stage == phase1_umbrella:
            phase1_umbrella_ms += ms
            phase1_has_umbrella = True
        else:
            phase1_leaves[stage] = phase1_leaves.get(stage, 0.0) + ms
        if row.get("timestamp"):
            timestamps.append(row["timestamp"])
        rows_used += 1

    for row in audit_rows:
        if row.get("case_id") != case_id:
            continue
        ms = _to_ms(row.get("duration_ms", "0"))
        module = row.get("module") or "unknown"
        if module == phase2_umbrella:
            phase2_umbrella_ms += ms
            phase2_has_umbrella = True
        else:
            phase2_leaves[module] = phase2_leaves.get(module, 0.0) + ms
        if row.get("timestamp"):
            timestamps.append(row["timestamp"])
        rows_used += 1

    phase1_total = phase1_umbrella_ms if phase1_has_umbrella else sum(phase1_leaves.values())
    phase2_total = phase2_umbrella_ms if phase2_has_umbrella else sum(phase2_leaves.values())
    total_ms = phase1_total + phase2_total
    span: Optional[Tuple[str, str]] = (
        (min(timestamps), max(timestamps)) if timestamps else None
    )
    return {
        "case_id": case_id,
        "rows_used": rows_used,
        "phase1_total_ms": round(phase1_total, 1),
        "phase2_total_ms": round(phase2_total, 1),
        "total_ms": round(total_ms, 1),
        "total_seconds": round(total_ms / 1000.0, 3),
        "phase1_total_source": "umbrella" if phase1_has_umbrella else "leaf-sum (no umbrella row)",
        "phase2_total_source": "umbrella" if phase2_has_umbrella else "leaf-sum (no umbrella row)",
        "phase1_by_stage_ms": {k: round(v, 1) for k, v in sorted(phase1_leaves.items())},
        "phase2_by_module_ms": {k: round(v, 1) for k, v in sorted(phase2_leaves.items())},
        "timestamp_range": span,
    }


def main() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_proc = os.path.join(here, "storage", "processing_log.csv")
    default_audit = os.path.join(
        here, "storage", "investigation", "investigation_audit_log.csv"
    )

    parser = argparse.ArgumentParser(description="Aggregate per-stage timings for a case.")
    parser.add_argument("--case", required=True, help="Case id, e.g. CASE_2CF24DBA5F")
    parser.add_argument("--processing-log", default=default_proc)
    parser.add_argument("--audit-log", default=default_audit)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    result = aggregate_processing_time(
        _read_csv(args.processing_log), _read_csv(args.audit_log), args.case
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Table 6.7 — End-to-End processing time (Implemented System)")
    print(f"  Case:            {result['case_id']}")
    print(f"  Log rows summed: {result['rows_used']}")
    print(f"  Timestamp range: {result['timestamp_range']}")
    print(f"  Phase-1 total: {result['phase1_total_ms']} ms  [{result['phase1_total_source']}]")
    print(f"    sub-stages (informational, already inside the total): {result['phase1_by_stage_ms']}")
    print(f"  Phase-2 total: {result['phase2_total_ms']} ms  [{result['phase2_total_source']}]")
    print(f"    modules (informational): {result['phase2_by_module_ms']}")
    print(f"  ── END-TO-END TOTAL: {result['total_ms']} ms  ({result['total_seconds']} s)")
    print()
    print("  Manual-workflow baseline: NOT computed — no such measurement exists")
    print("  in the codebase; supply an explicitly-cited estimate/SME figure.")
    print("  Report-correctness row: requires a human review pass (out of scope).")


if __name__ == "__main__":
    main()
