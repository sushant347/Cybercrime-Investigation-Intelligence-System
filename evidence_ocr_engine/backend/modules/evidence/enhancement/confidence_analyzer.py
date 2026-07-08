"""OCR confidence analysis for post-processing decisions.

Maps every line of the cleaned text back to the OCR line it originated from
(Prompt 1 stores per-line recognition confidence) so that each correction
decision can be gated by the *actual* recognition confidence:

* high-confidence text is never touched,
* medium confidence permits exact dictionary lookups,
* low confidence additionally permits rule-based repairs.

Cleaned lines rarely match OCR lines verbatim (cleaning merges/normalises),
so matching is done by similarity; when no plausible source line exists
(e.g. plain-text evidence that never went through OCR) a configurable
default applies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Mapping, Sequence

from ..logger import get_logger


class ConfidenceTier(str, Enum):
    """Correction permissions derived from OCR confidence."""

    HIGH = "high"       # >= 0.90 : no correction allowed
    MEDIUM = "medium"   # 0.30 - 0.90 : exact dictionary lookup allowed
    LOW = "low"         # < 0.30 : dictionary + OCR correction rules allowed


#: Tier boundaries (documented in the research design).
HIGH_CONFIDENCE_THRESHOLD: float = 0.90
LOW_CONFIDENCE_THRESHOLD: float = 0.30

#: Confidence assumed when a cleaned line cannot be traced to an OCR line.
DEFAULT_CONFIDENCE: float = 0.75


def tier_for(confidence: float) -> ConfidenceTier:
    """Classify a confidence value into its correction tier."""
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return ConfidenceTier.HIGH
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return ConfidenceTier.LOW
    return ConfidenceTier.MEDIUM


@dataclass
class ConfidenceMap:
    """Per-line confidence for a cleaned text plus document aggregate."""

    line_confidences: Dict[int, float] = field(default_factory=dict)  # 1-based
    document_confidence: float = DEFAULT_CONFIDENCE

    def for_line(self, line_number: int) -> float:
        return self.line_confidences.get(line_number, self.document_confidence)

    def tier_for_line(self, line_number: int) -> ConfidenceTier:
        return tier_for(self.for_line(line_number))


class ConfidenceAnalyzer:
    """Builds a :class:`ConfidenceMap` from Prompt 1 OCR page data."""

    def __init__(self, default_confidence: float = DEFAULT_CONFIDENCE) -> None:
        self._default = default_confidence
        self._log = get_logger("enhancement.confidence")

    def analyze(
        self,
        cleaned_text: str,
        ocr_pages: Sequence[Mapping[str, Any]] | None,
    ) -> ConfidenceMap:
        """Trace cleaned lines to OCR lines and collect their confidences.

        Args:
            cleaned_text: The Prompt 2 ``cleaned_text`` (never modified here).
            ocr_pages: ``pages`` list from the Prompt 1 result - each page has
                ``lines`` with ``text`` and ``confidence``. ``None``/empty is
                allowed (plain-text evidence): the default confidence applies.
        """
        source_lines = self._flatten(ocr_pages)
        line_confidences: Dict[int, float] = {}

        for number, line in enumerate(cleaned_text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            confidence = self._match(stripped, source_lines)
            if confidence is not None:
                line_confidences[number] = confidence

        document = (
            round(sum(line_confidences.values()) / len(line_confidences), 4)
            if line_confidences
            else self._default
        )
        self._log.debug(
            "confidence map: %d/%d lines traced, document=%.2f",
            len(line_confidences), cleaned_text.count("\n") + 1, document,
        )
        return ConfidenceMap(line_confidences=line_confidences,
                             document_confidence=document)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _flatten(
        ocr_pages: Sequence[Mapping[str, Any]] | None,
    ) -> List[tuple[str, float]]:
        """All OCR lines as ``(text, confidence)`` pairs, page order kept."""
        flattened: List[tuple[str, float]] = []
        for page in ocr_pages or []:
            for line in page.get("lines", []):
                text = str(line.get("text", "")).strip()
                if text:
                    flattened.append((text, float(line.get("confidence", 0.0))))
        return flattened

    def _match(
        self, cleaned_line: str, source_lines: List[tuple[str, float]]
    ) -> float | None:
        """Best-effort trace of a cleaned line back to its OCR source.

        A cleaned line may equal one OCR line, contain it (merged lines) or
        be a normalised variant. The confidence of the most similar source
        is used; merged lines take the *minimum* of their contributors so a
        single weak fragment keeps the whole line correctable.
        """
        if not source_lines:
            return None
        contributors = [
            conf for text, conf in source_lines
            if text and (text in cleaned_line or cleaned_line in text)
        ]
        if contributors:
            return min(contributors)

        best_score, best_conf = 0.0, None
        for text, conf in source_lines:
            score = SequenceMatcher(None, cleaned_line, text).ratio()
            if score > best_score:
                best_score, best_conf = score, conf
        return best_conf if best_score >= 0.55 else None
