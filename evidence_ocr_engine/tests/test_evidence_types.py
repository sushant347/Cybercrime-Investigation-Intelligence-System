"""Per-type evidence extraction: PDF (digital + scanned), URL, text, image.

The pipeline must pick the *right* extractor for each evidence type:

* digital PDF  -> read the embedded text layer verbatim (never OCR: OCR of a
  text PDF is slower and strictly less accurate),
* scanned PDF  -> render each page and OCR it,
* URL          -> read the link verbatim (no OCR),
* txt/csv      -> read verbatim,
* image        -> preprocess + OCR.

A recording fake OCR proves whether OCR ran, without the cost of PaddleOCR.
"""

from __future__ import annotations

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.models import EvidenceRecord, OCRLine
from backend.modules.evidence.pipeline import EvidencePipeline

fitz = pytest.importorskip("fitz", reason="PyMuPDF required for PDF evidence")


class RecordingOCR:
    """Fake OCR that records how many pages it was asked to read."""

    name = "fake-ocr"

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image):  # noqa: ARG002 - image content is irrelevant
        self.calls += 1
        return [OCRLine(text="OCR_TEXT_FROM_IMAGE", confidence=0.9)]


def _record(name: str, extension: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="EVID_T", case_id="CASE_T", original_file_name=name,
        stored_file_name=name, file_extension=extension,
        file_size_bytes=1, sha256_before="a" * 64,
    )


@pytest.fixture()
def pipeline(config: EvidenceConfig):
    ocr = RecordingOCR()
    return EvidencePipeline(config, ocr), ocr


def _digital_pdf(path, pages=("Contact 9812345678 at http://scam.top/login",)):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 100), text)
    doc.save(str(path))
    doc.close()
    return path


def _scanned_pdf(path, image_path):
    """A PDF whose page is a bare image — no text layer at all."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_image(fitz.Rect(0, 0, 400, 300), filename=str(image_path))
    doc.save(str(path))
    doc.close()
    return path


# ------------------------------------------------------------------- PDF
def test_digital_pdf_uses_text_layer_and_never_ocrs(pipeline, tmp_path):
    pipe, ocr = pipeline
    pdf = _digital_pdf(tmp_path / "digital.pdf")

    pages = pipe._extract_pdf(pdf, _record("digital.pdf", ".pdf"))

    assert ocr.calls == 0, "OCR must not run on a PDF that has a text layer"
    assert len(pages) == 1
    assert pages[0].preprocessing_steps == ["none(pdf_text_layer)"]
    body = " ".join(line.text for line in pages[0].lines)
    assert "9812345678" in body and "scam.top" in body
    assert all(line.confidence == 1.0 for line in pages[0].lines)


def test_multi_page_digital_pdf_keeps_page_order(pipeline, tmp_path):
    pipe, ocr = pipeline
    pdf = _digital_pdf(
        tmp_path / "multi.pdf",
        pages=("PAGE ONE about 9811111111", "PAGE TWO about 9822222222"),
    )
    pages = pipe._extract_pdf(pdf, _record("multi.pdf", ".pdf"))

    assert ocr.calls == 0
    assert [p.page_number for p in pages] == [1, 2]
    assert "PAGE ONE" in " ".join(l.text for l in pages[0].lines)
    assert "PAGE TWO" in " ".join(l.text for l in pages[1].lines)


def test_scanned_pdf_falls_back_to_ocr(pipeline, tmp_path, sample_image):
    """A page with no text layer must still be read — via render + OCR."""
    pipe, ocr = pipeline
    pdf = _scanned_pdf(tmp_path / "scanned.pdf", sample_image)

    pages = pipe._extract_pdf(pdf, _record("scanned.pdf", ".pdf"))

    assert ocr.calls == 1, "scanned page must be OCR'd"
    assert len(pages) == 1
    assert "OCR_TEXT_FROM_IMAGE" in " ".join(l.text for l in pages[0].lines)


# ------------------------------------------------------------------- URL
def test_url_evidence_is_read_verbatim(pipeline, tmp_path):
    pipe, ocr = pipeline
    link = tmp_path / "link.url"
    link.write_text("http://nabil-verify.scam.top/login?id=99\n", encoding="utf-8")

    pages = pipe._extract_pages(link, _record("link.url", ".url"))

    assert ocr.calls == 0, "a URL is text — it must not be OCR'd"
    assert len(pages) == 1
    assert pages[0].preprocessing_steps == ["none(url)"]
    assert "nabil-verify.scam.top" in pages[0].lines[0].text


def test_url_extension_is_a_supported_evidence_type(config):
    assert ".url" in config.supported_extensions


# ------------------------------------------------------- text + dispatch
def test_plain_text_is_read_verbatim(pipeline, tmp_path):
    pipe, ocr = pipeline
    txt = tmp_path / "chat.txt"
    txt.write_text("line one\nline two\n", encoding="utf-8")

    pages = pipe._extract_pages(txt, _record("chat.txt", ".txt"))

    assert ocr.calls == 0
    assert [l.text for l in pages[0].lines] == ["line one", "line two"]


def test_image_still_goes_through_ocr(pipeline, sample_image):
    pipe, ocr = pipeline
    pages = pipe._extract_pages(sample_image, _record("x.png", ".png"))

    assert ocr.calls == 1, "images must still be OCR'd"
    assert "OCR_TEXT_FROM_IMAGE" in " ".join(l.text for l in pages[0].lines)
