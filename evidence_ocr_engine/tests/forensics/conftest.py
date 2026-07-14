"""Fixtures for the Phase-1 forensics test suite.

Everything runs against a temp directory; no real OCR backend is required
(fake adapters prove the fusion engine is adapter-agnostic).
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.models import OCRLine
from backend.modules.evidence.forensics.audit import ForensicAuditTrail
from backend.modules.evidence.forensics.config import ForensicsConfig
from backend.modules.evidence.forensics.repository import ForensicReportRepository
from backend.modules.evidence.forensics.multi_ocr.engines import OCREngineAdapter


class FakeAdapter(OCREngineAdapter):
    """Deterministic fusion-engine double."""

    def __init__(self, key: str, lines: List[OCRLine], is_available: bool = True) -> None:
        self.key = key
        self._lines = lines
        self._available = is_available
        self.calls = 0

    @property
    def available(self) -> bool:
        return self._available

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        self.calls += 1
        return list(self._lines)


class FailingAdapter(OCREngineAdapter):
    key = "failing"

    @property
    def available(self) -> bool:
        return True

    def recognize(self, image: np.ndarray) -> List[OCRLine]:  # noqa: ARG002
        raise RuntimeError("engine crashed")


@pytest.fixture()
def fcfg(config: EvidenceConfig) -> ForensicsConfig:
    forensics = ForensicsConfig.from_evidence_config(config)
    forensics.ensure_directories()
    return forensics


@pytest.fixture()
def repo(fcfg: ForensicsConfig) -> ForensicReportRepository:
    return ForensicReportRepository(fcfg)


@pytest.fixture()
def audit(fcfg: ForensicsConfig) -> ForensicAuditTrail:
    return ForensicAuditTrail(fcfg)


@pytest.fixture()
def text_image() -> np.ndarray:
    """Clean synthetic document: white page with dark text-like strokes."""
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    for row in range(12):
        y = 60 + row * 65
        for col in range(14):
            x = 60 + col * 80
            draw.rectangle([x, y, x + 52, y + 16], fill=(20, 20, 20))
    return np.asarray(img)


@pytest.fixture()
def poor_image() -> np.ndarray:
    """Small, dark, noisy, low-contrast capture."""
    rng = np.random.default_rng(42)
    base = np.full((240, 320, 3), 55, dtype=np.uint8)
    noise = rng.integers(-35, 35, size=base.shape, dtype=np.int16)
    return np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)


@pytest.fixture()
def brand_image() -> np.ndarray:
    """Screenshot-like image with a large eSewa-green header bar."""
    img = np.full((800, 480, 3), 245, dtype=np.uint8)
    img[0:90, :] = (96, 187, 70)  # eSewa green (RGB)
    return img


def make_lines(*texts_confidences) -> List[OCRLine]:
    return [OCRLine(text=t, confidence=c) for t, c in texts_confidences]
