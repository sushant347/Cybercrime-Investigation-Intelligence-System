"""Context-aware correction gate.

A candidate correction is applied only when three independent signals agree
(triple-agreement principle of the framework):

1. **Dictionary signal** - a lexicon produced the candidate.
2. **OCR confidence signal** - the token's confidence tier permits the
   candidate's correction class (exact vs. fuzzy).
3. **Context signal** - the replacement is plausible in situ:
   * shape similarity between original and candidate is high (an OCR error
     garbles a few characters; it does not produce an unrelated word),
   * the scripts match (a Devanagari token is never replaced by Latin and
     vice versa),
   * optionally, the candidate (or its neighbours) already occurs elsewhere
     in the document - document-level consistency evidence.

If any signal disagrees, the token is left unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..logger import get_logger
from .confidence_analyzer import ConfidenceTier

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

#: Minimum original<->candidate similarity per correction class.
MIN_SIMILARITY_EXACT: float = 0.40   # exact lexicon hits are pre-vetted
MIN_SIMILARITY_FUZZY: float = 0.80   # fuzzy hits need strong shape agreement


@dataclass(frozen=True)
class ContextDecision:
    """Outcome of the triple-agreement check."""

    accepted: bool
    context_score: float
    reason: str


class ContextCorrector:
    """Validates dictionary candidates against context and confidence."""

    def __init__(self) -> None:
        self._log = get_logger("enhancement.context")

    def evaluate(
        self,
        original: str,
        candidate: str,
        tier: ConfidenceTier,
        is_fuzzy: bool,
        document_text: str = "",
    ) -> ContextDecision:
        """Apply the triple-agreement rules to one candidate correction."""
        # Confidence signal. Exact (non-fuzzy) corrections - dictionary hits and
        # mixed-script/character-confusion repairs - are UNAMBIGUOUS OCR errors
        # (e.g. "Seवson", "मं") and are allowed on every tier, including
        # high confidence, because a mixed-script or known-misrecognised token is
        # wrong regardless of the OCR score. Only *fuzzy* (guessed) corrections
        # remain gated to LOW confidence, so the engine never guesses on trusted
        # text.
        if is_fuzzy and tier != ConfidenceTier.LOW:
            return ContextDecision(False, 0.0, "fuzzy_requires_low_confidence")

        # Context signal 1: scripts must match - unless the original is
        # itself mixed-script, in which case restoring a single script IS
        # the goal of the correction (character-confusion repair).
        original_mixed = self._is_devanagari(original) and self._is_latin(original)
        if not original_mixed and (
            self._is_devanagari(original) != self._is_devanagari(candidate)
        ):
            return ContextDecision(False, 0.0, "script_mismatch")

        # Context signal 2: shape similarity.
        similarity = SequenceMatcher(None, original, candidate).ratio()
        floor = MIN_SIMILARITY_FUZZY if is_fuzzy else MIN_SIMILARITY_EXACT
        if similarity < floor:
            return ContextDecision(False, round(similarity, 3),
                                   "shape_similarity_too_low")

        # Context signal 3 (bonus evidence, never a veto for exact hits):
        # the candidate already appears elsewhere in the document.
        score = similarity
        if document_text and candidate in document_text:
            score = min(1.0, score + 0.10)

        self._log.debug("context accepted %r -> %r (score %.2f)",
                        original, candidate, score)
        return ContextDecision(True, round(score, 3), "agreement")

    @staticmethod
    def _is_devanagari(token: str) -> bool:
        return bool(_DEVANAGARI.search(token))

    @staticmethod
    def _is_latin(token: str) -> bool:
        return bool(re.search(r"[A-Za-z]", token))
