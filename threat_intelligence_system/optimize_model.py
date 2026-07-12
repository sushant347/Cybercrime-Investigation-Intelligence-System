"""
Model optimisation via cross-validation (ML Improvement, step 3).

Compares XGBoost, LightGBM, CatBoost, Random Forest and Logistic Regression
(plus hyperparameter variants for the boosters) with stratified K-fold CV on
the cached feature matrices, one candidate per invocation so every run fits
a short execution window.

Usage:
    python optimize_model.py --list                 # show candidates
    python optimize_model.py --candidate xgb_default
    ...(run each candidate)...
    python optimize_model.py --summary              # rank + write report

Results accumulate in results/model_optimization_report.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, roc_auc_score, accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

CACHE = Path("data/processed/cache")
REPORT = Path("results/model_optimization_report.json")
CV_SAMPLE = 60000
FOLDS = 3
SEED = 42


def candidates() -> dict[str, dict]:
    """Candidate registry: model family + hyperparameters."""
    return {
        "logistic_regression": {"family": "logreg", "params": {"C": 1.0, "max_iter": 2000}},
        "random_forest": {"family": "rf", "params": {
            "n_estimators": 100, "max_depth": 20, "n_jobs": -1, "random_state": SEED}},
        "xgb_default": {"family": "xgb", "params": {
            "n_estimators": 300, "max_depth": 6, "learning_rate": 0.1,
            "subsample": 0.9, "colsample_bytree": 0.9}},
        "xgb_deep": {"family": "xgb", "params": {
            "n_estimators": 400, "max_depth": 9, "learning_rate": 0.1,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "min_child_weight": 3, "gamma": 0.1}},
        "xgb_regularised": {"family": "xgb", "params": {
            "n_estimators": 500, "max_depth": 7, "learning_rate": 0.07,
            "subsample": 0.9, "colsample_bytree": 0.7,
            "reg_alpha": 0.5, "reg_lambda": 2.0, "min_child_weight": 5}},
        "lgbm_default": {"family": "lgbm", "params": {
            "n_estimators": 400, "num_leaves": 63, "learning_rate": 0.1,
            "subsample": 0.9, "colsample_bytree": 0.9}},
        "lgbm_tuned": {"family": "lgbm", "params": {
            "n_estimators": 600, "num_leaves": 127, "learning_rate": 0.07,
            "min_child_samples": 30, "reg_alpha": 0.3, "reg_lambda": 1.0}},
        "catboost_default": {"family": "catboost", "params": {
            "iterations": 400, "depth": 8, "learning_rate": 0.1}},
    }


def build(family: str, params: dict, scale_pos_weight: float):
    """Instantiate a model for the given family."""
    if family == "logreg":
        return LogisticRegression(class_weight="balanced", **params)
    if family == "rf":
        return RandomForestClassifier(class_weight="balanced", **params)
    if family == "xgb":
        import xgboost as xgb
        return xgb.XGBClassifier(
            tree_method="hist", eval_metric="logloss", n_jobs=-1,
            random_state=SEED, scale_pos_weight=scale_pos_weight, **params)
    if family == "lgbm":
        import lightgbm as lgb
        return lgb.LGBMClassifier(
            n_jobs=-1, random_state=SEED, verbose=-1,
            scale_pos_weight=scale_pos_weight, **params)
    if family == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(
            verbose=False, random_seed=SEED,
            scale_pos_weight=scale_pos_weight, **params)
    raise ValueError(family)


def load_cv_data():
    """Load a stratified CV subsample from the cached training matrix."""
    X = np.load(CACHE / "train_curated_X.npy")
    y = np.load(CACHE / "train_curated_y.npy")
    rng = np.random.RandomState(SEED)
    idx = rng.choice(len(y), size=min(CV_SAMPLE, len(y)), replace=False)
    return X[idx], y[idx]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    registry = candidates()
    if args.list:
        print("\n".join(registry))
        return 0

    report = json.loads(REPORT.read_text()) if REPORT.exists() else {"candidates": {}}

    if args.summary:
        ranked = sorted(
            report["candidates"].items(),
            key=lambda kv: kv[1].get("cv_f1_mean", 0), reverse=True,
        )
        report["ranking"] = [name for name, _ in ranked]
        report["best_candidate"] = ranked[0][0] if ranked else None
        report["cv_config"] = {"folds": FOLDS, "sample": CV_SAMPLE, "seed": SEED}
        REPORT.write_text(json.dumps(report, indent=2))
        for name, res in ranked:
            print(f"{name:<22} f1={res['cv_f1_mean']:.4f}±{res['cv_f1_std']:.4f} "
                  f"auc={res['cv_auc_mean']:.4f} acc={res['cv_acc_mean']:.4f} "
                  f"({res['fit_seconds']:.0f}s)")
        print(f"\nBEST: {report['best_candidate']}  -> {REPORT}")
        return 0

    spec = registry[args.candidate]
    X, y = load_cv_data()
    spw = float((y == 0).sum() / max(1, (y == 1).sum()))

    scaler = None
    if spec["family"] == "logreg":
        scaler = StandardScaler()
        X = scaler.fit_transform(X)

    f1s, aucs, accs = [], [], []
    t0 = time.time()
    for tr, va in StratifiedKFold(FOLDS, shuffle=True, random_state=SEED).split(X, y):
        model = build(spec["family"], spec["params"], spw)
        model.fit(X[tr], y[tr])
        proba = model.predict_proba(X[va])[:, 1]
        pred = (proba >= 0.5).astype(int)
        f1s.append(f1_score(y[va], pred))
        aucs.append(roc_auc_score(y[va], proba))
        accs.append(accuracy_score(y[va], pred))

    report["candidates"][args.candidate] = {
        "family": spec["family"],
        "params": spec["params"],
        "cv_f1_mean": float(np.mean(f1s)), "cv_f1_std": float(np.std(f1s)),
        "cv_auc_mean": float(np.mean(aucs)),
        "cv_acc_mean": float(np.mean(accs)),
        "fit_seconds": time.time() - t0,
        "scale_pos_weight": spw,
    }
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2))
    print(f"{args.candidate}: f1={np.mean(f1s):.4f} auc={np.mean(aucs):.4f} "
          f"acc={np.mean(accs):.4f} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
