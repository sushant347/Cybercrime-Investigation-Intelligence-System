"""Knowledge resources for candidate generation (data-only, offline).

Loads the three JSON dictionaries and exposes high-precision lookups used by
the candidate generator, in the required priority order:

    1. OCR confusion dictionary  (ocr_confusion_words.json)
    2. Cyber dictionary          (cyber_dictionary.json)
    3. Canonical dictionary      (canonical_words.json)

All lookups are pure data reads: they never generate text and never raise
(missing/broken files degrade to empty lookups so the pipeline is unaffected).
Adding new words/pairs requires editing the JSON only - no code change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

_DATA = Path(__file__).resolve().parent / "data"


def _load(name: str) -> dict:
    try:
        with open(_DATA / name, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


class KnowledgeBase:
    """Three-tier lookup over the OCR-confusion, cyber and canonical resources."""

    def __init__(self) -> None:
        # 1. OCR confusion: exact-token -> correction (+ case-insensitive index).
        self._ocr: Dict[str, str] = _load("ocr_confusion_words.json").get("confusions", {})
        self._ocr_ci: Dict[str, str] = {k.lower(): v for k, v in self._ocr.items()}

        # 2. Cyber vocabulary: canonical terms, indexed by lower-case form.
        cyber = _load("cyber_dictionary.json").get("categories", {})
        self._cyber_terms: List[str] = [t for terms in cyber.values() for t in terms]
        self._cyber_ci: Dict[str, str] = {t.lower(): t for t in self._cyber_terms}

        # 3. Canonical mappings: variant (lower) -> canonical form.
        mappings = _load("canonical_words.json").get("mappings", {})
        self._canonical: Dict[str, str] = {k.lower(): v for k, v in mappings.items()}

    # ------------------------------------------------------------ statistics
    @property
    def ocr_confusion_count(self) -> int:
        return len(self._ocr)

    @property
    def cyber_term_count(self) -> int:
        return len(self._cyber_terms)

    @property
    def canonical_count(self) -> int:
        return len(self._canonical)

    # ---------------------------------------------------------------- lookups
    def lookup_ocr_confusion(self, token: str) -> Optional[str]:
        """Exact OCR-confusion hit (then case-insensitive), else None."""
        hit = self._ocr.get(token) or self._ocr_ci.get(token.lower())
        return hit if hit and hit != token else None

    def lookup_cyber(self, token: str) -> Optional[str]:
        """Canonical cyber term whose lower-case form equals the token."""
        hit = self._cyber_ci.get(token.lower())
        return hit if hit and hit != token else None

    def lookup_canonical(self, token: str) -> Optional[str]:
        """Canonical form of a spelling/casing variant, else None."""
        hit = self._canonical.get(token.lower())
        return hit if hit and hit != token else None

    def is_known_term(self, word: str) -> bool:
        """Membership across cyber terms + canonical targets (case-insensitive)."""
        low = word.lower()
        return low in self._cyber_ci or low in self._canonical
