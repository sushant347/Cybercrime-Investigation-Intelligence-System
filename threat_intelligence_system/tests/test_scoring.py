"""Unit tests for composite ThreatScorer."""
from src.scoring.threat_scorer import ThreatScorer

def test_threat_scorer_phishing_high_confidence():
    scorer = ThreatScorer()
    
    # 90% confidence phishing, brand similarity, bad TLD, young domain
    score, level = scorer.score(
        prediction_confidence=0.9,
        prediction_label="phishing",
        features={"is_suspicious_tld": 1, "is_typosquatting": 1},
        intelligence={
            "whois_success": True,
            "whois_domain_age_days": 10,
            "virustotal_success": True,
            "virustotal_positives": 5,
            "virustotal_total_scanners": 70,
        }
    )
    
    assert score >= 50
    assert level in ("Medium", "High", "Critical")

def test_threat_scorer_legitimate_high_confidence():
    scorer = ThreatScorer()
    
    # 95% confidence legitimate, safe features, old domain
    score, level = scorer.score(
        prediction_confidence=0.95,
        prediction_label="legitimate",
        features={"is_suspicious_tld": 0, "is_typosquatting": 0},
        intelligence={
            "whois_success": True,
            "whois_domain_age_days": 500,
            "virustotal_success": True,
            "virustotal_positives": 0,
            "virustotal_total_scanners": 70,
            "ssl_success": True,
            "ssl_has_ssl": True,
            "dns_success": True,
            "dns_has_spf": True,
            "dns_has_dmarc": True,
        }
    )
    
    assert score <= 10
    assert level == "Safe"

def test_threat_scorer_missing_intelligence():
    scorer = ThreatScorer()
    
    # Missing all intelligence databases/keys should fall back gracefully without raising
    score, level = scorer.score(
        prediction_confidence=0.5,
        prediction_label="legitimate",
        features={},
        intelligence={}
    )
    
    assert 20 <= score <= 80
    assert level in ("Low", "Medium", "High")
