"""Tests for sentence reconstruction and keyword / risk-signal analysis."""

from __future__ import annotations

from backend.modules.evidence.cleaning.entity_preserver import EntityPreserver
from backend.modules.evidence.cleaning.keyword_analyzer import KeywordAnalyzer
from backend.modules.evidence.cleaning.sentence_reconstructor import (
    SentenceReconstructor,
)

# -------------------------------------------------------------- reconstruction


def test_broken_sentence_merged() -> None:
    text = "Verify your\naccount now"
    merged, ops = SentenceReconstructor().reconstruct(text)
    assert merged == "Verify your account now"
    assert ops == ["lines_merged(1)"]


def test_terminated_lines_not_merged() -> None:
    text = "Your account is suspended.\nverify immediately"
    merged, _ = SentenceReconstructor().reconstruct(text)
    assert "\n" in merged


def test_paragraph_boundaries_respected() -> None:
    text = "First paragraph line\n\nsecond paragraph line"
    merged, _ = SentenceReconstructor().reconstruct(text)
    assert merged == "First paragraph line\n\nsecond paragraph line"


def test_entity_lines_never_merged() -> None:
    """A standalone URL line must stay standalone (spec: never merge URLs)."""
    preserver = EntityPreserver()
    protected = preserver.protect("Click the link below\nhttps://scam.example/verify\nto continue")
    merged, _ = SentenceReconstructor().reconstruct(protected.text)
    restored = preserver.restore(merged, protected)
    assert "https://scam.example/verify" in restored.splitlines()


def test_heading_labels_keep_their_line() -> None:
    text = "Subject:\nyour parcel is held"
    merged, _ = SentenceReconstructor().reconstruct(text)
    assert merged.splitlines()[0] == "Subject:"


# -------------------------------------------------------------------- keywords


def test_keyword_frequency_counts() -> None:
    report = KeywordAnalyzer().analyze(
        "Verify your account. Verification code (OTP) sent. Bank asked to verify KYC."
    )
    assert report.keyword_frequency["verify"] == 3  # verify x2 + verification
    assert report.keyword_frequency["otp"] == 1
    assert report.keyword_frequency["bank"] == 1
    assert report.keyword_frequency["kyc"] == 1


def test_risk_signal_categories() -> None:
    report = KeywordAnalyzer().analyze(
        "URGENT: account suspended! Send money for the lottery prize. "
        "Share your OTP and PIN or police will take legal action."
    )
    assert report.risk_signals["urgency"] >= 2      # urgent + suspended
    assert report.risk_signals["financial"] >= 3    # money + lottery + prize
    assert report.risk_signals["credential"] >= 3   # account + otp + pin
    assert report.risk_signals["threat"] >= 1       # police / legal action


def test_bilingual_keywords_counted_not_translated() -> None:
    report = KeywordAnalyzer().analyze("पैसा पठाउनुहोस् र puraskar linus, चिठ्ठा!")
    assert report.keyword_frequency["money"] >= 1     # पैसा
    assert report.keyword_frequency["prize"] >= 1     # puraskar
    assert report.keyword_frequency["lottery"] >= 1   # चिठ्ठा


def test_clean_text_has_no_signals() -> None:
    report = KeywordAnalyzer().analyze("The weather in Kathmandu is pleasant today.")
    assert report.total_hits == 0
    assert all(count == 0 for count in report.risk_signals.values())
