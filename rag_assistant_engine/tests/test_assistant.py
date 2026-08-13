from __future__ import annotations

from ciis_rag.assistant import AssistantService
from ciis_rag.generation.ollama import StructuredGeneration
from ciis_rag.indexing import InMemoryVectorStore, IndexService, ManifestRepository
from ciis_rag.retrieval import RetrievalService


class FakeGenerator:
    def __init__(self, generated):
        self.generated = generated

    def generate(self, query, hits):  # noqa: ARG002
        return self.generated


def service(bundle, config, generated):
    store = InMemoryVectorStore()
    indexing = IndexService(config, store, ManifestRepository(config.manifest_dir))
    return AssistantService(
        indexing, RetrievalService(config, store), FakeGenerator(generated)
    )


def test_answer_returns_validated_sources_entities_and_links(bundle, config):
    assistant = service(bundle, config, StructuredGeneration(
        "The phone connects the chat and receipt [EVID_001] [EVID_002].",
        ("EVID_001", "EVID_002", "EVID_FAKE"),
        False,
    ))
    response = assistant.ask(bundle, "What is linked to 9800000001?")
    assert response.insufficient_evidence is False
    assert {source.evidence_id for source in response.cited_sources} == {
        "EVID_001", "EVID_002"
    }
    assert response.evidence_breakdown[0].entities == (
        "phone_numbers=9800000001",
    )
    assert len(response.shared_entity_links) == 1
    assert "EVID_FAKE" in response.warnings[0]


def test_uncited_model_answer_is_withheld(bundle, config):
    assistant = service(bundle, config, StructuredGeneration(
        "The suspect definitely received the payment.", (), False
    ))
    response = assistant.ask(bundle, "What happened to the payment?")
    assert response.insufficient_evidence is True
    assert "withheld" in response.answer
    assert response.cited_sources == ()


def test_irrelevant_question_abstains_without_calling_generator(bundle, config):
    class MustNotRun:
        def generate(self, query, hits):
            raise AssertionError("generator must not run without relevant evidence")

    assistant = service(bundle, config, StructuredGeneration("", (), False))
    assistant._generator = MustNotRun()
    response = assistant.ask(bundle, "quantum weather satellite")
    assert response.insufficient_evidence is True


def test_missing_exact_money_amount_abstains_without_model_substitution(bundle, config):
    class MustNotRun:
        def generate(self, query, hits):
            raise AssertionError("generator must not substitute a similar amount")

    assistant = service(bundle, config, StructuredGeneration("", (), False))
    assistant._generator = MustNotRun()
    response = assistant.ask(bundle, "Which evidence is connected through NPR 2000?")

    assert response.insufficient_evidence is True
    assert "NPR 2000" in response.answer
    assert "Similar values were not treated as matches" in response.answer
    assert response.cited_sources == ()


def test_explicit_evidence_pair_uses_deterministic_relationship(bundle, config):
    class MustNotRun:
        def generate(self, query, hits):
            raise AssertionError("explicit pair must use stored relationships")

    assistant = service(bundle, config, StructuredGeneration("", (), False))
    assistant._generator = MustNotRun()
    response = assistant.ask(bundle, "What connects EVID_001 and EVID_002?")

    assert response.insufficient_evidence is False
    assert "confidence 0.910" in response.answer
    assert "phone_numbers=9800000001" in response.answer
    assert {source.evidence_id for source in response.cited_sources} == {
        "EVID_001", "EVID_002"
    }
    assert len(response.shared_entity_links) == 1


def test_generated_answer_must_cite_explicit_requested_evidence(bundle, config):
    assistant = service(bundle, config, StructuredGeneration(
        "The receipt explains it [EVID_002].", ("EVID_002",), False
    ))
    response = assistant.ask(bundle, "What happened in EVID_001?")

    assert response.insufficient_evidence is True
    assert "withheld" in response.answer
    assert any("EVID_001" in warning for warning in response.warnings)


def test_explicit_entity_question_uses_extracted_values(bundle, config):
    class MustNotRun:
        def generate(self, query, hits):
            raise AssertionError("explicit entity question must be deterministic")

    assistant = service(bundle, config, StructuredGeneration("", (), False))
    assistant._generator = MustNotRun()
    response = assistant.ask(bundle, "What phone number appears in EVID_001?")

    assert response.insufficient_evidence is False
    assert "phone numbers: 9800000001" in response.answer
    assert response.cited_sources[0].evidence_id == "EVID_001"


def test_explicit_timeline_question_reports_provenance(bundle, config):
    class MustNotRun:
        def generate(self, query, hits):
            raise AssertionError("explicit timeline question must be deterministic")

    assistant = service(bundle, config, StructuredGeneration("", (), False))
    assistant._generator = MustNotRun()
    response = assistant.ask(bundle, "When did EVID_001 occur?")

    assert response.insufficient_evidence is False
    assert "2026-01-01T10:00:00Z" in response.answer
    assert "source=content_chat_timestamp" in response.answer
    assert "inferred=false" in response.answer


def test_citation_only_generated_answer_is_withheld(bundle, config):
    assistant = service(bundle, config, StructuredGeneration(
        "EVID_001", ("EVID_001",), False
    ))
    response = assistant.ask(bundle, "Summarize the payment evidence")

    assert response.insufficient_evidence is True
    assert "withheld" in response.answer
    assert any("substantive" in warning for warning in response.warnings)
