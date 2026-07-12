"""Tests for line-level language detection (no translation, no models)."""

from __future__ import annotations

import pytest

from backend.modules.evidence.cleaning.language_detector import (
    HeuristicLanguageDetector,
)


@pytest.fixture()
def detector() -> HeuristicLanguageDetector:
    return HeuristicLanguageDetector()


@pytest.mark.parametrize(
    "line,expected",
    [
        ("Your account has been suspended, verify immediately.", "english"),
        ("Dear customer, unusual activity was detected.", "english"),
        ("तपाईंको खाता निलम्बित गरिएको छ।", "nepali_unicode"),
        ("पैसा पाउन Rs 2000 पठाउनुहोस्", "mixed"),           # Devanagari + Latin
        ("Tapai ko account verify garnus", "roman_nepali"),
        ("Esewa id ma paisa pathaunus", "roman_nepali"),
        ("OTP halnus", "roman_nepali"),                       # short imperative
        ("1234 5678 !!!", "unknown"),                         # no letters
        ("", "unknown"),
    ],
)
def test_line_detection(detector: HeuristicLanguageDetector, line: str, expected: str) -> None:
    assert detector.detect_line(line) == expected


def test_roman_nepali_sprinkled_in_english_is_mixed(detector) -> None:
    line = "Please send the payment today, paisa pathaunus via the given account"
    assert detector.detect_line(line) == "mixed"


def test_lines_are_numbered_from_one(detector) -> None:
    results = detector.detect_lines("Hello world\nतपाईंको खाता\nOTP halnus")
    assert [(r.line_number, r.language) for r in results] == [
        (1, "english"), (2, "nepali_unicode"), (3, "roman_nepali"),
    ]


def test_document_aggregation(detector) -> None:
    assert detector.detect_document("Hello there\nGeneral message") == "english"
    assert detector.detect_document("Hello\nतपाईंको खाता") == "mixed"
    assert detector.detect_document("!!! ???") == "unknown"


def test_no_translation_ever(detector) -> None:
    """Detection must not alter the text in any way."""
    text = "Tapai ko account verify garnus"
    results = detector.detect_lines(text)
    assert results[0].text == text
