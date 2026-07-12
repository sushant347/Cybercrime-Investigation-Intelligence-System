"""Offline tests for the Threat Reputation Engine (no network required)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.reputation import (
    BlacklistEngine,
    OpenPhishConnector,
    ReputationEngine,
    TTLCache,
    detect_ioc,
    normalize_url,
)
from src.reputation.domain_analysis import DomainAnalyzer

# ------------------------------------------------------------------ IOC types


@pytest.mark.parametrize("value,expected", [
    ("http://scam.top/login", "url"),
    ("www.scam.top", "url"),
    ("scam-site.com", "domain"),
    ("help@bank.com", "email"),
    ("192.168.1.7", "ipv4"),
    ("2001:db8::1", "ipv6"),
    ("d41d8cd98f00b204e9800998ecf8427e", "md5"),
    ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "sha1"),
    ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "sha256"),
    ("+977-9812345678", "phone"),
    ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "btc_wallet"),
    ("0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "eth_wallet"),
    ("@scam_helper", "telegram"),
    ("wa.me/9779812345678", "whatsapp"),
    ("???", "unknown"),
])
def test_ioc_detection(value: str, expected: str) -> None:
    assert detect_ioc(value).ioc_type == expected


# -------------------------------------------------------------- normalisation


def test_url_normalization_canonicalises_duplicates() -> None:
    a = normalize_url("HTTP://ScAm.Top:80/path/?b=2&a=1&a=1#frag")
    b = normalize_url("http://scam.top/path?a=1&b=2")
    assert a == b == "http://scam.top/path?a=1&b=2"


def test_idn_becomes_punycode() -> None:
    assert normalize_url("http://пример.com/x").startswith("http://xn--")


def test_normalizer_never_raises() -> None:
    assert normalize_url("::::not a url::::")  # best effort, no exception


# ------------------------------------------------------------ domain analysis


def test_typosquat_and_brand_impersonation() -> None:
    analyzer = DomainAnalyzer()
    typo = analyzer.analyze("paypa1.com")
    assert typo.typosquat_of == "paypal" and typo.risk_points > 0
    brand = analyzer.analyze("esewa-verify-login.top")
    assert brand.impersonated_brand == "esewa"
    assert brand.suspicious_tld
    assert any("brand" in reason for reason in brand.explanations)


def test_homograph_and_entropy_signals() -> None:
    analyzer = DomainAnalyzer()
    assert analyzer.analyze("pаypal.com").unicode_attack  # Cyrillic 'а'
    random_domain = analyzer.analyze("xk7qz9wv2mfp.com")
    assert random_domain.random_domain_score >= 0.6
    assert analyzer.analyze("google.com").risk_points == 0


# ------------------------------------------------------- blacklists (offline)


def test_blacklist_local_feed_and_lifecycle(tmp_path: Path) -> None:
    feed = tmp_path / "feed.txt"
    feed.write_text("# comment\nhttp://known-bad.top/login\n", encoding="utf-8")
    connector = OpenPhishConnector(local_feed=feed)
    hit = connector.check("http://KNOWN-BAD.top/login")
    assert hit.available and hit.listed
    miss = connector.check("http://innocent.example/")
    assert miss.available and not miss.listed
    connector.disable()
    assert not connector.check("http://known-bad.top/login").available


def test_dead_feed_degrades_gracefully() -> None:
    class DeadConnector(OpenPhishConnector):
        feed_url = ""  # nothing to download, no local feed
    result = DeadConnector().check("http://x.example")
    assert not result.available and not result.listed  # never crashes


# -------------------------------------------------------------------- caching


def test_ttl_cache_expiry_and_lru() -> None:
    cache = TTLCache(max_entries=2, ttl_seconds=0.05)
    cache.set("a", 1)
    assert cache.get("a") == 1
    time.sleep(0.06)
    assert cache.get("a") is None          # expired
    cache.set("x", 1); cache.set("y", 2); cache.set("z", 3)
    assert cache.get("x") is None          # LRU evicted


# ------------------------------------------------------------------ engine


def _offline_engine(tmp_path: Path) -> ReputationEngine:
    feed = tmp_path / "feed.txt"
    feed.write_text("http://listed-bad.top/steal\n", encoding="utf-8")
    engine = BlacklistEngine(connectors=[OpenPhishConnector(local_feed=feed)])
    return ReputationEngine(blacklists=engine, intelligence=None)


def test_reputation_json_contract(tmp_path: Path) -> None:
    report = _offline_engine(tmp_path).analyze("http://esewa-verify-login.top/account")
    for key in ("indicator", "normalized", "ioc_type", "reputation_score",
                "reputation_level", "blacklists", "domain_analysis",
                "network_intelligence", "reasons", "positive_signals",
                "negative_signals", "recommendations", "sources_available",
                "sources_unavailable", "processing_time_ms"):
        assert key in report
    assert 0 <= report["reputation_score"] <= 100
    assert report["reputation_score"] < 60          # typosquat + bad TLD
    assert report["recommendations"]


def test_blacklisted_indicator_scores_hostile(tmp_path: Path) -> None:
    report = _offline_engine(tmp_path).analyze("http://listed-bad.top/steal")
    assert any(b["listed"] for b in report["blacklists"])
    assert report["reputation_score"] <= 40


def test_clean_domain_scores_high_and_is_cached(tmp_path: Path) -> None:
    engine = _offline_engine(tmp_path)
    first = engine.analyze("https://google.com/")
    assert first["reputation_score"] >= 85
    assert engine.analyze("https://google.com/") is first  # cache hit


def test_hash_and_wallet_iocs_return_partial_results(tmp_path: Path) -> None:
    engine = _offline_engine(tmp_path)
    for ioc in ("d41d8cd98f00b204e9800998ecf8427e",
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"):
        report = engine.analyze(ioc)
        assert report["ioc_type"] in ("md5", "btc_wallet")
        assert "reputation_score" in report  # never crashes on non-URL IOCs
        assert report["reputation_level"] == "unknown"  # honest: no source to score


# ------------------------------------------------------------- report generator


def test_report_generator_json_and_cli(tmp_path: Path) -> None:
    from src.reputation import ReportGenerator
    rep = _offline_engine(tmp_path).analyze("http://esewa-verify-login.top/account")
    report = ReportGenerator().build(
        indicator="http://esewa-verify-login.top/account",
        prediction={"prediction": "PHISHING", "risk_score": 88, "confidence": 0.94},
        reputation=rep,
        evidence_refs=["CASE_0001/EVID_00001"],
        investigator_notes="Reported by victim on 2026-07-07",
    )
    d = report.to_dict()
    for section in ("summary", "threat_reputation", "ml_prediction",
                    "threat_intelligence", "indicators", "positive_signals",
                    "negative_signals", "risk_factors", "recommendations",
                    "evidence_references", "investigator_notes"):
        assert section in d
    assert d["ml_prediction"]["prediction"] == "PHISHING"   # existing contract intact
    assert d["evidence_references"] == ["CASE_0001/EVID_00001"]
    cli = report.to_cli()
    assert "THREAT INTELLIGENCE REPORT" in cli
    assert "RECOMMENDATIONS" in cli


def test_report_without_prediction_is_backward_compatible(tmp_path: Path) -> None:
    from src.reputation import ReportGenerator
    rep = _offline_engine(tmp_path).analyze("https://google.com/")
    report = ReportGenerator().build(indicator="https://google.com/", reputation=rep)
    assert report.to_dict()["ml_prediction"] == {}  # prediction optional
    assert report.to_json()
