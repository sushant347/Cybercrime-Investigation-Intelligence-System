"""Module 8 tests - Evidence Confidence Scoring."""

from __future__ import annotations

import csv

import pytest

from backend.modules.evidence.forensics.confidence.service import ConfidenceScoringService


@pytest.fixture()
def service(fcfg, repo, audit):
    return ConfidenceScoringService(fcfg, repo, audit)


def test_perfect_evidence_scores_high(service):
    result = service.score(
        evidence_id="E", case_id="C",
        image_quality_score=95.0, forgery_score=5.0,
        metadata_consistency_notes=0, hash_verified=True,
        fingerprint_hash_match=True, ocr_confidence=0.95,
        processing_success=True, persist=False,
    )
    assert result.confidence_score >= 80.0
    assert result.confidence_level in {"HIGH", "VERY_HIGH"}
    assert result.explanation


def test_hash_mismatch_collapses_hash_component(service):
    good = service.score(evidence_id="E", case_id="C", hash_verified=True,
                         ocr_confidence=0.9, persist=False)
    bad = service.score(evidence_id="E", case_id="C", hash_verified=False,
                        ocr_confidence=0.9, persist=False)
    assert bad.confidence_score < good.confidence_score
    hash_component = next(c for c in bad.components if c.name == "hash_verification")
    assert hash_component.score == 0.0


def test_missing_components_renormalise_weights(service):
    """OCR-only input must still produce a sane 0-100 score."""
    result = service.score(evidence_id="E", case_id="C",
                           ocr_confidence=0.80, persist=False)
    available = [c for c in result.components if c.available]
    assert len(available) == 1
    assert result.confidence_score == pytest.approx(80.0, abs=0.11)


def test_forgery_score_is_inverted(service):
    clean = service.score(evidence_id="E", case_id="C", forgery_score=5.0,
                          persist=False)
    tampered = service.score(evidence_id="E", case_id="C", forgery_score=90.0,
                             persist=False)
    assert clean.confidence_score > tampered.confidence_score


def test_persistence_json_and_csv(service, fcfg, repo):
    service.score(evidence_id="EVID_00005", case_id="CASE_0001",
                  image_quality_score=70.0, hash_verified=True,
                  ocr_confidence=0.7, processing_success=True)
    assert repo.load_latest("EVID_00005", fcfg.confidence_report_name) is not None
    with open(fcfg.confidence_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and rows[-1]["evidence_id"] == "EVID_00005"
    assert rows[-1]["confidence_level"]


def test_no_inputs_yields_zero_score(service):
    result = service.score(evidence_id="E", case_id="C", persist=False)
    assert result.confidence_score == 0.0
    assert result.confidence_level == "VERY_LOW"
