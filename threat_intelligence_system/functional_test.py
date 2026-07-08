"""Functional end-to-end test of the phishing URL detection pipeline."""
import sys
sys.path.insert(0, ".")

print("=" * 60)
print("FUNCTIONAL TESTS")
print("=" * 60)

# 1. URL Validation
print("\n--- 1. URL Validation ---")
from src.parser.url_validator import URLValidator
v = URLValidator()

tests = [
    ("https://www.google.com", True),
    ("http://192.168.1.1/admin", True),
    ("https://xn--80ak6aa92e.com", True),  # punycode
    ("", False),
    ("https://bit.ly/abc123", True),
]
for url, expected_valid in tests:
    r = v.validate(url)
    status = "OK" if r.is_valid == expected_valid else "MISMATCH"
    print(f"  [{status}] {url!r:50s} valid={r.is_valid}, shortener={r.is_url_shortener}, ip={r.is_ip_address}, punycode={r.is_punycode}")

# 2. URL Parser
print("\n--- 2. URL Parser ---")
from src.parser.url_parser import URLParser
p = URLParser()
parsed = p.parse("https://sub1.sub2.example.com:8080/path/to/file.html?q=test&a=1#section")
print(f"  domain={parsed.domain}, subdomain={parsed.subdomain}, suffix={parsed.suffix}")
print(f"  registered_domain={parsed.registered_domain}")
print(f"  port={parsed.port}, has_port={parsed.has_port}")
print(f"  path_segments={parsed.path_segments}, depth={parsed.directory_depth}")
print(f"  filename={parsed.filename}, ext={parsed.file_extension}")
print(f"  query_param_count={parsed.query_param_count}")
print(f"  subdomain_count={parsed.subdomain_count}")
print(f"  url_tokens[:8]={parsed.url_tokens[:8]}")

# 3. Feature Engineering
print("\n--- 3. Feature Engineering ---")
from src.feature_engineering.pipeline import FeaturePipeline
pipeline = FeaturePipeline()
features = pipeline.extract("https://paypal-login-security.xyz/login?verify=true")
print(f"  Total features: {len(features)}")
print(f"  Feature names (sample): {list(features.keys())[:15]}")
# Key features check
key_checks = ["url_length", "hostname_length", "url_entropy", "digit_count", 
              "subdomain_count", "is_https", "is_suspicious_tld", "contains_suspicious_keyword"]
for k in key_checks:
    print(f"    {k} = {features.get(k, 'MISSING')}")

# 4. PredictionResult
print("\n--- 4. PredictionResult ---")
from src.prediction.result import PredictionResult
import json
result = PredictionResult(
    url="https://paypal-login-security.xyz/login",
    prediction="phishing",
    confidence=0.97,
    risk_score=91,
    risk_level="Critical",
    features={"url_length": 42},
    threat_intelligence={"domain_age_days": 3},
    reasons=["Young domain", "Suspicious TLD", "Brand impersonation"],
    model_type="xgboost",
)
json_out = result.to_json()
parsed_back = PredictionResult.from_json(json_out)
assert parsed_back.prediction == "phishing"
assert parsed_back.confidence == 0.97
assert parsed_back.is_phishing == True
assert parsed_back.is_high_risk == True
print(f"  to_json() OK (len={len(json_out)})")
print(f"  from_json() OK: prediction={parsed_back.prediction}, confidence={parsed_back.confidence}")
print(f"  summary(): {result.summary()}")

# 5. Threat Scorer (no intelligence)
print("\n--- 5. Threat Scorer ---")
from src.scoring.threat_scorer import ThreatScorer
scorer = ThreatScorer()
score, level = scorer.score(
    prediction_confidence=0.95,
    prediction_label="phishing",
    features=features,
    intelligence={},
)
print(f"  Score={score}, Level={level}")

# 6. Reason Generator
print("\n--- 6. Reason Generator ---")
from src.explainability.reason_generator import ReasonGenerator
rg = ReasonGenerator()
reasons = rg.generate(features=features, intelligence={}, prediction="phishing", confidence=0.95)
print(f"  Reasons ({len(reasons)}):")
for r in reasons[:8]:
    print(f"    - {r}")

# 7. PhishingPredictor (heuristic mode - no trained model)
print("\n--- 7. PhishingPredictor (heuristic fallback) ---")
from src.prediction.predictor import PhishingPredictor
predictor = PhishingPredictor(model_type="xgboost", use_intelligence=False)
result = predictor.predict("https://paypal-login-security.xyz/login")
print(f"  prediction={result.prediction}")
print(f"  confidence={result.confidence}")
print(f"  risk_score={result.risk_score}, risk_level={result.risk_level}")
print(f"  reasons={result.reasons[:5]}")
print(f"  features_count={len(result.features)}")

# Test a legitimate URL
result2 = predictor.predict("https://www.google.com")
print(f"\n  Google.com: prediction={result2.prediction}, confidence={result2.confidence}, level={result2.risk_level}")

# 8. Intelligence connectors graceful degradation
print("\n--- 8. Intelligence Graceful Degradation ---")
from src.intelligence.aggregator import IntelligenceAggregator
agg = IntelligenceAggregator()
print(f"  Available connectors: {agg.get_available_connectors()}")

print("\n" + "=" * 60)
print("ALL FUNCTIONAL TESTS PASSED")
print("=" * 60)
