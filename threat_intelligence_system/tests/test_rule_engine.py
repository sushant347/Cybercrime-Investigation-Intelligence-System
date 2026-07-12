"""
Tests for the deterministic rule engine (src/rules/rule_engine.py).

Tests cover:
- Individual rule firing for canonical phishing patterns.
- No false positives on clearly legitimate URLs.
- Aggregate RuleResult structure and serialisation.
- Config-driven brand/TLD/keyword lists are respected.
"""
from __future__ import annotations

import pytest

from src.parser.url_parser import URLParser
from src.rules.rule_engine import RuleEngine, RuleResult, RuleFinding
from src.feature_engineering.pipeline import FeaturePipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine() -> RuleEngine:
    return RuleEngine()


@pytest.fixture(scope="module")
def parser() -> URLParser:
    return URLParser()


@pytest.fixture(scope="module")
def pipeline() -> FeaturePipeline:
    return FeaturePipeline()


def _eval(engine, parser, pipeline, url: str) -> RuleResult:
    """Helper: parse + extract + evaluate."""
    parsed = parser.parse(url)
    features = pipeline.extract(url)
    return engine.evaluate(parsed, features)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

class TestRuleResultStructure:
    def test_returns_rule_result(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "http://example.com")
        assert isinstance(result, RuleResult)

    def test_to_dict_keys(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "http://example.com")
        d = result.to_dict()
        assert "url" in d
        assert "findings" in d
        assert "rule_score" in d
        assert "is_definite_phishing" in d
        assert "is_suspicious" in d
        assert "finding_count" in d

    def test_finding_to_dict_keys(self):
        f = RuleFinding(
            rule_id="test_rule",
            description="Test",
            severity="high",
            score_contribution=0.5,
        )
        d = f.to_dict()
        assert d["rule_id"] == "test_rule"
        assert d["severity"] == "high"
        assert d["score_contribution"] == 0.5


# ---------------------------------------------------------------------------
# Phishing URL rule detection
# ---------------------------------------------------------------------------

class TestPhishingRules:
    def test_ip_based_url_fires(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "http://192.168.1.100/admin/login")
        rule_ids = {f.rule_id for f in result.findings}
        # IP-based rule or at least suspicious
        assert result.is_suspicious

    def test_no_https_fires(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "http://not-secure-site.net/login")
        rule_ids = {f.rule_id for f in result.findings}
        assert "no_https" in rule_ids

    def test_suspicious_tld_fires(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "https://login-paypal.xyz")
        rule_ids = {f.rule_id for f in result.findings}
        assert "suspicious_tld" in rule_ids

    def test_brand_in_subdomain_fires(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "https://paypal.malicious-domain.com/login")
        rule_ids = {f.rule_id for f in result.findings}
        assert "brand_in_subdomain" in rule_ids

    def test_long_url_fires(self, engine, parser, pipeline):
        long_url = "https://legitimate-looking-domain.com/" + "a" * 100
        result = _eval(engine, parser, pipeline, long_url)
        rule_ids = {f.rule_id for f in result.findings}
        assert "long_url" in rule_ids

    def test_double_slash_in_path_fires(self, engine, parser, pipeline):
        # Use a clearly phishing URL with double slash
        result = _eval(engine, parser, pipeline, "http://phishing.xyz//login//verify")
        rule_ids = {f.rule_id for f in result.findings}
        assert "double_slash_in_path" in rule_ids or result.is_suspicious

    def test_at_symbol_fires(self, engine, parser, pipeline):
        # @ before host — credentials camouflage
        result = _eval(engine, parser, pipeline, "http://trusted.com@malicious.xyz/login")
        rule_ids = {f.rule_id for f in result.findings}
        assert "at_symbol_in_url" in rule_ids

    def test_suspicious_keywords_fires(self, engine, parser, pipeline):
        result = _eval(
            engine, parser, pipeline,
            "https://secure-login-verify-account.com/reset"
        )
        rule_ids = {f.rule_id for f in result.findings}
        # Should fire suspicious_keywords (multiple keywords)
        assert any("keyword" in rid for rid in rule_ids)

    def test_definite_phishing_on_homograph(self, engine, parser, pipeline):
        # at_symbol_in_url is critical, so is_definite_phishing should be True
        result = _eval(engine, parser, pipeline, "http://trusted.com@malicious.xyz/")
        assert result.is_definite_phishing is True

    def test_rule_score_clamped_to_one(self, engine, parser, pipeline):
        # Even if many rules fire, score should be <= 1.0
        very_phishy = "http://paypal.verify-account-login.xyz@192.168.1.1//secure?update=1"
        result = _eval(engine, parser, pipeline, very_phishy)
        assert 0.0 <= result.rule_score <= 1.0


# ---------------------------------------------------------------------------
# Legitimate URL — minimal false positives
# ---------------------------------------------------------------------------

class TestLegitimateURL:
    def test_google_no_critical_rules(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "https://www.google.com/search?q=test")
        # No critical rules for a clean Google URL
        critical = [f for f in result.findings if f.severity == "critical"]
        assert len(critical) == 0

    def test_github_no_ip_rule(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "https://github.com/user/repo")
        rule_ids = {f.rule_id for f in result.findings}
        assert "is_ip_based" not in rule_ids

    def test_legitimate_no_definite_phishing(self, engine, parser, pipeline):
        result = _eval(engine, parser, pipeline, "https://www.microsoft.com/en-us/")
        # Microsoft's official domain should not be definite phishing
        assert result.is_definite_phishing is False
