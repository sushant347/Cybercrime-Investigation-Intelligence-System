"""Automatic language detection for OCR output.

Reuses the existing (unchanged) cleaning-module line detector to classify the
recognised text as English, Nepali or mixed, and maps that to the correct
PP-OCRv5 language code (``ne`` covers Devanagari + Latin; ``en`` for pure
English). Manual override remains available through configuration/the caller.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .schemas import LanguageInfo


class OCRLanguageDetector:
    """Detects the dominant script and recommends a PP-OCRv5 language code."""

    def __init__(self, line_detector: object = None) -> None:
        self._detector = line_detector or self._default_detector()

    def detect(self, ocr_pages: Sequence[Mapping[str, Any]]) -> LanguageInfo:
        """Classify OCR text and recommend a Paddle language code."""
        text = "\n".join(
            str(line.get("text", ""))
            for page in (ocr_pages or [])
            for line in page.get("lines", [])
        )
        return self.detect_text(text)

    def detect_text(self, text: str) -> LanguageInfo:
        line_languages: Dict[str, str] = {}
        english = nepali = mixed = 0
        if self._detector is not None:
            for result in self._detector.detect_lines(text):
                label = result.language
                line_languages[str(result.line_number)] = label
                if label == "english":
                    english += 1
                elif label in ("nepali_unicode", "roman_nepali"):
                    nepali += 1
                elif label == "mixed":
                    mixed += 1

        detected = self._document_label(english, nepali, mixed)
        # PP-OCRv5: "ne" recogniser covers Devanagari + Latin, so it is the
        # safe choice for Nepali and mixed; pure English can use "en".
        recommended = "en" if detected == "english" else "ne"
        return LanguageInfo(
            detected=detected,
            recommended_paddle_lang=recommended,
            line_languages=line_languages,
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _document_label(english: int, nepali: int, mixed: int) -> str:
        if english == 0 and nepali == 0 and mixed == 0:
            return "unknown"
        if mixed > 0 or (english > 0 and nepali > 0):
            return "mixed"
        if nepali > 0:
            return "nepali"
        return "english"

    @staticmethod
    def _default_detector() -> object:
        try:
            from ..cleaning.language_detector import HeuristicLanguageDetector
            return HeuristicLanguageDetector()
        except Exception:  # noqa: BLE001 - optional dependency path
            return None
