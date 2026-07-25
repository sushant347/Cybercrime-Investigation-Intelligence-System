"""Table 6.3 (URL/Phishing classification) — regenerate from the real report.

Reads ``results/full_retraining_report_<run>.json`` (produced by
``src/training/full_retraining.py`` via ``train_from_datasets.py``) and prints
Precision / Recall / F1 / ROC-AUC / PR-AUC / FNR for every model, straight from
``test_evaluations.<model>`` (the held-out test split). No number is computed
here — this only reads and reshapes the artifact, so the table cannot drift
from what was actually measured.

Usage::

    python scripts/run_table_6_3.py \
        --report results/full_retraining_report_20260712T090000Z.json

The default report path is the latest ``full_retraining_report_*.json`` in
``results/``.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Dict, List

#: Column key in test_evaluations -> table header.
COLUMNS = [
    ("precision", "Precision"),
    ("recall", "Recall"),
    ("f1", "F1"),
    ("auc_roc", "ROC-AUC"),
    ("pr_auc", "PR-AUC"),
    ("false_negative_rate", "FNR"),
]

#: Display order (best-performing first); any extra models are appended.
PREFERRED_ORDER = [
    "xgboost", "lightgbm", "decision_tree", "random_forest",
    "extra_trees", "logistic_regression", "svm", "naive_bayes",
]


def build_table_6_3(report: Dict) -> List[Dict[str, object]]:
    """Return one row per model from ``test_evaluations`` (no computation)."""
    evals = report.get("test_evaluations")
    if not evals:
        raise ValueError("report has no 'test_evaluations' block")
    ordered = [m for m in PREFERRED_ORDER if m in evals]
    ordered += [m for m in sorted(evals) if m not in ordered]
    rows: List[Dict[str, object]] = []
    for model in ordered:
        metrics = evals[model]
        row: Dict[str, object] = {"model": model}
        for key, _ in COLUMNS:
            if key not in metrics:
                raise ValueError(f"model '{model}' missing metric '{key}'")
            row[key] = metrics[key]
        rows.append(row)
    return rows


def _default_report() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matches = sorted(glob.glob(os.path.join(here, "results", "full_retraining_report_*.json")))
    if not matches:
        raise SystemExit(
            "No results/full_retraining_report_*.json found. Provide --report, "
            "or run src/training/full_retraining.py to produce one."
        )
    return matches[-1]


def _format(rows: List[Dict[str, object]], test_n: int, production: str) -> str:
    header = f"{'Model':<20}" + "".join(f"{label:>10}" for _, label in COLUMNS)
    lines = [f"Table 6.3 — URL/Phishing classification (test set, n={test_n})",
             header, "-" * len(header)]
    for row in rows:
        name = row["model"] + (" *" if row["model"] == production else "")
        cells = "".join(f"{float(row[key]):>10.4f}" for key, _ in COLUMNS)
        lines.append(f"{name:<20}{cells}")
    lines.append(f"\n* deployed model: {production}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate Table 6.3 from the report.")
    parser.add_argument("--report", default=None, help="Path to full_retraining_report_*.json")
    parser.add_argument("--json", action="store_true", help="Emit rows as JSON")
    args = parser.parse_args()

    path = args.report or _default_report()
    with open(path, "r", encoding="utf-8") as handle:
        report = json.load(handle)

    rows = build_table_6_3(report)
    test_n = report.get("splits", {}).get("test", 0)
    production = (report.get("production_model") or {}).get("name", "")

    if args.json:
        print(json.dumps({"source": os.path.basename(path), "test_n": test_n,
                          "production_model": production, "rows": rows}, indent=2))
    else:
        print(f"Source: {os.path.basename(path)}  (run_id={report.get('run_id')})")
        print(_format(rows, test_n, production))


if __name__ == "__main__":
    main()
