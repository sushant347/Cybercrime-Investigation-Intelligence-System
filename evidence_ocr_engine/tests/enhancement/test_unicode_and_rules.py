"""Tests for Unicode validation and structural OCR correction rules."""

from __future__ import annotations

import unicodedata

from backend.modules.evidence.enhancement.ocr_correction_rules import (
    OCRCorrectionRules,
)
from backend.modules.evidence.enhancement.unicode_validator import UnicodeValidator

# ------------------------------------------------------------------- unicode


def test_nfc_recomposition_counted() -> None:
    decomposed = unicodedata.normalize("NFD", "café")
    repaired, report = UnicodeValidator().validate(decomposed)
    assert repaired == "café"
    assert report.nfc_recompositions == 1
    assert report.total >= 1


def test_duplicate_diacritics_removed() -> None:
    # The same vowel sign twice in a row (OCR stutter) is invalid.
    broken = "बैंकाा"  # doubled aa-matra
    repaired, report = UnicodeValidator().validate(broken)
    assert repaired == "बैंका"
    assert report.duplicate_marks_removed >= 1


def test_double_halant_collapsed() -> None:
    broken = "सम््पर्क"  # double halant
    repaired, report = UnicodeValidator().validate(broken)
    assert repaired == "सम्पर्क"
    assert report.duplicate_halants_collapsed == 1


def test_orphan_combining_mark_removed() -> None:
    broken = "ो नमस्ते"  # matra with no base character at line start
    repaired, report = UnicodeValidator().validate(broken)
    assert repaired == " नमस्ते"
    assert report.orphan_marks_removed >= 1


def test_zero_width_stripped_but_devanagari_joiners_kept() -> None:
    text = "क‍ख and ver​ify"  # ZWJ inside Devanagari, ZWSP inside Latin
    repaired, report = UnicodeValidator().validate(text)
    assert "‍" in repaired      # Devanagari joiner preserved
    assert "​" not in repaired  # zero-width space removed
    assert report.zero_width_removed >= 1


def test_valid_text_untouched() -> None:
    text = "तपाईंको खाता निलम्बित छ। Contact support."
    repaired, report = UnicodeValidator().validate(
        unicodedata.normalize("NFC", text))
    assert repaired == unicodedata.normalize("NFC", text)
    assert report.total == 0


# --------------------------------------------------------------------- rules


def test_url_scheme_fixes() -> None:
    rules = OCRCorrectionRules()
    fixed, fixes = rules.apply("go to http//a.example and https//b.example")
    assert "http://a.example" in fixed and "https://b.example" in fixed
    assert all(f.rule == "url_scheme_fix" for f in fixes)


def test_www_prefix_fix() -> None:
    fixed, fixes = OCRCorrectionRules().apply("see www,scam.example now")
    assert "www.scam.example" in fixed
    assert fixes[0].rule == "www_prefix_fix"


def test_danda_deduplication_and_spacing() -> None:
    fixed, fixes = OCRCorrectionRules().apply("खाता बन्द हुनेछ ।। अहिले ।")
    assert "।।" not in fixed
    assert " ।" not in fixed
    assert {f.rule for f in fixes} >= {"danda_dedup", "danda_spacing"}


def test_entity_safe_subset_never_touches_content() -> None:
    rules = OCRCorrectionRules()
    fixed, fixes = rules.apply_to_entity("http//scam-domain.top/acc0unt?x=1")
    assert fixed == "http://scam-domain.top/acc0unt?x=1"  # scheme only
    assert "acc0unt" in fixed  # entity substance untouched
    assert len(fixes) == 1 and fixes[0].rule == "url_scheme_fix"


def test_entity_safe_subset_skips_danda_rules() -> None:
    fixed, fixes = OCRCorrectionRules().apply_to_entity("hash।।value")
    assert fixed == "hash।।value"  # danda rules not part of the safe subset
    assert fixes == []
