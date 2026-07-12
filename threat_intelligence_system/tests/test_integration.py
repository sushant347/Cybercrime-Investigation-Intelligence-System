"""Integration tests for the phishing URL detection engine."""
import json
from unittest.mock import patch, MagicMock
from src.prediction.predictor import PhishingPredictor
from src.prediction.result import PredictionResult

def test_full_pipeline_legitimate(tmp_path):
    # Use predictor with intelligence mocked out for stability and speed
    with patch("src.intelligence.aggregator.IntelligenceAggregator.gather_dict") as mock_gather:
        mock_gather.return_value = {
            "whois_success": True,
            "whois_domain_age_days": 1000,
            "virustotal_success": True,
            "virustotal_positives": 0,
            "virustotal_total_scanners": 72,
            "ssl_success": True,
            "ssl_has_ssl": True,
            "dns_success": True,
            "dns_has_spf": True,
            "dns_has_dmarc": True,
        }
        
        predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=True)
        res = predictor.predict("https://www.google.com")
        
        assert isinstance(res, PredictionResult)
        assert res.prediction.lower() == "legitimate"
        assert res.risk_score <= 20
        assert res.risk_level in ("Safe", "Low")
        assert len(res.features) >= 72
        assert res.threat_intelligence["whois_domain_age_days"] == 1000

def test_full_pipeline_phishing(tmp_path):
    # Mock malicious intelligence signals
    with patch("src.intelligence.aggregator.IntelligenceAggregator.gather_dict") as mock_gather:
        mock_gather.return_value = {
            "whois_success": True,
            "whois_domain_age_days": 3,
            "virustotal_success": True,
            "virustotal_positives": 15,
            "virustotal_total_scanners": 72,
            "ssl_success": True,
            "ssl_has_ssl": False,
            "dns_success": True,
            "dns_has_spf": False,
            "dns_has_dmarc": False,
        }
        
        predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=True)
        res = predictor.predict("https://paypal-login-security.xyz/login")
        
        assert isinstance(res, PredictionResult)
        # Should classify as phishing due to heuristics + scoring
        assert res.prediction.lower() == "phishing"
        assert res.risk_score > 60
        assert any("paypal" in r for r in res.reasons)
        assert any("VirusTotal" in r for r in res.reasons)

def test_predictor_missing_deps_fallback(tmp_path):
    # Verify that missing components or key errors degrade gracefully and don't raise exceptions
    predictor = PhishingPredictor(model_type="xgboost", checkpoint_dir=tmp_path, use_intelligence=True)
    
    # Force a failure inside the feature pipeline or scorer
    with patch("src.feature_engineering.pipeline.FeaturePipeline.extract", side_effect=Exception("feature error")), \
         patch("src.intelligence.aggregator.IntelligenceAggregator.gather_dict", side_effect=Exception("api error")):
         
        # Predict should not raise, but return an unknown/legitimate prediction with errors handled
        res = predictor.predict("https://example.com")
        assert isinstance(res, PredictionResult)
        assert res.url == "https://example.com"
        assert res.risk_level in ("Safe", "Low", "Medium", "High", "Critical", "Unknown")
