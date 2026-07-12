"""Semantic Correction Engine pipeline (composition root).

Consumes ``enhanced_text`` (Prompt 2.5) and produces ``semantic_text`` - the
only field this module writes. The language model never generates text; it
only *validates* rule-proposed candidates in context::

    enhanced_text
      -> entity protection            (<URL_1> ... shielded)
      -> sentence reconstruction      (rebuild broken OCR sentences)
      -> mixed-script detection       (find suspicious tokens)
      -> rule candidate generation    (propose corrections, never invent)
      -> XLM-R context validation     (does the candidate fit the sentence?)
      -> language + dictionary + confidence gates
      -> accept / reject
      -> entity restoration
      -> semantic_text + corrections + statistics

Every validation stage is injected (Strategy + DI), so a future fine-tuned
model replaces the validator without changing this class. All inputs are
forensic invariants and are never modified.
"""

from __future__ import annotations

import re
import time
from typing import List, Optional

from ..cleaning.language_detector import BaseLanguageDetector, HeuristicLanguageDetector
from ..logger import get_logger
from .candidate_generator import CandidateGenerator
from .entity_protection import EntityProtector
from .mixed_script_detector import MixedScriptDetector
from .semantic_schemas import (
    EntityRef,
    SemanticCorrection,
    SemanticResult,
    SemanticStatistics,
)
from .sentence_builder import SentenceBuilder
from .validator import (
    BaseSemanticValidator,
    HeuristicSemanticValidator,
    SLOT,
    XLMRobertaValidator,
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


class SemanticCorrectionPipeline:
    """Context-validated correction of rule-enhanced OCR text."""

    def __init__(
        self,
        validator: Optional[BaseSemanticValidator] = None,
        entity_protector: Optional[EntityProtector] = None,
        sentence_builder: Optional[SentenceBuilder] = None,
        mixed_script_detector: Optional[MixedScriptDetector] = None,
        candidate_generator: Optional[CandidateGenerator] = None,
        language_detector: Optional[BaseLanguageDetector] = None,
        entity_extractor: object = None,
        confidence_threshold: float = 0.5,
        use_xlm_roberta: bool = True,
    ) -> None:
        self._protector = entity_protector or EntityProtector()
        self._sentences = sentence_builder or SentenceBuilder()
        self._mixed = mixed_script_detector or MixedScriptDetector()
        self._candidates = candidate_generator or CandidateGenerator()
        self._languages = language_detector or HeuristicLanguageDetector()
        self._threshold = confidence_threshold
        self._validator = validator or self._default_validator(use_xlm_roberta)
        # Reuse the EXISTING cleaning-module EntityExtractor unchanged (DI): it
        # now runs on ``semantic_text`` so semantic output feeds extraction, per
        # the merged pipeline. Lazy default keeps the module import-light.
        self._entities = entity_extractor if entity_extractor is not None \
            else self._default_extractor()
        self._log = get_logger("semantic.pipeline")

    @staticmethod
    def _default_extractor() -> object:
        try:
            from ..cleaning.entity_extractor import EntityExtractor
            return EntityExtractor()
        except Exception:  # noqa: BLE001 - extraction is optional/append-only
            return None

    def correct(self, enhanced_text: str, case_id: str = "",
                evidence_id: str = "") -> SemanticResult:
        """Produce ``semantic_text`` from ``enhanced_text`` (kept verbatim)."""
        started = time.perf_counter()

        protected = self._protector.protect(enhanced_text)
        working = protected.text
        rebuilt = self._sentences.rebuild(working)

        suspects = self._mixed.find(rebuilt)
        corrections: List[SemanticCorrection] = []
        candidates_evaluated = 0

        # Apply accepted corrections onto the rebuilt (protected) text.
        result_text = rebuilt
        for suspect in suspects:
            sentence = self._sentence_of(rebuilt, suspect.token)
            best = self._best_candidate(suspect.token, sentence)
            if best is None:
                continue
            candidates_evaluated += 1
            corrections.append(best)
            if best.accepted:
                result_text = self._replace_token(result_text, suspect.token,
                                                   best.candidate)

        semantic_text = self._protector.restore(result_text, protected)

        accepted = [c for c in corrections if c.accepted]
        rejected = [c for c in corrections if not c.accepted]
        confidence = (round(sum(c.confidence for c in accepted) / len(accepted), 4)
                      if accepted else 0.0)

        languages = sorted({
            r.language for r in self._languages.detect_lines(enhanced_text)
            if r.language != "unknown"})

        # Entity extraction now runs on semantic_text (merged pipeline). Uses
        # the existing extractor unchanged; result is append-only.
        entities = self._extract_entities(semantic_text)

        result = SemanticResult(
            case_id=case_id,
            evidence_id=evidence_id,
            enhanced_text=enhanced_text,   # forensic invariant
            semantic_text=semantic_text,
            corrections=corrections,
            accepted_corrections=accepted,
            rejected_corrections=rejected,
            confidence=confidence,
            entities=entities,
            statistics=SemanticStatistics(
                suspicious_tokens=len(suspects),
                candidates_evaluated=candidates_evaluated,
                accepted_corrections=len(accepted),
                rejected_corrections=len(rejected),
                average_confidence=confidence,
                protected_entities=protected.placeholder_count(),
                validator=self._validator.name,
                languages_detected=languages,
            ),
            processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self._log.info(
            "semantic %s: %d suspects, %d accepted, %d rejected (validator=%s) %.1f ms",
            evidence_id or "<text>", len(suspects), len(accepted), len(rejected),
            self._validator.name, result.processing_time_ms)
        return result

    # ---------------------------------------------------------------- internal

    def _best_candidate(self, token: str, sentence: str) -> Optional[SemanticCorrection]:
        """Evaluate ALL candidates, then choose by highest confidence."""
        candidates = self._candidates.generate(token)
        if not candidates:
            return None
        slotted = sentence.replace(token, SLOT, 1) if token in sentence else f"{sentence} {SLOT}"

        evaluated: List[SemanticCorrection] = []
        for candidate in candidates:
            if not self._language_consistent(candidate.proposal):
                continue
            verdict = self._validator.validate(slotted, token, candidate.proposal)
            accepted = verdict.fits and verdict.confidence >= self._threshold
            evaluated.append(SemanticCorrection(
                original=token,
                candidate=candidate.proposal,
                accepted=accepted,
                confidence=round(verdict.confidence, 4),
                validator=self._validator.name,
                candidate_source=candidate.source,
                reason=verdict.detail,
                language="nepali" if _DEVANAGARI.search(candidate.proposal) else "english",
            ))
        if not evaluated:
            return None

        # Rank all candidates by confidence (descending).
        evaluated.sort(key=lambda c: c.confidence, reverse=True)
        # Prefer the highest-confidence ACCEPTED candidate; fall back to the
        # highest-confidence rejected one purely for the audit record.
        accepted_ranked = [c for c in evaluated if c.accepted]
        return accepted_ranked[0] if accepted_ranked else evaluated[0]

    def _extract_entities(self, semantic_text: str) -> dict:
        """Run the existing EntityExtractor over semantic_text (append-only).

        Returns a JSON-serialisable mapping of entity_type -> [{value,
        normalized}]. Never raises: extraction failure yields an empty map so
        the merge can never break the pipeline.
        """
        if self._entities is None:
            return {}
        try:
            extracted = self._entities.extract(semantic_text)
        except Exception:  # noqa: BLE001
            return {}
        return {
            entity_type: [EntityRef(value=e.value, normalized=e.normalized)
                          for e in items]
            for entity_type, items in extracted.items() if items
        }

    @staticmethod
    def _language_consistent(candidate: str) -> bool:
        """A validated candidate must be single-script (no mixed output)."""
        has_latin = bool(re.search(r"[A-Za-z]", candidate))
        has_deva = bool(_DEVANAGARI.search(candidate))
        return has_latin != has_deva  # exactly one script

    @staticmethod
    def _sentence_of(text: str, token: str) -> str:
        for line in text.splitlines():
            if token in line:
                return line
        return text

    @staticmethod
    def _replace_token(text: str, token: str, replacement: str) -> str:
        return re.sub(rf"(?<!\S){re.escape(token)}(?!\S)", replacement, text, count=1)

    @staticmethod
    def _default_validator(use_xlm_roberta: bool) -> BaseSemanticValidator:
        """XLM-R if requested and importable; otherwise the heuristic fallback."""
        if use_xlm_roberta:
            try:
                import transformers  # noqa: F401
                return XLMRobertaValidator()
            except Exception:  # noqa: BLE001 - offline / not installed
                pass
        return HeuristicSemanticValidator()
