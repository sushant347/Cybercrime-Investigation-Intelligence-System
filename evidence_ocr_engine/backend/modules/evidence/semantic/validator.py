"""Semantic validation strategies (Strategy pattern + Dependency Injection).

``BaseSemanticValidator`` is the contract the pipeline depends on. Two
implementations ship:

* :class:`XLMRobertaValidator` - pretrained ``xlm-roberta-base`` used for
  *inference only* (no fine-tuning, no training). It scores whether a
  candidate word fits the surrounding sentence by masked-language-model
  fill-mask probability. The model is loaded once (lazy), on GPU if
  available else CPU.
* :class:`HeuristicSemanticValidator` - a lightweight, dependency-free
  fallback so the module works (and is fully testable) when Transformers or
  the model weights are unavailable, and for offline / air-gapped labs.

Because the pipeline depends only on the interface, a future fine-tuned model
can replace ``XLMRobertaValidator`` without touching anything else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..logger import get_logger

#: Sentinel used inside a sentence to mark the word position being judged.
SLOT = "⁣SLOT⁣"


@dataclass(frozen=True)
class ValidationVerdict:
    """Result of judging one candidate in one sentence."""

    fits: bool
    confidence: float      # 0.0 - 1.0
    detail: str = ""


class BaseSemanticValidator(ABC):
    """Contract: judge whether ``candidate`` fits ``sentence`` at ``SLOT``."""

    name: str = "base"

    @abstractmethod
    def validate(self, sentence_with_slot: str, original: str,
                 candidate: str) -> ValidationVerdict:
        """Return a verdict for replacing ``original`` (at SLOT) with
        ``candidate``. ``sentence_with_slot`` contains :data:`SLOT` where the
        token sits, so implementations can build masked contexts."""

    def warmup(self) -> None:  # optional model preload
        return None


class HeuristicSemanticValidator(BaseSemanticValidator):
    """Offline fallback: accepts a candidate when it is a single-script,
    dictionary-valid word replacing a mixed-script token. Deterministic and
    dependency-free; used when XLM-R is unavailable and in tests."""

    name = "heuristic"

    def __init__(self, nepali: object = None, english: object = None) -> None:
        self._nepali = nepali
        self._english = english
        self._log = get_logger("semantic.validator.heuristic")
        self._ensure()

    def validate(self, sentence_with_slot: str, original: str,
                 candidate: str) -> ValidationVerdict:
        import re
        mixed = bool(re.search(r"[A-Za-z]", original)) and bool(
            re.search(r"[ऀ-ॿ]", original))
        candidate_clean = bool(re.search(r"[A-Za-z]", candidate)) != bool(
            re.search(r"[ऀ-ॿ]", candidate))  # single script
        valid = self._is_valid(candidate)
        if mixed and candidate_clean and valid:
            return ValidationVerdict(True, 0.80,
                                     "single-script dictionary word replacing mixed-script token")
        if valid and candidate_clean:
            return ValidationVerdict(True, 0.65, "dictionary-valid candidate")
        return ValidationVerdict(False, 0.30, "no supporting evidence")

    def _is_valid(self, word: str) -> bool:
        for dictionary in (self._english, self._nepali):
            try:
                if dictionary is not None and dictionary.is_valid_word(word):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def _ensure(self) -> None:
        if self._english is not None or self._nepali is not None:
            return
        try:
            from ..enhancement.english_dictionary import EnglishDictionary
            from ..enhancement.nepali_dictionary import NepaliDictionary
            self._english = EnglishDictionary()
            self._nepali = NepaliDictionary()
        except Exception:  # noqa: BLE001
            self._english = self._nepali = None


class XLMRobertaValidator(BaseSemanticValidator):
    """Pretrained XLM-R masked-LM context validator (inference only)."""

    name = "xlm-roberta-base"

    def __init__(self, model_name: str = "xlm-roberta-base",
                 accept_threshold: float = 0.15, top_k: int = 20) -> None:
        self._model_name = model_name
        self._threshold = accept_threshold
        self._top_k = top_k
        self._pipe = None  # lazy fill-mask pipeline
        self._mask = None
        self._log = get_logger("semantic.validator.xlmr")

    def warmup(self) -> None:
        self._ensure_pipeline()

    def validate(self, sentence_with_slot: str, original: str,
                 candidate: str) -> ValidationVerdict:
        pipe = self._ensure_pipeline()
        if pipe is None:  # transformers/torch/model unavailable
            return ValidationVerdict(False, 0.0, "xlm-r unavailable")
        try:
            masked = sentence_with_slot.replace(SLOT, self._mask, 1)
            predictions = pipe(masked, top_k=self._top_k)
            if predictions and isinstance(predictions[0], list):
                predictions = predictions[0]
            cand_first = candidate.split()[0].lower()
            orig_first = original.split()[0].lower()
            cand_score = self._score_for(predictions, cand_first)
            orig_score = self._score_for(predictions, orig_first)
            fits = cand_score >= self._threshold and cand_score >= orig_score
            return ValidationVerdict(
                fits, float(min(1.0, cand_score)),
                f"xlm-r fill-mask cand={cand_score:.3f} orig={orig_score:.3f}")
        except Exception as exc:  # noqa: BLE001 - inference must never crash the pipeline
            self._log.warning("xlm-r validation failed: %s", exc)
            return ValidationVerdict(False, 0.0, "xlm-r inference error")

    # ---------------------------------------------------------------- internal

    @staticmethod
    def _score_for(predictions, word: str) -> float:
        best = 0.0
        for pred in predictions:
            token = str(pred.get("token_str", "")).strip().lower()
            if token == word or (token and word.startswith(token)):
                best = max(best, float(pred.get("score", 0.0)))
        return best

    def _ensure_pipeline(self):
        if self._pipe is not None:
            return self._pipe
        try:
            import torch
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            self._log.info("loading %s (device=%s) - inference only",
                           self._model_name, "cuda" if device == 0 else "cpu")
            self._pipe = pipeline("fill-mask", model=self._model_name, device=device)
            self._mask = self._pipe.tokenizer.mask_token
            return self._pipe
        except Exception as exc:  # noqa: BLE001 - graceful: fall back to heuristic upstream
            self._log.warning(
                "XLM-R unavailable (%s); pipeline will use the heuristic validator", exc)
            self._pipe = None
            return None
