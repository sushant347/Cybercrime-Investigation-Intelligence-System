"""Module 3 tests - Multi-OCR Fusion Engine (with fake adapters)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.forensics.multi_ocr.fusion import MultiOCRFusionService
from backend.modules.evidence.models import OCRLine

from .conftest import FailingAdapter, FakeAdapter, make_lines


@pytest.fixture()
def image() -> np.ndarray:
    return np.full((100, 100, 3), 255, dtype=np.uint8)


def _service(fcfg, repo, audit, engines):
    return MultiOCRFusionService(fcfg, repo, audit, engines)


def test_every_engine_output_is_stored_separately(fcfg, repo, audit, image):
    engines = [
        FakeAdapter("paddleocr", make_lines(("hello world", 0.95))),
        FakeAdapter("easyocr", make_lines(("hello world", 0.80))),
        FakeAdapter("tesseract", make_lines(("hallo warld", 0.55))),
    ]
    result = _service(fcfg, repo, audit, engines).run(
        image, evidence_id="EVID_00001", case_id="CASE_0001"
    )
    assert result.paddle_text == "hello world"
    assert result.easyocr_text == "hello world"
    assert result.tesseract_text == "hallo warld"
    assert result.raw_text == result.paddle_text
    assert set(result.engine_confidences) == {"paddleocr", "easyocr", "tesseract"}
    stored = repo.load_latest("EVID_00001", fcfg.ocr_fusion_report_name)
    assert stored is not None
    assert stored["report"]["final_text"]


def test_best_engine_is_selected(fcfg, repo, audit, image):
    engines = [
        FakeAdapter("paddleocr", make_lines(("high quality line", 0.96))),
        FakeAdapter("tesseract", make_lines(("hgh qlty lne", 0.30))),
    ]
    result = _service(fcfg, repo, audit, engines).run(
        image, evidence_id="E", case_id="C", persist=False
    )
    assert result.selected_engine == "paddleocr"
    assert result.final_text == "high quality line"
    assert result.selection_scores["paddleocr"] > result.selection_scores["tesseract"]


def test_merge_substitutes_higher_confidence_matching_line(fcfg, repo, audit, image):
    engines = [
        # paddle wins overall selection (higher average confidence) ...
        FakeAdapter("paddleocr", [
            OCRLine("send money to esewa", 0.98),
            OCRLine("acc0unt number 12345", 0.72),   # ... but this line is weak
        ]),
        FakeAdapter("easyocr", [
            OCRLine("send money to esewa", 0.60),
            OCRLine("account number 12345", 0.92),   # same line, better read
        ]),
    ]
    result = _service(fcfg, repo, audit, engines).run(
        image, evidence_id="E", case_id="C", persist=False
    )
    assert result.merge_applied
    assert "account number 12345" in result.final_text
    assert result.final_source == "merged"
    sources = {fl.source_engine for fl in result.merged_lines}
    assert sources == {"paddleocr", "easyocr"}


def test_unavailable_and_failing_engines_never_abort(fcfg, repo, audit, image):
    engines = [
        FakeAdapter("paddleocr", make_lines(("ok", 0.9))),
        FakeAdapter("easyocr", [], is_available=False),
        FailingAdapter(),
    ]
    result = _service(fcfg, repo, audit, engines).run(
        image, evidence_id="E", case_id="C", persist=False
    )
    assert result.final_text == "ok"
    runs = {r.engine: r for r in result.engine_runs}
    assert runs["easyocr"].available is False
    assert runs["failing"].succeeded is False
    assert runs["failing"].error


def test_no_engine_available_yields_empty_result(fcfg, repo, audit, image):
    engines = [FakeAdapter("easyocr", [], is_available=False)]
    result = _service(fcfg, repo, audit, engines).run(
        image, evidence_id="E", case_id="C", persist=False
    )
    assert result.final_text == ""
    assert result.final_source == "none"
    assert result.selected_engine == ""
