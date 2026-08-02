"""Large images must be OCR'd in bands, not in one oversized call.

PaddleOCR's cost grows much faster than linearly with pixel count, and past
roughly 2 MP it segfaults on some builds (Apple Silicon), killing the host
process - a scanned-PDF page took the whole API server down. Splitting the
image into overlapping horizontal bands keeps every call inside the fast,
stable region *at full resolution*; downscaling instead would shrink the text.

These tests exercise the geometry and merge logic directly, so they run
without PaddleOCR installed and without OCR-ing anything.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.models import OCRLine
from backend.modules.evidence.paddle_service import PaddleOCRService


def _service(**overrides) -> PaddleOCRService:
    """A service instance without touching PaddleOCR (never OCRs here)."""
    service = PaddleOCRService.__new__(PaddleOCRService)
    service._cfg = EvidenceConfig(**overrides)
    return service


def _image(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def _box(x: float, y: float, w: float = 100.0, h: float = 20.0):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


# ------------------------------------------------------------------ geometry
def test_small_images_are_left_alone():
    """The common case (a screenshot) must take the unchanged single call."""
    service = _service()
    image = _image(760, 620)                      # 0.47 MP

    bands = service._split_for_ocr(image)

    assert len(bands) == 1
    assert bands[0][0] == 0
    assert bands[0][1] is image, "small images must not be copied or altered"


@pytest.mark.parametrize(
    "width,height",
    [(1223, 1658),   # the scanned PDF page that segfaulted
     (720, 2183),    # a long chat screenshot
     (2000, 2000)],  # a phone photo
)
def test_every_band_fits_the_pixel_budget(width, height):
    """Including its overlap - sizing before overlap silently blows the budget.

    That mistake is not benign: because the cost curve is steep, bands that
    are slightly too large measured 266s where correctly sized ones took 77s.
    """
    service = _service()
    budget = service._cfg.ocr_max_pixels

    bands = service._split_for_ocr(_image(width, height))

    assert len(bands) > 1
    for _, band in bands:
        assert band.shape[0] * band.shape[1] <= budget


def test_bands_cover_the_whole_image_and_overlap():
    """No horizontal strip may fall between two bands."""
    service = _service()
    height = 2183
    bands = service._split_for_ocr(_image(720, height))

    covered_to = 0
    for top, band in bands:
        assert top <= covered_to, f"gap: band starts at {top}, covered to {covered_to}"
        covered_to = max(covered_to, top + band.shape[0])
    assert covered_to == height, "bands must reach the bottom of the image"


def test_bands_are_contiguous_arrays():
    """Paddle reads the buffer directly; a sliced view can crash it."""
    service = _service()
    for _, band in service._split_for_ocr(_image(1223, 1658)):
        assert band.flags["C_CONTIGUOUS"]


# --------------------------------------------------------------------- merge
def test_band_local_boxes_are_translated_back():
    service = _service()
    line = OCRLine(text="9847011223", confidence=0.9, bbox=_box(10, 5))

    moved = service._offset_line(line, 800)

    assert [p[1] for p in moved.bbox] == [805, 805, 825, 825]
    assert moved.text == "9847011223" and moved.confidence == 0.9


def test_overlap_duplicates_are_merged_keeping_the_better_read():
    """The same line read by two bands is rarely byte-identical.

    Keying de-duplication on text would let both spellings through and
    duplicate the content, so identity is positional.
    """
    service = _service()
    lines = [
        # Same physical line seen by two bands: a couple of pixels apart, and
        # the weaker band misread a character.
        OCRLine(text="Actve now", confidence=0.71, bbox=_box(41, 302)),
        OCRLine(text="Active now", confidence=0.93, bbox=_box(40, 300)),
    ]

    merged = service._deduplicate(lines)

    assert len(merged) == 1
    assert merged[0].text == "Active now", "the higher-confidence read must win"


def test_near_duplicates_straddling_a_boundary_still_merge():
    """Regression: bucketing positions let these two through as separate lines.

    Centres of 310 and 312 fall either side of a 16px bucket edge, so the
    duplicate survived and the text was reported twice.
    """
    service = _service()
    lines = [
        OCRLine(text="9847011223", confidence=0.80, bbox=_box(40, 300)),
        OCRLine(text="9847011223", confidence=0.85, bbox=_box(40, 302)),
    ]

    assert len(service._deduplicate(lines)) == 1


def test_distinct_lines_are_not_merged():
    """Different text at genuinely different places must both survive."""
    service = _service()
    lines = [
        OCRLine(text="NPR 200", confidence=0.9, bbox=_box(40, 300)),
        OCRLine(text="NPR 5000", confidence=0.9, bbox=_box(40, 900)),   # far below
        OCRLine(text="9847011223", confidence=0.9, bbox=_box(600, 300)),  # same row
    ]

    merged = service._deduplicate(lines)

    assert {line.text for line in merged} == {"NPR 200", "NPR 5000", "9847011223"}


def test_merged_lines_come_back_in_reading_order():
    service = _service()
    lines = [
        OCRLine(text="third", confidence=0.9, bbox=_box(0, 900)),
        OCRLine(text="first", confidence=0.9, bbox=_box(0, 100)),
        OCRLine(text="second", confidence=0.9, bbox=_box(0, 500)),
    ]

    assert [l.text for l in service._deduplicate(lines)] == ["first", "second", "third"]
