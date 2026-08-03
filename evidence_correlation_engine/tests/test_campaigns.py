"""Module 3 tests - Scam Campaign Clustering Engine."""

from __future__ import annotations

import pytest

from ciis_correlation.campaigns.service import CampaignService
from ciis_correlation.correlation.service import CorrelationService

from .conftest import CASE


@pytest.fixture()
def analysis(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False)
    return CampaignService(icfg, data, repo, audit).cluster(CASE, correlation)


def test_campaign_members_and_unclustered(analysis):
    assert analysis.campaign_count == 1
    campaign = analysis.campaigns[0]
    assert set(campaign.members) == {"EVID_A", "EVID_B", "EVID_C"}
    assert analysis.unclustered_evidence == ["EVID_D"]
    assert campaign.campaign_id.startswith("CAMP_CASE_9001_")


def test_membership_explanations(analysis):
    campaign = analysis.campaigns[0]
    assert len(campaign.memberships) == 3
    for membership in campaign.memberships:
        assert membership.linked_via
        assert membership.membership_explanation
        assert "linked to" in membership.membership_explanation


def test_signature_and_shared_indicators(analysis):
    campaign = analysis.campaigns[0]
    assert any("esewa_ids:+9779812345678" == s or "phones:9812345678" == s
               for s in campaign.signature)
    assert campaign.shared_brands == ["esewa"]
    assert campaign.shared_domains == ["scam-bank.top"]
    assert campaign.timeline_start < campaign.timeline_end
    assert 0.0 < campaign.campaign_confidence <= 1.0
    assert campaign.summary


def test_persistence(icfg, repo, analysis):
    stored = repo.load_latest(CASE, icfg.campaign_report_name)
    assert stored is not None
    assert stored["report"]["campaign_count"] == 1
