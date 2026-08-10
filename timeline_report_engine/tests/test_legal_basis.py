"""Statutory-basis mapping: what engages a provision, and what must never happen.

The output of this module is quoted in a document that reaches a prosecutor, so
the tests care as much about what it refuses to say as about what it finds.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

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


# =========================================================== Tier 1 additions

def evidence_with_logos(evidence_id: str, detections) -> EvidenceContext:
    """Evidence carrying Phase-1 logo detections."""
    context = evidence(evidence_id)
    context.forensics = {"logo_detections": {"detections": [
        {"brand": brand, "detection_method": method, "confidence": 0.9}
        for brand, method in detections
    ]}}
    return context


def test_lockout_language_engages_damage_to_a_system(service):
    items = [evidence("E1", raw_text="he blocked me and I cannot access my wallet")]
    result = service.assess(CASE, items)
    assert "46" in sections(result)
    damage = next(p for p in result.provisions if p.section == "46")
    # Inferential trigger: the basis must not present it as a technical finding.
    assert "complainant's description, not a technical finding" in damage.basis


def test_losing_money_is_not_losing_access(service):
    """'scammed' and 'cheated' are s.52 territory, not s.46."""
    items = [evidence("E1", raw_text="I was scammed and cheated out of NPR 5000")]
    assert "46" not in sections(service.assess(CASE, items))


def test_a_campaign_engages_both_abetment_and_accomplice(service):
    """Distinct liabilities: procuring the offence vs assisting it."""
    class Campaign:
        campaign_id = "CAMP_1"
        members = ["E1", "E2"]

    class Campaigns:
        campaigns = [Campaign()]

    engaged = sections(service.assess(CASE, [evidence("E1")], campaigns=Campaigns()))
    assert {"53", "54"} <= engaged


def test_confiscation_follows_any_engaged_offence(service):
    items = [evidence("E1", [("esewa_ids", "98"), ("money", "NPR 1")])]
    result = service.assess(CASE, items)
    assert "56" in sections(result)
    conf = next(p for p in result.provisions if p.section == "56")
    assert "s.52" in conf.basis, "confiscation must name the offence it follows from"


def test_confiscation_does_not_fire_on_its_own(service):
    """It is consequential; with no offence engaged there is nothing to seize."""
    result = service.assess(CASE, [evidence("E1")])
    assert result.provisions == []


# =========================================================== Tier 2 additions

def test_a_detected_brand_mark_engages_the_trade_mark_act(service):
    items = [evidence_with_logos("E1", [("eSewa", "ocr_keyword")])]
    result = service.assess(CASE, items)
    tm = [p for p in result.provisions if "Trade Mark" in p.citation]
    assert tm, "brand detection should engage the Trade Mark Act"
    assert tm[0].section == "19"
    assert "eSewa" in tm[0].basis
    # Registration and authority are records to check, not things to assert.
    assert "matters of record to be confirmed" in tm[0].basis


def test_naming_a_brand_does_not_engage_copyright(service):
    """Using the mark is s.19; reproducing the artwork is the Copyright Act."""
    items = [evidence_with_logos("E1", [("eSewa", "ocr_keyword"),
                                        ("Khalti", "colour_signature")])]
    result = service.assess(CASE, items)
    assert not [p for p in result.provisions if "Copyright" in p.citation]


def test_template_matched_artwork_engages_copyright(service):
    """The rule is dormant on a default install, not broken.

    Template matching only runs once an investigator supplies reference logos,
    so no case in the shipped corpus can trigger this. Simulating the detection
    proves the rule works, rather than leaving it unverified until someone
    happens to add artwork.
    """
    items = [evidence_with_logos("E1", [("eSewa", "template_match")])]
    result = service.assess(CASE, items)
    cr = [p for p in result.provisions if "Copyright" in p.citation]
    assert cr, "a template match should engage the Copyright Act"
    assert cr[0].section == "27"
    assert "reproduced rather than merely named" in cr[0].basis


def test_provisions_from_different_statutes_cite_their_own_act(service):
    items = [
        evidence_with_logos("E1", [("eSewa", "template_match")]),
    ]
    items[0].entities = evidence("E1", [("esewa_ids", "98"),
                                        ("money", "NPR 1")]).entities
    result = service.assess(CASE, items)
    acts = {p.citation.split(", ", 1)[1] for p in result.provisions}
    assert len(acts) >= 2, "a case can engage more than one statute"
    for p in result.provisions:
        assert p.citation.startswith(f"Section {p.section},")


# =============================================== source-backed legal guidance

def test_primary_legal_source_and_manual_review_scope_are_reported(service):
    result = service.assess(CASE, [evidence("E1")])

    assert {item.section for item in result.manual_review_provisions} == {
        "44", "48", "57"
    }
    assert all(item.reason for item in result.manual_review_provisions)
    eta = next(source for source in result.sources if source.source_id == "eta_2063")
    assert eta.authority == "Nepal Law Commission"
    assert eta.url.startswith("https://lawcommission.gov.np/")
    assert set(eta.sha256) == set(eta.local_documents)


def test_reported_source_hashes_match_the_repository_pdfs(service):
    result = service.assess(
        CASE, [evidence("E1", [("bank_accounts", "00123456789")])]
    )
    corpus = Path(__file__).resolve().parents[2] / "samples" / "legal_corpus"

    for source in result.sources:
        for document in source.local_documents:
            actual = hashlib.sha256((corpus / document).read_bytes()).hexdigest()
            assert actual == source.sha256[document], document


def test_every_case_gets_electronic_record_preservation_guidance(service):
    result = service.assess(CASE, [evidence("E1"), evidence("E2")])
    preservation = [
        item for item in result.investigative_guidance
        if item.category == "evidence_preservation"
    ]

    assert len(preservation) == 1
    assert preservation[0].control_ids == ["4", "6"]
    assert preservation[0].evidence_ids == ["E1", "E2"]
    assert "not by itself a statutory digital signature" in (
        preservation[0].recommended_action
    )


def test_payment_evidence_adds_nrb_log_preservation_follow_up(service):
    items = [evidence("E1", [("esewa_ids", "9800000000")])]
    result = service.assess(CASE, items)

    logging = [
        item for item in result.investigative_guidance
        if set(item.control_ids) == {"83", "84", "85", "86"}
    ]
    assert len(logging) == 1
    assert logging[0].status == "investigative_follow_up"
    assert "Conditional" in logging[0].applicability
    assert logging[0].evidence_ids == ["E1"]
    assert any(source.source_id == "nrb_crg_2023" for source in result.sources)


def test_payment_and_credential_evidence_adds_nrb_mfa_follow_up(service):
    items = [
        evidence(
            "E1",
            [("bank_accounts", "00123456789"), ("otp", "123456")],
            raw_text="Share the OTP",
        )
    ]
    result = service.assess(CASE, items)

    authentication = [
        item for item in result.investigative_guidance
        if item.control_ids == ["71(d)"]
    ]
    assert len(authentication) == 1
    assert authentication[0].evidence_ids == ["E1"]


def test_credentials_without_payment_context_do_not_invoke_nrb_scope(service):
    result = service.assess(
        CASE, [evidence("E1", [("otp", "123456")], raw_text="Share the OTP")]
    )

    assert not [
        item for item in result.investigative_guidance
        if item.source_id == "nrb_crg_2023"
    ]
    assert not [source for source in result.sources if source.source_id == "nrb_crg_2023"]


def test_nrb_guidance_never_claims_a_compliance_failure(service):
    items = [
        evidence(
            "E1",
            [("bank_accounts", "00123456789"), ("otp", "123456")],
            raw_text="Share the OTP",
        )
    ]
    result = service.assess(CASE, items)
    prose = " ".join(
        f"{item.basis} {item.expectation} {item.recommended_action}"
        for item in result.investigative_guidance
    ).lower()

    for forbidden in ("non-compliant", "violated the guideline", "the bank failed"):
        assert forbidden not in prose


def test_section_46_uses_the_two_hundred_thousand_rupee_penalty(service):
    result = service.assess(
        CASE, [evidence("E1", raw_text="I was locked out and cannot access it")]
    )
    section_46 = next(item for item in result.provisions if item.section == "46")
    assert "two hundred thousand" in section_46.penalty
