"""Semantic Correction Engine - context-validated OCR correction.

A NEW, independent module that sits between rule enhancement (Prompt 2.5) and
entity extraction. It uses a pretrained ``xlm-roberta-base`` model for
*inference only* to validate rule-proposed corrections in multilingual
context - the model never generates text. Forensic invariants (raw/cleaned/
enhanced text) are never modified; only ``semantic_text`` is produced.

Public API::

    from backend.modules.evidence.semantic import SemanticCorrectionPipeline

    result = SemanticCorrectionPipeline().correct(enhanced_text)
    print(result.semantic_text, result.accepted_corrections)

    SemanticCorrectionService(EvidenceConfig.from_env()).correct_case("CASE_0001")
"""

from .candidate_generator import Candidate, CandidateGenerator
from .entity_protection import EntityProtector, ProtectedText
from .mixed_script_detector import MixedScriptDetector, SuspiciousToken
from .orchestrator import EvidenceProcessingOrchestrator
from .semantic_pipeline import SemanticCorrectionPipeline
from .semantic_schemas import (
    EntityRef,
    SemanticCorrection,
    SemanticResult,
    SemanticStatistics,
)
from .semantic_service import SemanticCorrectionService
from .sentence_builder import SentenceBuilder
from .validator import (
    BaseSemanticValidator,
    HeuristicSemanticValidator,
    ValidationVerdict,
    XLMRobertaValidator,
)

__all__ = [
    "SemanticCorrectionPipeline",
    "SemanticCorrectionService",
    "EvidenceProcessingOrchestrator",
    "EntityRef",
    "BaseSemanticValidator",
    "XLMRobertaValidator",
    "HeuristicSemanticValidator",
    "ValidationVerdict",
    "EntityProtector",
    "ProtectedText",
    "MixedScriptDetector",
    "SuspiciousToken",
    "SentenceBuilder",
    "CandidateGenerator",
    "Candidate",
    "SemanticCorrection",
    "SemanticResult",
    "SemanticStatistics",
]
