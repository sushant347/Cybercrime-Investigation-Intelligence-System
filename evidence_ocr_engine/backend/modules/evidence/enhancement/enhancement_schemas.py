"""Pydantic output contract of the enhancement framework (Prompt 2.5).

The result adds a *third* text representation. Forensic hierarchy::

    raw_text       (Prompt 1)  - verbatim OCR output, never modified
    cleaned_text   (Prompt 2)  - cleaned working copy, never modified here
    enhanced_text  (Prompt 2.5) - the only field that may contain OCR
                                  corrections; every one is logged

The layout-aware upgrade adds two *views* over the enhanced text
(``ui_text`` / ``message_text``) - views never modify the text itself.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class CorrectionEntry(BaseModel):
    """One logged correction (spec format + provenance extras)."""

    original: str
    corrected: str
    confidence: float = Field(ge=0.0, le=1.0, description="OCR confidence of the source line")
    rule: str = Field(description=(
        "dictionary_match | fuzzy_dictionary_match | homoglyph_resolution | "
        "character_confusion | script_consistency | url_scheme_fix | "
        "www_prefix_fix | danda_* | pipe_to_danda | unicode_validation | "
        "entity_safe:*"
    ))
    language: str = Field(default="", description="nepali | english | mixed | ''")
    context_score: float = Field(default=0.0, ge=0.0, le=1.0)
    line: int = Field(default=0, description="1-based line number (0 = global)")
    character_replacement: str = Field(
        default="", description="Character-level substitutions, e.g. 'व→a, ८→C'")
    dictionary_match: str = Field(
        default="", description="Vocabulary that validated the correction")


class LayoutLineEntry(BaseModel):
    """Per-line layout classification (audit view)."""

    line: int
    role: str
    text: str


class CorrectionStatistics(BaseModel):
    """Aggregated quality metrics of one enhancement run."""

    total_corrections: int = 0
    dictionary_corrections: int = 0
    unicode_corrections: int = 0
    english_corrections: int = 0
    nepali_corrections: int = 0
    confidence_based: int = 0
    rule_based: int = 0
    entity_punctuation_fixes: int = 0
    character_confusion_corrections: int = 0
    mixed_script_corrections: int = 0
    layout_ui_lines: int = 0
    average_confidence_improvement: float = Field(
        default=0.0,
        description="Mean (context_score - ocr_confidence) over applied "
                    "token corrections; proxy for quality uplift")
    lines_analyzed: int = 0
    lines_high_confidence: int = 0
    lines_correctable: int = 0
    document_confidence: float = 0.0
    nepali_correction_rate: float = Field(
        default=0.0, description="nepali corrections / Devanagari word count")
    english_correction_rate: float = Field(
        default=0.0, description="english corrections / Latin word count")


class EnhancementResult(BaseModel):
    """Complete result for one evidence item's enhancement pass."""

    case_id: str = ""
    evidence_id: str = ""
    cleaned_text: str = Field(description="Input from Prompt 2 - never modified")
    enhanced_text: str = Field(default="", description="Analysis-ready text; "
                               "the only field that may contain corrections")
    ui_text: str = Field(default="", description="Mobile UI chrome separated "
                         "from the conversation (view, not a modification)")
    message_text: str = Field(default="", description="Conversation content "
                              "only: senders, chat timestamps, message bodies")
    layout: List[LayoutLineEntry] = Field(default_factory=list)
    corrections: List[CorrectionEntry] = Field(default_factory=list)
    correction_statistics: CorrectionStatistics = Field(
        default_factory=CorrectionStatistics)
    processing_time_ms: float = 0.0
