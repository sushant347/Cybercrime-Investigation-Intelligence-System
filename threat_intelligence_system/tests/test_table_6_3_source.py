"""Table 6.3 provenance + internal-consistency verification.

Confirms the table is sourced from the RIGHT artifact (the full retraining
report with test_evaluations), not the insufficient baseline_comparison_report,
and that the stored confusion matrix is internally consistent with the stored
precision/recall/f1 (so the numbers cannot be silently corrupted or swapped).

Skips cleanly when the (gitignored) report is not present on this machine —
it never fabricates a value.
"""

import glob
import json
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _report_path():
    matches = sorted(glob.glob(os.path.join(_ROOT, "results", "full_retraining_report_*.json")))
    return matches[-1] if matches else None


REPORT = _report_path()
pytestmark = pytest.mark.skipif(
    REPORT is None,
    reason="full_retraining_report_*.json not present (gitignored artifact).",
)


def _load():
    with open(REPORT, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_report_is_the_full_retraining_report_not_baseline():
    """The source must be the fuller report — the one WITH test_evaluations."""
    assert os.path.basename(REPORT).startswith("full_retraining_report_")
    report = _load()
    assert "test_evaluations" in report, "wrong source: no held-out test_evaluations"
    # the insufficient baseline report lacks precision/recall/FNR/PR-AUC
    xgb = report["test_evaluations"]["xgboost"]
    for required in ("precision", "recall", "f1", "auc_roc", "pr_auc",
                     "false_negative_rate", "confusion_matrix"):
        assert required in xgb, f"source missing '{required}'"


def test_confusion_matrix_is_consistent_with_reported_scores():
    """[[TN,FP],[FN,TP]] must reproduce the reported precision/recall/f1."""
    report = _load()
    for model, metrics in report["test_evaluations"].items():
        (tn, fp), (fn, tp) = metrics["confusion_matrix"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        fnr = fn / (fn + tp) if (fn + tp) else 0.0
        assert precision == pytest.approx(metrics["precision"], abs=1e-4), model
        assert recall == pytest.approx(metrics["recall"], abs=1e-4), model
        assert f1 == pytest.approx(metrics["f1"], abs=1e-4), model
        assert fnr == pytest.approx(metrics["false_negative_rate"], abs=1e-4), model
        assert (tp + tn + fp + fn) == report["splits"]["test"], f"{model}: n mismatch"


def test_deployed_model_matches_production_selection():
    report = _load()
    assert report["production_model"]["name"] == "xgboost"  # verified deployed model
