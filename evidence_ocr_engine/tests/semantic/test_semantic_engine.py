"""Tests for the Semantic Correction Engine.

All tests run offline: XLM-R is never downloaded. A deterministic
``FakeValidator`` exercises the pipeline's accept/reject logic, and the
dependency-free ``HeuristicSemanticValidator`` is tested directly. This also
proves the Strategy/DI design - the pipeline works with any validator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.semantic import (
    EntityProtector,
    HeuristicSemanticValidator,
    MixedScriptDetector,
    SemanticCorrectionPipeline,
    SemanticCorrectionService,
    SentenceBuilder,
)
from backend.modules.evidence.semantic.validator import (
    BaseSemanticValidator,
    SLOT,
    ValidationVerdict,
)


class FakeValidator(BaseSemanticValidator):
    """Accepts a fixed set of candidates; rejects everything else."""

    name = "fake"

    def __init__(self, accept: set[str] | None = None, confidence: float = 0.9):
        self._accept = accept if accept is not None else {"Season", "Nepal", "Google"}
        self._confidence = confidence

    def validate(self, sentence_with_slot: str, original: str,
                 candidate: str) -> ValidationVerdict:
        assert SLOT in sentence_with_slot  # pipeline builds a slotted context
        if candidate in self._accept:
            return ValidationVerdict(True, self._confidence, "fake accept")
        return ValidationVerdict(False, 0.2, "fake reject")


def _pipeline(**kwargs) -> SemanticCorrectionPipeline:
    return SemanticCorrectionPipeline(validator=FakeValidator(), **kwargs)


# --------------------------------------------------------- entity protection


def test_entities_protected_and_restored() -> None:
    protector = EntityProtector()
    text = "Visit https://scam.top/login or mail help@bank.com, call +977-9812345678"
    protected = protector.protect(text)
    assert "<URL_1>" in protected.text
    assert "<EMAIL_1>" in protected.text
    assert "<PHONE_1>" in protected.text
    assert "https://scam.top/login" not in protected.text
    assert protector.restore(protected.text, protected) == text


def test_entities_never_become_candidates() -> None:
    """A URL containing mixed-looking characters must not be 'corrected'."""
    pipeline = _pipeline()
    text = "Login at https://Seव-bank.top/x now"
    result = pipeline.correct(text)
    assert "https://Seव-bank.top/x" in result.semantic_text  # entity intact


# --------------------------------------------------------- mixed-script detect


@pytest.mark.parametrize("token", ["Seवson", "Nepव", "Go०gle", "Aज"])
def test_mixed_script_tokens_detected(token: str) -> None:
    assert MixedScriptDetector().is_suspicious(token)


@pytest.mark.parametrize("token", ["Season", "नेपाल", "Google", "12345"])
def test_clean_tokens_not_flagged(token: str) -> None:
    assert not MixedScriptDetector().is_suspicious(token)


# ---------------------------------------------------------- sentence builder


def test_broken_sentences_rebuilt() -> None:
    builder = SentenceBuilder()
    assert builder.rebuild("Verify your\naccount now") == "Verify your account now"
    assert "\n\n" in builder.rebuild("First para\n\nsecond para")


# --------------------------------------------------------- forensic invariants


def test_enhanced_text_never_modified() -> None:
    text = "Ramesh ko Seवson ticket"
    result = _pipeline().correct(text)
    assert result.enhanced_text == text                 # invariant
    assert result.semantic_text != text                 # separate field


def test_accepted_correction_reaches_semantic_text() -> None:
    result = _pipeline().correct("Ramesh ko Seवson ticket kinyo")
    assert "Season" in result.semantic_text
    assert any(c.accepted and c.candidate == "Season" for c in result.corrections)


def test_rejected_candidate_keeps_original_token() -> None:
    # FakeValidator rejects everything except the fixed accept set.
    validator = FakeValidator(accept=set())             # accept nothing
    result = SemanticCorrectionPipeline(validator=validator).correct("Ramesh Seवson aayo")
    assert "Seवson" in result.semantic_text             # unsafe correction rejected
    assert result.accepted_corrections == []
    assert result.rejected_corrections                  # recorded for audit


# ------------------------------------------------------------------- outputs


def test_result_contract_and_confidence() -> None:
    result = _pipeline().correct("Nepव FC ko Seवson")
    stats = result.statistics
    assert stats.suspicious_tokens >= 2
    assert stats.accepted_corrections + stats.rejected_corrections == stats.candidates_evaluated
    assert 0.0 <= result.confidence <= 1.0
    payload = result.model_dump()
    for key in ("enhanced_text", "semantic_text", "corrections",
                "accepted_corrections", "rejected_corrections", "confidence",
                "statistics", "processing_time_ms"):
        assert key in payload
    assert stats.validator == "fake"


def test_no_suspicious_tokens_is_noop() -> None:
    text = "This is a perfectly clean English sentence."
    result = _pipeline().correct(text)
    assert result.semantic_text == text
    assert result.corrections == []


# --------------------------------------------------- heuristic validator (real)


def test_heuristic_validator_accepts_single_script_dictionary_word() -> None:
    v = HeuristicSemanticValidator()
    verdict = v.validate(f"Ramesh ko {SLOT} ticket", "Seवson", "Season")
    assert verdict.confidence > 0.0  # runs without transformers


def test_pipeline_runs_with_heuristic_validator_offline() -> None:
    pipeline = SemanticCorrectionPipeline(validator=HeuristicSemanticValidator())
    result = pipeline.correct("Ramesh ko Seवson ticket")
    assert result.statistics.validator == "heuristic"
    assert result.semantic_text  # produces output without XLM-R


# ------------------------------------------------------------------- service


def test_service_appends_section_without_touching_existing(
    config: EvidenceConfig, tmp_path
) -> None:
    from backend.modules.evidence.cleaning.cleaning_service import CleaningService
    from backend.modules.evidence.enhancement.enhancement_service import (
        EnhancementService,
    )
    from backend.modules.evidence.json_storage import JSONCaseStorage
    from backend.modules.evidence.models import OCRLine
    from backend.modules.evidence.pipeline import EvidencePipeline
    from PIL import Image
    from tests.conftest import FakeOCR

    source = tmp_path / "chat.png"
    Image.new("RGB", (400, 200), "white").save(source)
    lines = [OCRLine(text="Ramesh ko Seवson ticket kinyo", confidence=0.5)]
    case_id = EvidencePipeline(config, FakeOCR(lines=lines)).process_file(source).case_id
    CleaningService(config).clean_case(case_id)
    EnhancementService(config).enhance_case(case_id)

    service = SemanticCorrectionService(
        config, pipeline=SemanticCorrectionPipeline(validator=FakeValidator()))
    results = service.correct_case(case_id)
    assert len(results) == 1

    document = JSONCaseStorage(config).load_case(case_id)
    evidence = document["evidence"][0]
    # Append-only: all prior sections still present and unchanged.
    assert "raw_text" in evidence and "cleaning" in evidence and "enhancement" in evidence
    assert "semantic_correction" in evidence
    sc = evidence["semantic_correction"]
    assert sc["enhanced_text"] == evidence["enhancement"]["enhanced_text"]
    assert sc["semantic_text"]


def test_service_requires_enhancement_first(config: EvidenceConfig, tmp_path) -> None:
    from backend.modules.evidence.models import OCRLine
    from backend.modules.evidence.pipeline import EvidencePipeline
    from PIL import Image
    from tests.conftest import FakeOCR

    source = tmp_path / "x.png"
    Image.new("RGB", (200, 100), "white").save(source)
    case_id = EvidencePipeline(
        config, FakeOCR(lines=[OCRLine(text="hello", confidence=0.9)])
    ).process_file(source).case_id
    # No clean/enhance run -> gracefully skipped, no crash.
    results = SemanticCorrectionService(config).correct_case(case_id)
    assert results == []


# ------------------------------------- audit fixes: ranking, vocab, placeholders


def test_highest_confidence_candidate_selected() -> None:
    """All candidates are evaluated; the highest-confidence ACCEPTED wins."""
    from backend.modules.evidence.semantic.candidate_generator import Candidate
    from backend.modules.evidence.semantic.validator import (
        BaseSemanticValidator, ValidationVerdict)

    class ScoredValidator(BaseSemanticValidator):
        name = "scored"
        def validate(self, s, o, c):
            scores = {"Season": 0.60, "Reason": 0.92}
            return ValidationVerdict(c in scores, scores.get(c, 0.1), "x")

    class TwoCandidates:
        def generate(self, token):
            return [Candidate(token, "Season", "dictionary"),
                    Candidate(token, "Reason", "dictionary")]

    result = SemanticCorrectionPipeline(
        validator=ScoredValidator(), candidate_generator=TwoCandidates()
    ).correct("Ramesh ko Seवson ticket")
    assert "Reason" in result.semantic_text          # 0.92 beat 0.60
    assert result.accepted_corrections[0].candidate == "Reason"
    assert result.accepted_corrections[0].confidence == 0.92


def test_lower_first_candidate_not_chosen_over_higher_later() -> None:
    """Proves it is no longer 'first-acceptable': a later, higher-confidence
    accepted candidate is preferred over an earlier accepted one."""
    from backend.modules.evidence.semantic.candidate_generator import Candidate
    from backend.modules.evidence.semantic.validator import (
        BaseSemanticValidator, ValidationVerdict)

    class V(BaseSemanticValidator):
        name = "v"
        def validate(self, s, o, c):
            return ValidationVerdict(True, {"First": 0.55, "Second": 0.88}[c], "x")

    class G:
        def generate(self, token):
            return [Candidate(token, "First", "dictionary"),
                    Candidate(token, "Second", "dictionary")]

    result = SemanticCorrectionPipeline(validator=V(), candidate_generator=G()
                                        ).correct("aाb Seवson caत")
    accepted = [c for c in result.corrections if c.accepted]
    assert accepted and accepted[0].candidate == "Second"


def test_expanded_vocabulary_generates_brand_candidates() -> None:
    from backend.modules.evidence.semantic.candidate_generator import CandidateGenerator
    gen = CandidateGenerator()
    # Devanagari zero inside a brand now resolves to a vocabulary word.
    assert gen.generate("Go०gle"), "Google-like token should now yield a candidate"
    assert gen.generate("Facebo०k")


def test_placeholder_containing_token_ignored() -> None:
    detector = MixedScriptDetector()
    # A token that merely CONTAINS a placeholder is not a candidate.
    assert not detector.is_suspicious("<URL_1>व-bank")
    found = detector.find("see <URL_1>व-bank.top now and Seवson too")
    tokens = [s.token for s in found]
    assert not any("<URL_1>" in t for t in tokens)
    assert "Seवson" in tokens                         # real mixed-script still caught
