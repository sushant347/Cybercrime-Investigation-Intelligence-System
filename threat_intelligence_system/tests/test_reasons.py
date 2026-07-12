"""Unit tests for ReasonGenerator."""
from src.explainability.reason_generator import ReasonGenerator

def test_reason_generator_clean_legitimate():
    rg = ReasonGenerator()
    reasons = rg.generate(
        features={"is_https": 1, "is_suspicious_tld": 0, "contains_suspicious_keyword": 0},
        intelligence={"whois_domain_age_days": 1000, "virustotal_positives": 0},
        prediction="legitimate",
        confidence=0.99
    )
    
    # Clean legimate URL should return very few / no threat reasons (maybe just a low confidence alert if low confidence, but here confidence is 99%)
    assert len(reasons) == 0

def test_reason_generator_phishing_triggers():
    rg = ReasonGenerator()
    reasons = rg.generate(
        features={
            "is_https": 0,
            "is_suspicious_tld": 1,
            "tld_risk_score": 0.8,
            "contains_suspicious_keyword": 1,
            "suspicious_keyword_count": 4,
            "is_punycode": 1,
            "is_ip_based": 1,
            "brand_in_domain": 1,
            "closest_brand": "paypal",
        },
        intelligence={
            "whois_domain_age_days": 3,
            "virustotal_success": True,
            "virustotal_positives": 12,
            "virustotal_total_scanners": 72,
        },
        prediction="phishing",
        confidence=0.92
    )
    
    assert len(reasons) > 0
    # Check that individual reasons are flagged
    assert any("AI model classified" in r for r in reasons)
    assert any("registered only 3 day" in r for r in reasons)
    assert any("top-level domain is frequently associated" in r for r in reasons)
    assert any("brand name" in r for r in reasons)
    assert any("IP address" in r for r in reasons)
    assert any("Punycode" in r for r in reasons)
    assert any("HTTPS" in r for r in reasons)
    assert any("suspicious keywords" in r for r in reasons)
    assert any("VirusTotal" in r for r in reasons)
