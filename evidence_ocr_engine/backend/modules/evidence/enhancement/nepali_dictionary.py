"""Nepali OCR correction dictionary (JSON lexicon, data-driven).

The lexicon lives in ``data/nepali_ocr_lexicon.json`` and can grow without
any code change: investigators add newly observed OCR errors as
``"misrecognised": "correct"`` pairs. The dictionary supports:

* **exact lookup** - the observed token is a known misrecognition,
* **fuzzy lookup** - the token is close (high similarity) to a known
  *valid* word; only used at LOW OCR confidence and never across scripts.
"""

from __future__ import annotations

import json
import unicodedata
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional

from ..logger import get_logger

_DATA_FILE = Path(__file__).resolve().parent / "data" / "nepali_ocr_lexicon.json"

#: Similarity floor for fuzzy matches (conservative: forensic context).
FUZZY_CUTOFF: float = 0.86


class NepaliDictionary:
    """Loads and queries the Nepali OCR lexicon."""

    def __init__(self, lexicon_path: Path | None = None) -> None:
        self._path = lexicon_path or _DATA_FILE
        self._log = get_logger("enhancement.nepali_dict")
        self._corrections: Dict[str, str] = {}
        self._valid_words: List[str] = []
        self._load()

    @property
    def size(self) -> int:
        return len(self._corrections)

    def lookup_exact(self, token: str) -> Optional[str]:
        """Known misrecognition -> correction, else ``None``.

        Lookup is NFC-normalised so visually identical spellings match.
        """
        normalized = unicodedata.normalize("NFC", token)
        corrected = self._corrections.get(normalized)
        if corrected and corrected != normalized:
            return corrected
        return None

    def lookup_fuzzy(self, token: str) -> Optional[str]:
        """Closest valid word above :data:`FUZZY_CUTOFF`, else ``None``.

        Intended only for LOW-confidence tokens; the caller additionally
        requires context agreement before applying the result.
        """
        normalized = unicodedata.normalize("NFC", token)
        if normalized in self._valid_words:
            return None  # already a valid word - nothing to fix
        matches = get_close_matches(normalized, self._valid_words, n=1,
                                    cutoff=FUZZY_CUTOFF)
        return matches[0] if matches and matches[0] != normalized else None

    def is_valid_word(self, token: str) -> bool:
        return unicodedata.normalize("NFC", token) in self._valid_set

    def add_correction(self, wrong: str, right: str, persist: bool = False) -> None:
        """Extend the lexicon at runtime (optionally writing back to JSON)."""
        self._corrections[unicodedata.normalize("NFC", wrong)] = (
            unicodedata.normalize("NFC", right)
        )
        if persist:
            self._persist()

    # ---------------------------------------------------------------- internal

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            self._log.error("cannot load Nepali lexicon '%s': %s", self._path, exc)
            data = {"corrections": {}, "valid_words": []}
        self._corrections = {
            unicodedata.normalize("NFC", key): unicodedata.normalize("NFC", value)
            for key, value in data.get("corrections", {}).items()
        }
        self._valid_words = [
            unicodedata.normalize("NFC", word)
            for word in data.get("valid_words", [])
        ]
        # Corrected forms are valid words by definition.
        for corrected in self._corrections.values():
            if corrected not in self._valid_words:
                self._valid_words.append(corrected)
        self._valid_set = set(self._valid_words)
        self._log.info(
            "Nepali lexicon loaded: %d corrections, %d valid words",
            len(self._corrections), len(self._valid_words),
        )

    def _persist(self) -> None:
        payload = {
            "_meta": {"name": "Nepali OCR correction lexicon",
                      "note": "extended at runtime"},
            "corrections": self._corrections,
            "valid_words": self._valid_words,
        }
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
