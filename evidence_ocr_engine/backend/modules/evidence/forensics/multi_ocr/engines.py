"""OCR engine adapters for the Multi-OCR Fusion Engine.

Each adapter wraps one engine behind the small :class:`OCREngineAdapter`
contract (which itself builds on the existing :class:`~...ocr_interface.BaseOCR`
line model). Engines are **optional**: when a backend library is not
installed the adapter reports ``available == False`` and the fusion engine
simply runs with the engines that exist. The original
:class:`~...paddle_service.PaddleOCRService` is reused verbatim - it is
wrapped, never modified.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

import numpy as np

from ...config import EvidenceConfig
from ...logger import get_logger
from ...models import OCRLine
from ...ocr_interface import BaseOCR
from ..config import ForensicsConfig


class OCREngineAdapter(ABC):
    """Contract every fusion engine satisfies (Open/Closed: add engines by
    writing a new adapter, nothing else changes)."""

    #: Stable identifier used in reports ("paddleocr" | "easyocr" | "tesseract").
    key: str = "base"

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether the backing library/binary is importable and usable."""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        """Run OCR on an RGB image, returning verbatim lines with confidence."""


class PaddleOCRAdapter(OCREngineAdapter):
    """Wraps the existing (unmodified) PaddleOCR service or any BaseOCR."""

    key = "paddleocr"

    def __init__(
        self,
        evidence_config: EvidenceConfig,
        engine: Optional[BaseOCR] = None,
    ) -> None:
        """``engine`` may be injected (e.g. an already-warm PaddleOCRService,
        or a fake in tests); otherwise it is created lazily on first use."""
        self._cfg = evidence_config
        self._engine: Optional[BaseOCR] = engine
        self._log = get_logger("forensics.ocr.paddle")
        self._import_error: Optional[str] = None

    @property
    def available(self) -> bool:
        if self._engine is not None:
            return True
        try:
            import paddleocr  # noqa: F401
            return True
        except Exception as exc:  # noqa: BLE001 - any import failure counts
            self._import_error = str(exc)
            return False

    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        if self._engine is None:
            from ...paddle_service import PaddleOCRService  # reuse, never modify
            self._engine = PaddleOCRService(self._cfg)
        return self._engine.recognize(image)


class EasyOCRAdapter(OCREngineAdapter):
    """EasyOCR backend (optional dependency ``easyocr``)."""

    key = "easyocr"

    def __init__(self, config: ForensicsConfig, reader: Any = None) -> None:
        self._cfg = config
        self._reader = reader  # injectable for tests
        self._log = get_logger("forensics.ocr.easyocr")

    @property
    def available(self) -> bool:
        if self._reader is not None:
            return True
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        reader = self._get_reader()
        results = reader.readtext(image)  # [(bbox, text, confidence), ...]
        lines: List[OCRLine] = []
        for bbox, text, confidence in results:
            if confidence < self._cfg.ocr_min_line_confidence or not text.strip():
                continue
            lines.append(OCRLine(
                text=text,
                confidence=float(confidence),
                bbox=[[float(x), float(y)] for x, y in bbox],
            ))
        return lines

    def _get_reader(self) -> Any:
        if self._reader is None:
            import easyocr
            # EasyOCR cannot mix Devanagari ("ne") with some latin packs in
            # every version; fall back to English-only if the combo fails.
            try:
                self._reader = easyocr.Reader(
                    list(self._cfg.easyocr_languages), gpu=False, verbose=False
                )
            except Exception:  # noqa: BLE001
                self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self._reader


class TesseractAdapter(OCREngineAdapter):
    """Tesseract backend via ``pytesseract`` (optional dependency + binary)."""

    key = "tesseract"

    def __init__(self, config: ForensicsConfig, pytesseract_module: Any = None) -> None:
        self._cfg = config
        self._pt = pytesseract_module  # injectable for tests
        self._log = get_logger("forensics.ocr.tesseract")

    @property
    def available(self) -> bool:
        if self._pt is not None:
            return True
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:  # noqa: BLE001 - missing module or binary
            return False

    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        pt = self._pt
        if pt is None:
            import pytesseract as pt  # type: ignore[no-redef]
        lang = self._resolve_lang(pt)
        config = f"--psm {self._cfg.tesseract_psm}"
        data = pt.image_to_data(
            image, lang=lang, config=config, output_type=pt.Output.DICT
        )
        return self._group_words_into_lines(data)

    # ---------------------------------------------------------------- helpers

    def _resolve_lang(self, pt: Any) -> str:
        """Use configured languages, dropping packs that are not installed."""
        wanted = self._cfg.tesseract_languages.split("+")
        try:
            installed = set(pt.get_languages(config=""))
            usable = [lang for lang in wanted if lang in installed]
            return "+".join(usable) if usable else "eng"
        except Exception:  # noqa: BLE001
            return "eng"

    def _group_words_into_lines(self, data: dict) -> List[OCRLine]:
        """Aggregate word-level TSV output into line-level OCRLine records."""
        lines: dict = {}
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            x, y = float(data["left"][i]), float(data["top"][i])
            w, h = float(data["width"][i]), float(data["height"][i])
            entry = lines.setdefault(key, {"words": [], "confs": [], "boxes": []})
            entry["words"].append(text)
            entry["confs"].append(conf / 100.0)
            entry["boxes"].append((x, y, x + w, y + h))
        result: List[OCRLine] = []
        for key in sorted(lines):
            entry = lines[key]
            confidence = float(np.mean(entry["confs"])) if entry["confs"] else 0.0
            if confidence < self._cfg.ocr_min_line_confidence:
                continue
            x0 = min(b[0] for b in entry["boxes"])
            y0 = min(b[1] for b in entry["boxes"])
            x1 = max(b[2] for b in entry["boxes"])
            y1 = max(b[3] for b in entry["boxes"])
            result.append(OCRLine(
                text=" ".join(entry["words"]),
                confidence=confidence,
                bbox=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
            ))
        return result
