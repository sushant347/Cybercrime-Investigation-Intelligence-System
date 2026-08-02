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
        """Recognise text with a hard timeout, returning verbatim lines.

        Large images are OCR'd as overlapping horizontal bands rather than in
        one call. Paddle's cost grows sharply faster than linearly with pixel
        count, and past roughly 2 MP it segfaults outright on some builds
        (notably Apple Silicon), taking the whole host process down. Splitting
        keeps every call inside the safe, fast region *at full resolution* -
        downscaling instead would shrink the text and cost accuracy.
        """
        bands = self._split_for_ocr(image)
        if len(bands) == 1:
            lines = self._recognize_one(image)
        else:
            self._log.info(
                "image %dx%d (%.2f MP) exceeds the %.2f MP OCR budget; "
                "reading it as %d overlapping bands",
                image.shape[1], image.shape[0],
                (image.shape[0] * image.shape[1]) / 1e6,
                self._cfg.ocr_max_pixels / 1e6, len(bands),
            )
            collected: List[OCRLine] = []
            for top, band in bands:
                for line in self._recognize_one(band):
                    collected.append(self._offset_line(line, top))
            lines = self._deduplicate(collected)
        for line in lines:
            if line.confidence < self._cfg.low_confidence_threshold:
                self._log.warning(
                    "low-confidence line (%.2f): %r", line.confidence, line.text[:80]
                )
        return lines

    # ------------------------------------------------------------- tiling

    def _split_for_ocr(self, image: np.ndarray) -> List[tuple]:
        """Split into ``(top_offset, band)`` pairs that each fit the budget.

        Returns a single ``(0, image)`` pair when the image already fits, so
        the common case (a screenshot) is completely unaffected. Bands overlap
        so a text line falling on a cut is still read whole by one of them.
        """
        height, width = image.shape[:2]
        budget = max(1, int(self._cfg.ocr_max_pixels))
        if height * width <= budget or height < 2:
            return [(0, image)]
        # Size the bands so that each one *including its overlap* fits the
        # budget. Sizing before adding overlap pushes every band back over the
        # limit, and because the cost curve is steep that is not a small miss:
        # it measured 266s instead of 85s on a 2 MP page.
        rows_per_band = max(1, budget // max(1, width))
        overlap = min(self._cfg.ocr_band_overlap_px, max(0, (rows_per_band - 1) // 2))
        step = max(1, rows_per_band - 2 * overlap)
        band_count = int(np.ceil(height / step))
        bands: List[tuple] = []
        for index in range(band_count):
            top = max(0, index * step - (overlap if index else 0))
            bottom = min(height, (index + 1) * step + overlap)
            if bottom - top <= 0:
                continue
            bands.append((top, np.ascontiguousarray(image[top:bottom])))
            if bottom >= height:
                break
        return bands or [(0, image)]

    @staticmethod
    def _offset_line(line: OCRLine, top: int) -> OCRLine:
        """Translate a band-local box back into whole-image coordinates."""
        if not line.bbox or not top:
            return line
        return OCRLine(
            text=line.text,
            confidence=line.confidence,
            bbox=[[x, y + top] for x, y in line.bbox],
        )

    @staticmethod
    def _centre(line: OCRLine) -> Optional[tuple]:
        """Centre point of a line's box, or ``None`` when it has no box."""
        if not line.bbox:
            return None
        xs = [point[0] for point in line.bbox]
        ys = [point[1] for point in line.bbox]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def _deduplicate(self, lines: List[OCRLine]) -> List[OCRLine]:
        """Drop lines the overlap made us read twice, keeping the best read.

        Matching is by *position*, not text: a line inside the overlap is read
        by both bands and the two reads are rarely byte-identical ("Active now"
        vs "Actve now"), so keying on text would let both through and duplicate
        the content. Its coordinates, though, agree to within a few pixels.

        Positions are compared by proximity rather than bucketed, because two
        nearly-identical coordinates can fall either side of a bucket boundary
        (310 and 312 do) and the duplicate then survives. The line count is in
        the tens, so the pairwise scan costs nothing.

        Order is preserved top-to-bottom, so the reconstructed text still reads
        in document order.
        """
        x_tolerance, y_tolerance = 24.0, 16.0
        kept: List[OCRLine] = []
        centres: List[Optional[tuple]] = []
        for line in lines:
            centre = self._centre(line)
            match = -1
            if centre is not None:
                for index, other in enumerate(centres):
                    if (other is not None
                            and abs(other[0] - centre[0]) <= x_tolerance
                            and abs(other[1] - centre[1]) <= y_tolerance):
                        match = index
                        break
            if match < 0:
                kept.append(line)
                centres.append(centre)
            elif line.confidence > kept[match].confidence:
                kept[match] = line          # keep the better of the two reads
                centres[match] = centre

        def _top(line: OCRLine) -> float:
            return min((point[1] for point in line.bbox), default=0.0)

        return sorted(kept, key=_top)

    # ---------------------------------------------------------------- internal

    def _recognize_one(self, image: np.ndarray) -> List[OCRLine]:
        """One engine call, guarded by the configured hard timeout."""
        engine = self._get_engine()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._predict, engine, image)
            try:
                return future.result(timeout=self._cfg.ocr_timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                raise OCRTimeoutError(
                    f"PaddleOCR exceeded {self._cfg.ocr_timeout_seconds:.0f}s timeout"
                ) from exc

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
