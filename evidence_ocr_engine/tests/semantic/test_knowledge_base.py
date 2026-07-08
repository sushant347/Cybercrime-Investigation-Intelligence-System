"""Tests for the three new knowledge resources and their integration into
the candidate generator. Data-only additions; existing behaviour preserved."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modules.evidence.semantic.candidate_generator import CandidateGenerator
from backend.modules.evidence.semantic.knowledge_base import KnowledgeBase

_DATA = Path(__file__).resolve().parents[2] / (
    "backend/modules/evidence/semantic/data")


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase()


@pytest.fixture(scope="module")
def gen() -> CandidateGenerator:
    return CandidateGenerator()


def _first(gen: CandidateGenerator, token: str):
    cands = gen.generate(token)
    return cands[0] if cands else None


# --------------------------------------------------------- resource integrity


def test_all_three_json_files_valid() -> None:
    for name in ("cyber_dictionary.json", "canonical_words.json",
                 "ocr_confusion_words.json"):
        data = json.loads((_DATA / name).read_text(encoding="utf-8"))
        assert data and "_meta" in data


def test_resource_counts(kb: KnowledgeBase) -> None:
    assert kb.ocr_confusion_count >= 60
    assert kb.cyber_term_count >= 100
    assert kb.canonical_count >= 50


# ------------------------------------------------ OCR confusion dictionary


@pytest.mark.parametrize("wrong,right", [
    ("Go०gle", "Google"),
    ("F८", "FC"),
    ("Nepव", "Nepal"),
    ("Seवson", "Season"),
    ("Facebo०k", "Facebook"),
    ("Instagraं", "Instagram"),
    ("KhaIti", "Khalti"),
    ("eSeवा", "eSewa"),
    ("Teलegram", "Telegram"),
    ("मोवाइल", "मोबाइल"),          # Nepali OCR confusion
    ("सुरक्शा", "सुरक्षा"),
    ("पासवड", "पासवर्ड"),
])
def test_ocr_confusion_lookup(kb: KnowledgeBase, wrong: str, right: str) -> None:
    assert kb.lookup_ocr_confusion(wrong) == right


def test_every_ocr_confusion_entry_produces_that_candidate(gen: CandidateGenerator) -> None:
    data = json.loads((_DATA / "ocr_confusion_words.json").read_text(encoding="utf-8"))
    for wrong, right in data["confusions"].items():
        if wrong == right:
            continue
        proposals = [c.proposal for c in gen.generate(wrong)]
        assert right in proposals, f"{wrong!r} should propose {right!r}"


# ------------------------------------------------------- cyber dictionary


@pytest.mark.parametrize("variant,canonical", [
    ("google", "Google"),
    ("esewa", "eSewa"),
    ("khalti", "Khalti"),
    ("telegram", "Telegram"),
    ("chrome", "Chrome"),
    ("windows", "Windows"),
])
def test_cyber_dictionary_membership(kb: KnowledgeBase, variant: str, canonical: str) -> None:
    # The canonical form is a known cyber term (case-insensitive).
    assert kb.is_known_term(variant)
    assert kb.lookup_cyber(variant) == canonical or kb.lookup_canonical(variant) == canonical


# ----------------------------------------------------- canonical mappings


@pytest.mark.parametrize("variant,canonical", [
    ("google", "Google"),
    ("gooogle", "Google"),
    ("facebook", "Facebook"),
    ("esewa", "eSewa"),
    ("imepay", "IME Pay"),
    ("connectips", "ConnectIPS"),
    ("otp", "OTP"),
])
def test_canonical_mapping(kb: KnowledgeBase, variant: str, canonical: str) -> None:
    assert kb.lookup_canonical(variant) == canonical


def test_every_canonical_entry_maps(kb: KnowledgeBase) -> None:
    data = json.loads((_DATA / "canonical_words.json").read_text(encoding="utf-8"))
    for variant, canonical in data["mappings"].items():
        if variant.lower() == canonical.lower() and variant == canonical:
            continue
        assert kb.lookup_canonical(variant) == canonical


# ------------------------------------------------------------- priority order


def test_ocr_confusion_has_highest_priority(gen: CandidateGenerator) -> None:
    """A token in the OCR-confusion dict yields that correction FIRST."""
    first = _first(gen, "Go०gle")
    assert first is not None and first.source == "ocr_confusion"
    assert first.proposal == "Google"


def test_cyber_used_when_no_ocr_or_canonical_hit(gen: CandidateGenerator) -> None:
    # "esewa" is not an OCR-confusion key but is a cyber term / canonical.
    proposals = {(c.source, c.proposal) for c in gen.generate("esewa")}
    assert ("cyber_dictionary", "eSewa") in proposals or ("canonical", "eSewa") in proposals


def test_source_labels_are_known(gen: CandidateGenerator) -> None:
    valid = {"ocr_confusion", "cyber_dictionary", "canonical",
             "dictionary", "character_confusion"}
    for token in ("Go०gle", "Seवson", "esewa", "मोवाइल"):
        for c in gen.generate(token):
            assert c.source in valid


# -------------------------------------------------------- backward compatibility


def test_generate_signature_and_contract_unchanged(gen: CandidateGenerator) -> None:
    cands = gen.generate("Seवson")
    assert cands and hasattr(cands[0], "original") and hasattr(cands[0], "proposal")
    assert hasattr(cands[0], "source") and hasattr(cands[0], "detail")
    assert cands[0].original == "Seवson"


def test_clean_token_yields_no_candidates(gen: CandidateGenerator) -> None:
    assert gen.generate("random123") == []


def test_generator_works_without_knowledge_base() -> None:
    """Injecting an empty KB must not break generation (graceful)."""
    class EmptyKB:
        ocr_confusion_count = cyber_term_count = canonical_count = 0
        def lookup_ocr_confusion(self, t): return None
        def lookup_cyber(self, t): return None
        def lookup_canonical(self, t): return None
        def is_known_term(self, t): return False
    gen = CandidateGenerator(knowledge_base=EmptyKB())
    # Falls back to the existing dictionaries / confusion matrix.
    assert isinstance(gen.generate("Seवson"), list)
