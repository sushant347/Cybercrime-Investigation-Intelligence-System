"""Tables 6.4 / 6.5 evaluation infrastructure — metric math, loaders, baselines.

These test the *code* on toy inputs (legitimate: it verifies the math and the
schema handling). They produce no thesis numbers — those require the human gold
labels the loaders consume.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modules.investigation.data_access import EntityRecord, EvidenceContext
from backend.modules.investigation.evaluation.correlation_baselines import (
    exact_match_pairs,
    unweighted_shared_entity_pairs,
)
from backend.modules.investigation.evaluation.gold_labels import (
    load_correlation_gold,
    load_timeline_gold,
)
from backend.modules.investigation.evaluation.timeline_eval import (
    evaluate_timestamp_accuracy,
)

GT = Path(__file__).resolve().parents[2] / "samples" / "ground_truth"


# --------------------------------------------------------- timestamp accuracy
def test_timestamp_accuracy_mae_and_tolerance():
    gold = {"E1": "2026-01-04T09:00:00Z", "E2": "2026-01-04T10:00:00Z"}
    pred = {"E1": "2026-01-04T09:00:30Z",   # 30s off -> within 60s
            "E2": "2026-01-04T11:00:00Z"}   # 3600s off -> within 3600s, not 60s
    result = evaluate_timestamp_accuracy(gold, pred).to_dict()
    assert result["resolved"] == 2
    assert result["unresolved"] == 0
    assert result["mae_seconds"] == pytest.approx((30 + 3600) / 2)
    assert result["within_tolerance"]["<= 60s"] == pytest.approx(0.5)
    assert result["within_tolerance"]["<= 3600s"] == pytest.approx(1.0)


def test_timestamp_accuracy_counts_unresolved_without_inflating_mae():
    gold = {"E1": "2026-01-04T09:00:00Z", "E2": "2026-01-04T10:00:00Z"}
    pred = {"E1": "2026-01-04T09:00:00Z"}  # E2 never resolved
    result = evaluate_timestamp_accuracy(gold, pred).to_dict()
    assert result["resolved"] == 1
    assert result["unresolved"] == 1
    assert result["unresolved_rate"] == pytest.approx(0.5)
    assert result["mae_seconds"] == 0.0  # the one resolved item was exact


# ------------------------------------------------------------------ baselines
def _ctx(eid, entities):
    recs = [EntityRecord("C", eid, t, v, n) for (t, v, n) in entities]
    return EvidenceContext(evidence_id=eid, case_id="C", entities=recs)


class _Cfg:
    correlation_entity_types = ("phones", "emails")


def test_exact_match_needs_identical_string():
    a = _ctx("A", [("phones", "+977 9812345678", "9812345678")])
    b = _ctx("B", [("phones", "9812345678", "9812345678")])
    # normalized values match, raw strings differ -> exact match finds NOTHING
    assert exact_match_pairs([a, b]) == set()
    # but the normalized baseline links them
    assert unweighted_shared_entity_pairs([a, b], _Cfg) == {("A", "B")}


def test_exact_match_links_identical_raw_values():
    a = _ctx("A", [("emails", "x@y.com", "x@y.com")])
    b = _ctx("B", [("emails", "x@y.com", "x@y.com")])
    assert exact_match_pairs([a, b]) == {("A", "B")}


def test_unweighted_ignores_non_linkable_types():
    a = _ctx("A", [("dates", "2026-01-04", "2026-01-04")])
    b = _ctx("B", [("dates", "2026-01-04", "2026-01-04")])
    assert unweighted_shared_entity_pairs([a, b], _Cfg) == set()  # dates not linkable


# --------------------------------------------------------------- gold loaders
def test_correlation_gold_template_parses_and_is_flagged_template():
    gold = load_correlation_gold(GT / "correlation_gold_template.json")
    assert gold.is_template()  # nothing labelled yet
    assert set(gold.within_case) == {"CASE_0021", "CASE_0042"}


def test_correlation_gold_parses_real_pairs(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({
        "within_case": {"CASE_1": {"related_pairs": [["E1", "E2"], ["E2", "E1"]]}},
        "cross_case": {"related_pairs": [["E1", "E9"]]},
    }))
    gold = load_correlation_gold(p)
    assert not gold.is_template()
    assert gold.within_case["CASE_1"] == [("E1", "E2"), ("E2", "E1")]
    assert gold.cross_case == [("E1", "E9")]


def test_timeline_gold_template_parses_and_is_flagged_template():
    gold = load_timeline_gold(GT / "timeline_gold_template.json")
    assert gold.is_template()


def test_example_gold_files_are_valid_and_not_templates():
    """The demo example gold must stay parseable and populated (so the
    out-of-the-box `run_all_evaluations` demo keeps working)."""
    corr = load_correlation_gold(GT / "correlation_gold_example.json")
    assert not corr.is_template()
    assert corr.within_case and corr.cross_case  # both populated
    tl = load_timeline_gold(GT / "timeline_gold_example.json")
    assert not tl.is_template()
    # every timeline gold item has a non-empty order
    assert all(order for order in tl.order.values())


def test_ocr_and_entity_demo_files_are_valid():
    """The 6.1/6.2 demo files stay well-formed and reference real sample images."""
    corpus = json.loads((GT / "ocr_corpus_example.json").read_text(encoding="utf-8"))
    real = [i for i in corpus if not i["id"].startswith("_")]
    assert {i["id"] for i in real} >= {"scam_sms", "phishing_email"}
    for item in real:
        assert item["reference"] and item["image"]
        assert (GT.parents[1] / item["image"]).is_file()  # image actually exists
    gold = json.loads((GT / "entities_gold_example.json").read_text(encoding="utf-8"))
    assert gold["phishing_email"]["emails"] and gold["phishing_email"]["urls"]
    texts = json.loads((GT / "texts_example.json").read_text(encoding="utf-8"))
    assert set(texts) >= {"scam_sms", "phishing_email"}


def test_bad_pair_shape_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"within_case": {"C": {"related_pairs": [["only_one"]]}}}))
    with pytest.raises(ValueError):
        load_correlation_gold(p)
