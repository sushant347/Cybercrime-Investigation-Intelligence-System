"""Unit tests for OCR CER/WER metrics (known, hand-computed values)."""
import math

from backend.modules.evidence.evaluation import ocr_metrics as m


def test_levenshtein_basic():
    assert m.levenshtein("kitten", "sitting") == 3
    assert m.levenshtein("", "abc") == 3
    assert m.levenshtein("abc", "abc") == 0


def test_cer_perfect_and_substitution():
    assert m.character_error_rate("hello", "hello") == 0.0
    # one substitution over 5 reference chars.
    assert math.isclose(m.character_error_rate("hello", "hallo"), 0.2)


def test_cer_empty_reference():
    assert m.character_error_rate("", "") == 0.0
    assert m.character_error_rate("", "x") == 1.0


def test_wer_word_level():
    assert m.word_error_rate("the cat sat", "the cat sat") == 0.0
    assert math.isclose(m.word_error_rate("the cat sat", "the dog sat"), 1 / 3)


def test_normalization_folds_case_and_whitespace():
    # Without normalization these differ; with it they match.
    assert m.character_error_rate("Hello  World", "hello world") == 0.0
    assert (
        m.character_error_rate(
            "Hello", "hello", normalize=True, lowercase=False
        )
        > 0.0
    )


def test_corpus_micro_average():
    pairs = [("hello", "hello"), ("world", "w0rld")]  # 0 edits + 1 edit / 10 chars
    res = m.corpus_ocr_metrics(pairs)
    assert res.samples == 2
    assert math.isclose(res.cer, 1 / 10)
    assert math.isclose(res.char_accuracy, 0.9)
    d = res.to_dict()
    assert d["samples"] == 2
    assert "cer_distribution" in d and d["cer_distribution"]["max"] >= d["cer_distribution"]["min"]


def test_devanagari_nfc_equivalence():
    # NFC vs decomposed Devanagari should compare equal after normalization.
    composed = "नि"  # नि (NFC)
    decomposed = "नि"
    assert m.character_error_rate(composed, decomposed) == 0.0
