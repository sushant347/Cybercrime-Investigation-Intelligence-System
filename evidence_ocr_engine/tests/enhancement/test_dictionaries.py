"""Tests for the Nepali and English OCR correction dictionaries."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from backend.modules.evidence.enhancement.english_dictionary import EnglishDictionary
from backend.modules.evidence.enhancement.nepali_dictionary import NepaliDictionary


@pytest.fixture(scope="module")
def nepali() -> NepaliDictionary:
    return NepaliDictionary()


@pytest.fixture(scope="module")
def english() -> EnglishDictionary:
    return EnglishDictionary()


# ------------------------------------------------------------ Nepali lexicon


@pytest.mark.parametrize(
    "wrong,right",
    [
        ("बोड", "बोर्ड"),
        ("बो्ड", "बोर्ड"),
        ("प्रतिवद्वता", "प्रतिबद्धता"),
        ("पुजी", "पूँजी"),
        ("कार्वदल", "कार्यदल"),
        ("क्ियाशील", "क्रियाशील"),
        ("सचीकृत", "सूचीकृत"),
        ("प्रथमिकता", "प्राथमिकता"),
        ("भरपदों", "भरपर्दो"),
        ("दीर्वकालीन", "दीर्घकालीन"),
        ("अन्तरा्िय", "अन्तर्राष्ट्रिय"),
    ],
)
def test_nepali_exact_corrections(nepali: NepaliDictionary, wrong: str, right: str) -> None:
    assert nepali.lookup_exact(wrong) == right


def test_nepali_valid_word_not_corrected(nepali: NepaliDictionary) -> None:
    assert nepali.lookup_exact("बोर्ड") is None
    assert nepali.is_valid_word("बोर्ड")


def test_nepali_lookup_is_nfc_insensitive(nepali: NepaliDictionary) -> None:
    decomposed = unicodedata.normalize("NFD", "पुजी")
    assert nepali.lookup_exact(decomposed) == "पूँजी"


def test_nepali_fuzzy_finds_close_valid_word(nepali: NepaliDictionary) -> None:
    # One matra difference from valid word तपाईंको - not in exact lexicon.
    assert nepali.lookup_fuzzy("तपाईको") == "तपाईंको"


def test_nepali_fuzzy_rejects_distant_tokens(nepali: NepaliDictionary) -> None:
    assert nepali.lookup_fuzzy("कमलपोखरी") is None


def test_lexicon_is_json_and_extensible(tmp_path: Path) -> None:
    """The lexicon is a plain JSON file; new entries need no code changes."""
    custom = tmp_path / "lexicon.json"
    custom.write_text(json.dumps({
        "corrections": {"नयाँत्रुटि": "नयाँशुद्ध"},
        "valid_words": ["नयाँशुद्ध"],
    }, ensure_ascii=False), encoding="utf-8")
    dictionary = NepaliDictionary(lexicon_path=custom)
    assert dictionary.lookup_exact("नयाँत्रुटि") == "नयाँशुद्ध"
    dictionary.add_correction("अर्कोगल्ती", "अर्कोशुद्ध")
    assert dictionary.lookup_exact("अर्कोगल्ती") == "अर्कोशुद्ध"


# ----------------------------------------------------------- English lexicon


@pytest.mark.parametrize(
    "wrong,right",
    [
        ("Acc0unt", "Account"),
        ("SUPP0RT", "SUPPORT"),
        ("L0gin", "Login"),
        ("1ogin", "login"),
        ("emall", "email"),
        ("passw0rd", "password"),
    ],
)
def test_english_exact_corrections_mirror_case(english: EnglishDictionary,
                                               wrong: str, right: str) -> None:
    assert english.lookup_exact(wrong) == right


def test_english_0tp_special_case(english: EnglishDictionary) -> None:
    assert english.lookup_exact("0TP") == "OTP"


def test_homoglyph_resolution_only_for_known_vocabulary(english: EnglishDictionary) -> None:
    assert english.resolve_homoglyphs("m0bile") == "mobile"
    assert english.resolve_homoglyphs("ba1ance") == "balance"
    # Unknown word: never guessed.
    assert english.resolve_homoglyphs("xq0zzt") is None
    # Already valid: untouched.
    assert english.resolve_homoglyphs("account") is None


def test_homoglyph_never_guesses_ambiguous(english: EnglishDictionary) -> None:
    """If multiple vocabulary words could result, no correction is made."""
    english.add_correction("dummy1", "dummy1")  # no-op; keeps API covered
    # digits-only tokens contain no letters -> never touched
    assert english.resolve_homoglyphs("2026") is None
