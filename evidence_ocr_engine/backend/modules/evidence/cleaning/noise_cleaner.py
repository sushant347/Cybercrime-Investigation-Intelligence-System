"""OCR noise removal and whitespace normalisation.

Removes artefacts OCR engines typically produce (stray symbol runs, scanner
border characters, decorative bullets) and normalises whitespace while
preserving paragraph boundaries. Also provides the Roman-Nepali line
normaliser (lowercase, whitespace, punctuation, repeated characters - words
are kept exactly as written, never converted or translated).

Entity placeholders (Private Use Area chars) are always preserved.
"""

from __future__ import annotations

import re
from typing import List, Tuple

_PUA = "-"  # entity placeholders live here - never remove

#: Runs of 3+ identical punctuation characters -> one ("!!!!" -> "!").
_REPEATED_PUNCT = re.compile(r"([!?.,;:*#~_\-=+])\1{2,}")

#: Lines that are pure decoration / scanner noise (no letters or digits).
_NOISE_ONLY_LINE = re.compile(rf"^[^\w{_PUA}ऀ-ॿ]+$")

#: Box-drawing, block and geometric characters injected by table borders.
_BORDER_CHARS = re.compile(r"[│┃┆┇┊┋║▌▐█▄▀■□▪▫◆◇●○◦∎—─━┄┅┈┉═|]{2,}")

#: Stray bullets / pipes at line starts left over from UI chrome.
_LINE_PREFIX_JUNK = re.compile(r"^[\s>*•·◦▪|~`]+")

#: 3+ repeats of one letter -> single letter ("garnusss" -> "garnus").
#: Applied to Roman-Nepali lines only; doubles ("aa", "ee") are kept because
#: they are legitimate in Romanised Nepali (e.g. "aaunus", "hameelai").
_REPEATED_LETTER = re.compile(r"([a-z])\1{2,}")

_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r" +([,.;:!?%)\]।])")


class NoiseCleaner:
    """Removes OCR artefacts; keeps every meaningful character."""

    def remove_noise(self, text: str) -> Tuple[str, List[str]]:
        """Strip OCR junk from ``text``; returns ``(text, operations)``."""
        operations: List[str] = []

        cleaned = _BORDER_CHARS.sub(" ", text)
        if cleaned != text:
            operations.append("border_chars_removed")
        text = cleaned

        cleaned = _REPEATED_PUNCT.sub(r"\1", text)
        if cleaned != text:
            operations.append("repeated_punctuation_collapsed")
        text = cleaned

        lines_out: List[str] = []
        dropped = 0
        for line in text.splitlines():
            stripped = _LINE_PREFIX_JUNK.sub("", line)
            if stripped != line and stripped and "line_prefix_junk_removed" not in operations:
                operations.append("line_prefix_junk_removed")
            if stripped and _NOISE_ONLY_LINE.match(stripped):
                dropped += 1
                continue  # decoration-only line: no evidential content
            lines_out.append(stripped)
        if dropped:
            operations.append(f"noise_only_lines_dropped({dropped})")
        return "\n".join(lines_out), operations

    def normalize_whitespace(self, text: str) -> Tuple[str, List[str]]:
        """Collapse duplicate spaces/newlines, trim line edges.

        Paragraph boundaries (blank lines) are preserved: runs of 3+ newlines
        collapse to exactly one blank line, never zero.
        """
        operations: List[str] = []
        lines = [line.strip() for line in text.split("\n")]
        collapsed = "\n".join(_MULTI_SPACE.sub(" ", line) for line in lines)
        collapsed = _SPACE_BEFORE_PUNCT.sub(r"\1", collapsed)
        collapsed = _MULTI_NEWLINE.sub("\n\n", collapsed).strip("\n ")
        if collapsed != text:
            operations.append("whitespace_normalized")
        return collapsed, operations

    def normalize_roman_nepali_line(self, line: str) -> str:
        """Normalise one Roman-Nepali line: lowercase + repeated characters.

        Words remain exactly as written - no transliteration, no translation,
        no spelling change beyond collapsing 3+ repeated letters. Placeholder
        tokens (PUA + digits) are unaffected by lowercasing.
        """
        lowered = line.lower()
        return _REPEATED_LETTER.sub(r"\1", lowered)
