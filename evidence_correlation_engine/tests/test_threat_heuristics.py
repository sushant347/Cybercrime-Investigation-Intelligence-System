"""Rule-based threat intelligence and the provider chain.

These pin the behaviour that made the threat panel usable at all: a verdict is
produced without a model or a data file, official domains are never flagged,
and the chain keeps the most serious *explained* verdict rather than the first
one it happens to receive.
"""

from __future__ import annotations

import pytest

from ciis_correlation.threat.heuristics import (
    ChainedThreatIntelProvider,
    HeuristicThreatIntelProvider,
)


@pytest.fixture()
def heuristics() -> HeuristicThreatIntelProvider:
    return HeuristicThreatIntelProvider()


def test_provider_is_always_available(heuristics) -> None:
    """No model, no indicator file, no network - so it cannot be unavailable."""
    assert heuristics.available is True


def test_brand_impersonation_is_malicious(heuristics) -> None:
    hit = heuristics.lookup("https://esewa-cashback-offer.xyz/claim?ref=DSN2026")
    assert hit["verdict"] == "malicious"
    assert hit["brand_impersonated"] == "esewa"
    assert any("esewa" in r for r in hit["reasons"])
    assert hit["domain"] == "esewa-cashback-offer.xyz"


def test_official_domain_is_never_flagged(heuristics) -> None:
    for url in ("https://esewa.com.np/login", "https://web.khalti.com/",
                "https://www.facebook.com/some.page"):
        hit = heuristics.lookup(url)
        assert hit["verdict"] == "benign"
        assert hit["official_domain"] is True
        assert hit["brand_impersonated"] == ""


def test_neutral_domain_scores_zero(heuristics) -> None:
    hit = heuristics.lookup("example.com")
    assert hit["verdict"] == "benign"
    assert hit["risk_score"] == 0
    assert hit["threat_signals"] == []


def test_ip_host_and_lure_words_are_suspicious(heuristics) -> None:
    hit = heuristics.lookup("http://192.168.10.4/verify-kyc")
    assert hit["verdict"] in {"suspicious", "malicious"}
    assert any("IP address" in r for r in hit["reasons"])


def test_shortener_is_flagged_because_it_hides_the_destination(heuristics) -> None:
    hit = heuristics.lookup("https://bit.ly/3xAbCd")
    assert hit["verdict"] == "suspicious"


def test_non_indicator_values_are_ignored(heuristics) -> None:
    assert heuristics.lookup("") is None
    assert heuristics.lookup("just some text") is None


# ------------------------------------------------------------------- chaining


class _Stub:
    def __init__(self, name, verdict, available=True):
        self.source_name = name
        self._verdict = verdict
        self.available = available

    def lookup(self, value):
        return {"verdict": self._verdict, "source": self.source_name,
                "reasons": [f"{self.source_name} says {self._verdict}"]}

    def is_malicious(self, value):
        return self._verdict == "malicious"


def test_chain_prefers_the_most_serious_verdict() -> None:
    chain = ChainedThreatIntelProvider(_Stub("feed", "benign"),
                                       _Stub("rules", "malicious"))
    hit = chain.lookup("https://scam.top")
    assert hit["verdict"] == "malicious"
    assert hit["source"] == "rules"
    assert chain.is_malicious("https://scam.top") is True


def test_chain_breaks_ties_towards_the_earlier_provider() -> None:
    chain = ChainedThreatIntelProvider(_Stub("feed", "malicious"),
                                       _Stub("rules", "malicious"))
    assert chain.lookup("https://scam.top")["source"] == "feed"


def test_chain_skips_unavailable_and_failing_providers() -> None:
    class _Broken:
        source_name = "broken"
        available = True

        def lookup(self, value):
            raise RuntimeError("provider exploded")

    chain = ChainedThreatIntelProvider(
        _Stub("offline", "malicious", available=False),
        _Broken(),
        _Stub("rules", "suspicious"),
    )
    assert chain.lookup("https://scam.top")["verdict"] == "suspicious"
    assert "offline" not in chain.source_name
    assert chain.available is True


def test_chain_reports_unavailable_when_nothing_is_usable() -> None:
    chain = ChainedThreatIntelProvider(_Stub("offline", "malicious", available=False))
    assert chain.available is False
    assert chain.source_name == "unavailable"
    assert chain.lookup("https://scam.top") is None
