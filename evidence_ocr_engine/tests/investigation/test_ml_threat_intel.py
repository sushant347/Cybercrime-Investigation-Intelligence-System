"""Unit tests for the ML threat-intel adapter (no heavy ML deps required)."""
from pathlib import Path
from types import SimpleNamespace

from backend.modules.investigation.ml_threat_intel import (
    MLThreatIntelProvider,
    _looks_like_url,
)


class _FakePredictor:
    """Stand-in for PhishingPredictor returning canned results by URL."""

    def __init__(self, table):
        self._table = table

    def predict(self, url):
        return self._table[url]


def _provider_with(table) -> MLThreatIntelProvider:
    p = MLThreatIntelProvider(Path("/nonexistent"))
    p._predictor = _FakePredictor(table)  # inject; skip lazy loader
    p._load_attempted = True
    return p


def test_url_detection():
    assert _looks_like_url("http://x.com/login")
    assert _looks_like_url("bad-domain.top/login")
    assert not _looks_like_url("hello world")
    assert not _looks_like_url("supp0rt@fake-bank.com")  # email, not a url


def test_graceful_degradation_when_system_missing():
    p = MLThreatIntelProvider(Path("/definitely/not/here"))
    assert p.available is False
    assert p.lookup("http://x.com") is None
    assert p.is_malicious("http://x.com") is False


def test_phishing_maps_to_malicious():
    url = "http://nabil-verify.scam.top/login"
    p = _provider_with(
        {url: SimpleNamespace(prediction="Phishing", risk_score=85,
                              confidence=0.85, model_type="xgboost",
                              risk_level="Critical", model_version="v1")}
    )
    hit = p.lookup(url)
    assert hit["verdict"] == "malicious"
    assert hit["source"] == "ml:xgboost"
    assert hit["risk_score"] == 85
    assert p.is_malicious(url) is True


def test_legitimate_maps_to_benign():
    url = "https://www.google.com"
    p = _provider_with(
        {url: SimpleNamespace(prediction="Legitimate", risk_score=15,
                              confidence=0.8, model_type="xgboost")}
    )
    hit = p.lookup(url)
    assert hit["verdict"] == "benign"
    assert p.is_malicious(url) is False


def test_midrange_risk_maps_to_suspicious():
    url = "http://promo-rewards.example/claim"
    p = _provider_with(
        {url: SimpleNamespace(prediction="Legitimate", risk_score=55,
                              confidence=0.6, model_type="xgboost")}
    )
    hit = p.lookup(url)
    assert hit["verdict"] == "suspicious"
    assert p.is_malicious(url) is False  # suspicious is not malicious


def test_non_url_values_ignored():
    p = _provider_with({})
    assert p.lookup("just some text") is None
    assert p.lookup("+9779812345678") is None
