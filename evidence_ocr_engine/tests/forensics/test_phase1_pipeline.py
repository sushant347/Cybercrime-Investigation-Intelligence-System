"""End-to-end Phase-1 pipeline tests (fake OCR engines, temp storage).

Prove the critical guarantees:
* the legacy pipeline result is untouched and chain of custody preserved,
* every Phase-1 report is stored separately under storage/forensics/,
* one failing analysis never aborts the run,
* re-running never overwrites earlier reports.
"""

from __future__ import annotations

import pytest
from PIL import Image

from backend.modules.evidence.forensics.audit import ForensicAuditTrail
from backend.modules.evidence.forensics.config import ForensicsConfig
from backend.modules.evidence.forensics.pipeline import ForensicPhase1Pipeline
from backend.modules.evidence.forensics.repository import ForensicReportRepository
from backend.modules.evidence.forensics.quality.service import QualityAssessmentService
from backend.modules.evidence.forensics.advanced_preprocessing.service import (
    AdvancedPreprocessingService,
)
from backend.modules.evidence.forensics.multi_ocr.fusion import MultiOCRFusionService
from backend.modules.evidence.forensics.forgery.service import ForgeryDetectionService
from backend.modules.evidence.forensics.logos.service import LogoDetectionService
from backend.modules.evidence.forensics.metadata.service import MetadataExtractionService
from backend.modules.evidence.forensics.integrity.service import FileIntegrityService
from backend.modules.evidence.forensics.confidence.service import ConfidenceScoringService
from backend.modules.evidence.pipeline import EvidencePipeline

from ..conftest import FakeOCR
from .conftest import FakeAdapter, make_lines


@pytest.fixture()
def phase1(config, fcfg: ForensicsConfig):
    audit = ForensicAuditTrail(fcfg)
    repo = ForensicReportRepository(fcfg)
    engines = [
        FakeAdapter("paddleocr", make_lines(("Paid Rs 5000 via esewa", 0.93))),
        FakeAdapter("easyocr", make_lines(("Paid Rs 5000 via esewa", 0.88))),
    ]
    return ForensicPhase1Pipeline(
        config, fcfg,
        evidence_pipeline=EvidencePipeline(config, FakeOCR()),
        quality=QualityAssessmentService(fcfg, repo, audit),
        preprocessing=AdvancedPreprocessingService(fcfg, repo, audit),
        fusion=MultiOCRFusionService(fcfg, repo, audit, engines),
        forgery=ForgeryDetectionService(fcfg, repo, audit),
        logos=LogoDetectionService(fcfg, repo, audit),
        metadata=MetadataExtractionService(fcfg, repo, audit),
        integrity=FileIntegrityService(fcfg, repo, audit,
                                       evidence_register_csv=config.evidence_csv),
        confidence=ConfidenceScoringService(fcfg, repo, audit),
        audit=audit,
    ), repo, fcfg


@pytest.fixture()
def evidence_file(tmp_path, text_image):
    path = tmp_path / "screenshot.png"
    Image.fromarray(text_image).save(path)
    return path


def test_full_run_preserves_legacy_behaviour_and_adds_reports(
    phase1, evidence_file, config
):
    pipeline, repo, fcfg = phase1
    outcome = pipeline.process_file(evidence_file, case_title="Phishing case")
    legacy = outcome["legacy_result"]

    # Legacy contract intact: chain of custody + verbatim Paddle raw text.
    assert legacy.hash_verified is True
    assert "Dear customer" in legacy.raw_text
    assert (config.json_dir / f"{legacy.case_id}.json").exists()

    # All Phase-1 reports stored separately.
    eid = legacy.evidence_id
    for name in (fcfg.quality_report_name, fcfg.forgery_report_name,
                 fcfg.metadata_report_name, fcfg.fingerprint_report_name,
                 fcfg.ocr_fusion_report_name, fcfg.logo_report_name,
                 fcfg.confidence_report_name):
        assert repo.load_latest(eid, name) is not None, name

    # Fusion consumed the fake adapters; logo keyword found via fused text.
    assert outcome["fusion"].final_text
    assert "eSewa" in outcome["logos"].detected_brands
    assert outcome["confidence"].confidence_score > 0
    assert outcome["failures"] == []
    assert fcfg.audit_csv.exists()


def test_original_evidence_bytes_never_change(phase1, evidence_file, config):
    pipeline, _, _ = phase1
    outcome = pipeline.process_file(evidence_file)
    legacy = outcome["legacy_result"]
    record_row = None
    import csv
    with open(config.evidence_csv, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["evidence_id"] == legacy.evidence_id:
                record_row = row
    assert record_row is not None
    stored = config.originals_dir / record_row["stored_file_name"]
    import hashlib
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == record_row["sha256_before"]


def test_reanalysis_creates_new_versions_not_overwrites(phase1, evidence_file):
    pipeline, repo, fcfg = phase1
    outcome = pipeline.process_file(evidence_file)
    eid = outcome["legacy_result"].evidence_id
    pipeline.analyze_evidence(eid)  # second pass on same evidence
    versions = repo.list_versions(eid, fcfg.quality_report_name)
    assert len(versions) == 2
    assert versions[0].name == "quality_report.json"
    assert versions[1].name == "quality_report_v2.json"


def test_one_failing_module_does_not_abort(phase1, evidence_file, monkeypatch):
    pipeline, repo, fcfg = phase1

    def boom(*args, **kwargs):
        raise RuntimeError("forgery module exploded")

    monkeypatch.setattr(pipeline._forgery, "analyze", boom)
    outcome = pipeline.process_file(evidence_file)
    assert any("forgery" in f for f in outcome["failures"])
    # Everything else still ran, including the final confidence score.
    assert outcome["confidence"] is not None
    eid = outcome["legacy_result"].evidence_id
    assert repo.load_latest(eid, fcfg.confidence_report_name) is not None


def test_unknown_evidence_raises(phase1):
    pipeline, _, _ = phase1
    from backend.modules.evidence.utils import EvidenceError
    with pytest.raises(EvidenceError):
        pipeline.analyze_evidence("EVID_99999")
