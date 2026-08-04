"""Demo gold must never be mistaken for a measurement.

``is_template()`` catches gold that is *empty*. The more dangerous case is gold
that is *filled in* with plausible values but was never human-verified: the
harness runs, prints a clean table, and nothing in the output distinguishes it
from a real evaluation. Those numbers can then be quoted in a dissertation.

The shipped sample files say so in their ``_note`` - "ILLUSTRATIVE DEMO ...
not thesis-grade" - but a note in a JSON file nobody opens protects nobody.
These tests pin the machine-readable flag and the guard built on it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ciis_correlation.evaluation.gold_labels import (
    is_illustrative,
    load_correlation_gold,
    load_timeline_gold,
)

GOLD_DIR = (Path(__file__).resolve().parents[2]
            / "evidence_ocr_engine" / "samples" / "ground_truth")


def test_shipped_correlation_sample_is_flagged_illustrative():
    gold = load_correlation_gold(GOLD_DIR / "correlation_gold_example.json")
    assert not gold.is_template(), "sample is filled in - that is the whole risk"
    assert gold.illustrative, "filled demo gold must still declare itself demo"


def test_shipped_timeline_sample_is_flagged_illustrative():
    gold = load_timeline_gold(GOLD_DIR / "timeline_gold_example.json")
    assert not gold.is_template()
    assert gold.illustrative


def test_real_gold_is_not_flagged(tmp_path):
    """A file without the marker must read as a genuine measurement source."""
    path = tmp_path / "real_gold.json"
    path.write_text(json.dumps({
        "_note": "Labelled by A. Investigator, 2026-08-01, double-checked.",
        "within_case": {"CASE_X": {"related_pairs": [["E1", "E2"]]}},
        "cross_case": {"related_pairs": []},
    }), encoding="utf-8")

    gold = load_correlation_gold(path)
    assert not gold.is_template()
    assert not gold.illustrative


@pytest.mark.parametrize("note", [
    "ILLUSTRATIVE DEMO — plausible values",
    "demo only, not thesis-grade",
    "Mixed CASE: Illustrative Demo with other text",
])
def test_marker_detection_is_case_insensitive(note):
    assert is_illustrative({"_note": note})


def test_absent_or_unrelated_note_is_not_illustrative():
    assert not is_illustrative({})
    assert not is_illustrative({"_note": "verified against the case file"})
    # Only underscore-prefixed meta keys are inspected, so a case id that
    # happens to contain the words cannot trip the flag.
    assert not is_illustrative({"ILLUSTRATIVE DEMO": {"related_pairs": []}})
