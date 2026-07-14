"""Module 1 tests - OCR Quality Assessment Engine."""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.forensics.quality.service import QualityAssessmentService
from backend.modules.evidence.utils import InvalidImageError


@pytest.fixture()
def service(fcfg, repo, audit):
    return QualityAssessmentService(fcfg, repo, audit)


def test_clean_document_scores_higher_than_poor_capture(service, text_image, poor_image):
    good = service.assess(text_image, evidence_id="EVID_00001", case_id="CASE_0001",
                          source_file="good.png", persist=False)
    bad = service.assess(poor_image, evidence_id="EVID_00002", case_id="CASE_0001",
                         source_file="bad.png", persist=False)
    assert good.overall_score > bad.overall_score
    assert good.expected_ocr_accuracy > bad.expected_ocr_accuracy
    assert 0.0 <= bad.overall_score <= 100.0


def test_assessment_never_modifies_the_image(service, text_image):
    before = text_image.copy()
    service.assess(text_image, evidence_id="EVID_00001", case_id="CASE_0001",
                   source_file="good.png", persist=False)
    assert np.array_equal(before, text_image)


def test_poor_image_triggers_recommendations(service, poor_image):
    result = service.assess(poor_image, evidence_id="EVID_00002", case_id="CASE_0001",
                            source_file="bad.png", persist=False)
    ops = set(result.recommended_operations)
    assert "adaptive_denoise" in ops
    assert "clahe" in ops
    assert "super_resolution" in ops  # 240x320 is below the trigger
    assert result.quality_grade in {"UNUSABLE", "POOR", "FAIR"}


def test_report_is_persisted_with_audit(service, fcfg, repo, text_image):
    service.assess(text_image, evidence_id="EVID_00001", case_id="CASE_0001",
                   source_file="good.png")
    stored = repo.load_latest("EVID_00001", fcfg.quality_report_name)
    assert stored is not None
    assert "overall_score" in stored["report"]
    assert fcfg.audit_csv.exists()


def test_rejects_non_rgb_input(service):
    with pytest.raises(InvalidImageError):
        service.assess(np.zeros((10, 10), dtype=np.uint8),
                       evidence_id="E", case_id="C", source_file="x.png",
                       persist=False)


def test_sub_scores_are_bounded(service, text_image):
    result = service.assess(text_image, evidence_id="E", case_id="C",
                            source_file="x.png", persist=False)
    for name, value in result.sub_scores.items():
        assert 0.0 <= value <= 100.0, name
