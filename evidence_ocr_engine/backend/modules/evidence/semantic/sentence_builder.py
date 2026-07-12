"""Sentence reconstruction before semantic analysis.

OCR breaks sentences at layout wraps. XLM-R judges a candidate word by its
surrounding *sentence*, so fragments must be re-joined first. This builder
merges continuation lines conservatively (never across blank lines, never
after terminal punctuation, never onto a placeholder-only line) and splits
the text into sentence units the validator can score independently.
"""

from __future__ import annotations

import re
from typing import List

_TERMINALS = (".", "!", "?", "।", "…")
_PLACEHOLDER_ONLY = re.compile(r"^\s*<[A-Z0-9_]+_\d+>\s*$")
_STARTS_LOWER = re.compile(r"^[a-zऀ-ॿ]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।…])\s+")


class SentenceBuilder:
    """Rejoins wrapped OCR lines and yields sentence units."""

    def rebuild(self, text: str) -> str:
        """Merge continuation lines; preserve paragraph boundaries."""
        paragraphs_out: List[str] = []
        for paragraph in text.split("\n\n"):
            merged: List[str] = []
            for line in paragraph.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                if merged and self._should_merge(merged[-1], stripped):
                    merged[-1] = f"{merged[-1]} {stripped}"
                else:
                    merged.append(stripped)
            paragraphs_out.append("\n".join(merged))
        return "\n\n".join(p for p in paragraphs_out if p)

    def sentences(self, text: str) -> List[str]:
        """Split rebuilt text into sentence units for validation."""
        units: List[str] = []
        for line in self.rebuild(text).splitlines():
            units.extend(s for s in _SENTENCE_SPLIT.split(line) if s.strip())
        return units

    @staticmethod
    def _should_merge(previous: str, current: str) -> bool:
        prev, curr = previous.rstrip(), current.strip()
        if not prev or not curr:
            return False
        if _PLACEHOLDER_ONLY.match(prev) or _PLACEHOLDER_ONLY.match(curr):
            return False
        if prev.endswith(_TERMINALS):
            return False
        return bool(_STARTS_LOWER.match(curr))
