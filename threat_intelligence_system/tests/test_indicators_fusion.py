"""Offline tests for Threat Indicators (Feature 8) and Confidence Fusion
(Feature 9). No network required."""

from __future__ import annotations

from pathlib import Path

from src.reputation import (
    BlacklistEngine,
    ConfidenceFusion,
    IndicatorGenerator,
    OpenPhishConnector,
    ReportGenerator,
    ReputationEngine,
)


def _engine(tmp_path: Path) -> ReputationEngine:
    feed = tmp_path / "feed.txt"
    feed.write_text("http://listed-bad.top/steal\n", encoding="utf-8")
    return ReputationEngine(
        blacklists=BlacklistEngine(connectors=[OpenPhishConnector(local_feed=feed)]),
        intelligence=None)


# ------------------------------------------------------------- indicators


def test_indicators_generated_for_impersonation(tmp_path: Path) -> None:
    rep = _engine(tmp_path).analyze("http://esewa-verify-login.top/account")
    assert "indicators" in rep                       # append-only engine key
    names = {i["name"] for i in rep["indicators"]}
    assert "Brand Impersonation" in names
    assert "Suspicious Hosting Zone" in names
    for ind in rep["indicators"]:
        assert ind["severity"] in ("critical", "high", "medium", "low", "info")
        assert 0.0 <= ind["confidence"] <= 1.0
        assert ind["reason"] and ind["recommendation"]


def test_indicators_severity_sorted(tmp_path: Path) -> None:
    rep = _engine(tmp_path).analyze("http://esewa-verify-login.top/account")
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    severities = [rank[i["severity"]] for i in rep["indicators"]]
    assert severities == sorted(severities, reverse=True)


def test_blacklist_indicator_is_critical(tmp_path: Path) -> None:
    rep = _engine(tmp_path).analyze("http://listed-bad.top/steal")
    critical = [i for i in rep["indicators"] if i["name"] == "Community Blacklist Hit"]
    assert critical and critical[0]["severity"] == "critical"


def test_intel_indicators_from_schema(tmp_path: Path) -> None:
    intel = {"whois": {"domain_age_days": 5}, "ssl": {"ssl_valid": False},
             "dns": {"has_spf": False, "has_dmarc": False}}
    indicators = IndicatorGenerator().generate({"network_intelligence": intel})
    names = {i["name"] for i in indicators}
    assert "Newly Registered Domain" in names
    assert "Expired or Invalid SSL" in names
    assert "Missing SPF" in names and "Missing DMARC" in names


def test_clean_domain_has_no_indicators(tmp_path: Path) -> None:
    rep = _engine(tmp_path).analyze("https://google.com/")
    assert rep["indicators"] == []


# --------------------------------------------------------------- fusion


def test_fusion_weight_normalised_over_available_sources() -> None:
    result = ConfidenceFusion().fuse(
        ml_threat_probability=0.9,
        reputation={"reputation_score": 20, "blacklists": [
            {"source": "openphish", "available": True, "listed": True}],
            "domain_analysis": {"risk_points": 45}},
    )
    assert 0 <= result.overall_threat_confidence <= 100
    assert result.overall_threat_confidence >= 70          # strong agreement
    weights = sum(c["weight"] for c in result.contributions)
    assert abs(weights - 1.0) < 1e-6                        # renormalised to 1
    assert "ml" in result.sources_used and "blacklist" in result.sources_used
    assert result.explanation


def test_fusion_degrades_with_missing_sources() -> None:
    only_ml = ConfidenceFusion().fuse(ml_threat_probability=0.8)
    assert only_ml.sources_used == ["ml"]
    assert only_ml.overall_threat_confidence == 80         # single source == its value
    assert ConfidenceFusion().fuse().overall_threat_confidence == 0  # nothing available


def test_fusion_benign_agreement_low_confidence() -> None:
    result = ConfidenceFusion().fuse(
        ml_threat_probability=0.05,
        reputation={"reputation_score": 96, "blacklists": [
            {"source": "openphish", "available": True, "listed": False}],
            "domain_analysis": {"risk_points": 0}})
    assert result.overall_threat_confidence <= 20


# --------------------------------------------------- report integration


def test_report_includes_indicators_and_confidence(tmp_path: Path) -> None:
    rep = _engine(tmp_path).analyze("http://esewa-verify-login.top/account")
    report = ReportGenerator().build(
        indicator="http://esewa-verify-login.top/account",
        prediction={"prediction": "PHISHING", "confidence": 0.94, "risk_score": 88},
        reputation=rep, evidence_refs=["CASE_0001/EVID_00001"])
    d = report.to_dict()
    assert d["threat_indicators"]                          # populated
    fusion = d["overall_threat_confidence"]
    assert 0 <= fusion["overall_threat_confidence"] <= 100
    assert fusion["explanation"]
    assert "ml" in fusion["sources_used"]
    cli = report.to_cli()
    assert "OVERALL THREAT CONFIDENCE" in cli
    assert "THREAT INDICATORS" in cli


def test_report_backward_compatible_keys_unchanged(tmp_path: Path) -> None:
    """All previously existing report keys remain present (append-only)."""
    rep = _engine(tmp_path).analyze("https://google.com/")
    d = ReportGenerator().build(indicator="https://google.com/", reputation=rep).to_dict()
    for legacy in ("summary", "threat_reputation", "ml_prediction",
                   "threat_intelligence", "indicators", "positive_signals",
                   "negative_signals", "risk_factors", "recommendations",
                   "evidence_references", "investigator_notes"):
        assert legacy in d
