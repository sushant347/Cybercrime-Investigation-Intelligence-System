"""
Tests for the Brand Intelligence Engine and its Rule Engine integration.

Covers official domains, legitimate subdomains, typosquatting (edit distance,
leetspeak, keyboard slips, repeated/missing/extra chars), Unicode homoglyph
attacks, cloud-hosted phishing, prefix/suffix abuse, brand tokens in paths and
subdomains, mixed-language / multi-label public-suffix domains, and explicit
false-positive / false-negative guards. Also asserts the additive Rule Engine
integration and full backward compatibility.
"""

from __future__ import annotations

import pytest

from src.intelligence.brand_intelligence import (
    BrandIntelligenceEngine,
    BrandIntelligenceResult,
)


@pytest.fixture(scope="module")
def engine() -> BrandIntelligenceEngine:
    return BrandIntelligenceEngine()


# ---------------------------------------------------------------------------
# Official domains & legitimate subdomains (must NOT be flagged)
# ---------------------------------------------------------------------------

class TestOfficialDomains:
    @pytest.mark.parametrize("url,brand", [
        ("https://www.microsoft.com", "microsoft"),
        ("https://login.microsoft.com/oauth2/authorize", "microsoft"),
        ("https://accounts.google.com/signin", "google"),
        ("https://mail.google.com", "google"),
        ("https://appleid.apple.com/account", "apple"),
        ("https://www.paypal.com/signin", "paypal"),
        ("https://web.whatsapp.com", "whatsapp"),
        ("https://github.com/login", "github"),
        ("https://khalti.com/#/login", "khalti"),
        ("https://esewa.com.np/login", "esewa"),
        ("https://nagarikapp.gov.np", "nagarik_app"),
        ("https://ird.gov.np", "government_of_nepal"),
        ("https://nabilbank.com/login", "nabil_bank"),
    ])
    def test_official_domains_are_trusted(self, engine, url, brand) -> None:
        result = engine.analyze(url)
        assert result.is_official_domain is True
        assert result.official_brand == brand
        assert result.risk_score == 0.0
        assert result.risk_level == "none"
        assert not result.findings

    def test_deep_subdomain_still_official(self, engine) -> None:
        result = engine.analyze("https://a.b.c.login.microsoftonline.com/x")
        assert result.is_official_domain is True
        assert result.registrable_domain == "microsoftonline.com"

    def test_gov_np_suffix_is_official(self, engine) -> None:
        result = engine.analyze("https://newportal.moha.gov.np/citizen")
        assert result.is_official_domain is True
        assert result.official_brand == "government_of_nepal"


# ---------------------------------------------------------------------------
# Registrable domain comparison (PSL) - the three spec examples
# ---------------------------------------------------------------------------

class TestRegistrableDomain:
    def test_login_microsoft_maps_to_microsoft(self, engine) -> None:
        assert engine.analyze(
            "https://login.microsoft.com"
        ).registrable_domain == "microsoft.com"

    def test_secure_login_paypal_is_own_domain(self, engine) -> None:
        result = engine.analyze("https://secure-login-paypal.com")
        assert result.registrable_domain == "secure-login-paypal.com"
        assert result.is_official_domain is False

    def test_multi_label_suffix_cn(self, engine) -> None:
        result = engine.analyze("https://edge-origin-whatsapp.com.cn/login")
        assert result.registrable_domain == "edge-origin-whatsapp.com.cn"
        assert result.is_official_domain is False


# ---------------------------------------------------------------------------
# Brand token detection (hostname / subdomain / path / query)
# ---------------------------------------------------------------------------

class TestBrandTokens:
    def test_token_in_subdomain(self, engine) -> None:
        result = engine.analyze("https://paypal.secure-verify.xyz/login")
        assert "paypal" in result.brands_detected
        assert "subdomain" in result.brand_locations["paypal"]

    def test_token_in_path_is_low_risk(self, engine) -> None:
        result = engine.analyze("https://example.com/articles/whatsapp-privacy")
        assert "whatsapp" in result.brands_detected
        assert result.brand_locations["whatsapp"] == ["path"]
        # A brand name in an editorial path is only a weak signal.
        assert result.risk_level in ("low", "medium")
        assert result.risk_score < engine._high_threshold

    def test_token_in_query(self, engine) -> None:
        result = engine.analyze("https://example.com/r?target=microsoft-login")
        assert "microsoft" in result.brands_detected


# ---------------------------------------------------------------------------
# Official-domain mismatch
# ---------------------------------------------------------------------------

class TestOfficialDomainMismatch:
    def test_whatsapp_impersonation(self, engine) -> None:
        result = engine.analyze("https://edge-origin-whatsapp.com.cn/login")
        assert result.has_finding("official_domain_mismatch")
        assert result.official_brand is None
        assert result.risk_level in ("medium", "high")
        # Human-readable explanation present
        assert any("does not belong to the official" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Typosquatting
# ---------------------------------------------------------------------------

class TestTyposquatting:
    @pytest.mark.parametrize("url,brand", [
        ("https://paypa1.com", "paypal"),          # leet 1->l
        ("https://micros0ft.com", "microsoft"),    # leet 0->o
        ("https://arnazon.com", "amazon"),         # rn->m
        ("https://g00gle.com", "google"),          # double leet
        ("https://facbook.com", "facebook"),       # missing char
        ("https://whatsaap.com", "whatsapp"),      # repeated char
        ("https://gogle.com", "google"),           # missing char
        ("https://payypal.com", "paypal"),         # extra char
    ])
    def test_typosquats_detected(self, engine, url, brand) -> None:
        result = engine.analyze(url)
        assert result.has_finding("typosquatting"), url
        assert brand in result.brands_detected
        assert result.risk_level in ("medium", "high")

    def test_keyboard_slip_flagged(self, engine) -> None:
        # 'paypsl' -> 'a' replaced by adjacent 's'
        result = engine.analyze("https://paypsl.com")
        assert result.has_finding("typosquatting")

    def test_short_brand_not_overmatched(self, engine) -> None:
        # 'meta' is short; a distant unrelated word must not trigger typosquat.
        result = engine.analyze("https://database-tools.com")
        assert not result.has_finding("typosquatting")


# ---------------------------------------------------------------------------
# Homoglyph / Unicode spoofing
# ---------------------------------------------------------------------------

class TestHomoglyphs:
    @pytest.mark.parametrize("url", [
        "https://раypal.com",            # Cyrillic r,a -> paypal
        "https://gοοgle.com",            # Greek omicrons -> google
        "https://microsоft.com",              # Cyrillic o -> microsoft
    ])
    def test_homoglyph_detected(self, engine, url) -> None:
        result = engine.analyze(url)
        assert result.has_finding("homoglyph"), url
        assert result.risk_level == "high"
        assert any("look-alike" in r or "homoglyph" in r for r in result.reasons)

    def test_pure_ascii_not_homoglyph(self, engine) -> None:
        result = engine.analyze("https://paypal-support.com")
        assert not result.has_finding("homoglyph")

    def test_genuine_idn_not_flagged(self, engine) -> None:
        # A legitimate non-ASCII domain unrelated to any brand.
        result = engine.analyze("https://例え.テスト")
        assert not result.has_finding("homoglyph")


# ---------------------------------------------------------------------------
# Prefix / suffix abuse
# ---------------------------------------------------------------------------

class TestPrefixSuffix:
    @pytest.mark.parametrize("url", [
        "https://secure-google.com",
        "https://login-facebook.net",
        "https://verify-paypal.info",
        "https://apple-support.online",
        "https://microsoft-security.xyz",
        "https://nabil-bank-login.com",
    ])
    def test_affix_combinations(self, engine, url) -> None:
        result = engine.analyze(url)
        assert result.has_finding("misleading_affix"), url
        assert result.risk_level in ("medium", "high")


# ---------------------------------------------------------------------------
# Cloud-hosted impersonation
# ---------------------------------------------------------------------------

class TestCloudHosting:
    def test_cloud_provider_alone_is_not_malicious(self, engine) -> None:
        result = engine.analyze("https://my-portfolio.netlify.app/home")
        assert not result.has_finding("cloud_hosted_impersonation")
        assert result.risk_level in ("none", "low")

    def test_brand_on_cloud_with_credentials_is_suspicious(self, engine) -> None:
        result = engine.analyze(
            "https://paypal-verify.web.app/login?password=1"
        )
        assert result.has_finding("cloud_hosted_impersonation")
        assert result.risk_level == "high"

    def test_brand_on_cloud_without_credentials_lower(self, engine) -> None:
        # Brand token on cloud but no login/credential context.
        result = engine.analyze("https://paypal-news.web.app/blog")
        assert not result.has_finding("cloud_hosted_impersonation")


# ---------------------------------------------------------------------------
# Brand risk score & external context
# ---------------------------------------------------------------------------

class TestBrandRiskScore:
    def test_context_amplifies_score(self, engine) -> None:
        url = "https://secure-login-paypal.com/verify"
        base = engine.analyze(url).risk_score
        amplified = engine.analyze(url, context={
            "domain_age_days": 3,
            "ssl_valid": False,
            "whois_private": True,
            "suspicious_keyword_count": 3,
        }).risk_score
        assert amplified > base

    def test_context_does_not_amplify_clean_domain(self, engine) -> None:
        result = engine.analyze("https://www.microsoft.com", context={
            "domain_age_days": 1, "ssl_valid": False,
        })
        assert result.risk_score == 0.0

    def test_score_is_bounded(self, engine) -> None:
        result = engine.analyze("https://secure-verify-paypal-login.web.app/password", context={
            "domain_age_days": 1, "ssl_valid": False,
            "whois_private": True, "suspicious_keyword_count": 9,
        })
        assert 0.0 <= result.risk_score <= 1.0


# ---------------------------------------------------------------------------
# False positives / false negatives
# ---------------------------------------------------------------------------

class TestFalsePositivesNegatives:
    @pytest.mark.parametrize("url", [
        "https://www.wikipedia.org",
        "https://news.ycombinator.com",
        "https://stackoverflow.com/questions/12345",
        "https://en.wikipedia.org/wiki/Phishing",
        "https://www.python.org/downloads",
    ])
    def test_unrelated_domains_not_flagged(self, engine, url) -> None:
        result = engine.analyze(url)
        assert result.risk_level in ("none", "low")
        assert not result.has_finding("typosquatting")
        assert not result.has_finding("homoglyph")

    @pytest.mark.parametrize("url", [
        "https://paypal-secure-login.com/account/verify",
        "https://appleid-icloud-verify.com",
        "https://microsoft-account-security.net/login",
    ])
    def test_obvious_impersonation_caught(self, engine, url) -> None:
        result = engine.analyze(url)
        assert result.risk_level in ("medium", "high")
        assert result.findings


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------

class TestExplainability:
    def test_reasons_are_human_readable(self, engine) -> None:
        result = engine.analyze("https://edge-origin-whatsapp.com.cn/login")
        assert result.reasons
        joined = " ".join(result.reasons)
        assert "WhatsApp" in joined
        assert "impersonation" in joined.lower()

    def test_result_is_json_serialisable(self, engine) -> None:
        import json
        result = engine.analyze("https://paypa1.com/login")
        payload = result.to_dict()
        assert json.dumps(payload)
        assert "findings" in payload and "risk_score" in payload


# ---------------------------------------------------------------------------
# Configuration & dependency injection
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_brand_database_loaded(self, engine) -> None:
        assert engine.brand_count >= 40
        assert engine.is_official_domain("microsoft.com") == "microsoft"
        assert engine.is_official_domain("khalti.com") == "khalti"
        assert engine.is_official_domain("evil.com") is None

    def test_custom_cloud_detector_injection(self) -> None:
        from src.reputation.cloud_hosting import CloudHostingDetector
        eng = BrandIntelligenceEngine(cloud_detector=CloudHostingDetector())
        assert eng.analyze("https://microsoft.com").is_official_domain

    def test_never_raises_on_garbage(self, engine) -> None:
        for junk in ("", "not a url", "http://", "ftp://x", "://///"):
            result = engine.analyze(junk)
            assert isinstance(result, BrandIntelligenceResult)


# ---------------------------------------------------------------------------
# Rule Engine integration (additive, backward compatible)
# ---------------------------------------------------------------------------

class TestRuleEngineIntegration:
    @pytest.fixture(scope="class")
    def rule_engine(self):
        from src.rules.rule_engine import RuleEngine
        return RuleEngine()

    @pytest.fixture(scope="class")
    def parser(self):
        from src.parser.url_parser import URLParser
        return URLParser()

    def _evaluate(self, rule_engine, parser, url):
        from src.feature_engineering.pipeline import FeaturePipeline
        parsed = parser.parse(url)
        features = FeaturePipeline().extract(url)
        return rule_engine.evaluate(parsed, features)

    def test_brand_rules_fire(self, rule_engine, parser) -> None:
        result = self._evaluate(
            rule_engine, parser, "http://edge-origin-whatsapp.com.cn/login"
        )
        rule_ids = {f.rule_id for f in result.findings}
        assert "bi_official_domain_mismatch" in rule_ids

    def test_typosquat_rule_fires(self, rule_engine, parser) -> None:
        result = self._evaluate(rule_engine, parser, "https://paypa1.com/login")
        rule_ids = {f.rule_id for f in result.findings}
        assert "bi_typosquatting" in rule_ids

    def test_unicode_spoofing_rule_fires(self, rule_engine, parser) -> None:
        result = self._evaluate(
            rule_engine, parser, "https://раypal.com/login"
        )
        rule_ids = {f.rule_id for f in result.findings}
        assert "bi_unicode_spoofing" in rule_ids

    def test_fake_login_rule_fires(self, rule_engine, parser) -> None:
        result = self._evaluate(
            rule_engine, parser, "https://secure-login-paypal.com/verify?password=1"
        )
        rule_ids = {f.rule_id for f in result.findings}
        assert "bi_fake_login_infrastructure" in rule_ids

    def test_cloud_hosted_rule_fires(self, rule_engine, parser) -> None:
        result = self._evaluate(
            rule_engine, parser, "https://paypal-verify.web.app/login?password=1"
        )
        rule_ids = {f.rule_id for f in result.findings}
        assert "bi_cloud_hosted_impersonation" in rule_ids

    def test_official_domain_no_brand_rules(self, rule_engine, parser) -> None:
        result = self._evaluate(rule_engine, parser, "https://login.microsoft.com/x")
        rule_ids = {f.rule_id for f in result.findings}
        assert not any(rid.startswith("bi_") for rid in rule_ids)

    def test_rule_engine_without_brand_engine_still_works(self, parser) -> None:
        """Injecting a disabled brand engine must not break evaluation."""
        from src.rules.rule_engine import RuleEngine
        from src.feature_engineering.pipeline import FeaturePipeline

        class _Disabled:
            def analyze(self, *a, **k):
                raise RuntimeError("brand engine offline")

        engine = RuleEngine(brand_engine=_Disabled())
        parsed = parser.parse("https://paypa1.com/login")
        features = FeaturePipeline().extract("https://paypa1.com/login")
        # Should not raise despite the failing brand engine.
        result = engine.evaluate(parsed, features)
        assert result is not None


# ---------------------------------------------------------------------------
# Brand Conflict Detection (trusted domain references a DIFFERENT brand)
# ---------------------------------------------------------------------------

class TestBrandConflict:
    """A trusted registrable domain (official brand OR cloud provider) that
    references a *different* protected brand is a Brand Conflict."""

    def test_conflict_official_domain_brand_in_path(self, engine) -> None:
        result = engine.analyze("https://github.io/microsoft-login")
        assert result.is_official_domain is True          # github.io is official
        assert result.official_brand == "github"
        assert result.has_finding("brand_conflict")
        assert "microsoft" in result.brands_detected
        assert result.risk_level in ("medium", "high")
        assert result.risk_score > 0.0

    def test_conflict_paypal_on_github(self, engine) -> None:
        result = engine.analyze("https://github.io/paypal-login")
        assert result.has_finding("brand_conflict")
        assert "paypal" in result.brands_detected

    def test_conflict_in_hostname_subdomain(self, engine) -> None:
        # A Microsoft-branded subdomain on an official GitHub domain.
        result = engine.analyze("https://microsoft-verify.github.io/account")
        assert result.is_official_domain is True
        assert result.has_finding("brand_conflict")
        conflict = next(
            f for f in result.findings if f.finding_type == "brand_conflict"
        )
        assert conflict.severity == "high"  # domain-level reference

    def test_conflict_in_query(self, engine) -> None:
        result = engine.analyze(
            "https://github.io/redirect?next=facebook-login"
        )
        assert result.has_finding("brand_conflict")
        assert "facebook" in result.brands_detected

    def test_conflict_cloud_hosted_firebase(self, engine) -> None:
        result = engine.analyze("https://firebaseapp.com/google-login")
        assert result.has_finding("brand_conflict")
        assert "google" in result.brands_detected
        assert result.risk_level in ("medium", "high")

    def test_conflict_cloud_hosted_netlify(self, engine) -> None:
        result = engine.analyze("https://myproj.netlify.app/facebook-auth")
        assert result.has_finding("brand_conflict")
        assert "facebook" in result.brands_detected

    def test_conflict_cloud_hosted_vercel_appleid(self, engine) -> None:
        result = engine.analyze("https://myproj.vercel.app/appleid")
        assert result.has_finding("brand_conflict")
        assert "apple" in result.brands_detected

    def test_conflict_is_explainable(self, engine) -> None:
        result = engine.analyze("https://github.io/microsoft-login")
        joined = " ".join(result.reasons)
        assert "Microsoft" in joined
        assert "GitHub" in joined
        assert "different trusted organisation" in joined.lower()
        assert "impersonation" in joined.lower() or "deceptive" in joined.lower()

    def test_conflict_does_not_force_phishing(self, engine) -> None:
        # Conflict raises risk but is not, by itself, a critical/definite verdict.
        result = engine.analyze("https://github.io/microsoft-login")
        conflict = next(
            f for f in result.findings if f.finding_type == "brand_conflict"
        )
        assert conflict.severity != "critical"

    # --- False-positive protection -----------------------------------------

    @pytest.mark.parametrize("url", [
        "https://github.com/login",
        "https://github.io",                       # owner brand only, no other
        "https://web.whatsapp.com",
        "https://support.apple.com/billing",
        "https://accounts.google.com/signin",
        "https://business.facebook.com/settings",
        "https://login.microsoft.com/oauth2",
        "https://outlook.office365.com/mail",      # microsoft alias on ms domain
    ])
    def test_no_conflict_for_same_brand(self, engine, url) -> None:
        result = engine.analyze(url)
        assert not result.has_finding("brand_conflict")

    def test_official_clean_domain_still_trusted(self, engine) -> None:
        result = engine.analyze("https://docs.google.com/document/d/abc")
        assert result.is_official_domain is True
        assert result.risk_level == "none"
        assert not result.findings

    def test_cloud_without_brand_not_conflict(self, engine) -> None:
        result = engine.analyze("https://my-portfolio.vercel.app/projects")
        assert not result.has_finding("brand_conflict")


class TestBrandConflictRuleEngine:
    """The conflict must surface as an additive Rule Engine finding."""

    @pytest.fixture(scope="class")
    def tools(self):
        from src.rules.rule_engine import RuleEngine
        from src.parser.url_parser import URLParser
        from src.feature_engineering.pipeline import FeaturePipeline
        return RuleEngine(), URLParser(), FeaturePipeline()

    def _eval(self, tools, url):
        engine, parser, pipeline = tools
        return engine.evaluate(parser.parse(url), pipeline.extract(url))

    def test_conflict_rule_fires(self, tools) -> None:
        result = self._eval(tools, "https://github.io/microsoft-login")
        ids = {f.rule_id for f in result.findings}
        assert "bi_brand_conflict" in ids
        # Raises the rule score but does not force a definite-phishing verdict.
        assert result.rule_score > 0
        conflict = next(
            f for f in result.findings if f.rule_id == "bi_brand_conflict"
        )
        assert conflict.severity != "critical"

    def test_cloud_conflict_rule_fires(self, tools) -> None:
        result = self._eval(tools, "https://firebaseapp.com/google-login")
        ids = {f.rule_id for f in result.findings}
        assert "bi_brand_conflict" in ids

    def test_official_clean_has_no_conflict_rule(self, tools) -> None:
        result = self._eval(tools, "https://github.com/login")
        ids = {f.rule_id for f in result.findings}
        assert "bi_brand_conflict" not in ids
