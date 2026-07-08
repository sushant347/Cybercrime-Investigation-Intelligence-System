"""Tests for per-case JSON storage."""

from __future__ import annotations

import json

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.json_storage import JSONCaseStorage
from backend.modules.evidence.schemas import EvidenceOCRResult, LineResult, PageResult


def _result(case_id: str = "CASE_0001", evidence_id: str = "EVID_00001") -> EvidenceOCRResult:
    page = PageResult(
        page=1,
        confidence=0.95,
        text="नमस्ते please verify खाता",
        lines=[LineResult(text="नमस्ते please verify खाता", confidence=0.95,
                          bbox=[[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]])],
        bounding_boxes=[[[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]]],
    )
    result = EvidenceOCRResult(
        case_id=case_id, evidence_id=evidence_id, file_name="shot.png",
        file_hash="f" * 64, file_size="1024",
        upload_time="2026-07-07T00:00:00Z", processing_time_ms=42.0,
        pages=[page], ocr_engine="fake",
    )
    result.build_raw_text()
    return result


def test_save_creates_one_file_per_case(config: EvidenceConfig) -> None:
    store = JSONCaseStorage(config)
    path = store.save_result(_result())
    assert path.name == "CASE_0001.json"
    document = store.load_case("CASE_0001")
    assert document is not None
    assert document["evidence_count"] == 1
    assert document["evidence"][0]["evidence_id"] == "EVID_00001"


def test_multiple_evidence_appended_to_same_case(config: EvidenceConfig) -> None:
    store = JSONCaseStorage(config)
    store.save_result(_result(evidence_id="EVID_00001"))
    store.save_result(_result(evidence_id="EVID_00002"))
    document = store.load_case("CASE_0001")
    assert document["evidence_count"] == 2


def test_reprocessing_replaces_instead_of_duplicating(config: EvidenceConfig) -> None:
    store = JSONCaseStorage(config)
    store.save_result(_result())
    store.save_result(_result())  # same evidence_id again
    assert store.load_case("CASE_0001")["evidence_count"] == 1


def test_unicode_preserved_verbatim_on_disk(config: EvidenceConfig) -> None:
    """Nepali Devanagari text must survive storage byte-for-byte (no ASCII escapes)."""
    store = JSONCaseStorage(config)
    path = store.save_result(_result())
    raw = path.read_text(encoding="utf-8")
    assert "नमस्ते" in raw
    parsed = json.loads(raw)
    assert parsed["evidence"][0]["raw_text"] == "नमस्ते please verify खाता"


def test_load_missing_case_returns_none(config: EvidenceConfig) -> None:
    assert JSONCaseStorage(config).load_case("CASE_0404") is None
