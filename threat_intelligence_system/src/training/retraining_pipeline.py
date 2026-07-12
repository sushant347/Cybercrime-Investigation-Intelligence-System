"""
Versioned retraining pipeline (Phase 3-F).

Orchestrates a full retraining cycle for the baseline XGBoost model:

1. Load the processed train/validation/test splits.
2. Optionally merge investigator corrections from the feedback store
   (Phase 3-E) into the training set.
3. Extract features with the current feature pipeline.
4. Train the model.
5. Evaluate every calibration method (Phase 3-D) and attach the best.
6. Benchmark on the test split with the full metric suite (Phase 3-G).
7. Stamp dataset / feature / model / calibration versions.
8. Save a versioned checkpoint and write a JSON retraining report.

The pipeline never runs automatically -- invoke it explicitly via
``retrain_pipeline.py`` or programmatically::

    from src.training.retraining_pipeline import RetrainingPipeline

    pipeline = RetrainingPipeline()
    report = pipeline.run(include_feedback=True)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.evaluation.evaluator import ModelEvaluator
from src.feature_engineering.pipeline import FeaturePipeline
from src.feedback.feedback_store import FeedbackStore
from src.models.baseline_models import create_baseline_model
from src.scoring.calibrator import CalibrationEvaluator
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Version of the feature schema produced by the current FeaturePipeline.
FEATURE_VERSION = "2.0.0"


class RetrainingPipeline:
    """End-to-end, versioned retraining orchestrator (Phase 3-F).

    Args:
        model_type: Baseline model to retrain (default ``'xgboost'``).
        processed_dir: Directory with train/validation/test CSV splits.
        checkpoint_dir: Directory for saved checkpoints.
        results_dir: Directory for retraining reports.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        processed_dir: Path | None = None,
        checkpoint_dir: Path | None = None,
        results_dir: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.model_type = model_type
        self.processed_dir = Path(processed_dir or settings.paths.processed_data_dir)
        self.checkpoint_dir = Path(checkpoint_dir or settings.paths.checkpoint_dir)
        self.results_dir = Path(results_dir or settings.paths.results_dir)
        self._feature_pipeline = FeaturePipeline()
        logger.info(
            "RetrainingPipeline initialised: model=%s processed=%s",
            model_type, self.processed_dir,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        include_feedback: bool = True,
        extra_datasets: Optional[list[Path]] = None,
        sample: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute the full retraining cycle.

        Args:
            include_feedback: Merge investigator corrections into training.
            extra_datasets: Optional additional CSVs with 'url' and 'label'
                columns to merge into the training set.
            sample: Optional cap on rows per split (for smoke testing).

        Returns:
            The retraining report dictionary (also written to results_dir).
        """
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        logger.info("Retraining run %s started", run_id)

        # 1. Load datasets ------------------------------------------------
        train_df = self._load_split("train.csv", sample)
        val_df = self._load_split("validation.csv", sample)
        test_df = self._load_split("test.csv", sample)

        sources: list[str] = ["train.csv"]

        # 2. Merge extra datasets and feedback corrections ---------------
        if extra_datasets:
            for path in extra_datasets:
                extra = pd.read_csv(path)[["url", "label"]]
                train_df = pd.concat([train_df, extra], ignore_index=True)
                sources.append(str(path))

        feedback_rows = 0
        if include_feedback:
            corrections = FeedbackStore().get_corrections()
            if corrections:
                from src.feedback.feedback_store import _LABEL_TO_INT
                rows = [
                    {"url": c.url, "label": _LABEL_TO_INT.get(str(c.correct_label).lower())}
                    for c in corrections
                    if _LABEL_TO_INT.get(str(c.correct_label).lower()) is not None
                ]
                if rows:
                    train_df = pd.concat(
                        [train_df, pd.DataFrame(rows)], ignore_index=True
                    )
                    feedback_rows = len(rows)
                    sources.append(f"feedback({feedback_rows})")

        train_df = train_df.drop_duplicates(subset=["url"]).reset_index(drop=True)

        # 3. Version stamps ----------------------------------------------
        dataset_version = f"ds-{run_id}"
        model_version = f"m-{run_id}"
        logger.info(
            "Dataset: %d train / %d val / %d test rows (feedback rows: %d)",
            len(train_df), len(val_df), len(test_df), feedback_rows,
        )

        # 4. Feature extraction -------------------------------------------
        feature_names = self._feature_pipeline.get_feature_names()
        x_train = self._featurise(train_df["url"], feature_names)
        y_train = train_df["label"].astype(int).to_numpy()
        x_val = self._featurise(val_df["url"], feature_names)
        y_val = val_df["label"].astype(int).to_numpy()
        x_test = self._featurise(test_df["url"], feature_names)
        y_test = test_df["label"].astype(int).to_numpy()

        # 5. Train ---------------------------------------------------------
        model = create_baseline_model(self.model_type)
        train_metrics = model.train(
            x_train, y_train, x_val, y_val, feature_names=feature_names
        )

        # 6. Calibration selection (Phase 3-D) -----------------------------
        raw_val_proba = (
            model.predict_proba_raw(x_val)
            if hasattr(model, "predict_proba_raw")
            else model.predict_proba(x_val)
        )
        calibration_evaluator = CalibrationEvaluator()
        calibration_report = calibration_evaluator.evaluate_methods(
            y_val, np.asarray(raw_val_proba, dtype=float)
        )
        best_method = calibration_report["best_method"]
        calibration_version = f"cal-{best_method}-{run_id}"

        if hasattr(model, "calibrator"):
            from src.scoring.calibrator import ConfidenceCalibrator
            model.calibrator = ConfidenceCalibrator(method=best_method)
            model.calibrator.fit(
                np.asarray(y_val, dtype=float),
                np.asarray(raw_val_proba, dtype=float),
            )

        # 7. Benchmark on test set (Phase 3-G) ------------------------------
        test_proba = np.asarray(model.predict_proba(x_test), dtype=float)
        test_pred = model.predict(x_test)
        evaluator = ModelEvaluator(results_dir=self.results_dir)
        evaluation = evaluator.evaluate(
            f"{self.model_type}-{model_version}", y_test, test_pred, test_proba
        )

        # 8. Stamp metadata & save checkpoint --------------------------------
        model.metadata.model_version = model_version
        model.metadata.dataset_version = dataset_version
        model.metadata.feature_version = FEATURE_VERSION
        model.metadata.calibration_version = calibration_version
        model.metadata.training_date = datetime.now(timezone.utc).isoformat()

        checkpoint_path = self.checkpoint_dir / f"{self.model_type}_{run_id}.pkl"
        model.save(checkpoint_path)

        # 9. Report -----------------------------------------------------------
        report: dict[str, Any] = {
            "run_id": run_id,
            "model_type": self.model_type,
            "versions": {
                "model_version": model_version,
                "dataset_version": dataset_version,
                "feature_version": FEATURE_VERSION,
                "calibration_version": calibration_version,
            },
            "data": {
                "train_rows": int(len(train_df)),
                "validation_rows": int(len(val_df)),
                "test_rows": int(len(test_df)),
                "feedback_rows": feedback_rows,
                "sources": sources,
            },
            "training_metrics": {k: float(v) for k, v in train_metrics.items()},
            "calibration": {
                "best_method": best_method,
                "uncalibrated": calibration_report["uncalibrated"],
                "methods": {
                    m: {k: v for k, v in d.items() if k != "reliability"}
                    for m, d in calibration_report["methods"].items()
                },
            },
            "benchmark": evaluation.to_dict(),
            "checkpoint": str(checkpoint_path),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        report_path = self.results_dir / f"retraining_report_{run_id}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
        logger.info("Retraining run %s complete -- report at %s", run_id, report_path)

        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_split(self, filename: str, sample: Optional[int]) -> pd.DataFrame:
        """Load one processed CSV split with 'url' and 'label' columns."""
        path = self.processed_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Processed split not found: {path}. Run the dataset pipeline first."
            )
        df = pd.read_csv(path)[["url", "label"]].dropna()
        if sample and len(df) > sample:
            df = df.sample(n=sample, random_state=42).reset_index(drop=True)
        return df

    def _featurise(self, urls: pd.Series, feature_names: list[str]) -> np.ndarray:
        """Extract the numeric feature matrix for a series of URLs."""
        matrix: list[list[float]] = []
        for url in urls.astype(str):
            try:
                features = self._feature_pipeline.extract(url)
            except Exception:  # noqa: BLE001 -- skip-proof batch extraction
                features = {}
            row = []
            for name in feature_names:
                value = features.get(name)
                try:
                    row.append(float(value) if value is not None else 0.0)
                except (TypeError, ValueError):
                    row.append(0.0)
            matrix.append(row)
        return np.asarray(matrix, dtype=float)
