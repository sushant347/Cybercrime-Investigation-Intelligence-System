"""Unit tests for Phase-2 accuracy evaluation (correlation + timeline)."""
import math

from ciis_correlation.evaluation import (
    evaluate_correlation,
    evaluate_timeline,
    predicted_order,
    predicted_related_pairs,
)


# --------------------------------------------------------------- correlation
def test_correlation_perfect():
    gold = [("E1", "E2"), ("E2", "E3")]
    pred = [("E2", "E1"), ("E3", "E2")]  # order-independent
    res = evaluate_correlation(gold, pred)
    assert res.precision == 1.0 and res.recall == 1.0 and res.f1 == 1.0


def test_correlation_partial():
    gold = [("E1", "E2"), ("E2", "E3")]
    pred = [("E1", "E2"), ("E1", "E3")]  # one right, one spurious
    res = evaluate_correlation(gold, pred)
    assert res.tp == 1 and res.fp == 1 and res.fn == 1
    assert math.isclose(res.f1, 0.5)


def test_predicted_related_pairs_filters_no_relationship():
    analysis = {
        "pairs": [
            {"evidence_a": "E1", "evidence_b": "E2", "relationship_strength": "STRONG"},
            {"evidence_a": "E1", "evidence_b": "E3", "relationship_strength": "NO_RELATIONSHIP"},
        ]
    }
    related = predicted_related_pairs(analysis)
    assert frozenset({"E1", "E2"}) in related
    assert frozenset({"E1", "E3"}) not in related


# ------------------------------------------------------------------ timeline
def test_timeline_exact_order():
    gold = ["E1", "E2", "E3"]
    res = evaluate_timeline(gold, ["E1", "E2", "E3"])
    assert res.pairwise_accuracy == 1.0
    assert res.kendall_tau == 1.0
    assert res.exact_match is True


def test_timeline_fully_reversed():
    gold = ["E1", "E2", "E3"]
    res = evaluate_timeline(gold, ["E3", "E2", "E1"])
    assert res.pairwise_accuracy == 0.0
    assert res.kendall_tau == -1.0


def test_timeline_one_swap():
    gold = ["E1", "E2", "E3"]
    res = evaluate_timeline(gold, ["E2", "E1", "E3"])
    # 2 of 3 pairs concordant.
    assert math.isclose(res.pairwise_accuracy, 2 / 3)


def test_timeline_handles_missing_items():
    gold = ["E1", "E2", "E3", "E4"]
    res = evaluate_timeline(gold, ["E1", "E3"])  # only 2 comparable
    assert res.comparable_pairs == 1
    assert res.pairwise_accuracy == 1.0


def test_predicted_order_dedupes():
    analysis = {
        "events": [
            {"evidence_id": "E1"},
            {"evidence_id": "E1"},
            {"evidence_id": "E2"},
        ]
    }
    assert predicted_order(analysis) == ["E1", "E2"]
