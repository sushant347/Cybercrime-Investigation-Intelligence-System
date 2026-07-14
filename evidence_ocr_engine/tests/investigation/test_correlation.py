"""Module 1 tests - Advanced Evidence Correlation Engine."""

from __future__ import annotations

import pytest

from backend.modules.investigation.correlation.service import CorrelationService

from .conftest import CASE


@pytest.fixture()
def service(icfg, data, repo, audit):
    return CorrelationService(icfg, data, repo, audit)


def _pair(analysis, a, b):
    for pair in analysis.pairs:
        if {pair.evidence_a, pair.evidence_b} == {a, b}:
            return pair
    raise AssertionError(f"pair {a}-{b} missing")


def test_strong_pair_from_shared_wallet_phone_device(service):
    analysis = service.analyze_case(CASE, persist=False)
    ab = _pair(analysis, "EVID_A", "EVID_B")
    factors = {f.factor for f in ab.factors}
    assert {"phones", "wallets", "device_metadata", "timeline_proximity"} <= factors
    assert ab.relationship_strength in {"STRONG", "VERY_STRONG"}
    assert ab.correlation_confidence > 0.7
    # explainability contract
    assert "9812345678" in " ".join(
        v for f in ab.factors for v in f.supporting_evidence
    )
    assert ab.explanation and "EVID_A" in ab.explanation
    assert len(ab.correlation_reasons) == len(ab.factors)


def test_threat_intel_and_domain_link(service):
    analysis = service.analyze_case(CASE, persist=False)
    ac = _pair(analysis, "EVID_A", "EVID_C")
    factors = {f.factor for f in ac.factors}
    assert "domains" in factors
    assert "threat_intelligence" in factors
    assert ac.relationship_strength in {"MEDIUM", "STRONG", "VERY_STRONG"}


def test_unrelated_evidence_scores_low(service):
    analysis = service.analyze_case(CASE, persist=False)
    ad = _pair(analysis, "EVID_A", "EVID_D")
    assert ad.relationship_strength in {"NO_RELATIONSHIP", "WEAK"}
    # even 'no relationship' must carry an explanation
    assert ad.explanation


def test_ordering_distribution_and_persistence(service, icfg, repo):
    analysis = service.analyze_case(CASE)
    confidences = [p.correlation_confidence for p in analysis.pairs]
    assert confidences == sorted(confidences, reverse=True)
    assert analysis.pair_count == 6  # C(4,2)
    assert sum(analysis.strength_distribution.values()) == 6
    assert analysis.strongest_pair == "EVID_A|EVID_B"
    stored = repo.load_latest(CASE, icfg.correlation_report_name)
    assert stored is not None and stored["report"]["pair_count"] == 6
