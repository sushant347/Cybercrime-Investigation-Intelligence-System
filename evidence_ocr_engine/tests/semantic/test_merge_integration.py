"""Merge tests: integration, regression and full-pipeline verification for
the Semantic Correction Engine wired into the OCR pipeline.

Confirms that semantic_text feeds entity extraction, that every earlier
section is preserved byte-for-byte, and that the full ingest → clean →
enhance → semantic chain runs end-to-end offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.json_storage import JSONCaseStorage
from backend.modules.evidence.models import OCRLine
from backend.modules.evidence.pipeline import EvidencePipeline
from backend.modules.evidence.semantic import (
    EvidenceProcessingOrchestrator,
    SemanticCorrectionPipeline,
)
from backend.modules.evidence.semantic.validator import (
    BaseSemanticValidator,
    ValidationVerdict,
)
from tests.conftest import FakeOCR


class AcceptSeason(BaseSemanticValidator):
    name = "accept-season"

    def validate(self, s, o, c):
        ok = c in {"Season", "Nepal"}
        return ValidationVerdict(ok, 0.9 if ok else 0.2, "test")


def _ingest(config: EvidenceConfig, tmp_path: Path, text: str) -> str:
    source = tmp_path / "evidence.png"
    Image.new("RGB", (400, 200), "white").save(source)
    return EvidencePipeline(
        config, FakeOCR(lines=[OCRLine(text=text, confidence=0.5)])
    ).process_file(source).case_id


# --------------------------------------------------------- entity extraction hook


def test_entities_extracted_from_semantic_text() -> None:
    """semantic_text is the input to entity extraction (merged pipeline)."""
    pipeline = SemanticCorrectionPipeline(validator=AcceptSeason())
    result = pipeline.correct(
        "Ramesh ko Seवson ticket, visit https://book.example/x mail a@book.com")
    assert "Season" in result.semantic_text
    # Entities were pulled from semantic_text using the existing extractor.
    urls = [e.value for e in result.entities.get("urls", [])]
    emails = [e.value for e in result.entities.get("emails", [])]
    assert "https://book.example/x" in urls
    assert "a@book.com" in emails


def test_entities_field_is_json_serialisable() -> None:
    result = SemanticCorrectionPipeline(validator=AcceptSeason()).correct(
        "call +977-9812345678 now")
    payload = result.model_dump()
    assert "entities" in payload
    assert isinstance(payload["entities"], dict)


# ------------------------------------------------------------------- full pipeline


def test_full_pipeline_ingest_clean_enhance_semantic(
    config: EvidenceConfig, tmp_path
) -> None:
    case_id = _ingest(config, tmp_path, "Ramesh ko Seवson ticket kinyo")
    pipeline = SemanticCorrectionPipeline(validator=AcceptSeason())
    summary = EvidenceProcessingOrchestrator(
        config, semantic_pipeline=pipeline).process_case(case_id)

    assert summary["stages"] == {"cleaning": 1, "enhancement": 1, "semantic": 1}
    document = JSONCaseStorage(config).load_case(case_id)
    evidence = document["evidence"][0]
    # All four text layers present and correctly chained.
    assert evidence["raw_text"]
    assert evidence["cleaning"]["cleaned_text"]
    assert evidence["enhancement"]["enhanced_text"]
    sc = evidence["semantic_correction"]
    assert sc["semantic_text"]
    assert sc["enhanced_text"] == evidence["enhancement"]["enhanced_text"]


# ------------------------------------------------------------- regression: order


def test_forensic_layers_never_overwritten(config: EvidenceConfig, tmp_path) -> None:
    case_id = _ingest(config, tmp_path, "Nepव FC Seवson https://x.example/a")
    storage = JSONCaseStorage(config)

    from backend.modules.evidence.cleaning.cleaning_service import CleaningService
    from backend.modules.evidence.enhancement.enhancement_service import EnhancementService
    from backend.modules.evidence.semantic import SemanticCorrectionService

    CleaningService(config).clean_case(case_id)
    raw_after_clean = storage.load_case(case_id)["evidence"][0]["raw_text"]
    cleaned = storage.load_case(case_id)["evidence"][0]["cleaning"]["cleaned_text"]

    EnhancementService(config).enhance_case(case_id)
    enhanced = storage.load_case(case_id)["evidence"][0]["enhancement"]["enhanced_text"]
    # raw and cleaned unchanged by enhancement.
    ev = storage.load_case(case_id)["evidence"][0]
    assert ev["raw_text"] == raw_after_clean
    assert ev["cleaning"]["cleaned_text"] == cleaned

    SemanticCorrectionService(
        config, pipeline=SemanticCorrectionPipeline(validator=AcceptSeason())
    ).correct_case(case_id)
    ev = storage.load_case(case_id)["evidence"][0]
    # raw / cleaned / enhanced ALL still byte-for-byte intact after semantic.
    assert ev["raw_text"] == raw_after_clean
    assert ev["cleaning"]["cleaned_text"] == cleaned
    assert ev["enhancement"]["enhanced_text"] == enhanced
    assert ev["semantic_correction"]["semantic_text"]


def test_cleaning_entities_csv_still_written(config: EvidenceConfig, tmp_path) -> None:
    """Existing entities.csv (from cleaning) is untouched by the merge."""
    case_id = _ingest(config, tmp_path, "mail help@bank.com now")
    from backend.modules.evidence.cleaning.cleaning_service import CleaningService
    from backend.modules.evidence.semantic import SemanticCorrectionService

    CleaningService(config).clean_case(case_id)
    entities_csv = config.storage_dir / "entities.csv"
    assert entities_csv.exists()
    rows_before = entities_csv.read_text(encoding="utf-8")

    SemanticCorrectionService(
        config, pipeline=SemanticCorrectionPipeline(validator=AcceptSeason())
    ).correct_case(case_id)
    # The merge does not write to entities.csv (semantic entities live in JSON).
    assert entities_csv.read_text(encoding="utf-8") == rows_before


def test_orchestrator_unknown_case_raises(config: EvidenceConfig) -> None:
    from backend.modules.evidence.utils import EvidenceError
    with pytest.raises(EvidenceError):
        EvidenceProcessingOrchestrator(config).process_case("CASE_9999")
