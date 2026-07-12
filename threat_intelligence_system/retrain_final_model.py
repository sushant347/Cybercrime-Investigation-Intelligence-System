"""
Final model retraining on the curated dataset (ML Improvement).

Trains the CV-winning XGBoost configuration on the cached 200k curated
training matrix, selects the best calibration method on validation,
evaluates on the held-out test matrix, stamps complete version metadata,
and saves the production checkpoint.

Phased so every step fits a short execution window:
    python retrain_final_model.py --phase train
    python retrain_final_model.py --phase finalize
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np

CACHE = Path("data/processed/cache")
CHECKPOINTS = Path("checkpoints")
RESULTS = Path("results")
TMP_MODEL = CHECKPOINTS / "xgboost_v3_intermediate.pkl"
FINAL_MODEL = CHECKPOINTS / "xgboost.pkl"
BACKUP_MODEL = CHECKPOINTS / "xgboost_v2_backup.pkl"

MODEL_VERSION = "3.0.0"
FEATURE_VERSION = "2.0.0"
DATASET_VERSION = "ds-curated-200k-v3"

# CV winner from optimize_model.py (xgb_regularised)
BEST_PARAMS = dict(
    n_estimators=500, max_depth=7, learning_rate=0.07,
    subsample=0.9, colsample_bytree=0.7,
    reg_alpha=0.5, reg_lambda=2.0, min_child_weight=5, gamma=0.0,
)


def load(split: str):
    X = np.load(CACHE / f"{split}_X.npy")
    y = np.load(CACHE / f"{split}_y.npy")
    return X, y


def phase_train() -> None:
    import logging; logging.disable(logging.INFO)
    from src.models.baseline_models import create_baseline_model

    X_train, y_train = load("train_curated")
    X_val, y_val = load("validation")
    meta = json.loads((CACHE / "train_curated_meta.json").read_text())
    feature_names = meta["feature_names"]

    model = create_baseline_model("xgboost", **BEST_PARAMS)
    spw = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))
    model.model.set_params(scale_pos_weight=spw)

    metrics = model.train(X_train, y_train, X_val, y_val, feature_names=feature_names)
    model.save(TMP_MODEL)
    print(f"trained on {len(y_train)} rows, spw={spw:.2f}")
    print({k: round(float(v), 4) for k, v in metrics.items()})


def phase_finalize() -> None:
    import logging; logging.disable(logging.INFO)
    from src.evaluation.evaluator import ModelEvaluator
    from src.models.baseline_models import create_baseline_model
    from src.scoring.calibrator import CalibrationEvaluator, ConfidenceCalibrator

    X_val, y_val = load("validation")
    X_test, y_test = load("test")

    model = create_baseline_model("xgboost")
    model.load(TMP_MODEL)

    # Best calibration method on validation (Platt / Isotonic / Temperature)
    raw_val = np.asarray(model.predict_proba_raw(X_val), dtype=float)
    cal_report = CalibrationEvaluator().evaluate_methods(y_val, raw_val)
    best_method = cal_report["best_method"]
    model.calibrator = ConfidenceCalibrator(method=best_method)
    model.calibrator.fit(np.asarray(y_val, float), raw_val)

    evaluator = ModelEvaluator(results_dir=RESULTS)
    val_result = evaluator.evaluate(
        "xgboost_v3_validation", y_val,
        (np.asarray(model.predict_proba(X_val)) >= 0.5).astype(int),
        np.asarray(model.predict_proba(X_val)),
    )
    test_result = evaluator.evaluate(
        "xgboost_v3_test", y_test,
        (np.asarray(model.predict_proba(X_test)) >= 0.5).astype(int),
        np.asarray(model.predict_proba(X_test)),
    )

    # Complete version metadata (ML Improvement, step 8)
    md = model.metadata
    md.model_version = MODEL_VERSION
    md.dataset_version = DATASET_VERSION
    md.feature_version = FEATURE_VERSION
    md.calibration_version = f"cal-{best_method}-v3"
    md.training_date = datetime.now(timezone.utc).isoformat()
    md.validation_metrics = {
        k: float(v) for k, v in val_result.to_dict().items()
        if isinstance(v, (int, float))
    }

    # Backup previous production checkpoint, then promote
    if FINAL_MODEL.exists() and not BACKUP_MODEL.exists():
        shutil.copy2(FINAL_MODEL, BACKUP_MODEL)
    model.save(FINAL_MODEL)

    report = {
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "feature_version": FEATURE_VERSION,
        "calibration": {
            "best_method": best_method,
            "uncalibrated": cal_report["uncalibrated"],
            "methods": {m: {k: v for k, v in d.items() if k != "reliability"}
                        for m, d in cal_report["methods"].items()},
        },
        "params": BEST_PARAMS,
        "validation": val_result.to_dict(),
        "test": test_result.to_dict(),
        "checkpoint": str(FINAL_MODEL),
        "backup_of_previous": str(BACKUP_MODEL),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    out = RESULTS / "final_model_v3_report.json"
    out.write_text(json.dumps(report, indent=2, default=str))

    print(f"calibration: {best_method}")
    print(f"val : acc={val_result.accuracy:.4f} f1={val_result.f1:.4f} auc={val_result.auc_roc:.4f} "
          f"fpr={val_result.false_positive_rate:.4f} fnr={val_result.false_negative_rate:.4f}")
    print(f"test: acc={test_result.accuracy:.4f} f1={test_result.f1:.4f} auc={test_result.auc_roc:.4f} "
          f"fpr={test_result.false_positive_rate:.4f} fnr={test_result.false_negative_rate:.4f} "
          f"brier={test_result.brier_score:.4f} ece={test_result.expected_calibration_error:.4f}")
    print(f"saved: {FINAL_MODEL} (previous backed up to {BACKUP_MODEL})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["train", "finalize"], required=True)
    args = parser.parse_args()
    if args.phase == "train":
        phase_train()
    else:
        phase_finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
