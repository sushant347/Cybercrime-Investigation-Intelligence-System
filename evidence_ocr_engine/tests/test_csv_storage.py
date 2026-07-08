"""Tests for the CSV repository layer."""

from __future__ import annotations

import csv

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.csv_storage import (
    CaseRepository,
    EvidenceRepository,
    OCRResultRepository,
    ProcessingLogRepository,
)
from backend.modules.evidence.models import EvidenceRecord


def test_repositories_create_files_with_headers(config: EvidenceConfig) -> None:
    CaseRepository(config)
    EvidenceRepository(config)
    OCRResultRepository(config)
    ProcessingLogRepository(config)
    for path in (config.cases_csv, config.evidence_csv,
                 config.ocr_results_csv, config.processing_log_csv):
        assert path.exists()
        with open(path, newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        assert header  # header row written


def test_case_ids_are_sequential(config: EvidenceConfig) -> None:
    repo = CaseRepository(config)
    first = repo.create(title="Phishing wave")
    second = repo.create()
    assert first.case_id == "CASE_0001"
    assert second.case_id == "CASE_0002"
    assert repo.get("CASE_0002") is not None
    assert repo.get("CASE_9999") is None


def test_case_evidence_count_increments(config: EvidenceConfig) -> None:
    repo = CaseRepository(config)
    case = repo.create()
    repo.increment_evidence_count(case.case_id)
    repo.increment_evidence_count(case.case_id)
    assert repo.get(case.case_id)["evidence_count"] == "2"


def test_evidence_add_and_update_roundtrip(config: EvidenceConfig) -> None:
    repo = EvidenceRepository(config)
    record = EvidenceRecord(
        evidence_id=repo.next_evidence_id(),
        case_id="CASE_0001",
        original_file_name="scam.png",
        stored_file_name="EVID_00001__ab__scam.png",
        file_extension=".png",
        file_size_bytes=1234,
        sha256_before="a" * 64,
        upload_time="2026-07-07T00:00:00Z",
    )
    repo.add(record)
    record.sha256_after = "a" * 64
    record.hash_verified = True
    record.status = "processed"
    repo.update(record)

    row = repo.get(record.evidence_id)
    assert row is not None
    assert row["status"] == "processed"
    assert row["hash_verified"] == "True"
    assert repo.count() == 1  # update replaced, not appended


def test_processing_log_stage_entries(config: EvidenceConfig) -> None:
    repo = ProcessingLogRepository(config)
    repo.log_stage("CASE_0001", "EVID_00001", "ocr", "42 lines", duration_ms=123.456)
    rows = repo.read_all()
    assert len(rows) == 1
    assert rows[0]["stage"] == "ocr"
    assert rows[0]["level"] == "INFO"
    assert float(rows[0]["duration_ms"]) == 123.5


def test_ocr_summary_preview_truncated_and_flattened(config: EvidenceConfig) -> None:
    repo = OCRResultRepository(config)
    repo.add_summary(
        evidence_id="EVID_00001", case_id="CASE_0001", ocr_engine="fake",
        page_count=1, line_count=2, average_confidence=0.95,
        processing_time_ms=10.0, raw_text="line1\nline2" + "x" * 500,
        json_file="CASE_0001.json",
    )
    row = repo.read_all()[0]
    assert "\n" not in row["raw_text_preview"]
    assert len(row["raw_text_preview"]) <= 200
