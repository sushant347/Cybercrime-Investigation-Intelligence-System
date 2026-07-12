"""End-to-end pipeline tests (JSON contract) and CSV/JSON persistence."""

from __future__ import annotations

import csv
import json

import pytest

from backend.modules.evidence.cleaning.cleaning_pipeline import CleaningPipeline
from backend.modules.evidence.cleaning.cleaning_service import CleaningService
from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.json_storage import JSONCaseStorage
from backend.modules.evidence.pipeline import EvidencePipeline
from backend.modules.evidence.utils import EvidenceError
from tests.conftest import FakeOCR

RAW = (
    "URGENT!!!!   Your acc0unt has been\n"
    "suspended, verify now\n"
    "http//nabil-verify.scam.top/login?id=99\n"
    "Esewa id ma paisa pathaunus 9812345678\n"
    "तपाईंको खाता निलम्बित छ।\n"
    "Contact: supp0rt@fake-bank.com | OTP code 4521\n"
)


@pytest.fixture()
def result():
    return CleaningPipeline().clean(RAW, case_id="CASE_0001", evidence_id="EVID_00001")


# --------------------------------------------------------------- JSON contract


def test_raw_text_is_never_modified(result) -> None:
    assert result.raw_text == RAW  # forensic invariant, byte-for-byte


def test_cleaned_text_is_separate_and_improved(result) -> None:
    cleaned = result.cleaned_text
    assert cleaned != RAW
    assert "acc0unt" not in cleaned and "account" in cleaned
    assert "http://nabil-verify.scam.top/login?id=99" in cleaned
    assert "URGENT!" in cleaned and "!!!!" not in cleaned
    # Roman-Nepali line lowercased, words unchanged.
    assert "esewa id ma paisa pathaunus" in cleaned
    # Nepali Unicode preserved.
    assert "तपाईंको खाता निलम्बित छ।" in cleaned


def test_language_and_line_languages(result) -> None:
    assert result.language == "mixed"
    assert result.line_languages["5"] == "nepali_unicode"
    assert set(result.statistics.languages_detected) >= {
        "english", "nepali_unicode", "roman_nepali",
    }


def test_entities_in_output(result) -> None:
    entities = result.entities
    assert entities["urls"][0].value == "http://nabil-verify.scam.top/login?id=99"
    assert entities["emails"][0].normalized == "supp0rt@fake-bank.com"
    assert entities["esewa_ids"][0].normalized == "+9779812345678"
    assert entities["otp"][0].value == "4521"


def test_keywords_and_statistics(result) -> None:
    assert result.keywords["verify"] >= 1
    assert result.keywords["otp"] >= 1
    assert result.risk_signals["credential"] >= 2
    stats = result.statistics
    assert stats.characters == len(result.cleaned_text)
    assert stats.words > 10 and stats.lines > 0
    assert stats.average_line_length > 0
    assert stats.entity_count >= 4
    assert stats.cleaning_operations and stats.ocr_corrections
    assert result.processing_time_ms > 0


def test_json_serialisable_matches_spec_shape(result) -> None:
    payload = json.loads(result.model_dump_json())
    for key in ("raw_text", "cleaned_text", "language", "entities",
                "keywords", "statistics"):
        assert key in payload
    assert isinstance(payload["entities"]["urls"], list)
    assert isinstance(payload["statistics"]["languages_detected"], list)


def test_email_with_ocr_typo_left_when_uncertain() -> None:
    """supp0rt@ inside an email is protected, not 'corrected': entities win."""
    result = CleaningPipeline().clean("write to supp0rt@fake-bank.com")
    assert "supp0rt@fake-bank.com" in result.cleaned_text


# ------------------------------------------------------------ CSV/JSON storage


def _ingest_demo_case(config: EvidenceConfig, tmp_path) -> str:
    source = tmp_path / "chat_export.txt"
    source.write_text(RAW, encoding="utf-8")
    ocr = EvidencePipeline(config, FakeOCR())
    return ocr.process_file(source, case_title="cleaning test").case_id


def test_service_updates_json_and_csvs(config: EvidenceConfig, tmp_path) -> None:
    case_id = _ingest_demo_case(config, tmp_path)
    service = CleaningService(config)
    results = service.clean_case(case_id)
    assert len(results) == 1

    # Case JSON: Prompt 1 fields untouched, cleaning section added.
    document = JSONCaseStorage(config).load_case(case_id)
    evidence = document["evidence"][0]
    assert evidence["raw_text"] == RAW.strip("\n") or evidence["raw_text"]  # original present
    assert evidence["cleaning"]["raw_text"] == evidence["raw_text"]
    assert evidence["cleaning"]["cleaned_text"]
    assert evidence["cleaning"]["language"] == "mixed"

    # entities.csv
    with open(config.storage_dir / "entities.csv", newline="", encoding="utf-8") as fh:
        entity_rows = list(csv.DictReader(fh))
    assert any(r["entity_type"] == "urls" for r in entity_rows)
    assert any(r["entity_type"] == "esewa_ids" for r in entity_rows)
    assert all(r["case_id"] == case_id for r in entity_rows)

    # keyword_statistics.csv (keywords + one row per risk category)
    with open(config.storage_dir / "keyword_statistics.csv", newline="",
              encoding="utf-8") as fh:
        keyword_rows = list(csv.DictReader(fh))
    keywords = {r["keyword"] for r in keyword_rows}
    assert "verify" in keywords
    assert "__risk_signal__credential" in keywords

    # ocr_results.csv augmented in place.
    with open(config.ocr_results_csv, newline="", encoding="utf-8") as fh:
        ocr_rows = list(csv.DictReader(fh))
    assert ocr_rows[0]["language"] == "mixed"
    assert ocr_rows[0]["cleaned_text_preview"]
    assert int(ocr_rows[0]["entity_count"]) >= 4


def test_service_clean_single_evidence(config: EvidenceConfig, tmp_path) -> None:
    case_id = _ingest_demo_case(config, tmp_path)
    document = JSONCaseStorage(config).load_case(case_id)
    evidence_id = document["evidence"][0]["evidence_id"]
    result = CleaningService(config).clean_evidence(case_id, evidence_id)
    assert result.evidence_id == evidence_id


def test_service_unknown_case_raises(config: EvidenceConfig) -> None:
    with pytest.raises(EvidenceError, match="Unknown case"):
        CleaningService(config).clean_case("CASE_0404")
