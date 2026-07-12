"""Tests for PDF page rendering."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.pdf_processor import PDFProcessor
from backend.modules.evidence.utils import CorruptedPDFError


def test_page_count_and_order(config: EvidenceConfig, sample_pdf: Path) -> None:
    processor = PDFProcessor(config)
    assert processor.page_count(sample_pdf) == 2
    pages = list(processor.iter_page_images(sample_pdf))
    assert [number for number, _ in pages] == [1, 2]  # strict page order


def test_pages_render_as_rgb_arrays(config: EvidenceConfig, sample_pdf: Path) -> None:
    processor = PDFProcessor(config)
    for _, image in processor.iter_page_images(sample_pdf):
        assert isinstance(image, np.ndarray)
        assert image.ndim == 3 and image.shape[2] == 3
        assert image.dtype == np.uint8
        assert image.shape[0] > 100 and image.shape[1] > 100


def test_corrupted_pdf_raises(config: EvidenceConfig, tmp_path: Path) -> None:
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.7 this is not really a pdf body")
    processor = PDFProcessor(config)
    with pytest.raises(CorruptedPDFError):
        list(processor.iter_page_images(bad))


def test_non_pdf_bytes_raise(config: EvidenceConfig, tmp_path: Path) -> None:
    bad = tmp_path / "fake.pdf"
    bad.write_bytes(b"\x00\x01\x02 nothing pdf about this")
    with pytest.raises(CorruptedPDFError):
        PDFProcessor(config).page_count(bad)
