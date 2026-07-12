"""
CLI for the full dataset-replacement retraining pipeline.

Trains every supported baseline model exclusively on the datasets found in
the configurable dataset directory (DATASET_PATH / config/settings.yaml
``dataset_path``, default ``../sample``).  By default the FULL dataset is
used (no row cap), models are compared with Stratified 5-Fold
cross-validation, the production model's calibration is analyzed (and
recalibrated when beneficial), error-analysis CSVs are exported and
evaluation figures (ROC / PR / calibration / confusion matrix / feature
importance / SHAP summary) are rendered as PNG + PDF.

Usage:
    python train_from_datasets.py
    python train_from_datasets.py --tune --trials 25
    python train_from_datasets.py --models xgboost lightgbm random_forest
    python train_from_datasets.py --dataset-dir ../sample --workers 2
    python train_from_datasets.py --sample 20000 --no-cv --no-reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.training.full_retraining import FullRetrainingPipeline


def main() -> int:
    """Entry point for the full retraining CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir", type=Path, default=None,
        help="Override the configured dataset directory (DATASET_PATH).",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Cap total merged rows (smoke testing). Default: full dataset.",
    )
    parser.add_argument(
        "--models", nargs="*", default=None,
        help="Subset of models to train (default: all registered models).",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Worker processes for feature extraction (default: CPU count).",
    )
    parser.add_argument(
        "--tune", action="store_true",
        help="Run Optuna hyperparameter optimization before training.",
    )
    parser.add_argument(
        "--trials", type=int, default=None,
        help="Optuna trials per tuned model (default: OPTUNA_TRIALS).",
    )
    parser.add_argument(
        "--no-cv", action="store_true",
        help="Skip the Stratified K-Fold cross-validation stage.",
    )
    parser.add_argument(
        "--cv-sample", type=int, default=None,
        help="Stratified row cap for CV only (default: CV_SAMPLE_SIZE).",
    )
    parser.add_argument(
        "--no-recalibrate", action="store_true",
        help="Skip calibration analysis / automatic recalibration.",
    )
    parser.add_argument(
        "--no-error-analysis", action="store_true",
        help="Skip FP/FN/high-confidence-mistake CSV export.",
    )
    parser.add_argument(
        "--no-reports", action="store_true",
        help="Skip PNG/PDF evaluation report generation.",
    )
    args = parser.parse_args()

    pipeline = FullRetrainingPipeline(
        dataset_dir=args.dataset_dir, n_workers=args.workers
    )
    report = pipeline.run(
        sample=args.sample,
        model_names=args.models,
        tune=args.tune,
        tuning_trials=args.trials,
        cross_validate=not args.no_cv,
        cv_sample=args.cv_sample,
        auto_recalibrate=not args.no_recalibrate,
        error_analysis=not args.no_error_analysis,
        generate_reports=not args.no_reports,
    )

    prep = report["preprocessing"]
    prod = report["production_model"]
    print(f"Full retraining complete: {report['run_id']}")
    print(f"  Dataset files used : {prep['files_used']}/{prep['files_discovered']}")
    print(f"  Final dataset size : {prep['final_rows']} "
          f"(phishing={prep['final_phishing']}, legitimate={prep['final_legitimate']})")
    print(f"  Production model   : {prod['name']}")
    print(f"  Checkpoints        : {report['checkpoint_dir']}")
    print(f"  Duration           : {report['training_duration_seconds']}s")
    for name, ev in sorted(
        report["test_evaluations"].items(),
        key=lambda kv: kv[1].get("f1", 0), reverse=True,
    ):
        print(f"    {name:<22} F1={ev['f1']:.4f} AUC={ev['auc_roc']:.4f} "
              f"Rec={ev['recall']:.4f} Prec={ev['precision']:.4f} "
              f"MCC={ev['mcc']:.4f}")
    cv = report.get("cross_validation") or {}
    if cv:
        print("  Cross-validation (mean +/- std):")
        for name, r in sorted(cv.items(), key=lambda kv: -kv[1]["mean"]["f1"]):
            print(f"    {name:<22} F1={r['mean']['f1']:.4f}+/-{r['std']['f1']:.4f} "
                  f"AUC={r['mean']['roc_auc']:.4f}+/-{r['std']['roc_auc']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
