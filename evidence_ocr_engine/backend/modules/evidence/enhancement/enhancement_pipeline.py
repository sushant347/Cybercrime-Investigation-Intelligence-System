"""Forensic OCR Post-Processing - Hybrid Character Confusion Resolution
Framework (Prompt 2.5, layout-aware upgrade).

Consumes ``cleaned_text`` (Prompt 2) plus the per-line OCR confidences
(Prompt 1) and produces ``enhanced_text`` - the only representation that may
contain corrections. Neither input is ever modified.

Stage order::

    cleaned_text -> OCR confidence analysis -> structural rules
    -> entity preservation -> unicode validation
    -> confidence-gated correction (dictionary + homoglyph +
       character-confusion + script-consistency, context-validated)
    -> entity restoration (entity-safe punctuation fixes only)
    -> layout analysis (ui_text / message_text views)
    -> enhanced_text + correction log + statistics

All collaborators are injected; every correction is logged with the OCR
confidence, rule, character replacements and context score that justified it.
"""

from __future__ import annotations

import re
import time
from typing import Any, List, Mapping, Optional, Sequence

from ..logger import get_logger
from ..cleaning.entity_preserver import EntityPreserver
from .character_confusion import CharacterConfusionResolver, ConfusionMatrix
from .confidence_analyzer import ConfidenceAnalyzer, ConfidenceMap, ConfidenceTier
from .confidence_corrector import ConfidenceCorrector
from .context_corrector import ContextCorrector
from .english_dictionary import EnglishDictionary
from .enhancement_schemas import (
    CorrectionEntry,
    CorrectionStatistics,
    EnhancementResult,
    LayoutLineEntry,
)
from .layout_analyzer import LayoutAnalyzer
from .nepali_dictionary import NepaliDictionary
from .ocr_correction_rules import OCRCorrectionRules
from .unicode_validator import UnicodeValidator

_DEVANAGARI_WORD = re.compile(r"[ऀ-ॿ]+")
_LATIN_WORD = re.compile(r"[A-Za-z]+")


class EnhancementPipeline:
    """Enhances one cleaned text under strict forensic constraints."""

    def __init__(
        self,
        confidence_analyzer: Optional[ConfidenceAnalyzer] = None,
        unicode_validator: Optional[UnicodeValidator] = None,
        correction_rules: Optional[OCRCorrectionRules] = None,
        nepali_dictionary: Optional[NepaliDictionary] = None,
        english_dictionary: Optional[EnglishDictionary] = None,
        context_corrector: Optional[ContextCorrector] = None,
        entity_preserver: Optional[EntityPreserver] = None,
        confusion_matrix: Optional[ConfusionMatrix] = None,
        layout_analyzer: Optional[LayoutAnalyzer] = None,
    ) -> None:
        self._confidence = confidence_analyzer or ConfidenceAnalyzer()
        self._unicode = unicode_validator or UnicodeValidator()
        self._rules = correction_rules or OCRCorrectionRules()
        self._preserver = entity_preserver or EntityPreserver()
        self._context = context_corrector or ContextCorrector()
        self._layout = layout_analyzer or LayoutAnalyzer()
        nepali = nepali_dictionary or NepaliDictionary()
        english = english_dictionary or EnglishDictionary()
        resolver = CharacterConfusionResolver(
            matrix=confusion_matrix or ConfusionMatrix(),
            nepali=nepali, english=english,
        )
        self._corrector = ConfidenceCorrector(nepali, english, self._context,
                                              confusion_resolver=resolver)
        self._log = get_logger("enhancement.pipeline")

    def enhance(
        self,
        cleaned_text: str,
        ocr_pages: Sequence[Mapping[str, Any]] | None = None,
        case_id: str = "",
        evidence_id: str = "",
    ) -> EnhancementResult:
        """Produce ``enhanced_text`` from ``cleaned_text`` (kept verbatim)."""
        started = time.perf_counter()
        corrections: List[CorrectionEntry] = []

        # 1. OCR confidence analysis.
        confidence_map = self._confidence.analyze(cleaned_text, ocr_pages)

        working = cleaned_text

        # 2. Structural rules FIRST ("http//x" -> "http://x") so repaired
        #    URLs are recognised and shielded by entity preservation.
        working, rule_fixes = self._rules.apply(working)
        for fix in rule_fixes:
            corrections.append(
                CorrectionEntry(
                    original=fix.original, corrected=fix.corrected,
                    confidence=confidence_map.document_confidence,
                    rule=fix.rule, language="",
                )
            )

        # 3. Entity preservation: URLs, emails, hashes, wallets, phones,
        #    OTP-bearing spans etc. are shielded before any word-level change.
        preserved = self._preserver.protect(working)
        working = preserved.text

        # 4. Unicode validation (invalid sequences only; meaning preserved).
        working, unicode_report = self._unicode.validate(working)
        for operation in unicode_report.operations:
            corrections.append(
                CorrectionEntry(
                    original="", corrected="", confidence=1.0,
                    rule=f"unicode_validation:{operation}", language="",
                )
            )

        # 5. Confidence-gated correction: dictionary, homoglyph, character
        #    confusion and script consistency - all context-validated.
        working, token_entries, tier_stats = self._correct_lines(
            working, confidence_map
        )
        corrections.extend(token_entries)

        # 6. Restore entities byte-for-byte; only entity-safe punctuation
        #    fixes (http// -> http://) are permitted inside them.
        enhanced_text, entity_fixes = self._restore_entities(working, preserved)
        for fix in entity_fixes:
            corrections.append(
                CorrectionEntry(
                    original=fix.original, corrected=fix.corrected,
                    confidence=confidence_map.document_confidence,
                    rule=f"entity_safe:{fix.rule}", language="",
                )
            )

        # 7. Layout-aware reconstruction: separate mobile UI chrome from
        #    conversation content (views only - enhanced_text is complete).
        layout = self._layout.analyze(enhanced_text)

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        result = EnhancementResult(
            case_id=case_id,
            evidence_id=evidence_id,
            cleaned_text=cleaned_text,   # forensic invariant
            enhanced_text=enhanced_text,
            ui_text=layout.ui_text,
            message_text=layout.message_text,
            layout=[LayoutLineEntry(line=l.line, role=l.role, text=l.text)
                    for l in layout.lines],
            corrections=corrections,
            correction_statistics=self._statistics(
                cleaned_text, corrections, unicode_report.total,
                len(entity_fixes), confidence_map, tier_stats,
                layout.ui_line_count,
            ),
            processing_time_ms=elapsed_ms,
        )
        stats = result.correction_statistics
        self._log.info(
            "enhanced %s: %d corrections (%d nepali, %d english, %d confusion, "
            "%d unicode), %d UI line(s) separated, %.1f ms",
            evidence_id or "<text>", stats.total_corrections,
            stats.nepali_corrections, stats.english_corrections,
            stats.character_confusion_corrections, stats.unicode_corrections,
            stats.layout_ui_lines, elapsed_ms,
        )
        return result

    # ---------------------------------------------------------------- internal

    def _correct_lines(
        self, text: str, confidence_map: ConfidenceMap
    ) -> tuple[str, List[CorrectionEntry], dict[str, int]]:
        """Run the confidence corrector line by line."""
        entries: List[CorrectionEntry] = []
        output: List[str] = []
        stats = {"lines": 0, "high": 0, "correctable": 0}

        for number, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                output.append(line)
                continue
            stats["lines"] += 1
            confidence = confidence_map.for_line(number)
            tier = confidence_map.tier_for_line(number)
            if tier == ConfidenceTier.HIGH:
                stats["high"] += 1
            else:
                stats["correctable"] += 1
            # Every line is processed: the corrector applies only exact/mixed-
            # script fixes on high-confidence lines and additionally fuzzy fixes
            # on low-confidence lines. Unambiguous OCR errors are repaired
            # regardless of the OCR score; trusted text is never *guessed* at.
            corrected_line, token_fixes = self._corrector.correct_line(
                line, confidence, tier, document_text=text
            )
            output.append(corrected_line)
            for fix in token_fixes:
                entries.append(
                    CorrectionEntry(
                        original=fix.original, corrected=fix.corrected,
                        confidence=fix.confidence, rule=fix.rule,
                        language=fix.language,
                        context_score=fix.context_score, line=number,
                        character_replacement=fix.character_replacement,
                        dictionary_match=fix.dictionary_match,
                    )
                )
        return "\n".join(output), entries, stats

    def _restore_entities(self, text: str, preserved) -> tuple[str, list]:
        """Restore originals; apply only entity-safe punctuation fixes."""
        entity_fixes = []
        for entity in preserved.vault.values():
            fixed, fixes = self._rules.apply_to_entity(entity.original)
            if fixes:
                entity.original = fixed
                entity_fixes.extend(fixes)
        return self._preserver.restore(text, preserved), entity_fixes

    @staticmethod
    def _statistics(
        cleaned_text: str,
        corrections: List[CorrectionEntry],
        unicode_total: int,
        entity_fix_count: int,
        confidence_map: ConfidenceMap,
        tier_stats: dict[str, int],
        ui_lines: int,
    ) -> CorrectionStatistics:
        dictionary = sum(
            1 for c in corrections
            if c.rule in ("dictionary_match", "fuzzy_dictionary_match")
        )
        confusion = sum(
            1 for c in corrections
            if c.rule in ("character_confusion", "script_consistency")
        )
        mixed = sum(1 for c in corrections if c.language == "mixed")
        nepali = sum(1 for c in corrections if c.language == "nepali")
        english = sum(
            1 for c in corrections
            if c.language == "english" or c.rule == "homoglyph_resolution"
        )
        token_corrections = [c for c in corrections if c.line > 0]
        confidence_based = len(token_corrections)
        improvement = (
            round(sum(max(0.0, c.context_score - c.confidence)
                      for c in token_corrections) / confidence_based, 4)
            if confidence_based else 0.0
        )
        rule_based = sum(
            1 for c in corrections
            if c.rule in ("url_scheme_fix", "www_prefix_fix", "danda_dedup",
                          "danda_spacing", "pipe_to_danda")
            or c.rule.startswith("entity_safe:")
        )
        devanagari_words = len(_DEVANAGARI_WORD.findall(cleaned_text)) or 1
        latin_words = len(_LATIN_WORD.findall(cleaned_text)) or 1
        return CorrectionStatistics(
            total_corrections=len(corrections),
            dictionary_corrections=dictionary,
            unicode_corrections=unicode_total,
            english_corrections=english,
            nepali_corrections=nepali,
            confidence_based=confidence_based,
            rule_based=rule_based,
            entity_punctuation_fixes=entity_fix_count,
            character_confusion_corrections=confusion,
            mixed_script_corrections=mixed,
            layout_ui_lines=ui_lines,
            average_confidence_improvement=improvement,
            lines_analyzed=tier_stats.get("lines", 0),
            lines_high_confidence=tier_stats.get("high", 0),
            lines_correctable=tier_stats.get("correctable", 0),
            document_confidence=confidence_map.document_confidence,
            nepali_correction_rate=round(nepali / devanagari_words, 4),
            english_correction_rate=round(english / latin_words, 4),
        )
