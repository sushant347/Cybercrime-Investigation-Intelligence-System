"""End-to-end pipeline tests plus graceful error handling."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.csv_storage import EvidenceRepository, OCRResultRepository
from backend.modules.evidence.json_storage import JSONCaseStorage
from backend.modules.evidence.pipeline import EvidencePipeline
from backend.modules.evidence.utils import (
    EmptyOCRError,
    EvidenceError,
    UnsupportedFormatError,
)
from tests.conftest import EmptyOCR, FakeOCR


def _pipeline(config: EvidenceConfig, engine=None) -> EvidencePipeline:
    return EvidencePipeline(config, engine or FakeOCR())


# --------------------------------------------------------------------- happy path


def test_image_evidence_full_flow(config: EvidenceConfig, sample_image: Path) -> None:
    pipeline = _pipeline(config)
    result = pipeline.process_file(sample_image, case_title="Phishing SMS wave")

    # Output contract.
    assert result.case_id == "CASE_0001"
    assert result.evidence_id == "EVID_00001"
    assert result.file_name == "phishing_screenshot.png"
    assert len(result.file_hash) == 64
    assert result.pages[0].page == 1
    assert result.pages[0].lines and result.pages[0].bounding_boxes
    assert "suspended" in result.raw_text
    assert result.processing_time_ms > 0
    assert result.hash_verified is True

    # CSV persistence.
    evidence_row = EvidenceRepository(config).get("EVID_00001")
    assert evidence_row["status"] == "processed"
    assert evidence_row["sha256_before"] == evidence_row["sha256_after"] == result.file_hash
    assert OCRResultRepository(config).count() == 1

    # JSON persistence (one file per case, complete output).
    document = JSONCaseStorage(config).load_case("CASE_0001")
    assert document["evidence"][0]["raw_text"] == result.raw_text


def test_pdf_evidence_pages_kept_in_order(config: EvidenceConfig, sample_pdf: Path) -> None:
    engine = FakeOCR()
    result = _pipeline(config, engine).process_file(sample_pdf)
    assert [p.page for p in result.pages] == [1, 2]
    # The sample PDF is a *digital* PDF: its embedded text layer is read
    # verbatim, so OCR is never invoked (OCR of a text PDF is slower and
    # strictly less accurate). Scanned pages still fall back to OCR - see
    # tests/test_evidence_types.py::test_scanned_pdf_falls_back_to_ocr.
    assert engine.calls == 0


def test_text_evidence_skips_ocr_and_preserves_content(
    config: EvidenceConfig, sample_text_file: Path
) -> None:
    engine = FakeOCR()
    result = _pipeline(config, engine).process_file(sample_text_file)
    assert engine.calls == 0  # no OCR for plain text evidence
    assert "किन?" in result.raw_text  # Nepali text preserved verbatim
    assert result.pages[0].confidence == 1.0


def test_multiple_evidence_same_case(config: EvidenceConfig, sample_image: Path,
                                     sample_text_file: Path) -> None:
    pipeline = _pipeline(config)
    first = pipeline.process_file(sample_image)
    second = pipeline.process_file(sample_text_file, case_id=first.case_id)
    assert second.case_id == first.case_id
    assert second.evidence_id == "EVID_00002"
    document = JSONCaseStorage(config).load_case(first.case_id)
    assert document["evidence_count"] == 2


# ------------------------------------------------------------------ error handling


def test_unknown_case_rejected(config: EvidenceConfig, sample_image: Path) -> None:
    with pytest.raises(EvidenceError, match="Unknown case"):
        _pipeline(config).process_file(sample_image, case_id="CASE_0404")


def test_unsupported_format_bubbles_up(config: EvidenceConfig, tmp_path: Path) -> None:
    bad = tmp_path / "dump.bin"
    bad.write_bytes(b"\x00" * 10)
    with pytest.raises(UnsupportedFormatError):
        _pipeline(config).process_file(bad)


def test_invalid_image_marks_evidence_failed(config: EvidenceConfig, tmp_path: Path) -> None:
    fake_png = tmp_path / "notimage.png"
    fake_png.write_bytes(b"this is not a png")
    with pytest.raises(EvidenceError):
        _pipeline(config).process_file(fake_png)
    row = EvidenceRepository(config).get("EVID_00001")
    assert row is not None and row["status"] == "failed"  # graceful recovery


def test_corrupted_pdf_marks_evidence_failed(config: EvidenceConfig, tmp_path: Path) -> None:
    bad_pdf = tmp_path / "broken.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4 broken body")
    with pytest.raises(EvidenceError):
        _pipeline(config).process_file(bad_pdf)
    assert EvidenceRepository(config).get("EVID_00001")["status"] == "failed"


def test_empty_ocr_warns_by_default(config: EvidenceConfig, sample_image: Path) -> None:
    result = _pipeline(config, EmptyOCR()).process_file(sample_image)
    assert result.raw_text == ""
    assert result.pages[0].confidence == 0.0
    assert result.hash_verified is True  # integrity still proven


def test_empty_ocr_raises_in_strict_mode(config: EvidenceConfig, sample_image: Path) -> None:
    strict_cfg = dataclasses.replace(config, strict_empty_ocr=True)
    with pytest.raises(EmptyOCRError):
        EvidencePipeline(strict_cfg, EmptyOCR()).process_file(sample_image)
