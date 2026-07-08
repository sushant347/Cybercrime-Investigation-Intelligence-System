"""Module 2 / Prompt 2.5 - Forensic OCR Post-Processing and
Confidence-Based Correction Framework.

Public API::

    from backend.modules.evidence.enhancement import (
        EnhancementPipeline, EnhancementService,
    )

    result = EnhancementPipeline().enhance(cleaned_text, ocr_pages)
    print(result.enhanced_text, result.correction_statistics)

    EnhancementService(EvidenceConfig.from_env()).enhance_case("CASE_0001")
"""

from .character_confusion import (
    CharacterConfusionResolver,
    ConfusionCandidate,
    ConfusionMatrix,
)
from .layout_analyzer import LayoutAnalyzer, LayoutLine, LayoutResult
from .script_detector import ScriptDetector, ScriptProfile
from .confidence_analyzer import (
    ConfidenceAnalyzer,
    ConfidenceMap,
    ConfidenceTier,
    tier_for,
)
from .confidence_corrector import ConfidenceCorrector, TokenCorrection
from .context_corrector import ContextCorrector, ContextDecision
from .correction_logger import CorrectionLogRepository
from .english_dictionary import EnglishDictionary
from .enhancement_pipeline import EnhancementPipeline
from .enhancement_schemas import (
    CorrectionEntry,
    CorrectionStatistics,
    EnhancementResult,
)
from .enhancement_service import EnhancementService
from .nepali_dictionary import NepaliDictionary
from .ocr_correction_rules import OCRCorrectionRules, RuleFix
from .unicode_validator import UnicodeValidator, ValidationReport

__all__ = [
    "CharacterConfusionResolver",
    "ConfusionCandidate",
    "ConfusionMatrix",
    "LayoutAnalyzer",
    "LayoutLine",
    "LayoutResult",
    "ScriptDetector",
    "ScriptProfile",
    "ConfidenceAnalyzer",
    "ConfidenceMap",
    "ConfidenceTier",
    "tier_for",
    "ConfidenceCorrector",
    "TokenCorrection",
    "ContextCorrector",
    "ContextDecision",
    "CorrectionLogRepository",
    "EnglishDictionary",
    "NepaliDictionary",
    "OCRCorrectionRules",
    "RuleFix",
    "UnicodeValidator",
    "ValidationReport",
    "EnhancementPipeline",
    "EnhancementService",
    "CorrectionEntry",
    "CorrectionStatistics",
    "EnhancementResult",
]
