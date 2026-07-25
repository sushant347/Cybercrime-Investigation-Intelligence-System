"""PDF evidence support.

Each PDF page is rendered to an RGB image at a configurable DPI, processed
separately through preprocessing + OCR, and results are merged in strict page
order with page numbers preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import numpy as np

from .config import EvidenceConfig
from .logger import get_logger
from .utils import CorruptedPDFError


class PDFProcessor:
    """Renders PDF pages to images using PyMuPDF (no external binaries)."""

    def __init__(self, config: EvidenceConfig) -> None:
        self._cfg = config
        self._log = get_logger("pdf")

    def page_count(self, path: Path | str) -> int:
        """Number of pages, raising :class:`CorruptedPDFError` for bad files."""
        doc = self._open(path)
        try:
            return doc.page_count
        finally:
            doc.close()

    def iter_page_text(self, path: Path | str) -> Iterator[Tuple[int, str]]:
        """Yield ``(page_number, text)`` from the PDF's embedded text layer.

        Digital (non-scanned) PDFs carry their text verbatim, so reading it is
        both faster and exact - OCR on such a page can only introduce errors.
        Pages without a text layer (scanned images) yield an empty string and
        must be rendered and OCR'd instead; see :meth:`iter_page_images`.
        """
        doc = self._open(path)
        try:
            total = min(doc.page_count, self._cfg.pdf_max_pages)
            for index in range(total):
                try:
                    text = doc.load_page(index).get_text() or ""
                except Exception as exc:  # noqa: BLE001 - one bad page is not fatal
                    self._log.warning("page %d text extraction failed: %s", index + 1, exc)
                    text = ""
                yield index + 1, text
        finally:
            doc.close()

    def iter_page_images(self, path: Path | str) -> Iterator[Tuple[int, np.ndarray]]:
        """Yield ``(page_number, rgb_image)`` for every page, in order.

        Page numbers are 1-based. Rendering one page at a time keeps memory
        bounded for large scanned PDFs.

        Raises:
            CorruptedPDFError: If the PDF cannot be opened or a page fails
                to render.
        """
        doc = self._open(path)
        try:
            total = min(doc.page_count, self._cfg.pdf_max_pages)
            if doc.page_count > self._cfg.pdf_max_pages:
                self._log.warning(
                    "PDF has %d pages; processing first %d (pdf_max_pages)",
                    doc.page_count, self._cfg.pdf_max_pages,
                )
            zoom = self._cfg.pdf_render_dpi / 72.0
            for index in range(total):
                try:
                    import fitz  # PyMuPDF

                    page = doc.load_page(index)
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )
                    if pixmap.n == 4:  # drop alpha channel if present
                        image = image[:, :, :3]
                    self._log.debug(
                        "rendered page %d/%d (%dx%d @ %d dpi)",
                        index + 1, total, pixmap.width, pixmap.height,
                        self._cfg.pdf_render_dpi,
                    )
                    yield index + 1, np.ascontiguousarray(image)
                except Exception as exc:  # noqa: BLE001 - normalise per-page failures
                    raise CorruptedPDFError(
                        f"Failed to render page {index + 1} of '{path}': {exc}"
                    ) from exc
        finally:
            doc.close()

    # ---------------------------------------------------------------- internal

    def _open(self, path: Path | str):  # type: ignore[no-untyped-def]
        """Open the PDF, translating library errors to :class:`CorruptedPDFError`."""
        try:
            import fitz  # PyMuPDF - imported lazily (optional at test time)

            doc = fitz.open(str(path))
            if doc.is_encrypted and not doc.authenticate(""):
                doc.close()
                raise CorruptedPDFError(f"PDF '{path}' is password-protected")
            # Trigger parsing of the page tree to surface corruption early.
            _ = doc.page_count
            return doc
        except CorruptedPDFError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CorruptedPDFError(f"Cannot open PDF '{path}': {exc}") from exc
