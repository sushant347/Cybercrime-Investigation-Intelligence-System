"""Hybrid multilingual forensic text-cleaning pipeline (composition root).

Stage order (per research design)::

    OCR output -> language detection -> unicode normalisation
    -> entity preservation -> noise removal -> OCR error correction
    -> whitespace normalisation -> sentence reconstruction
    -> Roman-Nepali line normalisation -> entity restoration
    -> entity extraction -> keyword / risk-signal analysis

Entity preservation runs *before* any mutating stage so that no cleaning
operation can ever touch a forensic entity. ``raw_text`` is stored verbatim
and never modified; every transformation happens on a working copy that
becomes ``cleaned_text``.

All collaborators are injected (Strategy pattern / DI): any stage can be
replaced without changing this class.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from ..logger import get_logger
from .cleaning_schemas import CleaningResult, CleaningStatistics, EntityRecord
from .entity_extractor import EntityExtractor
from .entity_preserver import EntityPreserver
from .keyword_analyzer import KeywordAnalyzer
from .language_detector import BaseLanguageDetector, HeuristicLanguageDetector
from .noise_cleaner import NoiseCleaner
from .ocr_corrector import OCRCorrector
from .sentence_reconstructor import SentenceReconstructor
from .unicode_normalizer import UnicodeNormalizer


class CleaningPipeline:
    """Cleans one OCR text and extracts structured forensic entities."""

    def __init__(
        self,
        language_detector: Optional[BaseLanguageDetector] = None,
        unicode_normalizer: Optional[UnicodeNormalizer] = None,
        noise_cleaner: Optional[NoiseCleaner] = None,
        ocr_corrector: Optional[OCRCorrector] = None,
        entity_preserver: Optional[EntityPreserver] = None,
        sentence_reconstructor: Optional[SentenceReconstructor] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        keyword_analyzer: Optional[KeywordAnalyzer] = None,
    ) -> None:
        self._detector = language_detector or HeuristicLanguageDetector()
        self._unicode = unicode_normalizer or UnicodeNormalizer()
        self._noise = noise_cleaner or NoiseCleaner()
        self._corrector = ocr_corrector or OCRCorrector()
        self._preserver = entity_preserver or EntityPreserver()
        self._reconstructor = sentence_reconstructor or SentenceReconstructor()
        self._extractor = entity_extractor or EntityExtractor()
        self._keywords = keyword_analyzer or KeywordAnalyzer()
        self._log = get_logger("cleaning.pipeline")

    def clean(
        self, raw_text: str, case_id: str = "", evidence_id: str = ""
    ) -> CleaningResult:
        """Run the full pipeline over ``raw_text`` (which is never modified).

        Returns:
            :class:`CleaningResult` with ``raw_text`` verbatim,
            ``cleaned_text``, per-line languages, entities, keywords,
            risk signals and quality statistics.
        """
        started = time.perf_counter()
        operations: List[str] = []

        # 1. Language detection (on the untouched raw lines).
        line_results = self._detector.detect_lines(raw_text)
        language = self._detector.detect_document(raw_text)
        self._log.info("language detected: %s (%d lines)", language, len(line_results))

        working = raw_text

        # 2. Unicode normalisation (meaning-preserving).
        working, ops = self._unicode.normalize(working)
        operations.extend(ops)

        # 3a. Structural OCR fixes BEFORE protection so that repaired URLs
        #     ("http//x.com" -> "http://x.com") are protected in full.
        working, corrections = self._corrector.correct_structural(working)

        # 4. Entity preservation - shield every forensic entity.
        preserved = self._preserver.protect(working)
        working = preserved.text
        if preserved.placeholder_count():
            operations.append(f"entities_protected({preserved.placeholder_count()})")

        # 3b. Token-level OCR fixes AFTER protection: a homoglyph inside an
        #     entity (supp0rt@bank.com) is evidence and is never altered.
        working, token_fixes = self._corrector.correct_tokens(working)
        corrections = corrections + token_fixes
        if corrections:
            operations.append(f"ocr_corrections({len(corrections)})")
            for correction in corrections:
                self._log.debug("ocr fix: %r -> %r", correction.original,
                                correction.corrected)

        # 5. Noise removal.
        working, ops = self._noise.remove_noise(working)
        operations.extend(ops)

        # 6. Whitespace normalisation (paragraphs preserved).
        working, ops = self._noise.normalize_whitespace(working)
        operations.extend(ops)

        # 7. Sentence reconstruction (placeholders are atomic, never merged).
        working, ops = self._reconstructor.reconstruct(working)
        operations.extend(ops)

        # 8. Roman-Nepali line normalisation (lowercase + repeated chars).
        working, ops = self._normalize_roman_lines(working)
        operations.extend(ops)

        # 9. Restore original entity spans byte-for-byte.
        cleaned_text = self._preserver.restore(working, preserved)

        # 10. Entity extraction + keyword analysis on the cleaned text.
        extracted = self._extractor.extract(cleaned_text)
        keyword_report = self._keywords.analyze(cleaned_text)

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        result = CleaningResult(
            case_id=case_id,
            evidence_id=evidence_id,
            raw_text=raw_text,  # forensic invariant: stored verbatim
            cleaned_text=cleaned_text,
            language=language,
            line_languages={str(r.line_number): r.language for r in line_results},
            entities={
                entity_type: [
                    EntityRecord(value=e.value, normalized=e.normalized)
                    for e in items
                ]
                for entity_type, items in extracted.items()
            },
            keywords=keyword_report.keyword_frequency,
            risk_signals=keyword_report.risk_signals,
            statistics=self._statistics(
                cleaned_text, line_results, operations,
                [f"{c.original}->{c.corrected}" for c in corrections],
                self._extractor.total_count(extracted),
                preserved.placeholder_count(),
            ),
            processing_time_ms=elapsed_ms,
        )
        self._log.info(
            "cleaned %s: %d entities, %d keyword hits, %.1f ms",
            evidence_id or "<text>", result.statistics.entity_count,
            keyword_report.total_hits, elapsed_ms,
        )
        return result

    # ---------------------------------------------------------------- helpers

    def _normalize_roman_lines(self, text: str) -> tuple[str, List[str]]:
        """Lowercase + collapse repeats on lines detected as Roman Nepali."""
        changed = 0
        output: List[str] = []
        for line in text.split("\n"):
            if self._detector.detect_line(line) == "roman_nepali":
                normalized = self._noise.normalize_roman_nepali_line(line)
                if normalized != line:
                    changed += 1
                output.append(normalized)
            else:
                output.append(line)
        operations = [f"roman_nepali_lines_normalized({changed})"] if changed else []
        return "\n".join(output), operations

    @staticmethod
    def _statistics(
        cleaned_text: str,
        line_results: list,
        operations: List[str],
        corrections: List[str],
        entity_count: int,
        protected: int,
    ) -> CleaningStatistics:
        lines = [line for line in cleaned_text.splitlines() if line.strip()]
        words = cleaned_text.split()
        languages = sorted(
            {r.language for r in line_results if r.language != "unknown"}
        )
        return CleaningStatistics(
            characters=len(cleaned_text),
            words=len(words),
            lines=len(lines),
            average_line_length=(
                round(sum(len(l) for l in lines) / len(lines), 1) if lines else 0.0
            ),
            languages_detected=languages,
            entity_count=entity_count,
            cleaning_operations=operations,
            ocr_corrections=corrections,
            protected_entities=protected,
        )
