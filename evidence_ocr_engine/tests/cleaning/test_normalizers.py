"""Tests for Unicode normalisation, noise removal and Roman-Nepali rules."""

from __future__ import annotations

import unicodedata

from backend.modules.evidence.cleaning.noise_cleaner import NoiseCleaner
from backend.modules.evidence.cleaning.unicode_normalizer import UnicodeNormalizer

# ------------------------------------------------------------------- unicode


def test_nfc_composition_normalizes_combining_characters() -> None:
    # "e" + combining acute -> precomposed form; meaning identical.
    decomposed = unicodedata.normalize("NFD", "caf\u00e9 khata")
    assert "\u0301" in decomposed  # really decomposed
    normalized, ops = UnicodeNormalizer().normalize(decomposed)
    assert normalized == "caf\u00e9 khata"
    assert "nfc_composition" in ops


def test_nepali_text_survives_normalization_unchanged() -> None:
    text = "तपाईंको खाता निलम्बित छ।"
    normalized, _ = UnicodeNormalizer().normalize(text)
    assert normalized == unicodedata.normalize("NFC", text)
    # Canonical equivalence: meaning identical.
    assert unicodedata.normalize("NFD", normalized) == unicodedata.normalize("NFD", text)


def test_hidden_characters_removed() -> None:
    dirty = "ver​ify﻿ now­"
    cleaned, ops = UnicodeNormalizer().normalize(dirty)
    assert cleaned == "verify now"
    assert any(op.startswith("hidden_chars_removed") for op in ops)


def test_zwnj_kept_only_inside_devanagari() -> None:
    normalizer = UnicodeNormalizer()
    nepali, _ = normalizer.normalize("क‌ख")     # joiner between Devanagari
    latin, _ = normalizer.normalize("a‌b")       # joiner between Latin
    assert "‌" in nepali
    assert latin == "ab"


def test_punctuation_and_space_folding() -> None:
    cleaned, _ = UnicodeNormalizer().normalize("“Smart” – ‘quotes’… here")
    assert cleaned == "\"Smart\" - 'quotes'... here"


def test_devanagari_danda_is_preserved() -> None:
    cleaned, _ = UnicodeNormalizer().normalize("खाता बन्द हुनेछ।")
    assert cleaned.endswith("।")


# --------------------------------------------------------------------- noise


def test_repeated_punctuation_collapsed() -> None:
    cleaned, ops = NoiseCleaner().remove_noise("URGENT!!!! Verify now....")
    assert cleaned == "URGENT! Verify now."
    assert "repeated_punctuation_collapsed" in ops


def test_decoration_only_lines_dropped() -> None:
    text = "Verify account\n------------------\n==========\nSend money"
    cleaned, ops = NoiseCleaner().remove_noise(text)
    assert cleaned == "Verify account\nSend money"
    assert any(op.startswith("noise_only_lines_dropped") for op in ops)


def test_border_characters_removed() -> None:
    cleaned, _ = NoiseCleaner().remove_noise("││ Account Statement ││")
    assert "│" not in cleaned
    assert "Account Statement" in cleaned


def test_whitespace_normalization_keeps_paragraphs() -> None:
    text = "  line one   with   gaps  \n\n\n\n  line two  "
    cleaned, ops = NoiseCleaner().normalize_whitespace(text)
    assert cleaned == "line one with gaps\n\nline two"
    assert "whitespace_normalized" in ops


# -------------------------------------------------------------- roman nepali


def test_roman_nepali_lowercase_and_repeats() -> None:
    cleaner = NoiseCleaner()
    line = cleaner.normalize_roman_nepali_line("PAISA Pathaunusss JHATTAII")
    assert line == "paisa pathaunus jhattaii"  # doubles kept, triples collapsed


def test_roman_nepali_words_never_rewritten() -> None:
    """Normalisation must not transliterate or translate words."""
    line = NoiseCleaner().normalize_roman_nepali_line("Tapai ko account verify garnus")
    assert line == "tapai ko account verify garnus"
