"""Shared pytest fixtures.

Tests never require PaddleOCR: a deterministic :class:`FakeOCR` implements
:class:`BaseOCR`, which also proves that the pipeline is engine-agnostic
(Dependency Injection working as designed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402
from backend.modules.evidence.models import OCRLine  # noqa: E402
from backend.modules.evidence.ocr_interface import BaseOCR  # noqa: E402


class FakeOCR(BaseOCR):
    """Deterministic OCR double returning fixed lines for every image."""

    name = "fake-ocr"

    def __init__(self, lines: List[OCRLine] | None = None) -> None:
        self.calls = 0
        self._lines = lines if lines is not None else [
            OCRLine("Dear customer your account is suspended", 0.97,
                    [[10.0, 10.0], [400.0, 10.0], [400.0, 40.0], [10.0, 40.0]]),
            OCRLine("Click http://fake-bank.example to verify", 0.93,
                    [[10.0, 50.0], [420.0, 50.0], [420.0, 80.0], [10.0, 80.0]]),
        ]

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        self.calls += 1
        return list(self._lines)


class EmptyOCR(BaseOCR):
    """OCR double simulating an image with no recognisable text."""

    name = "empty-ocr"

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        return []


@pytest.fixture()
def config(tmp_path: Path) -> EvidenceConfig:
    """Isolated configuration: all storage lives under a temp directory."""
    storage = tmp_path / "storage"
    cfg = EvidenceConfig(
        base_dir=tmp_path,
        storage_dir=storage,
        json_dir=storage / "json",
        originals_dir=storage / "originals",
        log_dir=tmp_path / "logs",
        cases_csv=storage / "cases.csv",
        evidence_csv=storage / "evidence.csv",
        ocr_results_csv=storage / "ocr_results.csv",
        processing_log_csv=storage / "processing_log.csv",
    )
    cfg.ensure_directories()
    return cfg


@pytest.fixture()
def fake_ocr() -> FakeOCR:
    return FakeOCR()


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """A small PNG containing rendered text (screenshot-like evidence)."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), "Dear customer your account is suspended", fill="black")
    draw.text((20, 90), "Click http://fake-bank.example to verify", fill="black")
    path = tmp_path / "phishing_screenshot.png"
    img.save(path)
    return path


@pytest.fixture()
def sample_text_file(tmp_path: Path) -> Path:
    path = tmp_path / "chat_export.txt"
    path.write_text(
        "[2026-01-04 09:12] scammer: send Rs 50000 to esewa id 98xxxx\n"
        "[2026-01-04 09:13] victim: kina? / किन?\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Two-page PDF built with PyMuPDF (each page has distinct text)."""
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "scam_report.pdf"
    doc = fitz.open()
    for number in (1, 2):
        page = doc.new_page()
        page.insert_text((72, 100), f"Evidence page {number}: fraudulent transfer")
    doc.save(str(path))
    doc.close()
    return path
