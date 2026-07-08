"""
Tests for the ML Improvement phase: pluggable ML ensemble, expanded SHAP,
model metadata versioning, and the famous-domain success criteria for the
standalone ML model.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.ensemble.ml_ensemble import MLMember, MLModelEnsemble


class _StubModel:
    """Minimal BaseModel-contract stub for ensemble tests."""

    def __init__(self, probability: float, trained: bool = True,
                 fail: bool = False) -> None:
        self._p = probability
        self.is_trained = trained
        self._fail = fail

    def predict_proba(self, X):  # noqa: N803
        if self._fail:
            raise RuntimeError("boom")
        return np.full(len(X), self._p)


class TestMLModelEnsemble:
    def test_weighted_average(self) -> None:
        ens = MLModelEnsemble()
        ens.register(MLMember("a", _StubModel(0.9), "features", weight=3.0))
        ens.register(MLMember("b", _StubModel(0.1), "url", weight=1.0))
        p, breakdown = ens.predict_proba("https://x.com", np.zeros(5))
        assert p == pytest.approx(0.9 * 0.75 + 0.1 * 0.25)
        assert set(breakdown["members"]) == {"a", "b"}

    def test_untrained_and_failing_members_skipped(self) -> None:
        ens = MLModelEnsemble()
        ens.register(MLMember("ok", _StubModel(0.6), "features"))
        ens.register(MLMember("untrained", _StubModel(0.9, trained=False), "features"))
        ens.register(MLMember("broken", _StubModel(0.9, fail=True), "url"))
        p, breakdown = ens.predict_proba("https://x.com", np.zeros(5))
        assert p == pytest.approx(0.6)
        assert set(breakdown["skipped"]) == {"untrained", "broken"}

    def test_no_members_returns_none(self) -> None:
        p, breakdown = MLModelEnsemble().predict_proba("https://x.com", None)
        assert p is None
        assert breakdown["members"] == {}

    def test_validation(self) -> None:
        ens = MLModelEnsemble()
        with pytest.raises(ValueError):
            ens.register(MLMember("x", _StubModel(0.5), "bogus"))
        with pytest.raises(ValueError):
            ens.register(MLMember("x", _StubModel(0.5), "url", weight=0))

    def test_url_members_need_no_features(self) -> None:
        """Future transformer members must work without feature vectors."""
        ens = MLModelEnsemble()
        ens.register(MLMember("transformer", _StubModel(0.7), "url"))
        p, _ = ens.predict_proba("https://x.com", feature_vector=None)
        assert p == pytest.approx(0.7)


@pytest.fixture(scope="module")
def production_model():
    checkpoint = Path("checkpoints/xgboost.pkl")
    if not checkpoint.exists():
        pytest.skip("no production checkpoint")
    from src.models.baseline_models import create_baseline_model
    model = create_baseline_model("xgboost")
    model.load(checkpoint)
    return model


@pytest.fixture(scope="module")
def featuriser():
    from src.feature_engineering.pipeline import FeaturePipeline
    pipeline = FeaturePipeline()
    names = pipeline.get_feature_names()

    def vec(url: str) -> np.ndarray:
        feats = pipeline.extract(url)
        row = []
        for name in names:
            value = feats.get(name)
            try:
                row.append(float(value) if value is not None else 0.0)
            except (TypeError, ValueError):
                row.append(0.0)
        return np.array([row])

    return names, vec


class TestExpandedSHAP:
    def test_percentages_and_explanation_text(self, production_model, featuriser) -> None:
        from src.explainability.shap_explainer import SHAPExplainer
        names, vec = featuriser
        explainer = SHAPExplainer(production_model, names, top_k=5)
        explanation = explainer.explain_local(
            vec("https://paypal-verify-login.xyz/login")
        )
        assert explanation.success
        assert explanation.explanation_text
        assert "phishing probability" in explanation.explanation_text
        # Percentages are shares of total |SHAP|
        all_pct = [c.percentage for c in explanation.top_features]
        assert all(0.0 <= p <= 100.0 for p in all_pct)
        data = explanation.to_dict()
        assert "explanation_text" in data
        assert "percentage" in data["top_features"][0]


class TestModelVersioningMetadata:
    def test_production_model_has_full_metadata(self, production_model) -> None:
        md = production_model.metadata
        assert md.model_version == "3.0.0"
        assert md.dataset_version.startswith("ds-")
        assert md.feature_version != ""
        assert md.calibration_version.startswith("cal-")
        assert md.training_date != ""
        assert md.training_metrics
        assert md.validation_metrics
        assert md.benchmark_metrics


class TestFamousDomainSuccessCriteria:
    """Standalone ML (no rules, no intelligence) must clear famous domains."""

    FAMOUS = [
        "https://www.facebook.com", "https://google.com", "https://github.com",
        "https://www.amazon.com", "https://paypal.com", "https://www.apple.com",
        "https://microsoft.com", "https://www.cloudflare.com",
    ]
    PHISHING = [
        "https://paypal-verify-login.xyz/login",
        "http://192.168.1.5/secure/update",
        "https://faceb00k-security-alert.top/verify",
        "https://chase-online-banking.click/login.php",
    ]

    def test_famous_domains_legitimate(self, production_model, featuriser) -> None:
        _, vec = featuriser
        wrong = []
        for url in self.FAMOUS:
            proba = float(production_model.predict_proba(vec(url))[0])
            if proba >= 0.5:
                wrong.append((url, proba))
        assert not wrong, f"famous domains misclassified by standalone ML: {wrong}"

    def test_phishing_still_detected(self, production_model, featuriser) -> None:
        _, vec = featuriser
        caught = sum(
            float(production_model.predict_proba(vec(url))[0]) >= 0.5
            for url in self.PHISHING
        )
        assert caught >= 3, f"only {caught}/{len(self.PHISHING)} phishing URLs caught"
