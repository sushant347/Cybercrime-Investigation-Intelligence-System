"""Tests for conservative OCR error correction."""

from __future__ import annotations

import pytest

from backend.modules.evidence.cleaning.ocr_corrector import OCRCorrector


@pytest.fixture()
def corrector() -> OCRCorrector:
    return OCRCorrector()


@pytest.mark.parametrize(
    "before,after",
    [
        ("visit http//scam.example now", "visit http://scam.example now"),
        ("https//secure.example", "https://secure.example"),
        ("go to www,example.com", "go to www.example.com"),
        ("send emall to us", "send email to us"),
        ("your acc0unt is locked", "your account is locked"),
        ("1ogin here", "login here"),
        ("contact SUPP0RT", "contact SUPPORT"),  # casing mirrored
        ("enter passw0rd", "enter password"),
    ],
)
def test_known_corrections(corrector: OCRCorrector, before: str, after: str) -> None:
    corrected, corrections = corrector.correct(before)
    assert corrected == after
    assert corrections  # audit trail recorded


def test_corrections_are_audited(corrector: OCRCorrector) -> None:
    _, corrections = corrector.correct("emall and acc0unt")
    pairs = {(c.original, c.corrected) for c in corrections}
    assert ("emall", "email") in pairs
    assert ("acc0unt", "account") in pairs


def test_unknown_words_never_guessed(corrector: OCRCorrector) -> None:
    """Low-confidence tokens are left exactly as OCR produced them."""
    text = "the qu1ck br0wn f0x acount xzqw123"
    corrected, corrections = corrector.correct(text)
    assert corrected == text
    assert corrections == []


def test_valid_urls_untouched(corrector: OCRCorrector) -> None:
    text = "https://real.example/path and http://other.example"
    corrected, corrections = corrector.correct(text)
    assert corrected == text
    assert corrections == []


def test_capitalised_token_mirrors_case(corrector: OCRCorrector) -> None:
    corrected, _ = corrector.correct("Emall support")
    assert corrected == "Email support"
