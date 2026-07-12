"""
Visual evaluation reports for the training pipeline.

Generates publication-ready evaluation artifacts, each saved as **PNG and
PDF** into ``<results_dir>/reports/``:

* ROC curve
* Precision-Recall curve
* Calibration (reliability) curve
* Confusion matrix
* Global feature importance
* SHAP summary (beeswarm) for tree-based models

Matplotlib is used with the non-interactive ``Agg`` backend so report
generation works in headless environments.  All functions degrade
gracefully (log + skip) rather than failing the pipeline when an optional
dependency or model capability is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _import_pyplot():
    """Import matplotlib with the headless Agg backend."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


class EvaluationReportGenerator:
    """Render and persist evaluation plots as PNG + PDF.

    Args:
        results_dir: Base results directory; figures are written to
            ``<results_dir>/reports/``.
        dpi: Raster resolution for the PNG output.
    """

    def __init__(self, results_dir: Path | None = None, dpi: int = 150) -> None:
        settings = get_settings()
        self.reports_dir = Path(results_dir or settings.paths.results_dir) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = int(dpi)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _save(self, fig: Any, stem: str) -> dict[str, str]:
        """Save *fig* as PNG and PDF; returns the artifact paths."""
        paths: dict[str, str] = {}
        for ext in ("png", "pdf"):
            path = self.reports_dir / f"{stem}.{ext}"
            fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
            paths[ext] = str(path)
        _import_pyplot().close(fig)
        logger.info("Report figure saved: %s (.png/.pdf)", self.reports_dir / stem)
        return paths

    # ------------------------------------------------------------------
    # Individual plots
    # ------------------------------------------------------------------

    def plot_roc_curve(
        self, y_true: np.ndarray, y_proba: np.ndarray, model_name: str = "model",
    ) -> dict[str, str]:
        """ROC curve with AUC annotation."""
        from sklearn.metrics import auc, roc_curve
        plt = _import_pyplot()
        fpr, tpr, _ = roc_curve(y_true, y_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(fpr, tpr, lw=2, label=f"{model_name} (AUC = {auc(fpr, tpr):.4f})")
        ax.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="Chance")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(f"ROC Curve - {model_name}")
        ax.legend(loc="lower right")
        ax.grid(alpha=0.3)
        return self._save(fig, f"roc_curve_{model_name}")

    def plot_precision_recall_curve(
        self, y_true: np.ndarray, y_proba: np.ndarray, model_name: str = "model",
    ) -> dict[str, str]:
        """Precision-Recall curve with average precision annotation."""
        from sklearn.metrics import average_precision_score, precision_recall_curve
        plt = _import_pyplot()
        precision, recall, _ = precision_recall_curve(y_true, y_proba)
        ap = average_precision_score(y_true, y_proba)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(recall, precision, lw=2, label=f"{model_name} (AP = {ap:.4f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(f"Precision-Recall Curve - {model_name}")
        ax.legend(loc="lower left")
        ax.grid(alpha=0.3)
        return self._save(fig, f"precision_recall_curve_{model_name}")

    def plot_calibration_curve(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        model_name: str = "model",
        n_bins: int = 10,
    ) -> dict[str, str]:
        """Reliability (calibration) curve with ECE/MCE annotation."""
        from src.scoring.calibration_analysis import CalibrationAnalyzer
        plt = _import_pyplot()
        report = CalibrationAnalyzer(n_bins=n_bins).analyze(y_true, y_proba)
        rel = report.reliability
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="Perfect calibration")
        ax.plot(
            rel.get("mean_predicted", []), rel.get("fraction_positive", []),
            marker="o", lw=2,
            label=(f"{model_name} (ECE = {report.ece:.4f}, "
                   f"MCE = {report.mce:.4f})"),
        )
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Observed phishing fraction")
        ax.set_title(f"Calibration Curve - {model_name}")
        ax.legend(loc="upper left")
        ax.grid(alpha=0.3)
        return self._save(fig, f"calibration_curve_{model_name}")

    def plot_confusion_matrix(
        self,
        confusion: np.ndarray | Sequence[Sequence[int]],
        model_name: str = "model",
        class_names: tuple[str, str] = ("Legitimate", "Phishing"),
    ) -> dict[str, str]:
        """Annotated confusion-matrix heatmap."""
        plt = _import_pyplot()
        matrix = np.asarray(confusion, dtype=int)
        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        im = ax.imshow(matrix, cmap="Blues")
        fig.colorbar(im, ax=ax, fraction=0.046)
        ax.set_xticks([0, 1], class_names)
        ax.set_yticks([0, 1], class_names)
        ax.set_xlabel("Predicted label")
        ax.set_ylabel("True label")
        ax.set_title(f"Confusion Matrix - {model_name}")
        threshold = matrix.max() / 2 if matrix.max() else 0
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(
                    j, i, f"{matrix[i, j]:,}",
                    ha="center", va="center",
                    color="white" if matrix[i, j] > threshold else "black",
                )
        return self._save(fig, f"confusion_matrix_{model_name}")

    def plot_feature_importance(
        self,
        model: Any,
        feature_names: Sequence[str],
        model_name: str = "model",
        top_n: int = 25,
    ) -> Optional[dict[str, str]]:
        """Global feature importance bar chart (skipped when unsupported)."""
        estimator = getattr(model, "model", model)
        importances: Optional[np.ndarray] = None
        if hasattr(estimator, "feature_importances_"):
            importances = np.asarray(estimator.feature_importances_, dtype=float)
        elif hasattr(estimator, "coef_"):
            importances = np.abs(np.asarray(estimator.coef_, dtype=float)).ravel()
        if importances is None or importances.size != len(feature_names):
            logger.warning(
                "Feature importance unavailable for %s - skipping plot",
                model_name,
            )
            return None

        plt = _import_pyplot()
        order = np.argsort(importances)[::-1][:top_n][::-1]
        fig, ax = plt.subplots(figsize=(7, max(4, 0.28 * len(order))))
        ax.barh([feature_names[i] for i in order], importances[order])
        ax.set_xlabel("Importance")
        ax.set_title(f"Global Feature Importance - {model_name} (top {len(order)})")
        ax.grid(alpha=0.3, axis="x")
        return self._save(fig, f"feature_importance_{model_name}")

    def plot_shap_summary(
        self,
        model: Any,
        X_sample: np.ndarray,
        feature_names: Sequence[str],
        model_name: str = "model",
        max_display: int = 20,
        max_samples: int = 2000,
    ) -> Optional[dict[str, str]]:
        """SHAP beeswarm summary for tree-based models (PNG + PDF).

        Args:
            model: ``BaselineModel`` wrapper or raw tree estimator.
            X_sample: Feature matrix to explain (subsampled to
                ``max_samples`` rows for tractability).
            feature_names: Ordered feature names.
            model_name: Used in titles and file names.
            max_display: Features shown in the beeswarm.
            max_samples: Upper bound on explained rows.

        Returns:
            Artifact paths, or *None* when SHAP is unavailable or the model
            is not tree-based.
        """
        try:
            import shap
        except ImportError:
            logger.warning("shap not installed - skipping SHAP summary")
            return None

        estimator = getattr(model, "model", model)
        X = np.asarray(X_sample, dtype=np.float32)
        if len(X) > max_samples:
            rng = np.random.RandomState(get_settings().dataset.random_seed)
            X = X[rng.choice(len(X), size=max_samples, replace=False)]

        shap_values: Optional[np.ndarray] = None
        try:
            explainer = shap.TreeExplainer(estimator)
            shap_values = explainer.shap_values(X, check_additivity=False)
        except Exception as exc:  # noqa: BLE001 -- version quirks / non-tree
            logger.warning(
                "shap.TreeExplainer failed for %s (%s) - trying XGBoost "
                "native pred_contribs fallback", model_name, exc,
            )
            shap_values = self._xgboost_contribs(estimator, X, feature_names)
        if shap_values is None:
            logger.warning(
                "SHAP summary unavailable for %s - skipping", model_name,
            )
            return None

        # Binary classifiers may return per-class arrays; use class 1.
        if isinstance(shap_values, list):
            shap_values = shap_values[-1]
        shap_values = np.asarray(shap_values)
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, -1]

        plt = _import_pyplot()
        fig = plt.figure(figsize=(8, 6))
        shap.summary_plot(
            shap_values, X,
            feature_names=list(feature_names),
            max_display=max_display,
            show=False,
        )
        fig = plt.gcf()
        fig.suptitle(f"SHAP Summary - {model_name}", fontsize=11)
        return self._save(fig, f"shap_summary_{model_name}")

    @staticmethod
    def _xgboost_contribs(
        estimator: Any,
        X: np.ndarray,
        feature_names: Sequence[str],
    ) -> Optional[np.ndarray]:
        """Exact TreeSHAP values via XGBoost's native ``pred_contribs``.

        Fallback used when ``shap.TreeExplainer`` cannot parse the booster
        (version incompatibilities).  Returns *None* for non-XGBoost models.
        """
        try:
            import xgboost as xgb
        except ImportError:  # pragma: no cover
            return None
        booster = None
        if isinstance(estimator, xgb.XGBClassifier):
            booster = estimator.get_booster()
        elif isinstance(estimator, xgb.Booster):
            booster = estimator
        if booster is None:
            return None
        try:
            dmatrix = xgb.DMatrix(X, feature_names=list(feature_names))
            contribs = booster.predict(dmatrix, pred_contribs=True)
            return np.asarray(contribs)[:, :-1]  # drop base-value column
        except Exception as exc:  # noqa: BLE001
            logger.warning("XGBoost pred_contribs fallback failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def generate_all(
        self,
        model: Any,
        model_name: str,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        confusion: np.ndarray | Sequence[Sequence[int]],
        feature_names: Sequence[str],
        X_sample: Optional[np.ndarray] = None,
    ) -> dict[str, dict[str, str]]:
        """Generate every available report figure for one model.

        Returns:
            Mapping of artifact name to ``{"png": ..., "pdf": ...}`` paths.
        """
        y_pred_proba = np.asarray(y_proba, dtype=float)
        artifacts: dict[str, dict[str, str]] = {}
        artifacts["roc_curve"] = self.plot_roc_curve(y_true, y_pred_proba, model_name)
        artifacts["precision_recall_curve"] = self.plot_precision_recall_curve(
            y_true, y_pred_proba, model_name)
        artifacts["calibration_curve"] = self.plot_calibration_curve(
            y_true, y_pred_proba, model_name)
        artifacts["confusion_matrix"] = self.plot_confusion_matrix(
            confusion, model_name)
        importance = self.plot_feature_importance(model, feature_names, model_name)
        if importance:
            artifacts["feature_importance"] = importance
        if X_sample is not None:
            shap_paths = self.plot_shap_summary(
                model, X_sample, feature_names, model_name)
            if shap_paths:
                artifacts["shap_summary"] = shap_paths
        return artifacts
