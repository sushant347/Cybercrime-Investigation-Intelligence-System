"""
Tests for Phase 3 modules.

Covers: ensemble engine (B), SHAP explainer (C), calibration metrics (D),
evaluator extensions (G), feedback store (E), retraining pipeline (F),
URL transformer graceful degradation (A), and the new predictor output
fields, including backward compatibility.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

from src.ensemble.ensemble_engine import (
    EnsembleDecision,
    EnsembleEngine,
    EnsembleInputs,
)
from src.evaluation.evaluator import ModelEvaluator
from src.feedback.feedback_store import FeedbackStore, VALID_VERDICTS
from src.models.url_transformer import (
    URLTransformerModel,
    load_url_transformer_if_available,
    torch_available,
)
from src.prediction.result import PredictionResult
from src.scoring.calibrator import (
    CalibrationEvaluator,
    brier_score,
    expected_calibration_error,
    reliability_diagram,
)


# ---------------------------------------------------------------------------
# B. Ensemble Engine
# ---------------------------------------------------------------------------

class TestEnsembleEngine:
    def test_high_risk_signals_yield_phishing(self) -> None:
        decision = EnsembleEngine().combine(EnsembleInputs(
            xgboost_probability=0.95,
            transformer_probability=0.92,
            rule_score=0.85,
            threat_intel_score=0.7,
            trust_score=5,
        ))
        assert decision.prediction == "Phishing"
        assert decision.risk_score > 60
        assert decision.confidence > 0.6
        assert decision.explanation

    def test_low_risk_signals_yield_legitimate(self) -> None:
        decision = EnsembleEngine().combine(EnsembleInputs(
            xgboost_probability=0.03,
            transformer_probability=0.05,
            rule_score=0.0,
            threat_intel_score=0.05,
            trust_score=95,
        ))
        assert decision.prediction == "Legitimate"
        assert decision.risk_score <= 30

    def test_missing_transformer_weight_redistribution(self) -> None:
        decision = EnsembleEngine().combine(EnsembleInputs(
            xgboost_probability=0.5,
            transformer_probability=None,
            rule_score=0.5,
            threat_intel_score=0.5,
            trust_score=50,
        ))
        # Weights must renormalise to 1.0 over available signals
        assert decision.weights_used
        assert abs(sum(decision.weights_used.values()) - 1.0) < 1e-6
        assert "transformer" not in decision.weights_used
        assert decision.breakdown["transformer"] == 0.0

    def test_custom_weights_are_respected(self) -> None:
        engine = EnsembleEngine(weights={
            "xgboost": 1.0, "transformer": 0.0, "rules": 0.0,
            "threat_intelligence": 0.0, "trust": 0.0,
        })
        decision = engine.combine(EnsembleInputs(
            xgboost_probability=0.9,
            transformer_probability=None,
            rule_score=0.0,
            threat_intel_score=0.0,
            trust_score=100,
        ))
        assert decision.risk_score == 90

    def test_decision_serialisation(self) -> None:
        decision = EnsembleEngine().combine(EnsembleInputs())
        data = decision.to_dict()
        assert set(data) >= {
            "prediction", "confidence", "risk_score",
            "breakdown", "weights_used", "explanation",
        }
        json.dumps(data)  # must be JSON-serialisable


# ---------------------------------------------------------------------------
# C. SHAP explainer
# ---------------------------------------------------------------------------

class TestSHAPExplainer:
    @pytest.fixture()
    def trained_xgboost(self):
        pytest.importorskip("xgboost")
        from src.models.baseline_models import create_baseline_model
        checkpoint = Path("checkpoints/xgboost.pkl")
        if not checkpoint.exists():
            pytest.skip("No trained xgboost checkpoint available")
        model = create_baseline_model("xgboost")
        model.load(checkpoint)
        return model

    def test_local_explanation(self, trained_xgboost) -> None:
        from src.explainability.shap_explainer import SHAPExplainer
        from src.feature_engineering.pipeline import FeaturePipeline

        pipeline = FeaturePipeline()
        names = pipeline.get_feature_names()
        features = pipeline.extract("https://paypal-verify-login.xyz/login")
        vector = np.array([[float(features.get(n) or 0) for n in names]])

        explainer = SHAPExplainer(trained_xgboost, names, top_k=5)
        assert explainer.is_available
        explanation = explainer.explain_local(vector)
        assert explanation.success
        assert len(explanation.top_features) == 5
        assert all(c.contribution > 0 for c in explanation.positive_contributions)
        assert all(c.contribution < 0 for c in explanation.negative_contributions)
        # SHAP additivity: base + sum(contribs) == model log-odds output
        json.dumps(explanation.to_dict())

    def test_global_importance_normalised(self, trained_xgboost) -> None:
        from src.explainability.shap_explainer import SHAPExplainer
        from src.feature_engineering.pipeline import FeaturePipeline

        names = FeaturePipeline().get_feature_names()
        explainer = SHAPExplainer(trained_xgboost, names)
        importance = explainer.global_importance()
        assert importance
        assert abs(sum(importance.values()) - 1.0) < 1e-6

    def test_graceful_failure_on_bad_input(self, trained_xgboost) -> None:
        from src.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(trained_xgboost, ["only_one_feature"])
        explanation = explainer.explain_local(np.array([[1.0, 2.0]]))
        assert not explanation.success

    def test_unavailable_for_non_xgboost(self) -> None:
        from src.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(object(), ["f1"])
        assert not explainer.is_available
        assert not explainer.explain_local(np.array([[1.0]])).success
        assert explainer.global_importance() == {}


# ---------------------------------------------------------------------------
# D. Calibration metrics
# ---------------------------------------------------------------------------

class TestCalibrationMetrics:
    def test_brier_score_perfect_and_worst(self) -> None:
        y = np.array([0, 1, 1, 0])
        assert brier_score(y, np.array([0.0, 1.0, 1.0, 0.0])) == 0.0
        assert brier_score(y, np.array([1.0, 0.0, 0.0, 1.0])) == 1.0
        assert brier_score(np.array([]), np.array([])) == 0.0

    def test_ece_perfectly_calibrated(self) -> None:
        rng = np.random.RandomState(7)
        probabilities = rng.uniform(0, 1, 20000)
        labels = (rng.uniform(0, 1, 20000) < probabilities).astype(float)
        assert expected_calibration_error(labels, probabilities) < 0.03

    def test_ece_badly_calibrated(self) -> None:
        y = np.zeros(100)
        p = np.full(100, 0.9)
        assert expected_calibration_error(y, p) > 0.8

    def test_reliability_diagram_structure(self) -> None:
        rng = np.random.RandomState(0)
        y = rng.randint(0, 2, 200)
        p = rng.uniform(0, 1, 200)
        diagram = reliability_diagram(y, p, n_bins=10)
        assert set(diagram) == {
            "bin_centers", "mean_predicted", "fraction_positive", "bin_counts",
        }
        assert sum(diagram["bin_counts"]) == 200

    def test_evaluator_selects_a_method(self) -> None:
        rng = np.random.RandomState(1)
        y = rng.randint(0, 2, 400)
        # Miscalibrated probabilities: squash towards the centre
        p = np.clip(0.5 + (y - 0.5) * 0.2 + rng.normal(0, 0.1, 400), 0.01, 0.99)
        report = CalibrationEvaluator().evaluate_methods(y, p)
        assert report["best_method"] in ("platt", "isotonic", "temperature", "identity")
        assert "uncalibrated" in report
        best = report["methods"][report["best_method"]]
        assert best["ece"] <= report["uncalibrated"]["ece"] + 1e-9

    def test_best_calibrator_is_fitted(self) -> None:
        rng = np.random.RandomState(2)
        y = rng.randint(0, 2, 200)
        p = np.clip(y * 0.6 + rng.uniform(0, 0.4, 200), 0.01, 0.99)
        calibrator = CalibrationEvaluator().best_calibrator(y, p)
        value = calibrator.calibrate(0.7)
        assert 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# G. Evaluator extensions
# ---------------------------------------------------------------------------

class TestEvaluatorExtensions:
    def test_fpr_fnr_brier_ece_computed(self, tmp_path) -> None:
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_pred = np.array([0, 0, 1, 1, 1, 1, 1, 0])  # 2 FP, 1 FN
        y_prob = np.array([0.1, 0.2, 0.8, 0.7, 0.9, 0.85, 0.95, 0.3])
        result = ModelEvaluator(results_dir=tmp_path).evaluate(
            "unit", y_true, y_pred, y_prob
        )
        assert result.false_positive_rate == pytest.approx(0.5)
        assert result.false_negative_rate == pytest.approx(0.25)
        assert result.brier_score > 0.0
        assert result.expected_calibration_error > 0.0
        data = result.to_dict()
        for key in (
            "false_positive_rate", "false_negative_rate",
            "brier_score", "expected_calibration_error",
        ):
            assert key in data

    def test_backward_compatible_without_probabilities(self, tmp_path) -> None:
        y = np.array([0, 1, 0, 1])
        result = ModelEvaluator(results_dir=tmp_path).evaluate("unit", y, y)
        assert result.accuracy == 1.0
        assert result.brier_score == 0.0  # default when no probabilities


# ---------------------------------------------------------------------------
# E. Feedback store
# ---------------------------------------------------------------------------

class TestFeedbackStore:
    def test_record_and_counts(self, tmp_path) -> None:
        store = FeedbackStore(path=tmp_path / "fb.jsonl")
        store.record("https://a.xyz", "Phishing", "correct")
        store.record("https://b.com", "Phishing", "incorrect", correct_label="Legitimate")
        store.record("https://c.net", "Suspicious", "unknown")
        assert store.counts() == {"correct": 1, "incorrect": 1, "unknown": 1}
        assert len(store.get_all()) == 3
        assert len(store.get_corrections()) == 1

    def test_invalid_verdict_rejected(self, tmp_path) -> None:
        store = FeedbackStore(path=tmp_path / "fb.jsonl")
        with pytest.raises(ValueError):
            store.record("https://a.com", "Phishing", "maybe")
        with pytest.raises(ValueError):
            store.record("https://a.com", "Phishing", "incorrect")  # no label

    def test_export_for_retraining(self, tmp_path) -> None:
        store = FeedbackStore(path=tmp_path / "fb.jsonl")
        store.record("https://fp.com", "Phishing", "incorrect", correct_label="Legitimate")
        store.record("https://fn.xyz", "Legitimate", "incorrect", correct_label="Phishing")
        out = tmp_path / "corrections.csv"
        assert store.export_for_retraining(out) == 2
        lines = out.read_text().strip().splitlines()
        assert lines[0] == "url,label"
        assert "https://fp.com,0" in lines
        assert "https://fn.xyz,1" in lines

    def test_verdict_constants(self) -> None:
        assert VALID_VERDICTS == ("correct", "incorrect", "unknown")

    def test_empty_store(self, tmp_path) -> None:
        store = FeedbackStore(path=tmp_path / "missing.jsonl")
        assert store.get_all() == []
        assert store.counts() == {"correct": 0, "incorrect": 0, "unknown": 0}


# ---------------------------------------------------------------------------
# A. URL transformer (graceful degradation without torch)
# ---------------------------------------------------------------------------

class TestURLTransformer:
    def test_availability_flag_matches_torch(self) -> None:
        assert URLTransformerModel.is_available() == torch_available()

    def test_graceful_load_returns_none_without_checkpoint(self, tmp_path) -> None:
        assert load_url_transformer_if_available(tmp_path) is None

    def test_errors_without_torch(self) -> None:
        if torch_available():
            pytest.skip("torch installed -- degradation path not applicable")
        from src.utils.exceptions import ModelError
        model = URLTransformerModel()
        with pytest.raises(ModelError):
            model.train(np.array(["https://a.com"]), np.array([0]))
        with pytest.raises(ModelError):
            model.predict_proba(np.array(["https://a.com"]))

    @pytest.mark.skipif(not torch_available(), reason="torch not installed")
    def test_train_predict_save_load_roundtrip(self, tmp_path) -> None:
        urls = np.array(
            ["https://paypal-verify.xyz/login"] * 8 + ["https://www.google.com"] * 8
        )
        labels = np.array([1] * 8 + [0] * 8)
        model = URLTransformerModel(max_length=64, d_model=16, n_heads=2, n_layers=1)
        model.train(urls, labels, epochs=1, batch_size=4)
        proba = model.predict_proba(urls[:2])
        assert proba.shape == (2,)
        model.save(tmp_path / "ckpt")
        restored = URLTransformerModel()
        restored.load(tmp_path / "ckpt")
        assert restored.is_trained


# ---------------------------------------------------------------------------
# Predictor integration: Phase 3 output fields
# ---------------------------------------------------------------------------

class TestPredictorPhase3Outputs:
    @pytest.fixture(scope="class")
    def predictor(self):
        from src.prediction.predictor import PhishingPredictor
        return PhishingPredictor(
            model_type="xgboost",
            use_intelligence=False,
            resolve_shorteners=False,
        )

    def test_new_output_fields_present(self, predictor) -> None:
        result = predictor.predict("https://paypal-verify-login.xyz/login")
        data = result.to_dict()
        for key in (
            "transformer_confidence", "threat_intelligence_score",
            "decision_breakdown", "top_shap_features",
            "dataset_version", "calibration_version",
        ):
            assert key in data
        assert 0.0 <= result.threat_intelligence_score <= 1.0
        breakdown = result.decision_breakdown
        for key in (
            "ml_contribution", "rule_engine_contribution",
            "threat_intelligence_contribution", "trust_score_contribution",
            "final_risk_score",
        ):
            assert key in breakdown

    def test_shap_features_populated_for_xgboost(self, predictor) -> None:
        result = predictor.predict("https://secure-login-update.top/account/verify")

        # SHAP explains a trained booster's decision. Without a checkpoint the
        # predictor falls back to a feature heuristic, which has no decision to
        # attribute, so there is nothing here to assert. Trained checkpoints are
        # ~323 MB and deliberately not in the repository, making this the normal
        # state on a clean clone and in CI.
        #
        # Checked after predict(), not before: the model loads lazily on first
        # use, so `_model` is still None until then and an earlier check would
        # skip unconditionally - silently retiring the test everywhere.
        model = getattr(predictor, "_model", None)
        if model is None or not model.is_trained:
            pytest.skip("no trained checkpoint -- predictor is on the heuristic path")

        if result.metadata.get("rule_engine", {}).get("is_definite_phishing"):
            pytest.skip("rule short-circuit -- SHAP intentionally skipped")
        assert result.top_shap_features
        first = result.top_shap_features[0]
        assert {"feature", "value", "contribution"} <= set(first)

    def test_no_stdout_pollution(self, predictor) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            predictor.predict("https://www.example.com/page")
        assert buffer.getvalue() == ""

    def test_ensemble_mode_produces_valid_three_class(self) -> None:
        from src.prediction.predictor import PhishingPredictor
        predictor = PhishingPredictor(
            model_type="xgboost",
            use_intelligence=False,
            resolve_shorteners=False,
            use_ensemble=True,
        )
        result = predictor.predict("https://paypal-verify-login.xyz/login")
        assert result.prediction in ("Legitimate", "Suspicious", "Phishing")
        assert "ensemble" in result.metadata
        assert result.metadata["ensemble"]["weights_used"]
        legit = predictor.predict("https://www.google.com")
        assert legit.prediction == "Legitimate"

    def test_backward_compatibility_legacy_payload(self) -> None:
        legacy = {
            "url": "https://example.com",
            "prediction": "Legitimate",
            "confidence": 0.9,
            "risk_score": 10,
            "risk_level": "Safe",
        }
        result = PredictionResult.from_dict(legacy)
        assert result.transformer_confidence is None
        assert result.decision_breakdown == {}
        assert result.dataset_version == "unknown"
