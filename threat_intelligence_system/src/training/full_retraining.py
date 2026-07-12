"""
Full dataset-replacement retraining pipeline.

Orchestrates a complete retraining cycle that sources ALL training data from
the configurable dataset directory (``settings.paths.dataset_dir`` /
``DATASET_PATH``), replacing whatever dataset was used previously:

1.  **Discover** datasets automatically (``DatasetDiscovery``) -- any mix of
    CSV / TSV / TXT / JSON / JSONL / Excel, mixed-class or single-class.
2.  **Clean** each dataset with the existing ``DatasetCleaner`` and
    **validate** with ``DatasetValidator``.
3.  **Merge** with the existing ``DatasetMerger`` (deduplication + shuffle),
    after removing URLs with conflicting labels across datasets.
4.  **Balance** the merged dataset when the class ratio exceeds the
    configurable guard (``BALANCE_MAX_RATIO``).
5.  **Split** into stratified train / validation / test and overwrite the
    processed splits on disk (the old dataset is thereby fully retired).
    The FULL dataset is used by default (``MAX_TRAINING_ROWS=0``).
6.  **Extract features** with the existing ``FeaturePipeline`` --
    parallelised AND chunk-streamed so memory stays bounded regardless of
    dataset size.
7.  **Optimize hyperparameters** (optional stage) with Optuna for the
    tree-based models; best parameters are persisted and reused
    automatically by later runs.
8.  **Train every model** in ``BASELINE_MODEL_REGISTRY`` via the existing
    ``BaselineTrainer`` (checkpoints replaced in-place,
    prediction-compatible), applying tuned hyperparameters when available.
9.  **Evaluate** every model on the held-out test split with the full metric
    suite (accuracy, precision, recall, F1, ROC-AUC, PR-AUC, MCC, FPR, FNR,
    confusion matrix).
10. **Cross-validate** every model with Stratified K-Fold (default 5) and
    report each metric as mean +/- standard deviation.
11. **Select the production model** by F1 -> ROC-AUC -> Recall -> Precision
    (never accuracy alone) and record the justification.
12. **Analyze calibration** (Brier / ECE / MCE / reliability diagram) and
    automatically recalibrate the production model when beneficial.
13. **Export error analysis** (false positives, false negatives,
    highest-confidence mistakes) as CSV.
14. **Render evaluation reports** (ROC, PR, calibration, confusion matrix,
    feature importance, SHAP summary) as PNG + PDF.
15. **Persist** feature metadata, versioning info and a complete JSON report.

Invoke via the thin CLI wrapper::

    python train_from_datasets.py [--tune] [--sample N] [--models ...]
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.datasets.cleaner import DatasetCleaner
from src.datasets.discovery import DatasetDiscovery, DatasetProfile
from src.datasets.merger import DatasetMerger
from src.datasets.validator import DatasetValidator
from src.evaluation.cross_validation import CrossValidator
from src.evaluation.error_analysis import ErrorAnalyzer
from src.evaluation.evaluator import ModelEvaluator
from src.feature_engineering.pipeline import FeaturePipeline
from src.models.baseline_models import BASELINE_MODEL_REGISTRY
from src.reporting.evaluation_plots import EvaluationReportGenerator
from src.scoring.calibration_analysis import CalibrationAnalyzer
from src.training.baseline_trainer import BaselineTrainer
from src.training.hyperparameter_tuner import (
    TUNABLE_MODELS,
    OptunaTuner,
    load_best_params,
)
from src.utils.exceptions import DatasetError
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Version of the feature schema produced by the current FeaturePipeline.
FEATURE_VERSION = "2.0.0"

#: Metric priority used for production-model selection (never accuracy alone).
SELECTION_PRIORITY: tuple[str, ...] = ("f1", "auc_roc", "recall", "precision")

# Module-level worker state for multiprocessing feature extraction.
_WORKER_PIPELINE: Optional[FeaturePipeline] = None
_WORKER_FEATURE_NAMES: list[str] = []


def _init_feature_worker(feature_names: list[str]) -> None:
    """Initialise one FeaturePipeline per worker process."""
    global _WORKER_PIPELINE, _WORKER_FEATURE_NAMES
    _WORKER_PIPELINE = FeaturePipeline()
    _WORKER_FEATURE_NAMES = feature_names


def _extract_row(url: str) -> list[float]:
    """Extract the ordered numeric feature vector for one URL (skip-proof)."""
    try:
        features = _WORKER_PIPELINE.extract(url)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 -- batch extraction must never abort
        features = {}
    row: list[float] = []
    for name in _WORKER_FEATURE_NAMES:
        value = features.get(name)
        try:
            row.append(float(value) if value is not None else 0.0)
        except (TypeError, ValueError):
            row.append(0.0)
    return row


@dataclass
class PreprocessingStats:
    """Aggregated statistics of the preprocessing stage."""

    files_discovered: int = 0
    files_used: int = 0
    files_skipped: int = 0
    rows_loaded: int = 0
    missing_values_removed: int = 0
    malformed_urls_removed: int = 0
    duplicates_removed: int = 0
    conflicting_labels_removed: int = 0
    balance_downsampled: int = 0
    final_rows: int = 0
    final_phishing: int = 0
    final_legitimate: int = 0
    profiles: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "files_discovered": self.files_discovered,
            "files_used": self.files_used,
            "files_skipped": self.files_skipped,
            "rows_loaded": self.rows_loaded,
            "missing_values_removed": self.missing_values_removed,
            "malformed_urls_removed": self.malformed_urls_removed,
            "duplicates_removed": self.duplicates_removed,
            "conflicting_labels_removed": self.conflicting_labels_removed,
            "balance_downsampled": self.balance_downsampled,
            "final_rows": self.final_rows,
            "final_phishing": self.final_phishing,
            "final_legitimate": self.final_legitimate,
            "datasets": self.profiles,
        }


class FullRetrainingPipeline:
    """End-to-end retraining from the configurable dataset directory.

    Args:
        dataset_dir: Override for the dataset directory (defaults to the
            configurable ``settings.paths.dataset_dir``).
        processed_dir: Output directory for train/validation/test splits.
        checkpoint_dir: Directory for model checkpoints.
        results_dir: Directory for JSON reports.
        n_workers: Worker processes for feature extraction (default: CPU
            count, minimum 1).
        extraction_chunk_size: URLs per extraction chunk; bounds peak memory
            regardless of dataset size (default from settings).
    """

    def __init__(
        self,
        dataset_dir: Path | str | None = None,
        processed_dir: Path | None = None,
        checkpoint_dir: Path | None = None,
        results_dir: Path | None = None,
        n_workers: int | None = None,
        extraction_chunk_size: int | None = None,
    ) -> None:
        self.settings = get_settings()
        self.dataset_dir = Path(dataset_dir or self.settings.paths.dataset_dir)
        self.processed_dir = Path(processed_dir or self.settings.paths.processed_data_dir)
        self.checkpoint_dir = Path(checkpoint_dir or self.settings.paths.checkpoint_dir)
        self.results_dir = Path(results_dir or self.settings.paths.results_dir)
        import os
        self.n_workers = max(1, n_workers if n_workers is not None else (os.cpu_count() or 1))
        self.extraction_chunk_size = int(
            extraction_chunk_size
            if extraction_chunk_size is not None
            else self.settings.training.extraction_chunk_size
        )
        logger.info(
            "FullRetrainingPipeline initialised - dataset_dir=%s workers=%d chunk=%d",
            self.dataset_dir, self.n_workers, self.extraction_chunk_size,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        sample: Optional[int] = None,
        model_names: Optional[list[str]] = None,
        tune: bool = False,
        tuning_trials: Optional[int] = None,
        cross_validate: bool = True,
        cv_sample: Optional[int] = None,
        auto_recalibrate: bool = True,
        error_analysis: bool = True,
        generate_reports: bool = True,
    ) -> dict[str, Any]:
        """Execute the full retraining cycle.

        Args:
            sample: Optional cap on total merged rows; falls back to
                ``settings.dataset.max_training_rows`` when *None*
                (0 = FULL dataset, the default).
            model_names: Optional subset of model registry keys to train.
            tune: Run Optuna hyperparameter optimization for the tree-based
                models before training.  Previously persisted best
                parameters are reused automatically even when *False*.
            tuning_trials: Trials per tuned model (default from settings).
            cross_validate: Run Stratified K-Fold CV for every trained model
                and report mean +/- std for the full metric suite.
            cv_sample: Stratified row cap for the CV stage only
                (default from settings; 0 = full training split).
            auto_recalibrate: Analyze the production model's calibration
                (Brier/ECE/MCE) and recalibrate when beneficial.
            error_analysis: Export FP / FN / high-confidence mistakes CSVs.
            generate_reports: Render ROC / PR / calibration / confusion /
                importance / SHAP figures as PNG + PDF.

        Returns:
            The complete retraining report dictionary (also written to
            ``results_dir``).
        """
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        started = time.perf_counter()
        logger.info("=" * 60)
        logger.info("FULL RETRAINING RUN %s - START", run_id)
        logger.info("=" * 60)

        # 1-5. Dataset preparation ---------------------------------------
        train_df, val_df, test_df, stats = self.prepare_datasets(sample=sample)

        # 6. Feature extraction (chunk-streamed) ---------------------------
        feature_pipeline = FeaturePipeline()
        feature_names = feature_pipeline.get_feature_names()
        x_train = self.extract_features(train_df["url"], feature_names, "train")
        y_train = train_df["label"].astype(int).to_numpy()
        x_val = self.extract_features(val_df["url"], feature_names, "validation")
        y_val = val_df["label"].astype(int).to_numpy()
        x_test = self.extract_features(test_df["url"], feature_names, "test")
        y_test = test_df["label"].astype(int).to_numpy()

        names = model_names or list(BASELINE_MODEL_REGISTRY)

        # 7. Hyperparameter optimization ------------------------------------
        tuning_report = self.tune_models(
            x_train, y_train,
            model_names=[n for n in names if n in TUNABLE_MODELS],
            n_trials=tuning_trials,
        ) if tune else {}
        best_params = load_best_params(self.results_dir)

        # 8. Train all models -----------------------------------------------
        trainer = BaselineTrainer(
            checkpoint_dir=self.checkpoint_dir, results_dir=self.results_dir
        )
        training_metrics: dict[str, dict[str, float]] = {}
        for name in names:
            params = best_params.get(name, {})
            if params:
                logger.info("Training %s with tuned hyperparameters", name)
            try:
                training_metrics[name] = trainer.train_model(
                    name, x_train, y_train, x_val, y_val,
                    save_checkpoint=True, feature_names=feature_names,
                    **params,
                )
            except Exception as exc:  # noqa: BLE001 -- keep training the rest
                logger.error("Training failed for %s: %s", name, exc)
                training_metrics[name] = {"error": str(exc)}  # type: ignore[dict-item]

        # 9. Evaluate on the held-out test split ----------------------------
        evaluator = ModelEvaluator(results_dir=self.results_dir)
        evaluations: dict[str, dict[str, Any]] = {}
        test_probas: dict[str, np.ndarray] = {}
        for name in names:
            if "error" in training_metrics.get(name, {}):
                continue
            try:
                model = trainer.get_model(name)
                y_pred = model.predict(x_test)
                y_proba = np.asarray(model.predict_proba(x_test), dtype=float)
                test_probas[name] = y_proba
                evaluations[name] = evaluator.evaluate(
                    name, y_test, y_pred, y_proba
                ).to_dict()
            except Exception as exc:  # noqa: BLE001
                logger.error("Evaluation failed for %s: %s", name, exc)

        if not evaluations:
            raise DatasetError(
                dataset=str(self.dataset_dir),
                operation="retrain",
                reason="No model could be trained and evaluated",
            )

        # 10. Stratified K-Fold cross-validation -----------------------------
        cv_report = self.cross_validate_models(
            x_train, y_train,
            model_names=list(evaluations),
            best_params=best_params,
            cv_sample=cv_sample,
        ) if cross_validate else {}

        # 11. Production model selection --------------------------------------
        production_model, justification = self.select_production_model(evaluations)

        # 12. Calibration analysis + automatic recalibration -------------------
        calibration_report: dict[str, Any] = {}
        if auto_recalibrate:
            calibration_report = self.recalibrate_production_model(
                trainer, production_model, x_val, y_val
            )

        # 13. Error analysis (FP / FN / high-confidence mistakes) --------------
        error_report: dict[str, Any] = {}
        if error_analysis:
            try:
                model = trainer.get_model(production_model)
                error_report = ErrorAnalyzer(self.results_dir).analyze(
                    production_model,
                    test_df["url"].tolist(),
                    y_test,
                    model.predict(x_test),
                    test_probas[production_model],
                ).to_dict()
            except Exception as exc:  # noqa: BLE001
                logger.error("Error analysis failed: %s", exc)

        # 14. Visual evaluation reports (PNG + PDF) ----------------------------
        report_artifacts: dict[str, Any] = {}
        if generate_reports:
            try:
                model = trainer.get_model(production_model)
                report_artifacts = EvaluationReportGenerator(
                    self.results_dir
                ).generate_all(
                    model=model,
                    model_name=production_model,
                    y_true=y_test,
                    y_proba=test_probas[production_model],
                    confusion=evaluations[production_model]["confusion_matrix"],
                    feature_names=feature_names,
                    X_sample=x_test,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Report generation failed: %s", exc)

        # 15. Versioning, metadata and report -----------------------------------
        duration = time.perf_counter() - started
        report = self._build_report(
            run_id=run_id,
            stats=stats,
            feature_names=feature_names,
            training_metrics=training_metrics,
            evaluations=evaluations,
            production_model=production_model,
            justification=justification,
            split_sizes={
                "train": len(train_df),
                "validation": len(val_df),
                "test": len(test_df),
            },
            duration_seconds=duration,
        )
        report["hyperparameter_optimization"] = tuning_report
        report["tuned_parameters_used"] = best_params
        report["cross_validation"] = cv_report
        report["calibration_analysis"] = calibration_report
        report["error_analysis"] = error_report
        report["report_artifacts"] = report_artifacts
        self._persist_metadata(run_id, report, feature_names)

        report_path = self.results_dir / f"full_retraining_report_{run_id}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        logger.info(
            "FULL RETRAINING RUN %s - COMPLETE (%.1fs). Report: %s",
            run_id, duration, report_path,
        )
        return report

    # ------------------------------------------------------------------
    # Dataset preparation
    # ------------------------------------------------------------------

    def prepare_datasets(
        self, sample: Optional[int] = None
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, PreprocessingStats]:
        """Discover, clean, merge, balance and split the training data.

        Args:
            sample: Optional cap on total merged rows (0 / None = FULL
                dataset unless ``MAX_TRAINING_ROWS`` is configured).

        Returns:
            Tuple ``(train_df, val_df, test_df, stats)``.
        """
        stats = PreprocessingStats()
        discovery = DatasetDiscovery(self.dataset_dir)
        datasets, profiles = discovery.load_all()

        stats.files_discovered = len(profiles)
        stats.files_used = len(datasets)
        stats.files_skipped = stats.files_discovered - stats.files_used
        stats.profiles = [p.to_dict() for p in profiles]
        stats.rows_loaded = sum(p.total_rows for p in profiles)
        stats.missing_values_removed = sum(
            p.missing_values + p.unmapped_labels for p in profiles
        )

        # Clean + validate each dataset with the existing components
        cleaner = DatasetCleaner()
        validator = DatasetValidator()
        prepared: dict[str, pd.DataFrame] = {}
        for name, df in datasets.items():
            before = len(df)
            cleaned = cleaner.clean(df)
            valid_df, invalid_df = validator.validate(cleaned)
            stats.malformed_urls_removed += (before - len(cleaned)) + len(invalid_df)
            if not valid_df.empty:
                prepared[name] = valid_df

        if not prepared:
            raise DatasetError(
                dataset=str(self.dataset_dir),
                operation="prepare",
                reason="No data survived cleaning and validation",
            )

        # Remove URLs with conflicting labels across datasets
        combined = pd.concat(prepared.values(), ignore_index=True)
        conflict_counts = combined.groupby("url")["label"].nunique()
        conflicting_urls = set(conflict_counts[conflict_counts > 1].index)
        if conflicting_urls:
            before = len(combined)
            combined = combined[~combined["url"].isin(conflicting_urls)]
            stats.conflicting_labels_removed = before - len(combined)
            logger.info(
                "Removed %d rows with conflicting labels (%d URLs)",
                stats.conflicting_labels_removed, len(conflicting_urls),
            )

        # Merge (dedup + shuffle) with the existing merger
        merger = DatasetMerger()
        rows_before_merge = len(combined)
        merged = merger.merge({"discovered": combined})
        stats.duplicates_removed = rows_before_merge - len(merged)

        # Balance guard
        merged, downsampled = self._balance(merged)
        stats.balance_downsampled = downsampled

        # Optional row cap (stratified).  Default is the FULL dataset:
        # MAX_TRAINING_ROWS=0 disables capping entirely.
        cap = sample if sample is not None else self.settings.dataset.max_training_rows
        if cap and 0 < cap < len(merged):
            logger.warning(
                "Training row cap EXPLICITLY configured: %d of %d rows "
                "will be used. Set MAX_TRAINING_ROWS=0 to train on the "
                "full dataset.", cap, len(merged),
            )
            merged = (
                merged.groupby("label", group_keys=False)
                .apply(lambda g: g.sample(
                    frac=cap / len(merged),
                    random_state=self.settings.dataset.random_seed,
                ))
                .sample(frac=1.0, random_state=self.settings.dataset.random_seed)
                .reset_index(drop=True)
            )
            logger.info("Applied training row cap: %d rows retained", len(merged))

        stats.final_rows = len(merged)
        stats.final_phishing = int((merged["label"] == 1).sum())
        stats.final_legitimate = int((merged["label"] == 0).sum())

        # Split and overwrite the processed splits (retires the old dataset)
        train_df, val_df, test_df = merger.split(merged)
        merger.save_splits(train_df, val_df, test_df, output_dir=self.processed_dir)
        return train_df, val_df, test_df, stats

    def _balance(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Downsample the majority class when the class ratio is excessive.

        Args:
            df: Merged DataFrame with ``['url', 'label']``.

        Returns:
            Tuple ``(balanced_df, rows_removed)``.
        """
        counts = df["label"].value_counts()
        if len(counts) < 2:
            return df, 0
        majority_label = int(counts.idxmax())
        majority, minority = int(counts.max()), int(counts.min())
        max_ratio = self.settings.dataset.balance_max_ratio
        if minority == 0 or majority / minority <= max_ratio:
            logger.info(
                "Class balance OK (ratio %.2f <= %.2f) - no downsampling",
                majority / max(minority, 1), max_ratio,
            )
            return df, 0

        target_majority = int(minority * max_ratio)
        majority_df = df[df["label"] == majority_label].sample(
            n=target_majority, random_state=self.settings.dataset.random_seed
        )
        balanced = (
            pd.concat([majority_df, df[df["label"] != majority_label]])
            .sample(frac=1.0, random_state=self.settings.dataset.random_seed)
            .reset_index(drop=True)
        )
        removed = len(df) - len(balanced)
        logger.info(
            "Balanced dataset: downsampled majority class %d by %d rows "
            "(ratio %.2f -> %.2f)",
            majority_label, removed, majority / minority, max_ratio,
        )
        return balanced, removed

    # ------------------------------------------------------------------
    # Feature extraction (chunk-streamed, memory-bounded)
    # ------------------------------------------------------------------

    def extract_features(
        self,
        urls: pd.Series,
        feature_names: list[str],
        split_name: str,
    ) -> np.ndarray:
        """Extract the feature matrix for *urls* using parallel workers.

        URLs are processed in chunks of ``extraction_chunk_size`` and
        written directly into a preallocated ``float32`` matrix, so peak
        memory stays bounded by one chunk of Python row lists regardless of
        the dataset size (incremental / streaming extraction).

        Args:
            urls: Series of URL strings.
            feature_names: Ordered feature names from the FeaturePipeline.
            split_name: Split label used for logging.

        Returns:
            Float32 matrix of shape ``(len(urls), len(feature_names))``.
        """
        url_list = urls.astype(str).tolist()
        n = len(url_list)
        matrix = np.zeros((n, len(feature_names)), dtype=np.float32)
        chunk = max(1, self.extraction_chunk_size)
        logger.info(
            "Extracting features for split '%s' - %d URLs "
            "(%d workers, chunks of %d)",
            split_name, n, self.n_workers, chunk,
        )
        started = time.perf_counter()

        if self.n_workers == 1 or n < 1000:
            _init_feature_worker(feature_names)
            for start in range(0, n, chunk):
                end = min(n, start + chunk)
                matrix[start:end] = [
                    _extract_row(url) for url in url_list[start:end]
                ]
        else:
            pool_chunk = max(250, chunk // (self.n_workers * 20))
            with Pool(
                processes=self.n_workers,
                initializer=_init_feature_worker,
                initargs=(feature_names,),
            ) as pool:
                for start in range(0, n, chunk):
                    end = min(n, start + chunk)
                    matrix[start:end] = pool.map(
                        _extract_row, url_list[start:end], chunksize=pool_chunk
                    )
                    logger.info(
                        "  '%s': %d/%d URLs extracted", split_name, end, n
                    )

        elapsed = time.perf_counter() - started
        logger.info(
            "Feature extraction for '%s' done in %.1fs (%.2f ms/URL)",
            split_name, elapsed, elapsed * 1000 / max(n, 1),
        )
        return matrix

    # ------------------------------------------------------------------
    # Hyperparameter optimization
    # ------------------------------------------------------------------

    def tune_models(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        model_names: Optional[list[str]] = None,
        n_trials: Optional[int] = None,
    ) -> dict[str, Any]:
        """Run Optuna optimization for the tunable tree-based models.

        Args:
            x_train: Training feature matrix.
            y_train: Training labels.
            model_names: Subset of ``TUNABLE_MODELS`` to tune.
            n_trials: Trials per model (default from settings).

        Returns:
            Mapping of model name to tuning-result dictionary.
        """
        training_cfg = self.settings.training
        names = [n for n in (model_names or TUNABLE_MODELS) if n in TUNABLE_MODELS]
        trials = int(n_trials if n_trials is not None else training_cfg.tuning_trials)
        results: dict[str, Any] = {}
        for name in names:
            try:
                tuner = OptunaTuner(
                    model_name=name,
                    n_trials=trials,
                    sample_size=training_cfg.tuning_sample_size,
                    early_stopping_rounds=training_cfg.early_stopping_rounds,
                    results_dir=self.results_dir,
                )
                result = tuner.tune(x_train, y_train)
                tuner.save_best_params(result)
                results[name] = result.to_dict()
            except Exception as exc:  # noqa: BLE001 -- tuning is best-effort
                logger.error("Hyperparameter tuning failed for %s: %s", name, exc)
                results[name] = {"error": str(exc)}
        return results

    # ------------------------------------------------------------------
    # Cross-validation
    # ------------------------------------------------------------------

    def cross_validate_models(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        model_names: list[str],
        best_params: Optional[dict[str, dict[str, Any]]] = None,
        cv_sample: Optional[int] = None,
    ) -> dict[str, Any]:
        """Stratified K-Fold CV (mean +/- std) for every requested model."""
        training_cfg = self.settings.training
        validator = CrossValidator(
            n_folds=training_cfg.cv_folds,
            sample_size=int(
                cv_sample if cv_sample is not None
                else training_cfg.cv_sample_size
            ),
            results_dir=self.results_dir,
        )
        results = {}
        for name in model_names:
            try:
                results[name] = validator.cross_validate(
                    name, x_train, y_train,
                    model_params=(best_params or {}).get(name),
                )
            except Exception as exc:  # noqa: BLE001 -- CV is best-effort
                logger.error("Cross-validation failed for %s: %s", name, exc)
        if results:
            validator.save_report(results)
        return {name: r.to_dict() for name, r in results.items()}

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def recalibrate_production_model(
        self,
        trainer: BaselineTrainer,
        production_model: str,
        x_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict[str, Any]:
        """Analyze calibration and recalibrate the production model when
        beneficial; the checkpoint is re-saved only if recalibration was
        applied (format unchanged)."""
        try:
            model = trainer.get_model(production_model)
            raw_val = (
                model.predict_proba_raw(x_val)
                if hasattr(model, "predict_proba_raw")
                else model.predict_proba(x_val)
            )
            analyzer = CalibrationAnalyzer()
            report = analyzer.auto_recalibrate(
                model, np.asarray(y_val, dtype=float),
                np.asarray(raw_val, dtype=float),
            )
            if report.get("recalibrated"):
                model.save(self.checkpoint_dir / f"{production_model}.pkl")
                logger.info(
                    "Production model '%s' re-saved with improved calibrator",
                    production_model,
                )
            return report
        except Exception as exc:  # noqa: BLE001
            logger.error("Calibration analysis failed: %s", exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Model selection & reporting
    # ------------------------------------------------------------------

    @staticmethod
    def select_production_model(
        evaluations: dict[str, dict[str, Any]],
    ) -> tuple[str, str]:
        """Select the production model by F1 -> ROC-AUC -> Recall -> Precision.

        Args:
            evaluations: Mapping of model name to evaluation dictionary.

        Returns:
            Tuple ``(model_name, human_readable_justification)``.
        """
        def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, ...]:
            _, ev = item
            return tuple(float(ev.get(metric, 0.0)) for metric in SELECTION_PRIORITY)

        ranked = sorted(evaluations.items(), key=sort_key, reverse=True)
        best_name, best_ev = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else "n/a"
        justification = (
            f"Selected '{best_name}' using the priority F1 > ROC-AUC > Recall > "
            f"Precision (accuracy alone is never used): "
            f"F1={best_ev.get('f1', 0):.4f}, ROC-AUC={best_ev.get('auc_roc', 0):.4f}, "
            f"Recall={best_ev.get('recall', 0):.4f}, "
            f"Precision={best_ev.get('precision', 0):.4f}, "
            f"PR-AUC={best_ev.get('pr_auc', 0):.4f}, "
            f"MCC={best_ev.get('mcc', 0):.4f}. Runner-up: '{runner_up}'."
        )
        logger.info(justification)
        return best_name, justification

    def _build_report(
        self,
        run_id: str,
        stats: PreprocessingStats,
        feature_names: list[str],
        training_metrics: dict[str, dict[str, float]],
        evaluations: dict[str, dict[str, Any]],
        production_model: str,
        justification: str,
        split_sizes: dict[str, int],
        duration_seconds: float,
    ) -> dict[str, Any]:
        """Assemble the complete retraining report dictionary."""
        return {
            "run_id": run_id,
            "versions": {
                "model_version": f"m-{run_id}",
                "dataset_version": f"ds-{run_id}",
                "feature_version": FEATURE_VERSION,
            },
            "dataset_directory": str(self.dataset_dir),
            "preprocessing": stats.to_dict(),
            "splits": split_sizes,
            "feature_count": len(feature_names),
            "training_metrics": training_metrics,
            "test_evaluations": evaluations,
            "production_model": {
                "name": production_model,
                "justification": justification,
                "checkpoint": str(self.checkpoint_dir / f"{production_model}.pkl"),
            },
            "checkpoint_dir": str(self.checkpoint_dir),
            "training_duration_seconds": round(duration_seconds, 1),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist_metadata(
        self,
        run_id: str,
        report: dict[str, Any],
        feature_names: list[str],
    ) -> None:
        """Write feature metadata and production-model metadata to disk."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        feature_metadata = {
            "feature_version": FEATURE_VERSION,
            "feature_count": len(feature_names),
            "feature_order": feature_names,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
        }
        (self.checkpoint_dir / "feature_metadata.json").write_text(
            json.dumps(feature_metadata, indent=2), encoding="utf-8"
        )

        preprocessing = report["preprocessing"]
        production_metadata = {
            "run_id": run_id,
            "training_date": report["completed_at"],
            "dataset_version": report["versions"]["dataset_version"],
            "model_version": report["versions"]["model_version"],
            "feature_version": FEATURE_VERSION,
            "dataset_size": preprocessing["final_rows"],
            "phishing_urls": preprocessing["final_phishing"],
            "legitimate_urls": preprocessing["final_legitimate"],
            "training_duration_seconds": report["training_duration_seconds"],
            "production_model": report["production_model"]["name"],
            "selection_justification": report["production_model"]["justification"],
            "dataset_directory": report["dataset_directory"],
        }
        (self.checkpoint_dir / "production_model.json").write_text(
            json.dumps(production_metadata, indent=2), encoding="utf-8"
        )
        logger.info(
            "Metadata persisted: feature_metadata.json, production_model.json"
        )
