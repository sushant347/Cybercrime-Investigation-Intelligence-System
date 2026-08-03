"""Module 4 tests - Suspect Confidence Engine."""

from __future__ import annotations

import pytest

from ciis_correlation.correlation.service import CorrelationService
from ciis_correlation.suspects.service import SuspectService

from .conftest import CASE


@pytest.fixture()
def assessment(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False)
    return SuspectService(icfg, data, repo, audit).assess(CASE, correlation)


def test_identity_anchors_found(assessment):
    anchors = {(s.identity_type, s.identity_value) for s in assessment.suspects}
    assert ("phones", "9812345678") in anchors
    assert ("esewa_ids", "+9779812345678") in anchors
    assert ("emails", "victim@example.com") in anchors


def test_wallet_outranks_lone_email(assessment):
    by_value = {s.identity_value: s for s in assessment.suspects}
    wallet = by_value["+9779812345678"]
    email = by_value["victim@example.com"]
    assert wallet.confidence_score > email.confidence_score
    assert wallet.evidence_count == 2
    assert wallet.evidence_ids == ["EVID_A", "EVID_B"]


def test_threat_flag_via_cooccurrence(assessment):
    wallet = next(s for s in assessment.suspects
                  if s.identity_value == "+9779812345678")
    assert wallet.threat_flagged  # co-occurs with scam-bank.top in EVID_A


def test_explainability_contract(assessment):
    for suspect in assessment.suspects:
        assert len(suspect.components) == 6
        assert abs(sum(c.weight for c in suspect.components) - 1.0) < 1e-6
        assert all(c.explanation for c in suspect.components)
        assert suspect.explanation
        assert 0.0 <= suspect.confidence_score <= 100.0
        assert suspect.confidence_level and suspect.risk_level
    assert assessment.top_suspect == assessment.suspects[0].suspect_id
    assert "no machine learning" in assessment.methodology.lower()


def test_persistence(icfg, repo, assessment):
    stored = repo.load_latest(CASE, icfg.suspect_report_name)
    assert stored is not None
    assert stored["report"]["suspect_count"] == assessment.suspect_count
