"""
Model evaluation module for the Phishing URL Detection Engine.

Provides comprehensive evaluation metrics, confusion matrices,
classification reports, and model comparison utilities.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationResult:
    """
    Container for model evaluation results.

    Attributes:
        model_name: Name of the evaluated model.
        accuracy: Overall accuracy.
        precision: Precision for the positive class.
        recall: Recall for the positive class.
        f1: F1 score for the positive class.
        auc_roc: Area under the ROC curve.
        log_loss_value: Log loss (cross-entropy).
        mcc: Matthews Correlation Coefficient.
        confusion_mat: Confusion matrix as nested list.
        classification_rep: Full classification report dictionary.
        support: Number of test samples.
    """

    model_name: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    auc_roc: float = 0.0
    log_loss_value: float = 0.0
    mcc: float = 0.0
    confusion_mat: list[list[int]] = field(default_factory=list)
    classification_rep: dict[str, Any] = field(default_factory=dict)
    support: int = 0

    # Extended metrics (Phase 3-G)
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    brier_score: float = 0.0
    expected_calibration_error: float = 0.0
    # PR-AUC (average precision) -- additive field, requires probabilities.
    pr_auc: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert evaluation result to dictionary."""
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "auc_roc": self.auc_roc,
            "log_loss": self.log_loss_value,
            "mcc": self.mcc,
            "confusion_matrix": self.confusion_mat,
            "classification_report": self.classification_rep,
            "support": self.support,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
            "brier_score": self.brier_score,
            "expected_calibration_error": self.expected_calibration_error,
            "pr_auc": self.pr_auc,
        }


class ModelEvaluator:
    """
    Comprehensive model evaluator for phishing URL detection models.

    Computes and reports a full suite of classification metrics including
    accuracy, precision, recall, F1, AUC-ROC, log loss, MCC, confusion
    matrix, and classification report.

    Supports single-model evaluation, multi-model comparison, and
    persistence of evaluation reports.

    Attributes:
        results_dir: Directory for saving evaluation reports.
    """

    def __init__(self, results_dir: Path | None = None) -> None:
        """
        Initialize the model evaluator.

        Args:
            results_dir: Directory for saving evaluation reports. Defaults to settings.
        """
        settings = get_settings()
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._results: dict[str, EvaluationResult] = {}

    def evaluate(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None,
    ) -> EvaluationResult:
        """
        Evaluate a model's predictions against ground truth.

        Args:
            model_name: Name of the model being evaluated.
            y_true: True labels.
            y_pred: Predicted labels.
            y_proba: Optional predicted probabilities for the positive class.

        Returns:
            EvaluationResult with all computed metrics.
        """
        logger.info("Evaluating model: %s on %d samples", model_name, len(y_true))

        result = EvaluationResult(
            model_name=model_name,
            accuracy=float(accuracy_score(y_true, y_pred)),
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            f1=float(f1_score(y_true, y_pred, zero_division=0)),
            mcc=float(matthews_corrcoef(y_true, y_pred)),
            confusion_mat=confusion_matrix(y_true, y_pred).tolist(),
            classification_rep=classification_report(
                y_true, y_pred,
                target_names=["Legitimate", "Phishing"],
                output_dict=True,
                zero_division=0,
            ),
            support=len(y_true),
        )

        # False positive / false negative rates from the confusion matrix (Phase 3-G)
        try:
            cm = np.asarray(result.confusion_mat)
            if cm.shape == (2, 2):
                tn, fp, fn, tp = int(cm[0][0]), int(cm[0][1]), int(cm[1][0]), int(cm[1][1])
                result.false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                result.false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        except Exception:  # noqa: BLE001
            logger.warning("Could not compute FPR/FNR for %s", model_name)

        # AUC-ROC and log loss require probabilities
        if y_proba is not None:
            try:
                result.auc_roc = float(roc_auc_score(y_true, y_proba))
            except ValueError:
                result.auc_roc = 0.0
                logger.warning("Could not compute AUC-ROC for %s", model_name)

            try:
                result.pr_auc = float(average_precision_score(y_true, y_proba))
            except ValueError:
                result.pr_auc = 0.0
                logger.warning("Could not compute PR-AUC for %s", model_name)

            try:
                # Clip probabilities to avoid log(0)
                clipped = np.clip(y_proba, 1e-7, 1 - 1e-7)
                proba_2d = np.column_stack([1 - clipped, clipped])
                result.log_loss_value = float(log_loss(y_true, proba_2d))
            except ValueError:
                result.log_loss_value = 0.0

            # Probabilistic calibration metrics (Phase 3-G)
            try:
                from src.scoring.calibrator import (
                    brier_score,
                    expected_calibration_error,
                )
                result.brier_score = brier_score(y_true, y_proba)
                result.expected_calibration_error = expected_calibration_error(
                    y_true, y_proba
                )
            except Exception:  # noqa: BLE001
                logger.warning("Could not compute Brier/ECE for %s", model_name)

        self._results[model_name] = result

        # Log summary
        logger.info(
            "Evaluation results for %s -- Acc=%.4f, P=%.4f, R=%.4f, F1=%.4f, AUC=%.4f, MCC=%.4f",
            model_name,
            result.accuracy, result.precision, result.recall,
            result.f1, result.auc_roc, result.mcc,
        )

        return result

    def compare_models(
        self,
        results: list[EvaluationResult] | None = None,
        sort_by: str = "f1",
    ) -> pd.DataFrame:
        """
        Create a comparison table of multiple model evaluations.

        Args:
            results: Optional list of EvaluationResult objects. If None, uses stored results.
            sort_by: Metric column to sort by (descending).

        Returns:
            DataFrame with comparison metrics for all models.
        """
        if results is None:
            results = list(self._results.values())

        if not results:
            logger.warning("No evaluation results to compare")
            return pd.DataFrame()

        rows = []
        for r in results:
            rows.append({
                "Model": r.model_name,
                "Accuracy": round(r.accuracy, 4),
                "Precision": round(r.precision, 4),
                "Recall": round(r.recall, 4),
                "F1": round(r.f1, 4),
                "AUC-ROC": round(r.auc_roc, 4),
                "MCC": round(r.mcc, 4),
                "Log Loss": round(r.log_loss_value, 4),
                "Samples": r.support,
            })

        df = pd.DataFrame(rows).sort_values(sort_by.title(), ascending=False)

        logger.info("\n=== Model Comparison (sorted by %s) ===\n%s", sort_by, df.to_string(index=False))

        return df

    def save_report(
        self,
        filename: str = "evaluation_report.json",
        results: list[EvaluationResult] | None = None,
    ) -> Path:
        """
        Save evaluation results to a JSON file.

        Args:
            filename: Output filename.
            results: Optional list of results. If None, uses stored results.

        Returns:
            Path to the saved report file.
        """
        if results is None:
            results = list(self._results.values())

        report = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "model_count": len(results),
            "evaluations": {r.model_name: r.to_dict() for r in results},
        }

        # Add comparison summary
        if len(results) > 1:
            comparison_df = self.compare_models(results)
            report["comparison"] = comparison_df.to_dict(orient="records")
            best = comparison_df.iloc[0]
            report["best_model"] = {
                "name": best["Model"],
                "f1": best["F1"],
                "accuracy": best["Accuracy"],
            }

        report_path = self.results_dir / filename
        report_path.write_text(json.dumps(report, indent=2, default=str))
        logger.info("Evaluation report saved to %s", report_path)
        return report_path

    def get_confusion_matrix_summary(self, result: EvaluationResult) -> dict[str, int]:
        """
        Extract a human-readable confusion matrix summary.

        Args:
            result: EvaluationResult containing the confusion matrix.

        Returns:
            Dictionary with TP, TN, FP, FN counts.
        """
        if not result.confusion_mat or len(result.confusion_mat) < 2:
            return {"TP": 0, "TN": 0, "FP": 0, "FN": 0}

        cm = result.confusion_mat
        return {
            "TN": cm[0][0],  # True Negatives (correctly identified legitimate)
            "FP": cm[0][1],  # False Positives (legitimate flagged as phishing)
            "FN": cm[1][0],  # False Negatives (phishing missed)
            "TP": cm[1][1],  # True Positives (correctly identified phishing)
        }

    def compute_roc_curve(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
    ) -> dict[str, list[float]]:
        """
        Compute ROC curve data points.

               Args:
            y_true: True labels.
            y_proba: Predicted probabilities.

        Returns:
            Dictionary with 'fpr', 'tpr', and 'thresholds' lists.
        """
        fpr, tpr, thresholds = roc_curve(y_true, y_proba)
        return {
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
            "thresholds": thresholds.tolist(),
        }

    def compute_precision_recall_curve(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
    ) -> dict[str, list[float]]:
        """
        Compute precision-recall curve data points.

        Args:
            y_true: True labels.
            y_proba: Predicted probabilities.

        Returns:
            Dictionary with 'precision', 'recall', and 'thresholds' lists.
        """
        precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
        return {
            "precision": precision.tolist(),
            "recall": recall.tolist(),
            "thresholds": thresholds.tolist(),
        }

    def get_result(self, model_name: str) -> EvaluationResult | None:
        """
        Retrieve a stored evaluation result by model name.

        Args:
            model_name: Name of the model.

        Returns:
            EvaluationResult if found, None otherwise.
        """
        return self._results.get(model_name)

    def clear_results(self) -> None:
        """Clear all stored evaluation results."""
        self._results.clear()
        logger.info("All evaluation results cleared")
