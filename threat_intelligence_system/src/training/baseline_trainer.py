"""
Baseline model trainer for the Phishing URL Detection Engine.

Orchestrates training, evaluation, and comparison of all baseline models.
Handles feature extraction from URLs, model training, checkpoint saving,
and generation of comparison reports.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.models.baseline_models import (
    BaselineModel,
    create_all_baseline_models,
    create_baseline_model,
    BASELINE_MODEL_REGISTRY,
)
from src.utils.exceptions import ModelError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaselineTrainer:
    """
    Trainer for baseline (sklearn-based) phishing URL detection models.

    Manages the end-to-end training workflow:
    1. Accept pre-extracted feature matrices or raw DataFrames.
    2. Train one or all baseline models.
    3. Evaluate on validation/test sets.
    4. Save model checkpoints.
    5. Generate comparison reports.

    Attributes:
        checkpoint_dir: Directory for saving model checkpoints.
        results_dir: Directory for saving evaluation reports.
    """

    def __init__(
        self,
        checkpoint_dir: Path | None = None,
        results_dir: Path | None = None,
    ) -> None:
        """
        Initialize the baseline trainer.

        Args:
            checkpoint_dir: Directory for model checkpoints. Defaults to settings.
            results_dir: Directory for evaluation reports. Defaults to settings.
        """
        settings = get_settings()
        self.checkpoint_dir = Path(checkpoint_dir or settings.paths.checkpoint_dir)
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._trained_models: dict[str, BaselineModel] = {}
        self._training_results: dict[str, dict[str, Any]] = {}

        logger.info(
            "BaselineTrainer initialized -- checkpoints: %s, results: %s",
            self.checkpoint_dir, self.results_dir,
        )

    def train_model(
        self,
        model_name: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        save_checkpoint: bool = True,
        feature_names: Optional[list[str]] = None,
        **model_kwargs: Any,
    ) -> dict[str, float]:
        """
        Train a single baseline model.

        Args:
            model_name: Model key from BASELINE_MODEL_REGISTRY.
            X_train: Training feature matrix.
            y_train: Training labels.
            X_val: Optional validation features.
            y_val: Optional validation labels.
            save_checkpoint: Whether to save the model after training.
            feature_names: Optional ordered list of feature names.
            **model_kwargs: Additional hyperparameters for the model.

        Returns:
            Dictionary of training metrics.

        Raises:
            ModelError: If training fails.
        """
        logger.info("Training model: %s", model_name)
        start_time = time.perf_counter()

        model = create_baseline_model(model_name, **model_kwargs)
        
        # Populate model metadata versioning info
        from datetime import datetime
        model._metadata.model_version = "2.0.0"
        model._metadata.training_date = datetime.now().isoformat()
        model._metadata.dataset_version = "2.0.0"
        model._metadata.feature_version = "2.0.0"
        model._metadata.calibration_version = "2.0.0"

        metrics = model.train(X_train, y_train, X_val, y_val, feature_names=feature_names)

        elapsed = time.perf_counter() - start_time
        metrics["training_time_seconds"] = round(elapsed, 2)

        self._trained_models[model_name] = model
        self._training_results[model_name] = {
            "metrics": metrics,
            "training_time": elapsed,
            "training_samples": len(y_train),
            "feature_count": X_train.shape[1],
        }

        if save_checkpoint:
            checkpoint_path = self.checkpoint_dir / f"{model_name}.pkl"
            model.save(checkpoint_path)
            logger.info("Checkpoint saved: %s", checkpoint_path)
            
            # Run regression suite
            try:
                from src.evaluation.regression_suite import run_regression_suite
                from src.feature_engineering.pipeline import FeaturePipeline
                run_regression_suite(model, FeaturePipeline(), model_name)
            except Exception as reg_err:
                logger.warning("Failed to run regression test suite: %s", reg_err)

        return metrics

    def train_all(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        save_checkpoints: bool = True,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, dict[str, float]]:
        """
        Train all available baseline models.

        Args:
            X_train: Training feature matrix.
            y_train: Training labels.
            X_val: Optional validation features.
            y_val: Optional validation labels.
            save_checkpoints: Whether to save all models.
            feature_names: Optional ordered list of feature names.

        Returns:
            Dictionary mapping model names to their metrics.
        """
        logger.info(
            "Training all %d baseline models on %d samples",
            len(BASELINE_MODEL_REGISTRY), len(y_train),
        )

        all_metrics = {}
        for model_name in BASELINE_MODEL_REGISTRY:
            try:
                metrics = self.train_model(
                    model_name, X_train, y_train, X_val, y_val,
                    save_checkpoint=save_checkpoints,
                    feature_names=feature_names,
                )
                all_metrics[model_name] = metrics
            except Exception as e:
                logger.error("Failed to train %s: %s", model_name, e)
                all_metrics[model_name] = {"error": str(e)}

        # Generate comparison report
        self._generate_comparison_report(all_metrics)

        return all_metrics

    def get_model(self, model_name: str) -> BaselineModel:
        """
        Get a trained model by name.

        Args:
            model_name: Model key.

        Returns:
            Trained BaselineModel instance.

        Raises:
            ModelError: If model hasn't been trained.
        """
        if model_name not in self._trained_models:
            # Try loading from checkpoint
            checkpoint_path = self.checkpoint_dir / f"{model_name}.pkl"
            if checkpoint_path.exists():
                model = create_baseline_model(model_name)
                model.load(checkpoint_path)
                self._trained_models[model_name] = model
            else:
                raise ModelError(
                    model_name, "get",
                    f"Model not trained and no checkpoint found at {checkpoint_path}"
                )
        return self._trained_models[model_name]

    def get_best_model(self, metric: str = "val_f1") -> tuple[str, BaselineModel]:
        """
        Get the best-performing model based on a specified metric.

        Args:
            metric: Metric key to compare (e.g., 'val_f1', 'val_accuracy', 'val_auc').

        Returns:
            Tuple of (model_name, model_instance).

        Raises:
            ModelError: If no models have been trained.
        """
        if not self._trained_models:
            raise ModelError("none", "get_best", "No models have been trained")

        best_name = None
        best_score = -1.0

        for name, model in self._trained_models.items():
            score = model.metadata.training_metrics.get(metric, 0.0)
            if score > best_score:
                best_score = score
                best_name = name

        if best_name is None:
            # Fallback to first trained model
            best_name = next(iter(self._trained_models))

        logger.info("Best model by %s: %s (score=%.4f)", metric, best_name, best_score)
        return best_name, self._trained_models[best_name]

    def _generate_comparison_report(self, all_metrics: dict[str, dict]) -> None:
        """
        Generate a comparison report across all trained models.

        Args:
            all_metrics: Dictionary mapping model names to their metrics.
        """
        report_path = self.results_dir / "baseline_comparison_report.json"

        report = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "models": {},
        }

        comparison_rows = []
        for model_name, metrics in all_metrics.items():
            if "error" in metrics:
                report["models"][model_name] = {"status": "failed", "error": metrics["error"]}
                continue

            report["models"][model_name] = {
                "status": "success",
                "metrics": metrics,
            }

            comparison_rows.append({
                "Model": model_name,
                "Train Acc": metrics.get("train_accuracy", 0),
                "Train F1": metrics.get("train_f1", 0),
                "Train AUC": metrics.get("train_auc", 0),
                "Val Acc": metrics.get("val_accuracy", 0),
                "Val F1": metrics.get("val_f1", 0),
                "Val AUC": metrics.get("val_auc", 0),
                "Time (s)": metrics.get("training_time_seconds", 0),
            })

        # Save JSON report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("Comparison report saved to %s", report_path)

        # Log comparison table
        if comparison_rows:
            df = pd.DataFrame(comparison_rows)
            df = df.sort_values("Val F1", ascending=False)
            logger.info("\n=== Baseline Model Comparison ===\n%s", df.to_string(index=False))

    def evaluate_on_test(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        model_names: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Evaluate trained models on a test set.

        Args:
            X_test: Test feature matrix.
            y_test: Test labels.
            model_names: Optional list of model names to evaluate. If None, evaluates all.

        Returns:
            Dictionary mapping model names to test metrics.
        """
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

        if model_names is None:
            model_names = list(self._trained_models.keys())

        results = {}
        for name in model_names:
            try:
                model = self.get_model(name)
                preds = model.predict(X_test)
                proba = model.predict_proba(X_test)

                metrics = {
                    "test_accuracy": float(accuracy_score(y_test, preds)),
                    "test_precision": float(precision_score(y_test, preds, zero_division=0)),
                    "test_recall": float(recall_score(y_test, preds, zero_division=0)),
                    "test_f1": float(f1_score(y_test, preds, zero_division=0)),
                }
                try:
                    metrics["test_auc"] = float(roc_auc_score(y_test, proba))
                except ValueError:
                    metrics["test_auc"] = 0.0

                results[name] = metrics
                logger.info("Test metrics for %s: %s", name, metrics)
            except Exception as e:
                logger.error("Failed to evaluate %s: %s", name, e)
                results[name] = {"error": str(e)}

        # Save test results
        test_report_path = self.results_dir / "baseline_test_results.json"
        test_report_path.write_text(json.dumps(results, indent=2, default=str))
        logger.info("Test results saved to %s", test_report_path)

        return results
