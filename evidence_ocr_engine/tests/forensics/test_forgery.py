"""Module 4 tests - Image Forgery Detection."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from backend.modules.evidence.forensics.forgery.service import ForgeryDetectionService


@pytest.fixture()
def service(fcfg, repo, audit):
    return ForgeryDetectionService(fcfg, repo, audit)


def test_report_shape_and_persistence(service, fcfg, repo, text_image, tmp_path):
    source = tmp_path / "doc.png"
    Image.fromarray(text_image).save(source)
    report = service.analyze(text_image, evidence_id="EVID_00001",
                             case_id="CASE_0001", source_file="doc.png",
                             source_path=source)
    assert 0.0 <= report.forgery_score <= 100.0
    assert report.forgery_risk in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert report.authenticity_status in {
        "LIKELY_AUTHENTIC", "INDETERMINATE", "SUSPICIOUS", "LIKELY_TAMPERED"
    }
    assert report.findings  # always at least one narrative finding
    assert repo.load_latest("EVID_00001", fcfg.forgery_report_name) is not None


def test_never_rejects_evidence(service, poor_image):
    """Even a terrible image produces findings, never an exception/rejection."""
    report = service.analyze(poor_image, evidence_id="E", case_id="C",
                             source_file="bad.png", persist=False)
    assert report is not None


def test_copy_move_detects_cloned_region(service):
    """Paste an exact copy of a textured patch elsewhere in the image."""
    rng = np.random.default_rng(7)
    img = rng.integers(0, 255, size=(400, 400, 3), dtype=np.uint8)
    patch = img[40:120, 40:120].copy()
    img[240:320, 260:340] = patch  # clone with a constant offset
    report = service.analyze(img, evidence_id="E", case_id="C",
                             source_file="clone.png", persist=False)
    assert report.copy_move.self_matches > 0
    assert report.copy_move.suspicious
    assert report.component_scores["copy_move"] > 0


def test_pristine_uniform_image_scores_low(service):
    img = np.full((300, 300, 3), 200, dtype=np.uint8)
    report = service.analyze(img, evidence_id="E", case_id="C",
                             source_file="flat.png", persist=False)
    assert not report.copy_move.suspicious
    assert report.forgery_risk in {"LOW", "MEDIUM"}


def test_metadata_editing_software_flagged(service, tmp_path, text_image):
    from PIL import Image as PILImage
    source = tmp_path / "edited.jpg"
    img = PILImage.fromarray(text_image)
    exif = img.getexif()
    exif[305] = "Adobe Photoshop 25.0"  # Software tag
    img.save(source, exif=exif)
    report = service.analyze(text_image, evidence_id="E", case_id="C",
                             source_file="edited.jpg", source_path=source,
                             persist=False)
    assert report.metadata.editing_software_detected
    assert report.component_scores["metadata"] >= 60.0
