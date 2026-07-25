"""Table 6.3 builder — reshapes test_evaluations without inventing numbers."""

import importlib.util
import os

import pytest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "run_table_6_3.py",
)
_spec = importlib.util.spec_from_file_location("run_table_6_3", _SCRIPT)
run_table_6_3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_table_6_3)


def _report():
    return {
        "splits": {"train": 4, "validation": 2, "test": 2},
        "production_model": {"name": "xgboost"},
        "test_evaluations": {
            "naive_bayes": {"precision": 0.85, "recall": 0.75, "f1": 0.80,
                            "auc_roc": 0.89, "pr_auc": 0.87, "false_negative_rate": 0.24},
            "xgboost": {"precision": 0.976, "recall": 0.984, "f1": 0.980,
                        "auc_roc": 0.997, "pr_auc": 0.998, "false_negative_rate": 0.016},
        },
    }


def test_rows_are_copied_verbatim_from_test_evaluations():
    rows = run_table_6_3.build_table_6_3(_report())
    by_model = {r["model"]: r for r in rows}
    assert by_model["xgboost"]["f1"] == 0.980  # exactly the source value
    assert by_model["naive_bayes"]["false_negative_rate"] == 0.24


def test_preferred_order_puts_xgboost_first():
    rows = run_table_6_3.build_table_6_3(_report())
    assert rows[0]["model"] == "xgboost"  # despite naive_bayes being first in the dict


def test_missing_metric_is_an_error_not_a_guess():
    bad = _report()
    del bad["test_evaluations"]["xgboost"]["pr_auc"]
    with pytest.raises(ValueError):
        run_table_6_3.build_table_6_3(bad)


def test_no_test_evaluations_raises():
    with pytest.raises(ValueError):
        run_table_6_3.build_table_6_3({"splits": {"test": 1}})
