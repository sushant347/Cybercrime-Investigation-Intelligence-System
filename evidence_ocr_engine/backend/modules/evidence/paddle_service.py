"""PaddleOCR 3.x implementation of :class:`BaseOCR`.

Supports multilingual recognition (English, Nepali/Devanagari, and mixed
scripts in the same image) via PaddleOCR's multilingual Devanagari model
(selected through the official language code ``"ne"``). Text is returned
exactly as recognised - never translated or autocorrected.

PaddleOCR is imported lazily so the rest of the module (upload, hashing,
storage, tests) works on machines where Paddle is not installed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Dict, List, Optional

import numpy as np

from .config import EvidenceConfig
from .logger import get_logger
from .models import OCRLine
from .ocr_interface import BaseOCR
from .utils import EvidenceError, OCRTimeoutError

#: Common aliases mapped to official PaddleOCR 3.x language identifiers.
#: PaddleOCR 3.x accepts concrete language codes only - script-group names
#: such as "devanagari" raise ``ValueError: No models are available for
#: lang='devanagari' and ocr_version=None``. Nepali is ``"ne"``, which maps
#: internally to the multilingual devanagari recognition model (Devanagari +
#: Latin dictionary => English, Nepali and mixed English+Nepali evidence).
_LANG_ALIASES: Dict[str, str] = {
    "devanagari": "ne",
    "nepali": "ne",
    "np": "ne",
    "english": "en",
    "hindi": "hi",
}


#: The only OCR model generation this engine supports.
SUPPORTED_OCR_VERSION = "PP-OCRv5"


class PaddleOCRService(BaseOCR):
    """OCR engine backed by PaddleOCR >= 3.0, pinned to the PP-OCRv5 pipeline.

    PP-OCRv5 is the sole supported model generation: ``PP-OCRv5_server_det``
    for detection and the multilingual ``devanagari_PP-OCRv5_mobile_rec``
    recogniser for ``lang="ne"`` (Devanagari + Latin), or ``en_PP-OCRv5_mobile_rec``
    for ``lang="en"``. Any other requested version is rejected.

    Args:
        config: Engine configuration (language, model version, timeout).
        lang: Optional language override; defaults to ``config.ocr_lang``.
            Use ``"ne"`` for Nepali / mixed Nepali+English evidence and
            ``"en"`` for English-only evidence.
        ocr_version: Optional override; must be ``"PP-OCRv5"`` (the default).
    """

    name = "paddleocr-v5"

    def __init__(
        self,
        config: EvidenceConfig,
        lang: Optional[str] = None,
        ocr_version: Optional[str] = None,
    ) -> None:
        self._cfg = config
        self._log = get_logger("ocr.paddle")
        self._lang = self._resolve_lang(lang or config.ocr_lang)
        self._ocr_version = self._resolve_version(ocr_version or config.ocr_version)
        self._engine: Any = None  # created lazily on first use

    def _resolve_version(self, version: Optional[str]) -> str:
        """Enforce PP-OCRv5. Reject any other generation (v5-only engine)."""
        resolved = version or SUPPORTED_OCR_VERSION
        if resolved != SUPPORTED_OCR_VERSION:
            raise EvidenceError(
                f"Unsupported OCR version {resolved!r}; this engine uses only "
                f"{SUPPORTED_OCR_VERSION}."
            )
        return resolved

    # ------------------------------------------------------------------ public

    def warmup(self) -> None:
        """Instantiate the Paddle pipeline (downloads models on first run)."""
        self._get_engine()

    def recognize(self, image: np.ndarray) -> List[OCRLine]:
        """Recognise text with a hard timeout, returning verbatim lines."""
        engine = self._get_engine()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._predict, engine, image)
            try:
                lines = future.result(timeout=self._cfg.ocr_timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                raise OCRTimeoutError(
                    f"PaddleOCR exceeded {self._cfg.ocr_timeout_seconds:.0f}s timeout"
                ) from exc
        for line in lines:
            if line.confidence < self._cfg.low_confidence_threshold:
                self._log.warning(
                    "low-confidence line (%.2f): %r", line.confidence, line.text[:80]
                )
        return lines

    # ---------------------------------------------------------------- internal

    def _resolve_lang(self, lang: str) -> str:
        """Translate common aliases to official PaddleOCR language codes."""
        resolved = _LANG_ALIASES.get(lang.strip().lower(), lang.strip())
        if resolved != lang:
            self._log.warning(
                "OCR language %r is not an official PaddleOCR identifier; "
                "using %r instead", lang, resolved,
            )
        return resolved

    def _get_engine(self) -> Any:
        """Lazily build the PaddleOCR pipeline (heavy import + model load)."""
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR  # local import: optional dependency
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise EvidenceError(
                    "PaddleOCR is not installed. Run: pip install paddleocr paddlepaddle"
                ) from exc
            self._log.info(
                "initialising PaddleOCR (lang=%s, ocr_version=%s)",
                self._lang, self._ocr_version,
            )
            # Document orientation/unwarping are disabled because our own
            # preprocessing layer already handles orientation, deskew and
            # perspective correction (single-responsibility, no double work).
            # lang="ne" + PP-OCRv5 -> PP-OCRv5_server_det +
            # devanagari_PP-OCRv5_mobile_rec (the only generation with a
            # Devanagari recogniser; PP-OCRv6 has no Devanagari model, so v5 is
            # the best fit for this Nepali-first forensic pipeline).
            self._engine = PaddleOCR(
                lang=self._lang,
                ocr_version=self._ocr_version,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
            self._log.info("PaddleOCR ready")
        return self._engine

    def _predict(self, engine: Any, image: np.ndarray) -> List[OCRLine]:
        """Call the engine and normalise its output into :class:`OCRLine`s."""
        raw = engine.predict(image)  # PaddleOCR 3.x API
        lines: List[OCRLine] = []
        for result in raw or []:
            lines.extend(self._parse_result(result))
        return lines

    def _parse_result(self, result: Any) -> List[OCRLine]:
        """Parse one PaddleOCR 3.x result object.

        3.x results behave like mappings with ``rec_texts``, ``rec_scores``
        and ``rec_polys`` keys. Access is defensive so minor upstream changes
        do not break evidence processing.
        """
        texts = self._get_field(result, "rec_texts") or []
        scores = self._get_field(result, "rec_scores") or []
        polys = self._get_field(result, "rec_polys")
        if polys is None:
            polys = self._get_field(result, "dt_polys") or []

        lines: List[OCRLine] = []
        for index, text in enumerate(texts):
            confidence = float(scores[index]) if index < len(scores) else 0.0
            bbox = self._poly_to_list(polys[index]) if index < len(polys) else []
            # Text stored verbatim - no strip/translate/autocorrect.
            lines.append(OCRLine(text=str(text), confidence=confidence, bbox=bbox))
        return lines

    @staticmethod
    def _get_field(result: Any, key: str) -> Any:
        """Read ``key`` from a mapping-like or attribute-style result object."""
        try:
            return result[key]
        except (TypeError, KeyError, IndexError):
            return getattr(result, key, None)

    @staticmethod
    def _poly_to_list(poly: Any) -> List[List[float]]:
        """Convert a polygon (numpy array or nested list) to ``[[x, y] x4]``."""
        array = np.asarray(poly, dtype=float)
        return [[float(x), float(y)] for x, y in array.reshape(-1, 2)]
