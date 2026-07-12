"""Unit tests for PhishingPredictor and PredictionResult, including edge cases."""
import pytest
from src.prediction.result import PredictionResult
from src.prediction.predictor import PhishingPredictor


def test_prediction_result_properties():
    res = PredictionResult(
        url="https://paypal.xyz",
        prediction="Phishing",
        confidence=0.85,
        risk_score=85,
        risk_level="Critical",
        reasons=["Reason 1", "Reason 2"],
        trust_score=10,
        ssl_status="INVALID",
    )
    
    assert res.is_phishing is True
    assert res.is_suspicious is False
    assert res.is_high_risk is True
    assert res.trust_score == 10
    assert res.ssl_status == "INVALID"
    assert "paypal.xyz" in res.summary()
    assert "85/100" in res.summary()


def test_prediction_result_json_roundtrip():
    res = PredictionResult(
        url="https://paypal.xyz",
        prediction="Phishing",
        confidence=0.85,
        risk_score=85,
        risk_level="Critical",
        reasons=["Reason 1", "Reason 2"],
        trust_score=15,
        ml_confidence=0.82,
        rule_confidence=0.90,
        decision_confidence=0.85,
        brand_detected="paypal",
        official_domain=False,
        ssl_status="INVALID",
        positive_indicators=["✓ Valid SSL"],
        negative_indicators=["✗ Phishing keyword"],
        neutral_indicators=["• GeoIP neutral"],
    )
    
    js = res.to_json()
    new_res = PredictionResult.from_json(js)
    
    assert new_res.url == res.url
    assert new_res.prediction == res.prediction
    assert new_res.confidence == res.confidence
    assert new_res.risk_score == res.risk_score
    assert new_res.risk_level == res.risk_level
    assert new_res.reasons == res.reasons
    assert new_res.trust_score == res.trust_score
    assert new_res.ml_confidence == res.ml_confidence
    assert new_res.rule_confidence == res.rule_confidence
    assert new_res.decision_confidence == res.decision_confidence
    assert new_res.brand_detected == res.brand_detected
    assert new_res.official_domain == res.official_domain
    assert new_res.ssl_status == res.ssl_status
    assert new_res.positive_indicators == res.positive_indicators
    assert new_res.negative_indicators == res.negative_indicators
    assert new_res.neutral_indicators == res.neutral_indicators


def test_predictor_heuristic_fallback(tmp_path):
    # PhishingPredictor without a trained model should fall back to heuristic prediction
    predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=False)
    
    res = predictor.predict("https://paypal-login-security.xyz/login")
    assert res.url == "https://paypal-login-security.xyz/login"
    assert res.prediction == "Phishing"  # Fired keywords, brand, TLD
    assert res.risk_score > 60
    assert len(res.reasons) > 0
    assert res.model_type == "xgboost"
    assert res.official_domain is False
    assert res.brand_detected == "paypal"
    
    # Official domain should be Legitimate
    res_legit = predictor.predict("https://www.google.com")
    assert res_legit.prediction == "Legitimate"
    assert res_legit.risk_score <= 20
    assert res_legit.official_domain is True
    assert res_legit.brand_detected == "google"


def test_predictor_batch(tmp_path):
    predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=False)
    urls = ["https://www.google.com", "https://paypal-login-security.xyz/login"]
    results = predictor.predict_batch(urls)
    
    assert len(results) == 2
    assert results[0].url == urls[0]
    assert results[1].url == urls[1]


@pytest.mark.parametrize(
    "url,expected_class,is_official",
    [
        # Official Legitimate
        ("https://www.facebook.com", "Legitimate", True),
        ("https://m.facebook.com", "Legitimate", True),
        ("https://accounts.google.com", "Legitimate", True),
        ("https://developer.github.com", "Legitimate", True),
        ("https://paypal.com", "Legitimate", True),
        ("https://amazon.com", "Legitimate", True),
        ("https://apple.com", "Legitimate", True),
        ("https://cloudflare.com", "Legitimate", True),
        
        # Lookalikes (Phishing/Suspicious)
        ("https://facebook-login.xyz", "Phishing", False),
        ("https://facebook.com.evil.xyz", "Phishing", False),
        ("https://google-security.xyz", "Phishing", False),
        ("https://paypal-login.net", "Phishing", False),
        ("https://github-authentication.ru", "Phishing", False),
        
        # Edge Cases
        ("https://192.168.1.10/login", "Phishing", False),
        ("https://paypaI.com", "Phishing", False),  # Homograph capital I
        ("https://xn--paypl-3ve.com", "Phishing", False),  # Punycode homograph
    ]
)
def test_predictor_edge_cases(tmp_path, url, expected_class, is_official):
    """Test predictor on complex lookalike, official, and edge-case URLs."""
    predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=False)
    res = predictor.predict(url)
    
    assert res.official_domain == is_official
    if is_official:
        assert res.prediction == "Legitimate"
        assert res.risk_score <= 20
        assert res.trust_score >= 80
        assert any("Official registered domain" in ind for ind in res.positive_indicators)
    else:
        assert res.prediction in ("Phishing", "Suspicious")
        assert res.risk_score >= 30
        assert res.trust_score <= 60
