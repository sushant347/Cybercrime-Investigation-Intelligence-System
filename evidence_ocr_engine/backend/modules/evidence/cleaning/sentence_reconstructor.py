"""Sentence reconstruction: merge OCR-broken lines back into sentences.

OCR splits sentences wherever the layout wraps ("Verify your\\naccount now").
This stage re-joins such fragments while respecting hard boundaries:

* blank lines (paragraph boundaries) are never crossed,
* a line ending in terminal punctuation (``. ! ? । ; :``) ends a sentence,
* lines that consist only of a protected entity placeholder are kept
  standalone - URLs, emails and phone numbers are never merged into prose,
* short heading-like lines (e.g. "Subject:") are not glued to body text.

Runs while entities are placeholder-protected, so an entity can never be
split or altered by the merge.
"""

from __future__ import annotations

import re
from typing import List, Tuple

_TERMINALS = (".", "!", "?", "।", ";", ":", "…")
_PLACEHOLDER_ONLY = re.compile(r"^\s*\d+\s*$")
_STARTS_LOWER = re.compile(r"^[a-zऀ-ॿ]")
_HEADING_LIKE = re.compile(r"^[A-Za-z][A-Za-z ]{0,24}:$")


class SentenceReconstructor:
    """Joins wrapped OCR lines conservatively."""

    def reconstruct(self, text: str) -> Tuple[str, List[str]]:
        """Merge continuation lines; returns ``(text, operations)``."""
        merged_count = 0
        paragraphs_out: List[str] = []

        for paragraph in text.split("\n\n"):
            lines = [line for line in paragraph.split("\n")]
            output: List[str] = []
            for line in lines:
                if not line.strip():
                    continue
                if output and self._should_merge(output[-1], line):
                    output[-1] = f"{output[-1].rstrip()} {line.strip()}"
                    merged_count += 1
                else:
                    output.append(line.strip())
            paragraphs_out.append("\n".join(output))

        operations = [f"lines_merged({merged_count})"] if merged_count else []
        return "\n\n".join(p for p in paragraphs_out if p), operations

    # ---------------------------------------------------------------- helpers

    def _should_merge(self, previous: str, current: str) -> bool:
        """Decide whether ``current`` continues the sentence in ``previous``."""
        prev = previous.rstrip()
        curr = current.strip()
        if not prev or not curr:
            return False
        # Standalone entities stay standalone (URLs/emails/phones unmergeable).
        if _PLACEHOLDER_ONLY.match(prev) or _PLACEHOLDER_ONLY.match(curr):
            return False
        # Sentence already terminated.
        if prev.endswith(_TERMINALS):
            return False
        # Heading-like labels ("From:", "Subject:") keep their own line.
        if _HEADING_LIKE.match(prev):
            return False
        # A line ending in a protected entity (URL/email/phone placeholder)
        # is a complete unit - never glue prose onto an entity.
        if prev.endswith("\ue001"):
            return False
        # Never merge across a script boundary: a Devanagari continuation
        # only joins a line that itself ends in Devanagari, and vice versa.
        curr_devanagari = "\u0900" <= curr[0] <= "\u097f"
        prev_last = prev[-1]
        prev_devanagari = "\u0900" <= prev_last <= "\u097f"
        if curr_devanagari != prev_devanagari:
            return False
        # Continuation must look like mid-sentence text (lowercase Latin or
        # Devanagari start). Uppercase starts usually begin a new field/line.
        return bool(_STARTS_LOWER.match(curr))
