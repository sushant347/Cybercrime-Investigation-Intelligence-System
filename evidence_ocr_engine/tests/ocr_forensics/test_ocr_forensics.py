"""Tests for the additive OCR forensic-metadata layer.

Covers confidence filtering, language detection, image quality assessment,
duplicate detection, bounding-box preservation, metadata generation, batch
processing, timing metrics and chat reconstruction. All offline (no Paddle).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.modules.evidence.ocr_forensics import (
    BatchProcessor,
    ChatReconstructor,
    ConfidenceAnalyzer,
    DuplicateDetector,
    ImageQualityAnalyzer,
    OCRForensicAnalyzer,
    OCRForensicConfig,
    OCRLanguageDetector,
    TimingRecorder,
)


def _pages(lines):
    return [{"page": 1, "lines": lines}]


# --------------------------------------------------------- confidence filtering


def test_confidence_tiers_and_statistics() -> None:
    analyzer = ConfidenceAnalyzer(OCRForensicConfig())
    pages = _pages([
        {"text": "a", "confidence": 0.98, "bbox": [[0, 0]]},
        {"text": "b", "confidence": 0.70, "bbox": [[0, 0]]},
        {"text": "c", "confidence": 0.20, "bbox": [[0, 0]]},
    ])
    lines, stats = analyzer.analyze(pages)
    assert [l.tier for l in lines] == ["high", "medium", "low"]
    assert stats.count == 3
    assert stats.maximum == 0.98 and stats.minimum == 0.20
    assert stats.high_count == 1 and stats.medium_count == 1 and stats.low_count == 1
    assert 0.6 < stats.average < 0.65
    assert stats.median == 0.70


def test_confidence_original_values_preserved() -> None:
    lines, _ = ConfidenceAnalyzer().analyze(
        _pages([{"text": "x", "confidence": 0.4321, "bbox": []}]))
    assert lines[0].confidence == 0.4321  # unchanged


def test_optional_discard_low_confidence() -> None:
    cfg = OCRForensicConfig(discard_low=True, confidence_discard_below=0.30)
    lines, stats = ConfidenceAnalyzer(cfg).analyze(
        _pages([{"text": "junk", "confidence": 0.1, "bbox": []}]))
    assert lines[0].tier == "discarded"
    assert stats.discarded_count == 1
    assert ConfidenceAnalyzer.kept_lines(lines) == []  # filtered out


def test_discard_off_by_default_keeps_everything() -> None:
    lines, stats = ConfidenceAnalyzer().analyze(
        _pages([{"text": "junk", "confidence": 0.1, "bbox": []}]))
    assert lines[0].tier == "low" and stats.discarded_count == 0  # forensic default


# ----------------------------------------------------------- language detection


def test_language_detection_english_nepali_mixed() -> None:
    det = OCRLanguageDetector()
    assert det.detect_text("Your account is suspended").detected == "english"
    assert det.detect_text("तपाईंको खाता निलम्बित छ").detected == "nepali"
    mixed = det.detect_text("Verify your खाता now")
    assert mixed.detected == "mixed"
    # English-only recommends "en"; anything Nepali recommends "ne".
    assert det.detect_text("hello world").recommended_paddle_lang == "en"
    assert det.detect_text("तपाईं").recommended_paddle_lang == "ne"


# ------------------------------------------------------- image quality (offline)


def _write_image(path: Path, colour, size=(400, 300)) -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


def test_image_quality_metrics_and_recommendations(tmp_path: Path) -> None:
    # A flat mid-grey image: low blur variance, low contrast.
    img = _write_image(tmp_path / "flat.png", (128, 128, 128))
    m = ImageQualityAnalyzer().analyze_path(img)
    assert m.width == 400 and m.height == 300
    assert m.megapixels == pytest.approx(0.12, abs=0.01)
    assert m.is_low_contrast  # solid colour has zero contrast
    assert m.recommendations  # always gives at least one tip


def test_low_resolution_flagged(tmp_path: Path) -> None:
    img = _write_image(tmp_path / "small.png", (255, 255, 255), size=(200, 150))
    m = ImageQualityAnalyzer().analyze_path(img)
    assert m.low_resolution


def test_quality_never_rejects_bad_image() -> None:
    # Decoding failure yields metadata + a note, not an exception.
    m = ImageQualityAnalyzer().analyze_path("/nonexistent/does-not-exist.png")
    assert m.recommendations


# ------------------------------------------------------------ duplicate detect


def test_duplicate_detection_by_sha256(tmp_path: Path) -> None:
    a = _write_image(tmp_path / "a.png", (10, 20, 30))
    b = tmp_path / "b.png"
    b.write_bytes(a.read_bytes())            # byte-identical copy
    detector = DuplicateDetector(OCRForensicConfig())
    first = detector.check(a, evidence_id="EVID_1")
    second = detector.check(b, evidence_id="EVID_2")
    assert first.image_sha256 == second.image_sha256
    assert not first.is_duplicate
    assert second.is_duplicate and second.first_seen_evidence_id == "EVID_1"
    assert second.reused_ocr


def test_duplicate_disabled_still_hashes(tmp_path: Path) -> None:
    a = _write_image(tmp_path / "a.png", (1, 2, 3))
    detector = DuplicateDetector(OCRForensicConfig(dedup_enabled=False))
    info = detector.check(a, evidence_id="EVID_1")
    assert info.image_sha256 and not info.is_duplicate  # hash kept, no flagging


# --------------------------------------------------------- chat reconstruction


def test_chat_reconstruction_order_and_sides() -> None:
    pages = _pages([
        {"text": "hi there", "confidence": 0.9, "bbox": [[20, 20], [200, 20], [200, 50], [20, 50]]},
        {"text": "09:41", "confidence": 0.9, "bbox": [[20, 55], [80, 55], [80, 70], [20, 70]]},
        {"text": "hello back", "confidence": 0.9, "bbox": [[500, 100], [780, 100], [780, 130], [500, 130]]},
    ])
    chat = ChatReconstructor().reconstruct(pages, image_width=800)
    assert chat.is_chat_screenshot
    assert [m.text for m in chat.messages] == ["hi there", "hello back"]
    assert chat.messages[0].side == "left" and chat.messages[1].side == "right"
    assert chat.messages[0].timestamp == "09:41"     # timestamp attached
    assert chat.messages[1].sender == "me"           # right side => me


def test_non_chat_layout_not_flagged() -> None:
    # All left-aligned, no app hint -> not a chat.
    pages = _pages([
        {"text": "Invoice No 42", "confidence": 0.9, "bbox": [[10, 10], [200, 10], [200, 40], [10, 40]]},
        {"text": "Total 500", "confidence": 0.9, "bbox": [[10, 50], [200, 50], [200, 80], [10, 80]]},
        {"text": "Thank you", "confidence": 0.9, "bbox": [[10, 90], [200, 90], [200, 120], [10, 120]]},
    ])
    assert not ChatReconstructor().reconstruct(pages, image_width=800).is_chat_screenshot


# ------------------------------------------------------------------- timing


def test_timing_recorder_accumulates_and_totals() -> None:
    t = TimingRecorder()
    t.record("ocr", 100.0)
    t.record("cleaning", 25.0)
    t.record("ocr", 50.0)                    # accumulates
    metrics = t.to_metrics()
    assert metrics.ocr_ms == 150.0 and metrics.cleaning_ms == 25.0
    assert metrics.total_ms == 175.0


# --------------------------------------------------------- metadata generation


def test_full_metadata_bundle_and_bbox_traceability(tmp_path: Path) -> None:
    img = _write_image(tmp_path / "e.png", (240, 240, 240))
    pages = _pages([
        {"text": "Verify account", "confidence": 0.95, "bbox": [[5, 5], [90, 5], [90, 20], [5, 20]]},
        {"text": "OTP 4521", "confidence": 0.58, "bbox": [[5, 25], [90, 25], [90, 40], [5, 40]]},
    ])
    meta = OCRForensicAnalyzer().analyze(pages, image_path=img, evidence_id="EVID_9")
    payload = meta.model_dump()
    for key in ("ocr_engine", "ocr_version", "detected_language", "image_sha256",
                "confidence_statistics", "lines", "image_quality", "language",
                "timing", "duplicate", "chat", "warnings"):
        assert key in payload
    assert meta.ocr_version == "PP-OCRv5"
    assert meta.image_sha256                       # hash computed
    assert meta.confidence_statistics.count == 2
    # Bounding boxes are preserved and traceable to the original coordinates.
    assert meta.lines[0].bbox == [[5.0, 5.0], [90.0, 5.0], [90.0, 20.0], [5.0, 20.0]]
    assert meta.timing.forensic_analysis_ms >= 0.0


# ----------------------------------------------------------------- batch


def test_batch_processing_parallel_and_graceful(tmp_path: Path) -> None:
    for i in range(3):
        _write_image(tmp_path / f"img{i}.png", (i * 10, i * 10, i * 10))
    (tmp_path / "broken.png").write_bytes(b"not an image")

    def fake_ocr(path: Path):
        if path.name == "broken.png":
            raise ValueError("simulated OCR failure")
        return _pages([{"text": path.name, "confidence": 0.9, "bbox": [[0, 0], [1, 0], [1, 1], [0, 1]]}])

    seen = []
    report = BatchProcessor(fake_ocr, OCRForensicConfig(batch_workers=2)).process_folder(
        tmp_path, progress=lambda done, total, path: seen.append((done, total)))
    assert report.total == 4
    assert report.succeeded == 3 and report.failed == 1   # continues past failure
    assert any(not r.ok for r in report.results)
    assert seen and seen[-1][0] == 4                       # progress reported to completion


def test_batch_empty_folder(tmp_path: Path) -> None:
    report = BatchProcessor(lambda p: _pages([])).process_folder(tmp_path)
    assert report.total == 0 and report.results == []


# --------------------------------------------------------- config from env


def test_config_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCE_OCR_CONF_HIGH", "0.95")
    monkeypatch.setenv("EVIDENCE_OCR_DISCARD_LOW", "true")
    monkeypatch.setenv("EVIDENCE_OCR_WORKERS", "8")
    cfg = OCRForensicConfig.from_env()
    assert cfg.confidence_high == 0.95
    assert cfg.discard_low is True
    assert cfg.batch_workers == 8
