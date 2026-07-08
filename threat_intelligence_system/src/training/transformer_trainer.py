"""
Transformer model trainer for the Phishing URL Detection Engine.

Provides a high-level training orchestrator for transformer models with
support for mixed precision, early stopping, checkpoint management,
training resumption, and evaluation reporting.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.config.settings import get_settings
from src.models.transformer_models import (
    TransformerURLClassifier,
    TransformerConfig,
    create_transformer_model,
    TRANSFORMER_REGISTRY,
)
from src.utils.exceptions import ModelError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TransformerTrainer:
    """
    High-level trainer for transformer-based URL classifiers.

    Manages the full lifecycle of transformer model training:
    1. Model initialization and configuration.
    2. Training with mixed precision and early stopping.
    3. Checkpoint saving and training resumption.
    4. Evaluation and comparison across transformer variants.

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
        Initialize the transformer trainer.

        Args:
            checkpoint_dir: Directory for model checkpoints.
            results_dir: Directory for evaluation reports.
        """
        settings = get_settings()
        self.checkpoint_dir = Path(checkpoint_dir or settings.paths.checkpoint_dir)
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._trained_models: dict[str, TransformerURLClassifier] = {}
        self._training_results: dict[str, dict[str, Any]] = {}

        logger.info(
            "TransformerTrainer initialized -- checkpoints: %s, results: %s",
            self.checkpoint_dir, self.results_dir,
        )

    def train_model(
        self,
        model_name: str,
        train_urls: list[str] | np.ndarray,
        train_labels: list[int] | np.ndarray,
        val_urls: Optional[list[str] | np.ndarray] = None,
        val_labels: Optional[list[int] | np.ndarray] = None,
        save_checkpoint: bool = True,
        config_overrides: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """
        Train a single transformer model.

        Args:
            model_name: Transformer name ('distilbert', 'bert', 'roberta', etc.).
            train_urls: List or array of training URL strings.
            train_labels: List or array of binary labels.
            val_urls: Optional validation URL strings.
            val_labels: Optional validation labels.
            save_checkpoint: Whether to save the model after training.
            config_overrides: Optional dict of TransformerConfig field overrides.

        Returns:
            Dictionary of training metrics.

        Raises:
            ModelError: If training fails.
        """
        logger.info("Training transformer: %s", model_name)
        start_time = time.perf_counter()

        # Create model with optional config overrides
        kwargs = config_overrides or {}
        model = create_transformer_model(model_name, **kwargs)

        # Convert to numpy arrays if needed
        X_train = np.array(train_urls) if not isinstance(train_urls, np.ndarray) else train_urls
        y_train = np.array(train_labels) if not isinstance(train_labels, np.ndarray) else train_labels
        X_val = np.array(val_urls) if val_urls is not None and not isinstance(val_urls, np.ndarray) else val_urls
        y_val = np.array(val_labels) if val_labels is not None and not isinstance(val_labels, np.ndarray) else val_labels

        # Train
        metrics = model.train(X_train, y_train, X_val, y_val)

        elapsed = time.perf_counter() - start_time
        metrics["training_time_seconds"] = round(elapsed, 2)

        self._trained_models[model_name] = model
        self._training_results[model_name] = {
            "metrics": metrics,
            "training_time": elapsed,
            "training_samples": len(y_train),
        }

        # Save checkpoint
        if save_checkpoint:
            checkpoint_path = self.checkpoint_dir / f"transformer_{model_name}"
            model.save(checkpoint_path)
            logger.info("Transformer checkpoint saved: %s", checkpoint_path)

        return metrics

    def train_multiple(
        self,
        model_names: list[str],
        train_urls: list[str] | np.ndarray,
        train_labels: list[int] | np.ndarray,
        val_urls: Optional[list[str] | np.ndarray] = None,
        val_labels: Optional[list[int] | np.ndarray] = None,
        save_checkpoints: bool = True,
    ) -> dict[str, dict[str, float]]:
        """
        Train multiple transformer models sequentially.

        Args:
            model_names: List of transformer names to train.
            train_urls: Training URL strings.
            train_labels: Training labels.
            val_urls: Optional validation URLs.
            val_labels: Optional validation labels.
            save_checkpoints: Whether to save all models.

        Returns:
            Dictionary mapping model names to their metrics.
        """
        logger.info("Training %d transformer models", len(model_names))
        all_metrics = {}

        for model_name in model_names:
            try:
                metrics = self.train_model(
                    model_name, train_urls, train_labels,
                    val_urls, val_labels, save_checkpoint=save_checkpoints,
                )
                all_metrics[model_name] = metrics
            except Exception as e:
                logger.error("Failed to train %s: %s", model_name, e)
                all_metrics[model_name] = {"error": str(e)}

        # Generate comparison report
        self._generate_comparison_report(all_metrics)
        return all_metrics

    def resume_training(
        self,
        model_name: str,
        train_urls: list[str] | np.ndarray,
        train_labels: list[int] | np.ndarray,
        val_urls: Optional[list[str] | np.ndarray] = None,
        val_labels: Optional[list[int] | np.ndarray] = None,
        additional_epochs: int = 3,
    ) -> dict[str, float]:
        """
        Resume training a transformer model from a checkpoint.

        Args:
            model_name: Transformer name.
            train_urls: Training URL strings.
            train_labels: Training labels.
            val_urls: Optional validation URLs.
            val_labels: Optional validation labels.
            additional_epochs: Number of additional epochs to train.

        Returns:
            Updated training metrics.
        """
        checkpoint_path = self.checkpoint_dir / f"transformer_{model_name}"

        if not checkpoint_path.exists():
            raise ModelError(
                model_name, "resume",
                f"No checkpoint found at {checkpoint_path}"
            )

        logger.info("Resuming training for %s from %s", model_name, checkpoint_path)

        # Load existing model
        model = create_transformer_model(model_name)
        model.load(checkpoint_path)

        # Update epoch count for additional training
        model.config = TransformerConfig(
            model_name=model.config.model_name,
            pretrained_path=model.config.pretrained_path,
            max_length=model.config.max_length,
            num_labels=model.config.num_labels,
            batch_size=model.config.batch_size,
            learning_rate=model.config.learning_rate * 0.1,  # Lower LR for fine-tuning
            num_epochs=additional_epochs,
            warmup_ratio=model.config.warmup_ratio,
            weight_decay=model.config.weight_decay,
            mixed_precision=model.config.mixed_precision,
            early_stopping_patience=model.config.early_stopping_patience,
            gradient_accumulation_steps=model.config.gradient_accumulation_steps,
        )

        # Mark as untrained to allow re-training
        model._is_trained = False

        X_train = np.array(train_urls) if not isinstance(train_urls, np.ndarray) else train_urls
        y_train = np.array(train_labels) if not isinstance(train_labels, np.ndarray) else train_labels
        X_val = np.array(val_urls) if val_urls is not None and not isinstance(val_urls, np.ndarray) else val_urls
        y_val = np.array(val_labels) if val_labels is not None and not isinstance(val_labels, np.ndarray) else val_labels

        metrics = model.train(X_train, y_train, X_val, y_val)

        # Save updated checkpoint
        model.save(checkpoint_path)
        self._trained_models[model_name] = model

        return metrics

    def get_model(self, model_name: str) -> TransformerURLClassifier:
        """
        Get a trained transformer model by name.

        Args:
            model_name: Transformer name key.

        Returns:
            Trained TransformerURLClassifier instance.

        Raises:
            ModelError: If model is not available.
        """
        if model_name not in self._trained_models:
            checkpoint_path = self.checkpoint_dir / f"transformer_{model_name}"
            if checkpoint_path.exists():
                model = create_transformer_model(model_name)
                model.load(checkpoint_path)
                self._trained_models[model_name] = model
            else:
                raise ModelError(
                    model_name, "get",
                    f"Model not trained and no checkpoint at {checkpoint_path}"
                )
        return self._trained_models[model_name]

    def evaluate_on_test(
        self,
        X_test: list[str] | np.ndarray,
        y_test: list[int] | np.ndarray,
        model_names: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Evaluate transformer models on a test set.

        Args:
            X_test: Test URL strings.
            y_test: Test labels.
            model_names: Optional list of model names to evaluate.

        Returns:
            Dictionary mapping model names to test metrics.
        """
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

        if model_names is None:
            model_names = list(self._trained_models.keys())

        X_test = np.array(X_test) if not isinstance(X_test, np.ndarray) else X_test
        y_test = np.array(y_test) if not isinstance(y_test, np.ndarray) else y_test

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

        # Save results
        test_path = self.results_dir / "transformer_test_results.json"
        test_path.write_text(json.dumps(results, indent=2, default=str))
        return results

    def _generate_comparison_report(self, all_metrics: dict[str, dict]) -> None:
        """
        Generate comparison report for transformer models.

        Args:
            all_metrics: Dictionary of model metrics.
        """
        import pandas as pd

        report = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "models": all_metrics,
        }

        report_path = self.results_dir / "transformer_comparison_report.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("Transformer comparison report saved to %s", report_path)

        # Log comparison table
        rows = []
        for name, metrics in all_metrics.items():
            if "error" not in metrics:
                rows.append({
                    "Model": name,
                    "Train Acc": metrics.get("train_accuracy", 0),
                    "Val Acc": metrics.get("val_accuracy", 0),
                    "Train Loss": metrics.get("train_loss", 0),
                    "Val Loss": metrics.get("val_loss", 0),
                    "Time (s)": metrics.get("training_time_seconds", 0),
                })

        if rows:
            df = pd.DataFrame(rows)
            logger.info("\n=== Transformer Comparison ===\n%s", df.to_string(index=False))
