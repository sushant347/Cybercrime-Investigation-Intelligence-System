"""Offline tests for cloud-hosting awareness (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.reputation import CloudHostingDetector
from src.reputation.cloud_hosting import CLOUD_PROVIDERS


@pytest.fixture(scope="module")
def detector() -> CloudHostingDetector:
    return CloudHostingDetector()


@pytest.mark.parametrize("url,provider", [
    ("https://myproject.github.io/portfolio", "GitHub Pages"),
    ("https://cool-site.netlify.app/", "Netlify"),
    ("https://demo.vercel.app/", "Vercel"),
    ("https://app.web.app/", "Firebase"),
    ("https://bucket.s3.amazonaws.com/file", "Amazon S3"),
    ("https://x.pages.dev/", "Cloudflare Pages"),
    ("https://data.blob.core.windows.net/c/o", "Azure Blob"),
    ("https://svc.onrender.com/", "Render"),
])
def test_provider_detection(detector, url: str, provider: str) -> None:
    result = detector.analyze(url)
    assert result.is_cloud_hosted and result.provider == provider


def test_non_cloud_url_not_flagged(detector) -> None:
    result = detector.analyze("https://example.com/login")
    assert not result.is_cloud_hosted
    assert not result.suspicious_context


def test_benign_cloud_site_is_not_suspicious(detector) -> None:
    # Cloud host with NO phishing signals -> benign, zero added risk.
    result = detector.analyze("https://myblog.netlify.app/posts/hello")
    assert result.is_cloud_hosted
    assert not result.suspicious_context
    assert result.risk_points == 0
    assert any("benign by itself" in r for r in result.reasons)


def test_cloud_with_login_and_brand_is_suspicious(detector) -> None:
    result = detector.analyze("https://paypal-login-verify.netlify.app/account/signin")
    assert result.is_cloud_hosted and result.suspicious_context
    assert result.risk_points > 0
    joined = " ".join(result.signals)
    assert "login" in joined and "paypal" in joined
    assert any("elevated suspicion" in r for r in result.reasons)


def test_risk_scales_with_signal_count(detector) -> None:
    one = detector.analyze("https://x.netlify.app/login")
    many = detector.analyze("https://paypal-bank-verify.netlify.app/login/otp")
    assert many.risk_points >= one.risk_points > 0


def test_reuses_domain_analysis_signals(detector) -> None:
    result = detector.analyze(
        "https://secure.vercel.app/x",
        domain_analysis={"impersonated_brand": "esewa", "subdomain_depth": 3})
    assert result.suspicious_context
    assert any("impersonation" in s for s in result.signals)
    assert any("subdomain" in s for s in result.signals)


def test_never_raises_on_bad_input(detector) -> None:
    for bad in ("", "not a url", "::::", "ftp://"):
        assert detector.analyze(bad).is_cloud_hosted in (True, False)


def test_provider_table_nonempty() -> None:
    assert len(CLOUD_PROVIDERS) >= 14  # required providers covered


# ------------------------------------------------------- engine integration


def test_reputation_engine_adds_cloud_block(tmp_path: Path) -> None:
    from src.reputation import BlacklistEngine, OpenPhishConnector, ReputationEngine
    feed = tmp_path / "feed.txt"
    feed.write_text("http://listed.top/x\n", encoding="utf-8")
    engine = ReputationEngine(
        blacklists=BlacklistEngine(connectors=[OpenPhishConnector(local_feed=feed)]),
        intelligence=None)

    phishing = engine.analyze("https://paypal-login.web.app/verify/signin")
    assert "cloud_hosting" in phishing                      # append-only key
    assert phishing["cloud_hosting"]["suspicious_context"]
    assert any(i["name"] == "Cloud Abuse" for i in phishing["indicators"])

    benign = engine.analyze("https://docs-guide.github.io/manual")
    assert benign["cloud_hosting"]["is_cloud_hosted"]
    assert not benign["cloud_hosting"]["suspicious_context"]
    assert benign["reputation_score"] >= 85                 # not penalised
    assert not any(i["name"] == "Cloud Abuse" for i in benign["indicators"])


def test_engine_backward_compatible_keys_intact(tmp_path: Path) -> None:
    """All previously existing reputation keys remain present."""
    from src.reputation import ReputationEngine
    rep = ReputationEngine(intelligence=None).analyze("https://example.com/")
    for legacy in ("indicator", "normalized", "ioc_type", "reputation_score",
                   "reputation_level", "blacklists", "domain_analysis",
                   "reasons", "recommendations", "indicators"):
        assert legacy in rep
