"""Statutory-basis mapping: what engages a provision, and what must never happen.

The output of this module is quoted in a document that reaches a prosecutor, so
the tests care as much about what it refuses to say as about what it finds.
"""

from __future__ import annotations

import pytest

from ciis_correlation.core.data_access import EntityRecord, EvidenceContext

from ciis_timeline_report.legal.provisions import ASSESSMENT_CAVEAT
from ciis_timeline_report.legal.service import LegalBasisService

CASE = "CASE_LEGAL"


def evidence(evidence_id: str, entities=(), raw_text: str = "") -> EvidenceContext:
    return EvidenceContext(
        evidence_id=evidence_id,
        case_id=CASE,
        raw_text=raw_text,
        entities=[
            EntityRecord(case_id=CASE, evidence_id=evidence_id,
                         entity_type=t, value=v, normalized=v.lower())
            for t, v in entities
        ],
    )


@pytest.fixture()
def service(icfg):
    return LegalBasisService(icfg)


def sections(assessment) -> set:
    return {p.section for p in assessment.provisions}


# ------------------------------------------------------------------ s.52 fraud

def test_payment_rail_with_money_engages_computer_fraud(service):
    items = [evidence("E1", [("esewa_ids", "9800000000"), ("money", "NPR 5,000")])]
    result = service.assess(CASE, items)
    assert "52" in sections(result)
    fraud = next(p for p in result.provisions if p.section == "52")
    assert fraud.evidence_ids == ["E1"]
    # The basis must name the finding, not merely restate the offence.
    assert "payment identifier" in fraud.basis and "money value" in fraud.basis


def test_payment_rail_without_money_does_not_engage_fraud(service):
    """An account number alone is not evidence of a financial benefit."""
    items = [evidence("E1", [("esewa_ids", "9800000000")])]
    assert "52" not in sections(service.assess(CASE, items))


def test_money_without_a_payment_rail_does_not_engage_fraud(service):
    """A price in a screenshot is not evidence that money moved."""
    items = [evidence("E1", [("money", "NPR 5,000")])]
    assert "52" not in sections(service.assess(CASE, items))


# ------------------------------------------------------- s.47 illegal material

def test_flagged_indicator_with_web_address_engages_publication(service):
    class Analytics:
        threat_statistics = {"intel_available": True, "malicious_indicators": 2}

    items = [evidence("E1", [("domains", "scam-bank.top")])]
    result = service.assess(CASE, items, analytics=Analytics())
    assert "47" in sections(result)


def test_no_threat_intel_means_no_publication_finding(service):
    """Absent intel is not a clean bill of health, so nothing is claimed."""
    class Analytics:
        threat_statistics = {"intel_available": False, "malicious_indicators": 0}

    items = [evidence("E1", [("domains", "scam-bank.top")])]
    assert "47" not in sections(service.assess(CASE, items, analytics=Analytics()))


# ---------------------------------------------------- s.45 unauthorised access

def test_credential_words_in_the_text_engage_unauthorised_access(service):
    items = [evidence("E1", raw_text="Please share the OTP sent to your phone")]
    result = service.assess(CASE, items)
    assert "45" in sections(result)
    assert next(p for p in result.provisions if p.section == "45").evidence_ids == ["E1"]


def test_ordinary_scam_text_does_not_engage_unauthorised_access(service):
    """Urgency is not a credential; only naming a secret counts."""
    items = [evidence("E1", raw_text="URGENT: your account will be suspended today")]
    assert "45" not in sections(service.assess(CASE, items))


# ------------------------------------------------------------- s.53 / s.55

def test_campaign_of_two_or_more_engages_abetment(service):
    class Campaign:
        campaign_id = "CAMP_1"
        members = ["E1", "E2", "E3"]

    class Campaigns:
        campaigns = [Campaign()]

    result = service.assess(CASE, [evidence("E1")], campaigns=Campaigns())
    assert "53" in sections(result)


def test_cross_case_link_engages_the_extraterritorial_provision(service):
    class CrossCase:
        link_count = 1
        links = []

    result = service.assess(CASE, [evidence("E1")], cross_case=CrossCase())
    assert "55" in sections(result)


# ------------------------------------------------------------------ contracts

def test_nothing_engaged_is_not_reported_as_no_offence(service):
    """Silence must read as 'not assessed', never as exoneration."""
    result = service.assess(CASE, [evidence("E1")])
    assert result.provisions == []
    assert "not a conclusion that no offence occurred" in result.summary


def test_the_caveat_always_travels_with_the_assessment(service):
    items = [evidence("E1", [("esewa_ids", "98"), ("money", "NPR 1")])]
    assert service.assess(CASE, items).caveat == ASSESSMENT_CAVEAT


def test_no_provision_asserts_guilt(service):
    """The module reports engagement, never commission.

    Guards the one failure that would make the whole section inadmissible: a
    generated sentence that reads as a finding of guilt.
    """
    class Analytics:
        threat_statistics = {"intel_available": True, "malicious_indicators": 3}

    items = [
        evidence("E1", [("esewa_ids", "98"), ("money", "NPR 1"),
                        ("domains", "bad.top")], raw_text="send the otp"),
    ]
    result = service.assess(CASE, items, analytics=Analytics())
    assert result.provisions, "expected this fixture to engage something"

    prose = " ".join(
        [result.summary, result.caveat]
        + [f"{p.basis} {p.conduct}" for p in result.provisions]
    ).lower()
    for forbidden in ("is guilty", "has committed", "the suspect committed",
                      "proves that", "must be charged"):
        assert forbidden not in prose, forbidden


def test_a_failing_rule_does_not_lose_the_whole_section(service, monkeypatch):
    """One bad rule must not cost the officer the other four."""
    monkeypatch.setattr(
        LegalBasisService, "_computer_fraud",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    items = [evidence("E1", [("esewa_ids", "98"), ("money", "NPR 1")],
                      raw_text="send the otp")]
    result = service.assess(CASE, items)
    assert "52" not in sections(result)      # the broken rule
    assert "45" in sections(result)          # the others still ran


# ------------------------------------------------------- bilingual rendering

def test_the_act_is_named_in_nepali_for_a_nepali_filing(service):
    """A report filed in Nepal should name the instrument as law names it."""
    result = service.assess(CASE, [evidence("E1")])
    assert result.statute_nepali == "विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३"
    assert "authoritative" in result.language_note, (
        "the report must say which language text governs"
    )


def test_the_pdf_never_prints_unrenderable_devanagari():
    """Standard-14 fonts draw Devanagari as boxes, not as nothing.

    The Nepali title once printed as 'IIIIIIIII (IIIIIIIIIIII)' in the PDF,
    which on a legal document reads as corruption. The renderer must detect
    that and substitute text it can actually draw.
    """
    from ciis_timeline_report.reporting.pdf_renderer import renderable

    assert renderable("Electronic Transactions Act, 2063 (2008)")
    assert not renderable("विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३")
