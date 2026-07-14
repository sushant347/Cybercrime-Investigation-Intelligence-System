"""Module 2 tests - Advanced Image Preprocessing."""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.forensics.advanced_preprocessing.planner import (
    EXECUTION_ORDER,
    PreprocessingPlanner,
)
from backend.modules.evidence.forensics.advanced_preprocessing.service import (
    AdvancedPreprocessingService,
)
from backend.modules.evidence.forensics.quality.service import QualityAssessmentService


@pytest.fixture()
def quality(fcfg, repo, audit):
    return QualityAssessmentService(fcfg, repo, audit)


@pytest.fixture()
def service(fcfg, repo, audit):
    return AdvancedPreprocessingService(fcfg, repo, audit)


def test_plan_respects_canonical_order(quality, poor_image):
    assessment = quality.assess(poor_image, evidence_id="E", case_id="C",
                                source_file="x.png", persist=False)
    plan = PreprocessingPlanner().plan(assessment)
    indices = [EXECUTION_ORDER.index(op) for op in plan]
    assert indices == sorted(indices)
    assert plan  # a poor image must get at least one operation


def test_clean_image_gets_minimal_plan(quality, text_image):
    assessment = quality.assess(text_image, evidence_id="E", case_id="C",
                                source_file="x.png", persist=False)
    plan = PreprocessingPlanner().plan(assessment)
    # No unnecessary preprocessing: tonal repairs must not be planned.
    assert "adaptive_denoise" not in plan
    assert "illumination_correction" not in plan


def test_enhance_never_mutates_input(quality, service, poor_image):
    assessment = quality.assess(poor_image, evidence_id="E", case_id="C",
                                source_file="x.png", persist=False)
    before = poor_image.copy()
    service.enhance(poor_image, assessment, persist=False, save_derived_image=False)
    assert np.array_equal(before, poor_image)


def test_enhance_applies_and_logs_operations(quality, service, fcfg, repo, poor_image):
    assessment = quality.assess(poor_image, evidence_id="EVID_00009",
                                case_id="CASE_0001", source_file="x.png",
                                persist=False)
    enhanced, report = service.enhance(poor_image, assessment)
    assert enhanced.shape[2] == 3
    assert report.planned_operations
    assert len(report.operations) == len(report.planned_operations)
    applied = [op for op in report.operations if op.applied]
    assert applied  # denoise/clahe/super-resolution must fire on a poor image
    assert all(op.reason for op in report.operations)

    stored = repo.load_latest("EVID_00009", fcfg.preprocessing_report_name)
    assert stored is not None
    assert stored["report"]["operations"]


def test_super_resolution_upscales_small_images(quality, service, poor_image):
    assessment = quality.assess(poor_image, evidence_id="E", case_id="C",
                                source_file="x.png", persist=False)
    enhanced, report = service.enhance(poor_image, assessment, persist=False,
                                       save_derived_image=False)
    if any(op.name == "super_resolution" and op.applied for op in report.operations):
        assert min(enhanced.shape[:2]) > min(poor_image.shape[:2])


def test_one_failing_operation_does_not_abort(quality, service, monkeypatch, poor_image):
    from backend.modules.evidence.forensics.advanced_preprocessing import operations

    def boom(*args, **kwargs):
        raise RuntimeError("kernel exploded")

    monkeypatch.setattr(operations, "adaptive_denoise", boom)
    assessment = quality.assess(poor_image, evidence_id="E", case_id="C",
                                source_file="x.png", persist=False)
    _, report = service.enhance(poor_image, assessment, persist=False,
                                save_derived_image=False)
    failed = [op for op in report.operations if op.name == "adaptive_denoise"]
    assert failed and not failed[0].applied and "failed" in failed[0].detail
    # later operations still executed
    assert any(op.applied for op in report.operations if op.name != "adaptive_denoise")
