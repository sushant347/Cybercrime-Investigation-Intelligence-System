"""Strict Unicode validation for the enhanced text.

Prompt 2 already performs meaning-preserving normalisation; this validator
goes further and repairs *structurally invalid* Unicode that OCR engines
produce in Devanagari output:

* duplicate combining marks (the same matra/diacritic twice in a row),
* broken combining marks (a combining mark with no base character - at
  start of line or after whitespace/punctuation),
* orphan halant/virama sequences (double halant collapses to one),
* stray zero-width characters outside Devanagari conjunct context,
* NFC re-composition.

Every repair is counted and reported; meaning is never changed - only
sequences that are invalid under Unicode rules are touched.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List

from ..logger import get_logger

_COMBINING = re.compile(r"[ऀ-ःऺ-ॏ॑-ॗॢॣ]")
_HALANT = "्"
_ZERO_WIDTH = {"​", "⁠", "﻿"}
_JOINERS = {"‌", "‍"}

#: The same combining mark repeated immediately (invalid; OCR stutter).
#: The halant (U+094D) is excluded - duplicate halants have their own rule.
_DUPLICATE_MARK = re.compile(
    r"([ऀ-ःऺ-ौॎॏ॑-ॗॢॣ])\1+"
)

#: Double (or longer) halant runs - structurally meaningless.
_DUPLICATE_HALANT = re.compile(f"{_HALANT}{{2,}}")

#: A combining mark that has no base: start of text/line or after a
#: non-Devanagari, non-joiner character (space, punctuation, Latin, digit).
_ORPHAN_MARK = re.compile(
    r"(?:(?<=^)|(?<=[^ऀ-ॿ‌‍]))"
    r"[ऺ-ॏ॑-ॗॢॣऀ-ं]+",
    re.MULTILINE,
)


def _is_devanagari(char: str) -> bool:
    return "ऀ" <= char <= "ॿ"


@dataclass
class ValidationReport:
    """Counts of every repair category performed."""

    nfc_recompositions: int = 0
    duplicate_marks_removed: int = 0
    orphan_marks_removed: int = 0
    duplicate_halants_collapsed: int = 0
    zero_width_removed: int = 0
    operations: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.nfc_recompositions + self.duplicate_marks_removed
            + self.orphan_marks_removed + self.duplicate_halants_collapsed
            + self.zero_width_removed
        )


class UnicodeValidator:
    """Repairs invalid Unicode sequences without altering meaning."""

    def __init__(self) -> None:
        self._log = get_logger("enhancement.unicode")

    def validate(self, text: str) -> tuple[str, ValidationReport]:
        """Return ``(repaired_text, report)``."""
        report = ValidationReport()

        # 1. NFC composition (canonical order for combining marks).
        composed = unicodedata.normalize("NFC", text)
        if composed != text:
            report.nfc_recompositions = 1
            report.operations.append("nfc_recomposition")
        text = composed

        # 2. Zero-width characters; joiners survive only inside Devanagari.
        text, removed = self._strip_zero_width(text)
        if removed:
            report.zero_width_removed = removed
            report.operations.append(f"zero_width_removed({removed})")

        # 3. Duplicate combining marks ("कारर्" style OCR stutter).
        text, count = self._sub_count(_DUPLICATE_MARK, r"\1", text)
        if count:
            report.duplicate_marks_removed = count
            report.operations.append(f"duplicate_marks_removed({count})")

        # 4. Halant runs.
        text, count = self._sub_count(_DUPLICATE_HALANT, _HALANT, text)
        if count:
            report.duplicate_halants_collapsed = count
            report.operations.append(f"duplicate_halants_collapsed({count})")

        # 5. Combining marks with no base character.
        text, count = self._sub_count(_ORPHAN_MARK, "", text)
        if count:
            report.orphan_marks_removed = count
            report.operations.append(f"orphan_marks_removed({count})")

        if report.total:
            self._log.info("unicode validation: %d repairs (%s)",
                           report.total, ", ".join(report.operations))
        return text, report

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _sub_count(pattern: re.Pattern[str], replacement: str,
                   text: str) -> tuple[str, int]:
        result, count = pattern.subn(replacement, text)
        return result, count

    @staticmethod
    def _strip_zero_width(text: str) -> tuple[str, int]:
        output: List[str] = []
        removed = 0
        for index, char in enumerate(text):
            if char in _ZERO_WIDTH:
                removed += 1
                continue
            if char in _JOINERS:
                prev_ok = index > 0 and _is_devanagari(text[index - 1])
                next_ok = index + 1 < len(text) and _is_devanagari(text[index + 1])
                if not (prev_ok and next_ok):
                    removed += 1
                    continue
            output.append(char)
        return "".join(output), removed
