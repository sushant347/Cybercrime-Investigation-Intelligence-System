"""Confidence-gated token corrector (the decision core of the framework).

For every word token the corrector consults the OCR confidence tier:

* ``HIGH``   (>= 0.90): the token is trusted - no correction attempted.
* ``MEDIUM`` (0.30-0.90): exact lexicon lookups (Nepali + English),
  unambiguous homoglyph resolution, and character-confusion resolution
  (mixed-script repair, Devanagari matra repair) - all dictionary-validated.
* ``LOW``    (< 0.30): additionally, fuzzy Nepali dictionary matching.

Every candidate passes the :class:`ContextCorrector` triple-agreement gate
before being applied, and every applied correction is recorded with its
confidence, rule, character replacements and category.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..logger import get_logger
from .character_confusion import CharacterConfusionResolver
from .confidence_analyzer import ConfidenceTier
from .context_corrector import ContextCorrector
from .english_dictionary import EnglishDictionary
from .nepali_dictionary import NepaliDictionary

#: Word tokens: any run of Devanagari/Latin/digit/joiner characters. Mixed
#: runs (``Seवson``, ``F८``) are captured as ONE token so the resolver can
#: repair them.
_TOKEN = re.compile(r"[A-Za-z0-9ऀ-ॿ‌‍@$|!]*[A-Za-zऀ-ॿ][A-Za-z0-9ऀ-ॿ‌‍@$|!]*")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class TokenCorrection:
    """One applied word-level correction."""

    original: str
    corrected: str
    confidence: float
    rule: str
    language: str    # nepali | english | mixed
    context_score: float
    character_replacement: str = ""
    dictionary_match: str = ""


class ConfidenceCorrector:
    """Applies dictionary + confusion corrections gated by confidence/context."""

    def __init__(
        self,
        nepali: NepaliDictionary,
        english: EnglishDictionary,
        context: ContextCorrector,
        confusion_resolver: Optional[CharacterConfusionResolver] = None,
    ) -> None:
        self._nepali = nepali
        self._english = english
        self._context = context
        self._confusion = confusion_resolver or CharacterConfusionResolver(
            nepali=nepali, english=english)
        self._log = get_logger("enhancement.corrector")

    def correct_line(
        self,
        line: str,
        confidence: float,
        tier: ConfidenceTier,
        document_text: str = "",
    ) -> Tuple[str, List[TokenCorrection]]:
        """Correct one line of text; returns ``(line, corrections)``.

        Every tier is processed. Exact dictionary and mixed-script/character-
        confusion corrections apply on all tiers (they are unambiguous OCR
        errors); the tier only affects whether *fuzzy* candidates are offered
        (LOW only, decided in :meth:`_candidate_for`), so trusted text is never
        guessed at - only definitively repaired.
        """
        corrections: List[TokenCorrection] = []

        def _fix(match: re.Match[str]) -> str:
            token = match.group(0)
            candidate = self._candidate_for(token, tier)
            if candidate is None:
                return token
            corrected, rule, language, fuzzy, chars, dictionary = candidate
            decision = self._context.evaluate(
                token, corrected, tier, fuzzy, document_text
            )
            if not decision.accepted:
                return token
            corrections.append(
                TokenCorrection(
                    original=token,
                    corrected=corrected,
                    confidence=round(confidence, 4),
                    rule=rule,
                    language=language,
                    context_score=decision.context_score,
                    character_replacement=chars,
                    dictionary_match=dictionary,
                )
            )
            return corrected

        return _TOKEN.sub(_fix, line), corrections

    # ---------------------------------------------------------------- helpers

    def _candidate_for(
        self, token: str, tier: ConfidenceTier
    ) -> Optional[Tuple[str, str, str, bool, str, str]]:
        """(corrected, rule, language, is_fuzzy, char_replacements, dict)."""
        has_devanagari = bool(_DEVANAGARI.search(token))
        has_latin = bool(_LATIN.search(token))

        # Mixed-script tokens go straight to confusion resolution.
        if has_devanagari and has_latin:
            resolved = self._confusion.resolve(token)
            if resolved:
                return (resolved.corrected, resolved.rule, "mixed", False,
                        resolved.replacements, resolved.validated_by)
            return None

        if has_devanagari:
            exact = self._nepali.lookup_exact(token)
            if exact:
                return exact, "dictionary_match", "nepali", False, "", "nepali_lexicon"
            resolved = self._confusion.resolve(token)  # matra/spurious repair
            if resolved:
                return (resolved.corrected, resolved.rule, "nepali", False,
                        resolved.replacements, resolved.validated_by)
            if tier == ConfidenceTier.LOW:
                fuzzy = self._nepali.lookup_fuzzy(token)
                if fuzzy:
                    return (fuzzy, "fuzzy_dictionary_match", "nepali", True,
                            "", "nepali_valid_words")
            return None

        exact = self._english.lookup_exact(token)
        if exact:
            return exact, "dictionary_match", "english", False, "", "english_lexicon"
        resolved = self._english.resolve_homoglyphs(token)
        if resolved:
            return (resolved, "homoglyph_resolution", "english", False,
                    "", "english_vocabulary")
        return None
