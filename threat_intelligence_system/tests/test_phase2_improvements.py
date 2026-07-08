"""
Regression tests for Phase 2 verification improvements (v2.1).

Covers:
1. Brand registry expansion -- official_domains.yaml drives known_brands.
2. Token-boundary matching for short brand names (no 'ups' in 'groups').
3. PredictionResult versioning fields (model_version / feature_version).
4. predict() must not pollute stdout unless diagnostics=True.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from src.config.settings import get_settings
from src.feature_engineering.brand_features import BrandFeatureExtractor
from src.parser.url_parser import URLParser
from src.prediction.result import PredictionResult


# ---------------------------------------------------------------------------
# 1. Brand registry coverage
# ---------------------------------------------------------------------------

def test_official_domains_registry_covers_major_brands() -> None:
    """The registry must retain broad brand coverage for impersonation checks."""
    brands = set(get_settings().threat.known_brands)
    expected = {
        "paypal", "apple", "amazon", "google", "microsoft", "facebook",
        "netflix", "chase", "wellsfargo", "coinbase", "dhl", "fedex",
        "ups", "usps", "ebay", "steam", "wikipedia",
    }
    missing = expected - brands
    assert not missing, f"Brand registry missing: {sorted(missing)}"


def test_official_domain_match_for_registry_entries() -> None:
    """Official domains must be recognised and suppress impersonation flags."""
    parser = URLParser()
    extractor = BrandFeatureExtractor()

    features = extractor.extract(parser.parse("https://www.netflix.com/browse"))
    assert features["official_domain_match"] is True
    assert features["brand_in_domain"] == 0
    assert features["is_typosquatting"] == 0


# ---------------------------------------------------------------------------
# 2. Token-boundary matching for short brands
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://groups.example.com/discussion",   # 'ups' inside 'groups'
        "https://startups-weekly.com/news",        # 'ups' inside 'startups'
    ],
)
def test_short_brand_no_substring_false_positive(url: str) -> None:
    parser = URLParser()
    extractor = BrandFeatureExtractor()
    features = extractor.extract(parser.parse(url))
    assert features.get("brand_detected") != "ups"


def test_short_brand_token_match_still_fires() -> None:
    """A real short-brand impersonation (token-delimited) must still be caught."""
    parser = URLParser()
    extractor = BrandFeatureExtractor()
    features = extractor.extract(
        parser.parse("https://ups-tracking-delivery.xyz/parcel")
    )
    assert features["brand_detected"] == "ups"
    assert features["brand_in_domain"] == 1


def test_long_brand_concatenation_still_fires() -> None:
    """Longer brands must keep substring semantics ('paypalverify')."""
    parser = URLParser()
    extractor = BrandFeatureExtractor()
    features = extractor.extract(parser.parse("https://paypalverify-account.top/login"))
    assert features["brand_detected"] == "paypal"
    assert features["brand_in_domain"] == 1


# ---------------------------------------------------------------------------
# 3. Versioning fields in the structured output
# ---------------------------------------------------------------------------

def test_prediction_result_has_version_fields() -> None:
    result = PredictionResult(
        url="https://example.com",
        prediction="Legitimate",
        confidence=0.9,
        risk_score=10,
        risk_level="Safe",
    )
    data = result.to_dict()
    assert data["model_version"] == "unknown"
    assert data["feature_version"] == "unknown"

    # Explicit values round-trip through dict/json
    result2 = PredictionResult(
        url="https://example.com",
        prediction="Legitimate",
        confidence=0.9,
        risk_score=10,
        risk_level="Safe",
        model_version="2.0.0",
        feature_version="2.0.0",
    )
    restored = PredictionResult.from_json(result2.to_json())
    assert restored.model_version == "2.0.0"
    assert restored.feature_version == "2.0.0"


def test_prediction_result_backward_compatible_from_dict() -> None:
    """Old serialised payloads (without version fields) must still load."""
    legacy = {
        "url": "https://example.com",
        "prediction": "Phishing",
        "confidence": 0.8,
        "risk_score": 80,
        "risk_level": "Critical",
    }
    result = PredictionResult.from_dict(legacy)
    assert result.model_version == "unknown"
    assert result.feature_version == "unknown"


# ---------------------------------------------------------------------------
# 4. No stdout pollution in library mode
# ---------------------------------------------------------------------------

def test_predict_does_not_print_to_stdout() -> None:
    """predict() must stay silent on stdout unless diagnostics=True."""
    from src.prediction.predictor import PhishingPredictor

    predictor = PhishingPredictor(
        model_type="xgboost",
        use_intelligence=False,
        resolve_shorteners=False,
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = predictor.predict("https://www.example.com/page")

    assert buffer.getvalue() == "", (
        "predict() wrote to stdout in non-diagnostics mode: "
        f"{buffer.getvalue()[:200]!r}"
    )
    assert result.prediction in ("Legitimate", "Suspicious", "Phishing", "unknown")
