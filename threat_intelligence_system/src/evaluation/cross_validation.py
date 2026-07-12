"""
Stratified k-fold cross-validation for the Phishing URL Detection Engine.

Replaces the simple train/validation comparison with a statistically robust
Stratified K-Fold evaluation.  For every model the full metric suite is
reported per fold and aggregated as mean +/- standard deviation:

    Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, MCC

Design notes
------------
* ``evaluate_fold`` is a public, self-contained unit of work so callers may
  execute folds independently (e.g. resumable / distributed execution) and
  aggregate afterwards with ``aggregate``.
* ``cross_validate`` is the convenience end-to-end API used on machines
  without execution-time constraints.
* A configurable stratified ``sample_size`` (0 = use everything) bounds the
  CV cost on very large datasets without touching the final training run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from src.config.settings import get_settings
from src.models.baseline_models import create_baseline_model
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Metrics reported per fold and aggregated across folds.
CV_METRICS: tuple[str, ...] = (
    "accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "mcc",
)


@dataclass
class CrossValidationResult:
    """Aggregated cross-validation result for one model.

    Attributes:
        model_name: Registry key of the evaluated model.
        n_folds: Number of folds evaluated.
        n_samples: Number of samples used for CV.
        fold_metrics: Per-fold metric dictionaries.
        mean: Mean of each metric across folds.
        std: Standard deviation of each metric across folds.
    """

    model_name: str
    n_folds: int = 0
    n_samples: int = 0
    fold_metrics: list[dict[str, float]] = field(default_factory=list)
    mean: dict[str, float] = field(default_factory=dict)
    std: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "model_name": self.model_name,
            "n_folds": self.n_folds,
            "n_samples": self.n_samples,
            "fold_metrics": self.fold_metrics,
            "mean": self.mean,
            "std": self.std,
        }


class CrossValidator:
    """Stratified k-fold cross-validation runner.

    Args:
        n_folds: Number of stratified folds (default 5).
        sample_size: Optional stratified cap on rows used for CV
            (0 = use every row).  Bounds cost on very large datasets;
            the final model training is unaffected.
        random_seed: Seed for fold shuffling and sampling.
        results_dir: Directory for the JSON cross-validation report.
    """

    def __init__(
        self,
        n_folds: int = 5,
        sample_size: int = 0,
        random_seed: int | None = None,
        results_dir: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.n_folds = int(n_folds)
        self.sample_size = int(sample_size)
        self.random_seed = (
            random_seed if random_seed is not None
            else settings.dataset.random_seed
        )
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        logger.info(
            "CrossValidator initialised - folds=%d sample=%s seed=%d",
            self.n_folds, self.sample_size or "all", self.random_seed,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subsample(
        self, X: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Stratified subsample of (X, y) honouring ``sample_size``."""
        if not self.sample_size or self.sample_size >= len(y):
            return X, y
        rng = np.random.RandomState(self.random_seed)
        idx_parts = []
        for cls in np.unique(y):
            cls_idx = np.where(y == cls)[0]
            take = int(round(self.sample_size * len(cls_idx) / len(y)))
            idx_parts.append(rng.choice(cls_idx, size=min(take, len(cls_idx)),
                                        replace=False))
        idx = np.concatenate(idx_parts)
        rng.shuffle(idx)
        logger.info("CV subsample: %d -> %d rows", len(y), len(idx))
        return X[idx], y[idx]

    def fold_indices(
        self, y: np.ndarray
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Deterministic stratified fold indices for *y*."""
        skf = StratifiedKFold(
            n_splits=self.n_folds, shuffle=True, random_state=self.random_seed
        )
        return list(skf.split(np.zeros(len(y)), y))

    def evaluate_fold(
        self,
        model_name: str,
        X: np.ndarray,
        y: np.ndarray,
        fold_index: int,
        model_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, float]:
        """Train and evaluate one fold; self-contained and resumable.

        Args:
            model_name: Key from ``BASELINE_MODEL_REGISTRY``.
            X: Full CV feature matrix (already subsampled if desired).
            y: Full CV label vector.
            fold_index: Which fold (0-based) to evaluate.
            model_params: Optional hyperparameter overrides.

        Returns:
            Metric dictionary for the fold (keys: ``CV_METRICS`` + ``fold``).
        """
        train_idx, test_idx = self.fold_indices(y)[fold_index]
        model = create_baseline_model(model_name, **(model_params or {}))
        estimator = model.model
        estimator.fit(X[train_idx], y[train_idx])

        y_pred = estimator.predict(X[test_idx])
        if hasattr(estimator, "predict_proba"):
            y_proba = estimator.predict_proba(X[test_idx])[:, 1]
        elif hasattr(estimator, "decision_function"):
            decision = estimator.decision_function(X[test_idx])
            y_proba = 1.0 / (1.0 + np.exp(-decision))
        else:  # pragma: no cover - all registry models expose one of the two
            y_proba = y_pred.astype(float)

        y_test = y[test_idx]
        metrics = {
            "fold": float(fold_index),
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "mcc": float(matthews_corrcoef(y_test, y_pred)),
        }
        try:
            metrics["roc_auc"] = float(roc_auc_score(y_test, y_proba))
            metrics["pr_auc"] = float(average_precision_score(y_test, y_proba))
        except ValueError:  # single-class fold edge case
            metrics["roc_auc"] = 0.0
            metrics["pr_auc"] = 0.0

        logger.info(
            "CV %s fold %d/%d - F1=%.4f AUC=%.4f",
            model_name, fold_index + 1, self.n_folds,
            metrics["f1"], metrics["roc_auc"],
        )
        return metrics

    @staticmethod
    def aggregate(
        model_name: str,
        fold_metrics: list[dict[str, float]],
        n_samples: int,
    ) -> CrossValidationResult:
        """Aggregate per-fold metrics into mean +/- std."""
        result = CrossValidationResult(
            model_name=model_name,
            n_folds=len(fold_metrics),
            n_samples=int(n_samples),
            fold_metrics=fold_metrics,
        )
        for metric in CV_METRICS:
            values = np.array([m[metric] for m in fold_metrics], dtype=float)
            result.mean[metric] = float(values.mean())
            result.std[metric] = float(values.std())
        return result

    def cross_validate(
        self,
        model_name: str,
        X: np.ndarray,
        y: np.ndarray,
        model_params: Optional[dict[str, Any]] = None,
    ) -> CrossValidationResult:
        """Run the complete stratified k-fold CV for one model."""
        X_cv, y_cv = self.subsample(np.asarray(X), np.asarray(y))
        fold_metrics = [
            self.evaluate_fold(model_name, X_cv, y_cv, fold, model_params)
            for fold in range(self.n_folds)
        ]
        result = self.aggregate(model_name, fold_metrics, len(y_cv))
        logger.info(
            "CV %s complete: F1=%.4f+/-%.4f ROC-AUC=%.4f+/-%.4f",
            model_name, result.mean["f1"], result.std["f1"],
            result.mean["roc_auc"], result.std["roc_auc"],
        )
        return result

    def save_report(
        self,
        results: dict[str, CrossValidationResult],
        filename: str = "cross_validation_report.json",
    ) -> Path:
        """Persist all CV results as a single JSON report."""
        report = {
            "n_folds": self.n_folds,
            "sample_size": self.sample_size,
            "random_seed": self.random_seed,
            "models": {name: r.to_dict() for name, r in results.items()},
        }
        path = self.results_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("Cross-validation report saved to %s", path)
        return path
