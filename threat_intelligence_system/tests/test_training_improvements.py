"""
Tests for the ML training pipeline improvements:

* Stratified K-Fold cross-validation (metrics + mean/std aggregation)
* Optuna hyperparameter optimization (search spaces, resume, persistence)
* Calibration analysis (ECE / MCE / Brier, automatic recalibration)
* SHAP artifacts and evaluation report generation (PNG + PDF)
* Error analysis CSV export (FP / FN / high-confidence mistakes)

All tests run on small synthetic data so the suite stays fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evaluation.cross_validation import (
    CV_METRICS,
    CrossValidationResult,
    CrossValidator,
)
from src.evaluation.error_analysis import ErrorAnalyzer
from src.scoring.calibration_analysis import (
    CalibrationAnalyzer,
    maximum_calibration_error,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RNG = np.random.RandomState(42)
N_SAMPLES = 400
N_FEATURES = 8


@pytest.fixture(scope="module")
def synthetic_data() -> tuple[np.ndarray, np.ndarray]:
    """Separable synthetic binary dataset (deterministic)."""
    rng = np.random.RandomState(42)
    X0 = rng.normal(loc=0.0, scale=1.0, size=(N_SAMPLES // 2, N_FEATURES))
    X1 = rng.normal(loc=1.5, scale=1.0, size=(N_SAMPLES // 2, N_FEATURES))
    X = np.vstack([X0, X1]).astype(np.float32)
    y = np.concatenate([np.zeros(N_SAMPLES // 2), np.ones(N_SAMPLES // 2)]).astype(int)
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

class TestCrossValidation:
    def test_fold_indices_stratified(self, synthetic_data) -> None:
        X, y = synthetic_data
        cv = CrossValidator(n_folds=5)
        folds = cv.fold_indices(y)
        assert len(folds) == 5
        for train_idx, test_idx in folds:
            # No leakage between train and test indices
            assert not set(train_idx) & set(test_idx)
            # Stratification keeps both classes in every fold
            assert set(np.unique(y[test_idx])) == {0, 1}

    def test_evaluate_fold_metrics(self, synthetic_data) -> None:
        X, y = synthetic_data
        cv = CrossValidator(n_folds=5)
        metrics = cv.evaluate_fold("decision_tree", X, y, fold_index=0)
        for metric in CV_METRICS:
            assert metric in metrics
            assert 0.0 <= metrics[metric] <= 1.0 or metric == "mcc"

    def test_cross_validate_reports_mean_and_std(self, synthetic_data) -> None:
        X, y = synthetic_data
        cv = CrossValidator(n_folds=3)
        result = cv.cross_validate("naive_bayes", X, y)
        assert isinstance(result, CrossValidationResult)
        assert result.n_folds == 3
        assert len(result.fold_metrics) == 3
        for metric in CV_METRICS:
            assert metric in result.mean
            assert metric in result.std
            assert result.std[metric] >= 0.0
        # Separable data: the model must clearly beat chance
        assert result.mean["f1"] > 0.7
        assert result.mean["roc_auc"] > 0.7

    def test_subsample_is_stratified_and_capped(self, synthetic_data) -> None:
        X, y = synthetic_data
        cv = CrossValidator(n_folds=3, sample_size=100)
        X_s, y_s = cv.subsample(X, y)
        assert len(y_s) <= 102  # rounding tolerance
        ratio = y_s.mean()
        assert 0.4 <= ratio <= 0.6  # class balance preserved

    def test_save_report(self, synthetic_data, tmp_path: Path) -> None:
        X, y = synthetic_data
        cv = CrossValidator(n_folds=3, results_dir=tmp_path)
        result = cv.cross_validate("naive_bayes", X, y)
        path = cv.save_report({"naive_bayes": result})
        payload = json.loads(path.read_text())
        assert payload["n_folds"] == 3
        assert "naive_bayes" in payload["models"]
        assert "mean" in payload["models"]["naive_bayes"]


# ---------------------------------------------------------------------------
# Optuna hyperparameter optimization
# ---------------------------------------------------------------------------

class TestOptunaTuner:
    def test_rejects_unsupported_model(self, tmp_path: Path) -> None:
        from src.training.hyperparameter_tuner import OptunaTuner
        with pytest.raises(ValueError):
            OptunaTuner("naive_bayes", results_dir=tmp_path)

    @pytest.mark.parametrize("model_name", ["xgboost", "random_forest"])
    def test_tune_finds_params_and_persists(
        self, synthetic_data, tmp_path: Path, model_name: str
    ) -> None:
        pytest.importorskip("optuna")
        from src.training.hyperparameter_tuner import (
            OptunaTuner,
            load_best_params,
        )
        X, y = synthetic_data
        tuner = OptunaTuner(
            model_name,
            n_trials=3,
            results_dir=tmp_path,
            storage=f"sqlite:///{tmp_path / 'studies.db'}",
        )
        result = tuner.tune(X, y)
        assert result.n_trials == 3
        assert 0.0 <= result.best_score <= 1.0
        assert "n_estimators" in result.best_params
        assert "max_depth" in result.best_params
        if model_name == "xgboost":
            for key in ("learning_rate", "subsample", "colsample_bytree",
                        "gamma", "min_child_weight", "reg_alpha", "reg_lambda"):
                assert key in result.best_params

        tuner.save_best_params(result)
        loaded = load_best_params(tmp_path)
        assert loaded[model_name] == result.best_params

    def test_study_resumes(self, synthetic_data, tmp_path: Path) -> None:
        pytest.importorskip("optuna")
        from src.training.hyperparameter_tuner import OptunaTuner
        X, y = synthetic_data
        storage = f"sqlite:///{tmp_path / 'studies.db'}"
        tuner = OptunaTuner("xgboost", n_trials=2, results_dir=tmp_path,
                            storage=storage)
        first = tuner.tune(X, y)
        # New tuner instance, same storage: study must resume, not restart
        tuner2 = OptunaTuner("xgboost", n_trials=2, results_dir=tmp_path,
                             storage=storage)
        second = tuner2.tune(X, y)
        assert second.n_trials == first.n_trials + 2

    def test_load_best_params_missing_file(self, tmp_path: Path) -> None:
        from src.training.hyperparameter_tuner import load_best_params
        assert load_best_params(tmp_path) == {}


# ---------------------------------------------------------------------------
# Calibration analysis
# ---------------------------------------------------------------------------

class TestCalibrationAnalysis:
    def test_mce_perfect_calibration_is_zero(self) -> None:
        y_prob = np.linspace(0.05, 0.95, 1000)
        rng = np.random.RandomState(0)
        y_true = (rng.rand(1000) < y_prob).astype(float)
        mce = maximum_calibration_error(y_true, y_prob, n_bins=5)
        assert mce < 0.1  # near-perfect calibration

    def test_mce_detects_miscalibration(self) -> None:
        # Model always predicts 0.9 but is right only half the time
        y_prob = np.full(200, 0.9)
        y_true = np.array([0, 1] * 100, dtype=float)
        mce = maximum_calibration_error(y_true, y_prob)
        assert mce > 0.3

    def test_analyze_reports_all_metrics(self) -> None:
        rng = np.random.RandomState(1)
        y_true = rng.randint(0, 2, 500).astype(float)
        y_prob = np.clip(y_true * 0.7 + rng.rand(500) * 0.3, 0, 1)
        report = CalibrationAnalyzer().analyze(y_true, y_prob)
        payload = report.to_dict()
        for key in ("brier_score", "expected_calibration_error",
                    "maximum_calibration_error", "reliability_diagram"):
            assert key in payload
        assert payload["maximum_calibration_error"] >= payload[
            "expected_calibration_error"] - 1e-9

    def test_auto_recalibrate_improves_miscalibrated_model(
        self, synthetic_data
    ) -> None:
        from src.models.baseline_models import create_baseline_model
        from src.scoring.calibrator import ConfidenceCalibrator
        X, y = synthetic_data
        model = create_baseline_model("naive_bayes")
        model.model.fit(X, y)
        model._is_trained = True
        # Force an identity (uncalibrated) starting point
        model.calibrator = ConfidenceCalibrator(method="identity")
        model.calibrator.is_fitted = True

        raw = model.predict_proba_raw(X)
        analyzer = CalibrationAnalyzer(min_improvement=0.0)
        report = analyzer.auto_recalibrate(model, y.astype(float), raw)
        assert report["best_method"] in ("platt", "isotonic", "temperature")
        assert "current" in report and "candidates" in report
        if report["recalibrated"]:
            assert model.calibrator.method == report["best_method"]
            assert model.calibrator.is_fitted

    def test_auto_recalibrate_respects_threshold(self, synthetic_data) -> None:
        from src.models.baseline_models import create_baseline_model
        X, y = synthetic_data
        model = create_baseline_model("naive_bayes")
        model.model.fit(X, y)
        model._is_trained = True
        raw = model.predict_proba_raw(X)
        model.calibrator.fit(y.astype(float), raw)  # already calibrated
        analyzer = CalibrationAnalyzer(min_improvement=1.0)  # unreachable bar
        report = analyzer.auto_recalibrate(model, y.astype(float), raw)
        assert report["recalibrated"] is False


# ---------------------------------------------------------------------------
# Error analysis
# ---------------------------------------------------------------------------

class TestErrorAnalysis:
    def test_csv_exports(self, tmp_path: Path) -> None:
        urls = [f"http://site-{i}.com" for i in range(10)]
        y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        y_pred = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])  # 2 FP, 2 FN
        y_proba = np.array([.1, .9, .2, .6, .3, .8, .4, .7, .05, .95])

        summary = ErrorAnalyzer(tmp_path, high_confidence_top_k=3).analyze(
            "test_model", urls, y_true, y_pred, y_proba
        )
        assert summary.false_positives == 2
        assert summary.false_negatives == 2
        assert summary.high_confidence_mistakes == 3

        fp = pd.read_csv(summary.files["false_positives"])
        fn = pd.read_csv(summary.files["false_negatives"])
        hc = pd.read_csv(summary.files["high_confidence_mistakes"])
        assert set(fp["predicted_label"]) == {1}
        assert set(fn["predicted_label"]) == {0}
        # Highest-confidence mistake first
        assert hc["prediction_confidence"].is_monotonic_decreasing
        for frame in (fp, fn, hc):
            assert list(frame.columns) == [
                "url", "true_label", "predicted_label",
                "phishing_probability", "prediction_confidence",
            ]

    def test_no_mistakes_yields_empty_csvs(self, tmp_path: Path) -> None:
        urls = ["http://a.com", "http://b.com"]
        y = np.array([0, 1])
        summary = ErrorAnalyzer(tmp_path).analyze(
            "perfect", urls, y, y, np.array([0.1, 0.9])
        )
        assert summary.false_positives == 0
        assert summary.false_negatives == 0
        assert Path(summary.files["false_positives"]).exists()


# ---------------------------------------------------------------------------
# Report generation (PNG + PDF) and SHAP
# ---------------------------------------------------------------------------

class TestReportGeneration:
    @pytest.fixture(scope="class")
    def trained_xgb(self, synthetic_data):
        from src.models.baseline_models import create_baseline_model
        X, y = synthetic_data
        model = create_baseline_model("xgboost", n_estimators=25, max_depth=3)
        model.model.fit(X, y)
        model._is_trained = True
        return model

    def test_curve_plots_png_and_pdf(self, synthetic_data, tmp_path: Path,
                                     trained_xgb) -> None:
        pytest.importorskip("matplotlib")
        from src.reporting.evaluation_plots import EvaluationReportGenerator
        X, y = synthetic_data
        proba = trained_xgb.model.predict_proba(X)[:, 1]
        gen = EvaluationReportGenerator(tmp_path)
        for method, args in (
            ("plot_roc_curve", (y, proba, "m")),
            ("plot_precision_recall_curve", (y, proba, "m")),
            ("plot_calibration_curve", (y, proba, "m")),
        ):
            paths = getattr(gen, method)(*args)
            assert Path(paths["png"]).exists()
            assert Path(paths["pdf"]).exists()

    def test_confusion_and_importance_plots(self, tmp_path: Path,
                                            trained_xgb) -> None:
        pytest.importorskip("matplotlib")
        from src.reporting.evaluation_plots import EvaluationReportGenerator
        gen = EvaluationReportGenerator(tmp_path)
        cm_paths = gen.plot_confusion_matrix([[50, 5], [3, 42]], "m")
        assert Path(cm_paths["png"]).exists() and Path(cm_paths["pdf"]).exists()
        names = [f"f{i}" for i in range(N_FEATURES)]
        fi_paths = gen.plot_feature_importance(trained_xgb, names, "m")
        assert fi_paths is not None
        assert Path(fi_paths["png"]).exists() and Path(fi_paths["pdf"]).exists()

    def test_shap_summary_generated_for_tree_model(
        self, synthetic_data, tmp_path: Path, trained_xgb
    ) -> None:
        pytest.importorskip("shap")
        pytest.importorskip("matplotlib")
        from src.reporting.evaluation_plots import EvaluationReportGenerator
        X, _ = synthetic_data
        names = [f"f{i}" for i in range(N_FEATURES)]
        paths = EvaluationReportGenerator(tmp_path).plot_shap_summary(
            trained_xgb, X[:100], names, "m", max_samples=100
        )
        assert paths is not None
        assert Path(paths["png"]).exists() and Path(paths["pdf"]).exists()

    def test_generate_all(self, synthetic_data, tmp_path: Path,
                          trained_xgb) -> None:
        pytest.importorskip("matplotlib")
        from sklearn.metrics import confusion_matrix
        from src.reporting.evaluation_plots import EvaluationReportGenerator
        X, y = synthetic_data
        proba = trained_xgb.model.predict_proba(X)[:, 1]
        pred = (proba > 0.5).astype(int)
        names = [f"f{i}" for i in range(N_FEATURES)]
        artifacts = EvaluationReportGenerator(tmp_path).generate_all(
            model=trained_xgb, model_name="m",
            y_true=y, y_proba=proba,
            confusion=confusion_matrix(y, pred),
            feature_names=names, X_sample=X[:100],
        )
        for key in ("roc_curve", "precision_recall_curve",
                    "calibration_curve", "confusion_matrix",
                    "feature_importance"):
            assert key in artifacts

    def test_local_shap_top10_available_for_predictions(
        self, synthetic_data, trained_xgb
    ) -> None:
        """Every prediction can be explained with its top-10 features."""
        from src.explainability.shap_explainer import SHAPExplainer
        X, _ = synthetic_data
        names = [f"f{i}" for i in range(N_FEATURES)]
        explainer = SHAPExplainer(trained_xgb, names, top_k=10)
        assert explainer.is_available
        explanation = explainer.explain_local(X[0])
        assert explanation.success
        assert len(explanation.top_features) == min(10, N_FEATURES)
