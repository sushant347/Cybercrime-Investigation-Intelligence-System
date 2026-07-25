"""Table 6.7 aggregation — sums real duration_ms, invents nothing.

Critically, it must NOT double-count: the engine records a per-evidence
umbrella row ("pipeline") that already includes its sub-stages, and a per-case
"phase2_pipeline" umbrella. The total uses the umbrella, not umbrella+leaves.
"""

import importlib.util
import os

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "aggregate_processing_time.py",
)
_spec = importlib.util.spec_from_file_location("aggregate_processing_time", _SCRIPT)
agg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agg)


def test_umbrella_total_does_not_double_count_leaves():
    processing = [
        {"timestamp": "2026-07-24T16:06:34Z", "case_id": "CASE_1",
         "evidence_id": "E1", "stage": "ocr", "duration_ms": "120.5"},
        {"timestamp": "2026-07-24T16:06:35Z", "case_id": "CASE_1",
         "evidence_id": "E1", "stage": "hashing", "duration_ms": "0.5"},
        {"timestamp": "2026-07-24T16:06:35Z", "case_id": "CASE_1",
         "evidence_id": "E1", "stage": "pipeline", "duration_ms": "125.0"},  # umbrella
        {"timestamp": "2026-07-24T16:06:36Z", "case_id": "CASE_2",
         "evidence_id": "E9", "stage": "pipeline", "duration_ms": "999.0"},  # other case
    ]
    audit = [
        {"timestamp": "2026-07-24T16:06:39Z", "case_id": "CASE_1",
         "module": "correlation", "duration_ms": "0.7"},
        {"timestamp": "2026-07-24T16:06:40Z", "case_id": "CASE_1",
         "module": "phase2_pipeline", "duration_ms": "56.0"},  # umbrella
    ]
    result = agg.aggregate_processing_time(processing, audit, "CASE_1")

    assert result["rows_used"] == 5  # the CASE_2 row is excluded
    assert result["phase1_total_ms"] == 125.0  # umbrella, not 125+120.5+0.5
    assert result["phase2_total_ms"] == 56.0   # umbrella, not 56+0.7
    assert result["total_ms"] == 181.0
    assert result["phase1_total_source"] == "umbrella"
    # leaves are reported for insight but excluded from the total
    assert result["phase1_by_stage_ms"] == {"hashing": 0.5, "ocr": 120.5}
    assert result["timestamp_range"] == ("2026-07-24T16:06:34Z", "2026-07-24T16:06:40Z")


def test_falls_back_to_leaf_sum_when_no_umbrella_row():
    processing = [
        {"case_id": "C", "stage": "ocr", "duration_ms": "10.0"},
        {"case_id": "C", "stage": "hashing", "duration_ms": "2.0"},
    ]
    result = agg.aggregate_processing_time(processing, [], "C")
    assert result["phase1_total_ms"] == 12.0
    assert result["phase1_total_source"].startswith("leaf-sum")


def test_unknown_case_is_zero_not_error():
    result = agg.aggregate_processing_time([], [], "CASE_MISSING")
    assert result["total_ms"] == 0.0
    assert result["rows_used"] == 0
    assert result["timestamp_range"] is None


def test_malformed_duration_is_ignored_not_fatal():
    processing = [{"case_id": "C", "stage": "ocr", "duration_ms": "not-a-number"}]
    result = agg.aggregate_processing_time(processing, [], "C")
    assert result["total_ms"] == 0.0
    assert result["rows_used"] == 1
