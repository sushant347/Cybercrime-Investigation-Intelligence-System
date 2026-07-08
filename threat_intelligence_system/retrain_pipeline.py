"""
CLI for the versioned retraining pipeline (Phase 3-F).

Usage:
    python retrain_pipeline.py [--model xgboost] [--no-feedback]
                               [--extra path.csv ...] [--sample N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.training.retraining_pipeline import RetrainingPipeline


def main() -> int:
    """Entry point for the retraining CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="xgboost", help="Baseline model type.")
    parser.add_argument(
        "--no-feedback", action="store_true",
        help="Do not merge investigator corrections into training data.",
    )
    parser.add_argument(
        "--extra", nargs="*", type=Path, default=None,
        help="Extra CSV datasets (url,label) to merge into training.",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Cap rows per split (smoke testing).",
    )
    args = parser.parse_args()

    pipeline = RetrainingPipeline(model_type=args.model)
    report = pipeline.run(
        include_feedback=not args.no_feedback,
        extra_datasets=args.extra,
        sample=args.sample,
    )

    print(f"Retraining complete: {report['run_id']}")
    print(f"  Model version      : {report['versions']['model_version']}")
    print(f"  Dataset version    : {report['versions']['dataset_version']}")
    print(f"  Calibration        : {report['calibration']['best_method']}")
    print(f"  Test accuracy      : {report['benchmark']['accuracy']:.4f}")
    print(f"  Test F1            : {report['benchmark']['f1']:.4f}")
    print(f"  Checkpoint         : {report['checkpoint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
