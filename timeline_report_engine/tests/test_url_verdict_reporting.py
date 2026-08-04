"""A URL submitted as evidence must produce a *usable* verdict in the report.

A bare "malicious" label is not an investigative finding. The report has to
name the domain and state the grounds — registrar, domain age, SPF/DMARC, SSL,
hosting and the model's plain-language reasons — because those are what an
investigator cites.

These tests are offline: they drive the adapter with a stub classifier so the
mapping from classifier output to report fields is pinned without depending on
a live WHOIS/DNS lookup or the ML model artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

from ciis_correlation.threat.ml_provider import (
    MLThreatIntelProvider,
    _registrable_domain,
)
from ciis_timeline_report.reporting.service import _url_host


@dataclass
class _StubResult:
    """Mimics the classifier's PredictionResult (only the fields we read)."""

    url: str
    prediction: str = "Phishing"
    confidence: float = 0.82
    risk_score: int = 82
    risk_level: str = "Critical"
    model_type: str = "xgboost"
    model_version: str = "4.0.0"
    trust_score: int = 10
    brand_detected: str = "telegram"
    official_domain: bool = False
    ssl_status: str = "VALID"
    reasons: List[str] = field(default_factory=lambda: ["Brand impersonation."])
    negative_indicators: List[str] = field(default_factory=lambda: ["Young domain"])
    positive_indicators: List[str] = field(default_factory=lambda: ["Valid SSL"])
    # Flat, connector-prefixed — the real shape, not a nested mapping.
    threat_intelligence: Dict[str, Any] = field(
        default_factory=lambda: {
            "whois_success": True,
            "whois_registrar": "Spaceship, Inc.",
            "whois_domain_age_days": 42,
            "dns_success": True,
            "dns_has_spf": False,
            "dns_has_dmarc": False,
            "ssl_success": True,
            "ssl_days_until_expiry": 51,
            "geoip_success": True,
            "geoip_asn_org": "Cloudflare, Inc.",
            "geoip_country": "Canada",
            "geoip_ip_address": "104.21.88.199",
        }
    )


class _StubPredictor:
    def predict(self, url: str) -> _StubResult:
        return _StubResult(url=url)


@pytest.fixture()
def provider(tmp_path) -> MLThreatIntelProvider:
    p = MLThreatIntelProvider(tmp_path)
    p._predictor = _StubPredictor()  # bypass the lazy heavyweight load
    return p


def test_verdict_carries_the_facts_an_investigator_cites(provider):
    hit = provider.lookup("https://www.telegrammessage.com/login")

    assert hit["verdict"] == "malicious"
    assert hit["risk_score"] == 82
    # The domain, not just the full URL — this is what goes in the report.
    assert hit["domain"] == "www.telegrammessage.com"
    assert hit["registrar"] == "Spaceship, Inc."
    assert hit["domain_age_days"] == 42
    assert hit["spf_present"] is False and hit["dmarc_present"] is False
    assert hit["ssl_status"] == "VALID" and hit["ssl_days_left"] == 51
    assert hit["hosting"] == "Cloudflare, Inc., Canada"
    assert hit["ip_address"] == "104.21.88.199"
    assert hit["brand_impersonated"] == "telegram"
    assert hit["official_domain"] is False
    assert hit["reasons"] and hit["threat_signals"] and hit["trust_signals"]


def test_failed_lookups_are_omitted_not_reported_as_zero(provider):
    """An offline analysis must not claim a domain is 0 days old."""
    result = _StubResult(url="http://x.top")
    result.threat_intelligence = {
        "whois_success": False,
        "dns_success": False,
        "ssl_success": False,
        "geoip_success": False,
    }
    provider._predictor.predict = lambda url: result  # type: ignore[method-assign]
    provider._classify.cache_clear()

    hit = provider.lookup("http://x.top")

    assert hit["verdict"] == "malicious"          # the verdict still stands
    for absent in ("registrar", "domain_age_days", "spf_present",
                   "dmarc_present", "ssl_days_left", "hosting", "ip_address"):
        assert absent not in hit, f"{absent} must be omitted, not guessed"


def test_non_urls_are_not_classified(provider):
    assert provider.lookup("9812345678") is None
    assert provider.lookup("victim@example.com") is None
    assert provider.lookup("") is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://www.x.top/login?id=9", "www.x.top"),
        ("http://user:pw@x.top:8080/a", "x.top"),
        ("x.top", "x.top"),
        ("HTTPS://X.TOP/", "x.top"),
    ],
)
def test_host_extraction_agrees_across_modules(value, expected):
    """The adapter and the report de-duper must agree on what a host is.

    They are separate helpers (different layers); if they disagreed, a site
    could be de-duplicated under one name and reported under another.
    """
    assert _url_host(value) == expected
    assert _registrable_domain(value) == expected
