"""Module 5 tests - Timeline Intelligence Engine."""

from __future__ import annotations

import pytest

from ciis_timeline_report.timeline.service import TimelineService

from .conftest import CASE


@pytest.fixture()
def analysis(icfg, data, repo, audit):
    return TimelineService(icfg, data, repo, audit).analyze(CASE)


def test_chronological_integrity(analysis):
    timestamps = [e.timestamp for e in analysis.events]
    assert timestamps == sorted(timestamps)
    assert len(analysis.events) == 4


def test_stage_detection(analysis):
    stages = {s.stage for s in analysis.attack_stages}
    assert {"initial_contact", "social_engineering", "credential_theft",
            "financial_transaction", "post_attack"} <= stages
    financial = next(s for s in analysis.attack_stages
                     if s.stage == "financial_transaction")
    assert "EVID_B" in financial.evidence_ids
    assert financial.matched_keywords
    assert "EVID_B" in financial.explanation


def test_acquisition_only_fixture_does_not_invent_stage_order(analysis):
    assert analysis.stage_progression == []
    assert analysis.progression_consistent
    assert not bool(analysis.statistics["progression_assessable"])


def test_critical_events_from_entities(analysis):
    critical_ids = {e.evidence_id for e in analysis.critical_events}
    assert "EVID_B" in critical_ids  # otp + money + wallet entities
    event_b = next(e for e in analysis.critical_events
                   if e.evidence_id == "EVID_B")
    assert any("otp" in r for r in event_b.critical_reasons)


def test_milestones_summary_statistics(analysis, icfg, repo):
    # This synthetic fixture has upload timestamps only. Intake provenance may
    # be listed, but it must not create incident milestones or duration.
    assert analysis.milestones == []
    assert analysis.summary
    assert "no evidence-derived event times" in analysis.summary
    assert analysis.statistics["event_count"] == 4.0
    assert analysis.statistics["timeline_span_hours"] > 0
    assert analysis.statistics["event_time_span_hours"] == 0
    assert repo.load_latest(CASE, icfg.timeline_report_name) is not None
