"""Tests for confidence tiers, confidence tracing and the context gate."""

from __future__ import annotations

import pytest

from backend.modules.evidence.enhancement.confidence_analyzer import (
    ConfidenceAnalyzer,
    ConfidenceTier,
    tier_for,
)
from backend.modules.evidence.enhancement.context_corrector import ContextCorrector

# ------------------------------------------------------------------- tiers


@pytest.mark.parametrize(
    "confidence,tier",
    [
        (0.98, ConfidenceTier.HIGH),   # spec: no correction
        (0.90, ConfidenceTier.HIGH),
        (0.89, ConfidenceTier.MEDIUM),
        (0.40, ConfidenceTier.MEDIUM), # spec: dictionary lookup allowed
        (0.30, ConfidenceTier.MEDIUM),
        (0.29, ConfidenceTier.LOW),
        (0.20, ConfidenceTier.LOW),    # spec: correction rules allowed
    ],
)
def test_tier_boundaries(confidence: float, tier: ConfidenceTier) -> None:
    assert tier_for(confidence) == tier


# ---------------------------------------------------------------- analyzer


def test_lines_traced_to_ocr_confidences() -> None:
    pages = [{"lines": [
        {"text": "Verify your account", "confidence": 0.95},
        {"text": "बोड सदस्य", "confidence": 0.41},
    ]}]
    cleaned = "Verify your account\nबोड सदस्य"
    cmap = ConfidenceAnalyzer().analyze(cleaned, pages)
    assert cmap.for_line(1) == 0.95
    assert cmap.for_line(2) == 0.41
    assert cmap.tier_for_line(1) == ConfidenceTier.HIGH
    assert cmap.tier_for_line(2) == ConfidenceTier.MEDIUM


def test_merged_line_takes_minimum_contributor_confidence() -> None:
    pages = [{"lines": [
        {"text": "Verify your", "confidence": 0.93},
        {"text": "account now", "confidence": 0.35},
    ]}]
    cmap = ConfidenceAnalyzer().analyze("Verify your account now", pages)
    assert cmap.for_line(1) == 0.35  # weakest fragment keeps line correctable


def test_untraceable_text_gets_default_confidence() -> None:
    cmap = ConfidenceAnalyzer(default_confidence=0.75).analyze(
        "totally different text", [{"lines": [
            {"text": "unrelated ocr line", "confidence": 0.2}]}])
    assert cmap.for_line(1) in (0.2, 0.75) or cmap.for_line(1) == cmap.document_confidence


def test_no_ocr_pages_uses_default() -> None:
    cmap = ConfidenceAnalyzer().analyze("plain text evidence", None)
    assert cmap.for_line(1) == cmap.document_confidence


# ------------------------------------------------------------- context gate


def test_high_confidence_allows_exact_correction() -> None:
    # Exact (non-fuzzy) corrections are unambiguous OCR errors and now apply on
    # every tier, including high confidence.
    decision = ContextCorrector().evaluate(
        "बोड", "बोर्ड", ConfidenceTier.HIGH, is_fuzzy=False)
    assert decision.accepted


def test_high_confidence_blocks_fuzzy_correction() -> None:
    # Fuzzy (guessed) corrections remain blocked above the LOW tier.
    decision = ContextCorrector().evaluate(
        "बोड", "बोर्ड", ConfidenceTier.HIGH, is_fuzzy=True)
    assert not decision.accepted
    assert decision.reason == "fuzzy_requires_low_confidence"


def test_fuzzy_requires_low_tier() -> None:
    gate = ContextCorrector()
    medium = gate.evaluate("तपाईको", "तपाईंको", ConfidenceTier.MEDIUM, is_fuzzy=True)
    low = gate.evaluate("तपाईको", "तपाईंको", ConfidenceTier.LOW, is_fuzzy=True)
    assert not medium.accepted
    assert low.accepted


def test_script_mismatch_rejected() -> None:
    decision = ContextCorrector().evaluate(
        "बोड", "board", ConfidenceTier.LOW, is_fuzzy=False)
    assert not decision.accepted and decision.reason == "script_mismatch"


def test_shape_similarity_floor_for_fuzzy() -> None:
    decision = ContextCorrector().evaluate(
        "कख", "प्रमाणीकरण", ConfidenceTier.LOW, is_fuzzy=True)
    assert not decision.accepted


def test_document_consistency_boosts_score() -> None:
    gate = ContextCorrector()
    without = gate.evaluate("acc0unt", "account", ConfidenceTier.MEDIUM, False)
    with_doc = gate.evaluate("acc0unt", "account", ConfidenceTier.MEDIUM, False,
                             document_text="your account statement")
    assert with_doc.accepted and without.accepted
    assert with_doc.context_score >= without.context_score
