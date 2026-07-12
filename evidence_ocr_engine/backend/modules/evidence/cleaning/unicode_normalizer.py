"""Forensically safe Unicode normalisation.

Applied to the *working copy* only (``cleaned_text``); ``raw_text`` is never
touched. All operations are meaning-preserving:

* NFC composition (canonical form for Devanagari combining marks)
* removal of invisible/hidden characters (zero-width space, BOM, soft
  hyphen, directional marks) that OCR frequently injects
* ZWJ/ZWNJ are kept **only** between Devanagari characters, where they are
  linguistically meaningful (conjunct control); elsewhere they are noise
* punctuation homoglyph folding (curly quotes -> straight, en/em dash ->
  hyphen, ellipsis char -> dots)
* exotic whitespace (NBSP, thin space, ideographic space) -> plain space

Entity placeholders from :mod:`entity_preserver` use the Unicode Private Use
Area and pass through untouched.
"""

from __future__ import annotations

import unicodedata
from typing import List, Tuple

#: Invisible characters that carry no meaning in OCR'd evidence text.
_HIDDEN_CHARS = {
    "​",  # zero-width space
    "⁠",  # word joiner
    "﻿",  # BOM / zero-width no-break space
    "­",  # soft hyphen
    "‎",  # left-to-right mark
    "‏",  # right-to-left mark
    "‪", "‫", "‬", "‭", "‮",  # directional overrides
}

_JOINERS = {"‌", "‍"}  # ZWNJ, ZWJ - meaningful inside Devanagari

_PUNCTUATION_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "−": "-",
    "…": "...",
    "´": "'", "`": "'",
}

_SPACE_CHARS = {
    " ", " ", " ", " ", " ", " ", " ",
    " ", " ", " ", " ", " ", " ", " ",
    "　",
}


def _is_devanagari(char: str) -> bool:
    return "ऀ" <= char <= "ॿ"


class UnicodeNormalizer:
    """Meaning-preserving Unicode clean-up for multilingual OCR text."""

    def normalize(self, text: str) -> Tuple[str, List[str]]:
        """Normalise ``text``; returns ``(normalised, operations_applied)``."""
        operations: List[str] = []

        composed = unicodedata.normalize("NFC", text)
        if composed != text:
            operations.append("nfc_composition")
        text = composed

        text, removed_hidden = self._strip_hidden(text)
        if removed_hidden:
            operations.append(f"hidden_chars_removed({removed_hidden})")

        folded = text.translate(str.maketrans(_PUNCTUATION_MAP))
        if folded != text:
            operations.append("punctuation_folding")
        text = folded

        spaced = "".join(" " if ch in _SPACE_CHARS else ch for ch in text)
        if spaced != text:
            operations.append("exotic_whitespace_folding")
        text = spaced

        return text, operations

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _strip_hidden(text: str) -> Tuple[str, int]:
        """Drop hidden chars; keep ZWJ/ZWNJ only in Devanagari context."""
        output: List[str] = []
        removed = 0
        for index, char in enumerate(text):
            if char in _HIDDEN_CHARS:
                removed += 1
                continue
            if char in _JOINERS:
                prev_ok = index > 0 and _is_devanagari(text[index - 1])
                next_ok = index + 1 < len(text) and _is_devanagari(text[index + 1])
                if prev_ok and next_ok:
                    output.append(char)  # linguistically meaningful joiner
                else:
                    removed += 1
                continue
            # Drop non-printable control characters except newline/tab.
            if unicodedata.category(char) == "Cc" and char not in ("\n", "\t"):
                removed += 1
                continue
            output.append(char)
        return "".join(output), removed
