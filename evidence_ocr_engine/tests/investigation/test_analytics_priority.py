"""Module 6 + Module 8 tests - Analytics and Case Prioritization."""

from __future__ import annotations

import pytest

from backend.modules.investigation.analytics.service import AnalyticsService
from backend.modules.investigation.campaigns.service import CampaignService
from backend.modules.investigation.correlation.service import CorrelationService
from backend.modules.investigation.prioritization.service import PrioritizationService
from backend.modules.investigation.timeline.service import TimelineService

from .conftest import CASE


@pytest.fixture()
def bundle(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False)
    campaigns = CampaignService(icfg, data, repo, audit).cluster(
        CASE, correlation, persist=False)
    timeline = TimelineService(icfg, data, repo, audit).analyze(
        CASE, persist=False)
    analytics = AnalyticsService(icfg, data, repo, audit).generate(
        CASE, None, correlation, campaigns, timeline)
    return correlation, campaigns, timeline, analytics


def test_entity_and_quality_statistics(bundle):
    _, _, _, analytics = bundle
    assert analytics.evidence_count == 4
    assert analytics.entity_statistics["phones"] == 2
    assert analytics.entity_statistics["wallets"] == 2
    top_phones = analytics.top_entities["phones"]
    assert top_phones[0].value == "9812345678" and top_phones[0].count == 2
    quality = analytics.evidence_quality_statistics
    assert quality["mean_evidence_confidence"] == pytest.approx(73.75)
    assert quality["max_forgery_score"] == 65.0
    assert quality["hash_verified_count"] == 4.0


def test_threat_brand_device_statistics(bundle):
    _, _, _, analytics = bundle
    threat = analytics.threat_statistics
    assert threat["intel_available"] == 1.0
    assert threat["evidence_with_threats"] == 2.0  # EVID_A, EVID_C
    assert threat["threat_evidence_ratio"] == 0.5
    assert analytics.brand_statistics[0].value == "eSewa"
    assert analytics.device_statistics[0].value == "Samsung SM-A505"
    assert analytics.campaign_statistics["campaign_count"] == 1.0


def test_three_analytics_files_persisted(icfg, repo, bundle):
    for name in (icfg.analytics_report_name, icfg.case_statistics_name,
                 icfg.entity_statistics_name):
        assert repo.load_latest(CASE, name) is not None, name


def test_priority_score_and_indicators(icfg, repo, audit, bundle):
    correlation, campaigns, timeline, analytics = bundle
    priority = PrioritizationService(icfg, repo, audit).prioritize(
        CASE, analytics=analytics, correlation=correlation,
        campaigns=campaigns, timeline=timeline)
    assert 0.0 <= priority.priority_score <= 100.0
    assert priority.priority_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    # The seeded case has threats, a campaign, forgery 65 and critical events.
    assert priority.priority_level in {"HIGH", "CRITICAL"}
    indicators = " ".join(priority.high_risk_indicators)
    assert "threat-flagged" in indicators
    assert "tampering" in indicators
    assert "critical event" in indicators
    assert priority.investigation_recommendation
    assert priority.explanation
    assert repo.load_latest(CASE, icfg.priority_report_name) is not None


def test_priority_renormalises_when_inputs_missing(icfg, repo, audit):
    priority = PrioritizationService(icfg, repo, audit).prioritize(
        CASE, persist=False)
    available = [c for c in priority.components if c.available]
    assert len(available) == 0
    assert priority.priority_score == 0.0
    assert priority.priority_level == "LOW"
