"""Module 2 / Prompt 2 - Hybrid Multilingual Forensic Text Cleaning and
Entity Extraction Engine.

Public API::

    from backend.modules.evidence.cleaning import CleaningPipeline, CleaningService

    result = CleaningPipeline().clean(raw_ocr_text)
    print(result.cleaned_text, result.entities, result.keywords)

    CleaningService(EvidenceConfig.from_env()).clean_case("CASE_0001")
"""

from .cleaning_pipeline import CleaningPipeline
from .cleaning_schemas import CleaningResult, CleaningStatistics, EntityRecord
from .cleaning_service import CleaningService
from .cleaning_storage import (
    EntityRepository,
    KeywordStatisticsRepository,
    OCRResultsAugmenter,
)
from .entity_extractor import EntityExtractor, ExtractedEntity
from .entity_preserver import EntityPreserver, PreservationResult
from .keyword_analyzer import KeywordAnalyzer, KeywordReport
from .language_detector import BaseLanguageDetector, HeuristicLanguageDetector
from .noise_cleaner import NoiseCleaner
from .ocr_corrector import Correction, OCRCorrector
from .sentence_reconstructor import SentenceReconstructor
from .unicode_normalizer import UnicodeNormalizer

__all__ = [
    "CleaningPipeline",
    "CleaningService",
    "CleaningResult",
    "CleaningStatistics",
    "EntityRecord",
    "EntityRepository",
    "KeywordStatisticsRepository",
    "OCRResultsAugmenter",
    "EntityExtractor",
    "ExtractedEntity",
    "EntityPreserver",
    "PreservationResult",
    "KeywordAnalyzer",
    "KeywordReport",
    "BaseLanguageDetector",
    "HeuristicLanguageDetector",
    "NoiseCleaner",
    "OCRCorrector",
    "Correction",
    "SentenceReconstructor",
    "UnicodeNormalizer",
]
