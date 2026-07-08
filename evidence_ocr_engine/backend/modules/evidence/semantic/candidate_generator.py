"""Rule candidate generator.

The semantic engine never lets the language model *invent* text - the model
only *judges* candidates. This generator proposes correction candidates for
suspicious tokens from rule-based knowledge resources. Each candidate is later
validated in context by XLM-R.

Lookup priority (highest first)::

    1. OCR confusion dictionary   (data/ocr_confusion_words.json)
    2. Cyber dictionary           (data/cyber_dictionary.json)
    3. Canonical dictionary       (data/canonical_words.json)
    4. Existing English dictionary (enhancement module, unchanged)
    5. Existing Nepali dictionary  (enhancement module, unchanged)
    6. Character confusion matrix  (enhancement module, unchanged)
    -> XLM-R validation (downstream, unchanged)

If any resource is unavailable, that lookup is skipped - generation degrades
to "no candidates" (the token is kept), never an error. The ``Candidate``
contract and ``generate`` signature are unchanged (backward compatible).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .knowledge_base import KnowledgeBase


@dataclass(frozen=True)
class Candidate:
    """One proposed correction for a suspicious token."""

    original: str
    proposal: str
    source: str          # ocr_confusion | cyber_dictionary | canonical |
                         # character_confusion | dictionary
    detail: str = ""


class CandidateGenerator:
    """Produces rule-based correction candidates (no text generation)."""

    def __init__(self, confusion_resolver: object = None,
                 nepali: object = None, english: object = None,
                 knowledge_base: Optional[KnowledgeBase] = None) -> None:
        self._resolver = confusion_resolver
        self._nepali = nepali
        self._english = english
        self._kb = knowledge_base or KnowledgeBase()
        self._ensure_resources()

    def generate(self, token: str) -> List[Candidate]:
        """All plausible candidates for ``token`` in priority order (may be empty)."""
        candidates: List[Candidate] = []
        seen: set[str] = set()

        def _add(proposal: Optional[str], source: str, detail: str = "") -> None:
            if proposal and proposal != token and proposal not in seen:
                candidates.append(Candidate(token, proposal, source, detail))
                seen.add(proposal)

        # 1-3. New high-precision knowledge resources (priority order).
        _add(self._kb.lookup_ocr_confusion(token), "ocr_confusion", "ocr_confusion_words")
        _add(self._kb.lookup_cyber(token), "cyber_dictionary", "cyber_dictionary")
        _add(self._kb.lookup_canonical(token), "canonical", "canonical_words")

        # 4-5. Existing English then Nepali dictionaries (unchanged logic).
        for dictionary, lang in ((self._english, "english"), (self._nepali, "nepali")):
            if dictionary is None:
                continue
            try:
                hit = dictionary.lookup_exact(token)
            except Exception:  # noqa: BLE001
                hit = None
            _add(hit, "dictionary", lang)

        # 6. Character confusion matrix (existing resolver, unchanged).
        if self._resolver is not None:
            try:
                resolved = self._resolver.resolve(token)
            except Exception:  # noqa: BLE001 - generation must never crash
                resolved = None
            if resolved and resolved.corrected != token:
                _add(resolved.corrected, "character_confusion",
                     getattr(resolved, "replacements", ""))
        return candidates

    # ---------------------------------------------------------------- internal

    def _ensure_resources(self) -> None:
        """Lazily wire enhancement resources when not injected (DI-friendly)."""
        if self._resolver is not None:
            return
        try:
            from ..enhancement.character_confusion import CharacterConfusionResolver
            from ..enhancement.english_dictionary import EnglishDictionary
            from ..enhancement.nepali_dictionary import NepaliDictionary

            self._nepali = self._nepali or NepaliDictionary()
            self._english = self._english or EnglishDictionary()
            self._resolver = CharacterConfusionResolver(
                nepali=self._nepali, english=self._english)
        except Exception:  # noqa: BLE001 - optional dependency path
            self._resolver = None
