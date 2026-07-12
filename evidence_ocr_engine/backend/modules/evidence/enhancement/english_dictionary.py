"""English OCR correction dictionary (JSON lexicon + homoglyph resolution).

Two mechanisms, both local and deterministic:

1. **Exact lexicon lookup** from ``data/english_ocr_lexicon.json``
   (``"acc0unt": "account"``) - extendable without code changes.
2. **Homoglyph resolution**: a token containing digit/letter confusions
   (``0<->o``, ``1<->l``, ``5<->s`` ...) is corrected only when the resolved
   form is a known vocabulary word. Unknown words are never guessed.

Casing of the original token is mirrored (``SUPP0RT -> SUPPORT``).
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..logger import get_logger

_DATA_FILE = Path(__file__).resolve().parent / "data" / "english_ocr_lexicon.json"

#: OCR homoglyph confusions (digit/symbol -> intended letter).
HOMOGLYPHS: Dict[str, str] = {
    "0": "o", "1": "l", "3": "e", "5": "s", "8": "b", "@": "a", "$": "s",
    "|": "l", "!": "i",
}

#: Cap on substitution combinations to keep resolution O(1)-ish per token.
_MAX_VARIANTS = 64

_HAS_LETTER = re.compile(r"[A-Za-z]")
_HOMOGLYPH_CHARS = re.compile("[" + re.escape("".join(HOMOGLYPHS)) + "]")


class EnglishDictionary:
    """Loads and queries the English OCR lexicon."""

    def __init__(self, lexicon_path: Path | None = None) -> None:
        self._path = lexicon_path or _DATA_FILE
        self._log = get_logger("enhancement.english_dict")
        self._corrections: Dict[str, str] = {}
        self._vocabulary: set[str] = set()
        self._load()

    @property
    def size(self) -> int:
        return len(self._corrections)

    def lookup_exact(self, token: str) -> Optional[str]:
        """Known misrecognition -> correction (case mirrored), else None."""
        fixed = self._corrections.get(token.lower())
        if fixed is None:
            return None
        mirrored = self._mirror_case(token, fixed)
        return mirrored if mirrored != token else None

    def resolve_homoglyphs(self, token: str) -> Optional[str]:
        """Correct digit/letter homoglyphs when the result is vocabulary.

        Rules: the token must mix letters with homoglyph characters, must
        not itself be valid, and exactly one vocabulary word may result -
        ambiguity means no correction (never guess).
        """
        if token.lower() in self._vocabulary or not _HAS_LETTER.search(token):
            return None
        positions = [m.start() for m in _HOMOGLYPH_CHARS.finditer(token)]
        if not positions or 2 ** len(positions) > _MAX_VARIANTS:
            return None

        candidates: set[str] = set()
        lower = token.lower()
        for combo in itertools.product((False, True), repeat=len(positions)):
            if not any(combo):
                continue
            chars = list(lower)
            for flag, pos in zip(combo, positions):
                if flag:
                    chars[pos] = HOMOGLYPHS[lower[pos]]
            candidate = "".join(chars)
            if candidate in self._vocabulary:
                candidates.add(candidate)

        if len(candidates) != 1:
            return None  # zero or ambiguous: leave unchanged
        return self._mirror_case(token, candidates.pop())

    def is_valid_word(self, token: str) -> bool:
        return token.lower() in self._vocabulary

    def add_correction(self, wrong: str, right: str) -> None:
        """Extend the lexicon at runtime."""
        self._corrections[wrong.lower()] = right
        self._vocabulary.add(right.lower())

    # ---------------------------------------------------------------- internal

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            self._log.error("cannot load English lexicon '%s': %s", self._path, exc)
            data = {"corrections": {}, "vocabulary": []}
        self._corrections = {
            key.lower(): value for key, value in data.get("corrections", {}).items()
        }
        self._vocabulary = {word.lower() for word in data.get("vocabulary", [])}
        for corrected in self._corrections.values():
            self._vocabulary.add(corrected.lower())
        self._log.info(
            "English lexicon loaded: %d corrections, %d vocabulary words",
            len(self._corrections), len(self._vocabulary),
        )

    @staticmethod
    def _mirror_case(original: str, fixed: str) -> str:
        if original.isupper():
            return fixed.upper()
        if original[:1].isupper():
            return fixed.capitalize()
        return fixed


def homoglyph_positions(token: str) -> List[int]:
    """Utility used in tests: positions of homoglyph characters."""
    return [m.start() for m in _HOMOGLYPH_CHARS.finditer(token)]
