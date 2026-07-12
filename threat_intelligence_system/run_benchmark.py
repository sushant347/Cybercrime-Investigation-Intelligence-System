"""
Permanent benchmark runner (ML Improvement, step 7).

Evaluates the production model against the permanent benchmark dataset
(data/processed/benchmark_dataset.csv -- 1000 legitimate + 1000 phishing
URLs, held stable across model versions) and appends the full metric suite
to results/benchmarks/benchmark_history.jsonl so every model version can be
compared over time.  Also stamps the metrics into the model checkpoint's
metadata (step 8).

Usage:  python run_benchmark.py [--model xgboost] [--no-stamp]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

BENCHMARK_CSV = Path("data/processed/benchmark_dataset.csv")
HISTORY = Path("results/benchmarks/benchmark_history.jsonl")


def main() -> int:
    import logging; logging.disable(logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="xgboost")
    parser.add_argument("--no-stamp", action="store_true",
                        help="Do not write benchmark metrics into the checkpoint.")
    args = parser.parse_args()

    from src.evaluation.evaluator import ModelEvaluator
    from src.feature_engineering.pipeline import FeaturePipeline
    from src.models.baseline_models import create_baseline_model

    df = pd.read_csv(BENCHMARK_CSV)[["url", "label"]].dropna()
    y = df["label"].astype(int).to_numpy()

    pipeline = FeaturePipeline()
    names = pipeline.get_feature_names()
    X = np.zeros((len(df), len(names)), dtype=float)
    for i, url in enumerate(df["url"].astype(str)):
        try:
            feats = pipeline.extract(url)
        except Exception:  # noqa: BLE001
            feats = {}
        for j, name in enumerate(names):
            value = feats.get(name)
            try:
                X[i, j] = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                X[i, j] = 0.0

    checkpoint = Path("checkpoints") / f"{args.model}.pkl"
    model = create_baseline_model(args.model)
    model.load(checkpoint)

    proba = np.asarray(model.predict_proba(X), dtype=float)
    pred = (proba >= 0.5).astype(int)

    result = ModelEvaluator().evaluate(
        f"{args.model}-benchmark", y, pred, proba
    )
    metrics = {
        k: v for k, v in result.to_dict().items()
        if isinstance(v, (int, float))
    }

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_type": args.model,
        "model_version": model.metadata.model_version,
        "dataset_version": model.metadata.dataset_version,
        "feature_version": model.metadata.feature_version,
        "calibration_version": model.metadata.calibration_version,
        "benchmark_rows": int(len(df)),
        "metrics": metrics,
    }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    if not args.no_stamp:
        model.metadata.benchmark_metrics = {
            k: float(v) for k, v in metrics.items()
        }
        model.save(checkpoint)

    print(f"model={record['model_version']} on {len(df)} benchmark URLs")
    print(f"acc={result.accuracy:.4f} precision={result.precision:.4f} "
          f"recall={result.recall:.4f} f1={result.f1:.4f}")
    print(f"auc={result.auc_roc:.4f} fpr={result.false_positive_rate:.4f} "
          f"fnr={result.false_negative_rate:.4f} brier={result.brier_score:.4f} "
          f"ece={result.expected_calibration_error:.4f}")
    print(f"history: {HISTORY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
