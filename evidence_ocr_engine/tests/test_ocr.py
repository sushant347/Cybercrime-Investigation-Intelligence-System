"""Tests for the OCR abstraction, PaddleOCR result parsing and preprocessing."""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.models import OCRPageResult
from backend.modules.evidence.ocr_interface import BaseOCR, FutureOCRService
from backend.modules.evidence.paddle_service import PaddleOCRService
from backend.modules.evidence.preprocessing import ImagePreprocessor, load_image
from backend.modules.evidence.utils import InvalidImageError
from tests.conftest import FakeOCR

# --------------------------------------------------------------------- interface


def test_base_ocr_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseOCR()  # type: ignore[abstract]


def test_future_ocr_service_is_explicit_placeholder() -> None:
    service = FutureOCRService()
    with pytest.raises(NotImplementedError):
        service.recognize(np.zeros((10, 10, 3), dtype=np.uint8))


def test_fake_engine_satisfies_interface() -> None:
    """Any BaseOCR implementation plugs into the pipeline unchanged."""
    engine: BaseOCR = FakeOCR()
    lines = engine.recognize(np.zeros((10, 10, 3), dtype=np.uint8))
    assert lines and lines[0].confidence > 0.9


# ------------------------------------------------- PaddleOCR language handling


def test_default_lang_is_official_nepali_code(config: EvidenceConfig) -> None:
    """Config must use 'ne' (official PaddleOCR 3.x id), not 'devanagari'."""
    assert config.ocr_lang == "ne"
    service = PaddleOCRService(config)
    assert service._lang == "ne"
    # OCR generation is pinned to PP-OCRv5 project-wide (only Devanagari-capable
    # generation; PP-OCRv6 has no Devanagari model).
    assert config.ocr_version == "PP-OCRv5"
    assert service._ocr_version == "PP-OCRv5"


def test_non_v5_ocr_version_is_rejected(config: EvidenceConfig) -> None:
    """The engine is PP-OCRv5-only: any other generation is refused."""
    import dataclasses

    from backend.modules.evidence.utils import EvidenceError

    for bad in ("PP-OCRv3", "PP-OCRv4", "PP-OCRv6"):
        with pytest.raises(EvidenceError):
            PaddleOCRService(config, lang="ne", ocr_version=bad)
        with pytest.raises(EvidenceError):
            PaddleOCRService(dataclasses.replace(config, ocr_version=bad))


def test_unsupported_script_alias_is_resolved(config: EvidenceConfig) -> None:
    """'devanagari'/'nepali' aliases map to 'ne' instead of crashing PaddleOCR."""
    assert PaddleOCRService(config, lang="devanagari")._lang == "ne"
    assert PaddleOCRService(config, lang="Nepali")._lang == "ne"
    assert PaddleOCRService(config, lang="english")._lang == "en"
    assert PaddleOCRService(config, lang="en")._lang == "en"  # passthrough


def test_ocr_version_override_is_stored(config: EvidenceConfig) -> None:
    service = PaddleOCRService(config, lang="ne", ocr_version="PP-OCRv5")
    assert service._ocr_version == "PP-OCRv5"


# ----------------------------------------------------- PaddleOCR result parsing


def test_paddle_parser_handles_3x_dict_results(config: EvidenceConfig) -> None:
    """PaddleOCR 3.x returns mapping-like results with rec_texts/scores/polys."""
    service = PaddleOCRService(config)
    result = {
        "rec_texts": ["Hello", "नमस्ते खाता"],
        "rec_scores": [0.98, 0.91],
        "rec_polys": [
            np.array([[0, 0], [50, 0], [50, 20], [0, 20]]),
            np.array([[0, 30], [80, 30], [80, 55], [0, 55]]),
        ],
    }
    lines = service._parse_result(result)
    assert [ln.text for ln in lines] == ["Hello", "नमस्ते खाता"]  # verbatim
    assert lines[0].bbox == [[0.0, 0.0], [50.0, 0.0], [50.0, 20.0], [0.0, 20.0]]
    assert lines[1].confidence == pytest.approx(0.91)


def test_paddle_parser_tolerates_missing_fields(config: EvidenceConfig) -> None:
    service = PaddleOCRService(config)
    lines = service._parse_result({"rec_texts": ["only text"]})
    assert lines[0].text == "only text"
    assert lines[0].confidence == 0.0
    assert lines[0].bbox == []


def test_page_text_and_confidence_aggregation() -> None:
    page = OCRPageResult(page_number=1, lines=FakeOCR().recognize(
        np.zeros((5, 5, 3), dtype=np.uint8)))
    assert "suspended" in page.text.splitlines()[0]
    assert page.average_confidence == pytest.approx(0.95, abs=0.01)
    assert OCRPageResult(page_number=1).average_confidence == 0.0


# ------------------------------------------------------------------ preprocessing


def test_load_image_rejects_non_image(tmp_path) -> None:
    bad = tmp_path / "fake.png"
    bad.write_bytes(b"definitely not an image")
    with pytest.raises(InvalidImageError):
        load_image(bad)


def test_load_image_returns_rgb(sample_image) -> None:
    image = load_image(sample_image)
    assert image.ndim == 3 and image.shape[2] == 3


def test_preprocess_records_steps_and_returns_valid_image(
    config: EvidenceConfig, sample_image
) -> None:
    preprocessor = ImagePreprocessor(config)
    processed, steps = preprocessor.preprocess(load_image(sample_image))
    assert processed.ndim == 3 and processed.dtype == np.uint8
    assert "convert_rgb" in steps and "exif_orientation" in steps


def test_preprocess_downscales_huge_images(config: EvidenceConfig) -> None:
    huge = np.full((config.max_image_dimension + 500, 800, 3), 255, dtype=np.uint8)
    processed, steps = ImagePreprocessor(config).preprocess(huge)
    assert max(processed.shape[:2]) <= config.max_image_dimension
    assert "resize_large" in steps


def test_preprocess_upscales_tiny_images(config: EvidenceConfig) -> None:
    tiny = np.full((120, 200, 3), 255, dtype=np.uint8)
    processed, steps = ImagePreprocessor(config).preprocess(tiny)
    assert max(processed.shape[:2]) > 200
    assert "resolution_enhancement" in steps


def test_quality_assessment_metrics(config: EvidenceConfig, sample_image) -> None:
    report = ImagePreprocessor(config).assess_quality(load_image(sample_image))
    assert report.width == 600 and report.height == 200
    assert report.brightness > 200  # mostly white image
    assert report.noise_level >= 0.0
