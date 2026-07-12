"""End-to-end enhancement tests: forensic invariants, entity preservation,
correction logging and CSV/JSON persistence."""

from __future__ import annotations

import csv
import json

import pytest

from backend.modules.evidence.cleaning.cleaning_service import CleaningService
from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.enhancement.correction_logger import (
    CorrectionLogRepository,
)
from backend.modules.evidence.enhancement.enhancement_pipeline import (
    EnhancementPipeline,
)
from backend.modules.evidence.enhancement.enhancement_service import (
    EnhancementService,
)
from backend.modules.evidence.json_storage import JSONCaseStorage
from backend.modules.evidence.pipeline import EvidencePipeline
from backend.modules.evidence.utils import EvidenceError
from tests.conftest import FakeOCR

CLEANED = (
    "बोड सदस्यको प्रतिवद्वता अनुसार पुजी बृद्धि हुनेछ\n"
    "Your acc0unt is suspended, contact SUPP0RT\n"
    "Visit http//nabil-verify.scam.top/l0gin\n"
    "send to supp0rt@fake-bank.com or call +977-9812345678\n"
    "hash: d41d8cd98f00b204e9800998ecf8427e"
)

PAGES = [{"lines": [
    {"text": "बोड सदस्यको प्रतिवद्वता अनुसार पुजी बृद्धि हुनेछ", "confidence": 0.42},
    {"text": "Your acc0unt is suspended, contact SUPP0RT", "confidence": 0.55},
    {"text": "Visit http//nabil-verify.scam.top/l0gin", "confidence": 0.60},
    {"text": "send to supp0rt@fake-bank.com or call +977-9812345678", "confidence": 0.65},
    {"text": "hash: d41d8cd98f00b204e9800998ecf8427e", "confidence": 0.50},
]}]


@pytest.fixture()
def result():
    return EnhancementPipeline().enhance(CLEANED, PAGES, "CASE_0001", "EVID_00001")


# --------------------------------------------------------- forensic invariants


def test_cleaned_text_never_modified(result) -> None:
    assert result.cleaned_text == CLEANED  # byte-for-byte


def test_enhanced_text_is_separate_field(result) -> None:
    assert result.enhanced_text != result.cleaned_text
    assert "बोर्ड" in result.enhanced_text
    assert "प्रतिबद्धता" in result.enhanced_text
    assert "पूँजी" in result.enhanced_text
    assert "account" in result.enhanced_text
    assert "SUPPORT" in result.enhanced_text


def test_every_correction_is_logged(result) -> None:
    pairs = {(c.original, c.corrected) for c in result.corrections if c.original}
    assert ("बोड", "बोर्ड") in pairs
    assert ("प्रतिवद्वता", "प्रतिबद्धता") in pairs
    assert ("acc0unt", "account") in pairs
    assert ("SUPP0RT", "SUPPORT") in pairs
    for c in result.corrections:
        assert c.rule  # every entry carries its justification
        assert 0.0 <= c.confidence <= 1.0


# ---------------------------------------------------------- entity preservation


def test_email_with_homoglyph_preserved(result) -> None:
    """supp0rt@... is an entity: its content is evidence, never 'fixed'."""
    assert "supp0rt@fake-bank.com" in result.enhanced_text


def test_phone_and_hash_preserved(result) -> None:
    assert "+977-9812345678" in result.enhanced_text
    assert "d41d8cd98f00b204e9800998ecf8427e" in result.enhanced_text


def test_url_scheme_fixed_but_domain_untouched(result) -> None:
    assert "http://nabil-verify.scam.top/l0gin" in result.enhanced_text
    # l0gin inside the URL path is entity content - never corrected.
    assert "/login" not in result.enhanced_text


# ------------------------------------------------------------ confidence rules


def test_high_confidence_exact_correction_applies() -> None:
    # Exact dictionary/mixed-script fixes are unambiguous OCR errors and now
    # apply even on high-confidence lines (fuzzy guessing stays blocked).
    pages = [{"lines": [{"text": "बोड सदस्य", "confidence": 0.98}]}]
    result = EnhancementPipeline().enhance("बोड सदस्य", pages)
    assert "बोर्ड" in result.enhanced_text  # exact lexicon hit corrected


def test_high_confidence_fuzzy_still_blocked() -> None:
    # A fuzzy-only candidate must NOT be applied on a high-confidence line.
    pages = [{"lines": [{"text": "इन्टरनट खाता", "confidence": 0.98}]}]
    result = EnhancementPipeline().enhance("इन्टरनट खाता", pages)
    assert "इन्टरनट" in result.enhanced_text  # not guessed at on trusted text


def test_medium_confidence_allows_dictionary() -> None:
    pages = [{"lines": [{"text": "बोड सदस्य", "confidence": 0.40}]}]
    result = EnhancementPipeline().enhance("बोड सदस्य", pages)
    assert "बोर्ड" in result.enhanced_text


def test_low_confidence_allows_fuzzy() -> None:
    # "इन्टरनट" (missing matra) is not an exact lexicon entry and not a
    # single-character confusion - only fuzzy matching can repair it.
    pages = [{"lines": [{"text": "इन्टरनट खाता", "confidence": 0.20}]}]
    result = EnhancementPipeline().enhance("इन्टरनट खाता", pages)
    assert "इन्टरनेट" in result.enhanced_text
    rules = {c.rule for c in result.corrections}
    assert "fuzzy_dictionary_match" in rules


def test_fuzzy_blocked_at_medium_confidence() -> None:
    pages = [{"lines": [{"text": "इन्टरनट खाता", "confidence": 0.60}]}]
    result = EnhancementPipeline().enhance("इन्टरनट खाता", pages)
    assert "इन्टरनट" in result.enhanced_text  # left unchanged


# ------------------------------------------------------------------ statistics


def test_statistics_structure(result) -> None:
    stats = result.correction_statistics
    assert stats.total_corrections == len(result.corrections)
    assert stats.nepali_corrections == 3
    assert stats.english_corrections == 2
    assert stats.dictionary_corrections >= 5
    assert stats.confidence_based >= 5
    assert stats.lines_analyzed == 5
    assert 0 < stats.document_confidence < 0.9
    assert stats.nepali_correction_rate > 0
    assert stats.english_correction_rate > 0


def test_json_output_shape(result) -> None:
    payload = json.loads(result.model_dump_json())
    assert "enhanced_text" in payload and "corrections" in payload
    stats = payload["correction_statistics"]
    for key in ("total_corrections", "dictionary_corrections",
                "unicode_corrections", "english_corrections",
                "nepali_corrections", "confidence_based"):
        assert key in stats


# ------------------------------------------------------- service + CSV logging


def _prepare_case(config: EvidenceConfig, tmp_path) -> str:
    """Ingest via the OCR path with low line confidences so that the
    enhancement tier system has something to correct (a TXT file would be
    stored at confidence 1.0 and - correctly - never be corrected)."""
    from PIL import Image

    from backend.modules.evidence.models import OCRLine

    source = tmp_path / "scam_note.png"
    Image.new("RGB", (400, 200), "white").save(source)
    lines = [
        OCRLine(text=text, confidence=conf)
        for text, conf in zip(CLEANED.splitlines(),
                              (0.42, 0.55, 0.60, 0.65, 0.50))
    ]
    ocr = FakeOCR(lines=lines)
    case_id = EvidencePipeline(config, ocr).process_file(source).case_id
    CleaningService(config).clean_case(case_id)
    return case_id


def test_service_persists_enhancement_and_csv(config: EvidenceConfig, tmp_path) -> None:
    case_id = _prepare_case(config, tmp_path)
    results = EnhancementService(config).enhance_case(case_id)
    assert len(results) == 1

    document = JSONCaseStorage(config).load_case(case_id)
    evidence = document["evidence"][0]
    assert "enhancement" in evidence
    assert evidence["cleaning"]["cleaned_text"] == evidence["enhancement"]["cleaned_text"]
    assert evidence["enhancement"]["enhanced_text"]

    csv_path = config.storage_dir / "ocr_corrections.csv"
    assert csv_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "corrections must be persisted"
    expected_columns = {"case_id", "evidence_id", "original", "corrected",
                        "confidence", "rule", "timestamp"}
    assert expected_columns <= set(rows[0].keys())
    assert all(row["case_id"] == case_id for row in rows)


def test_service_requires_cleaning_first(config: EvidenceConfig, tmp_path) -> None:
    source = tmp_path / "raw_only.txt"
    source.write_text("some text", encoding="utf-8")
    case_id = EvidencePipeline(config, FakeOCR()).process_file(source).case_id
    results = EnhancementService(config).enhance_case(case_id)
    assert results == []  # skipped gracefully, no crash


def test_service_unknown_case_raises(config: EvidenceConfig) -> None:
    with pytest.raises(EvidenceError, match="Unknown case"):
        EnhancementService(config).enhance_case("CASE_0404")


def test_correction_logger_rows(config: EvidenceConfig) -> None:
    from backend.modules.evidence.enhancement.enhancement_schemas import (
        CorrectionEntry,
    )
    repo = CorrectionLogRepository(config)
    written = repo.log_corrections("CASE_0001", "EVID_00001", [
        CorrectionEntry(original="बोड", corrected="बोर्ड", confidence=0.42,
                        rule="dictionary_match", language="nepali"),
    ])
    assert written == 1
    row = repo.read_all()[0]
    assert row["original"] == "बोड" and row["corrected"] == "बोर्ड"
    assert row["rule"] == "dictionary_match"
    assert float(row["confidence"]) == 0.42
    assert row["timestamp"]
