"""Module 5 tests - Logo & Brand Detection."""

from __future__ import annotations

import numpy as np
import pytest

from backend.modules.evidence.forensics.logos.registry import BrandRegistry
from backend.modules.evidence.forensics.logos.service import LogoDetectionService
from backend.modules.evidence.models import OCRLine


@pytest.fixture()
def service(fcfg, repo, audit):
    return LogoDetectionService(fcfg, repo, audit)


def test_registry_loads_all_required_brands():
    registry = BrandRegistry()
    names = {b.display_name for b in registry.all()}
    for required in ["eSewa", "Khalti", "IME Pay", "Facebook", "Messenger",
                     "WhatsApp", "Telegram", "Gmail", "Outlook", "Google",
                     "Microsoft"]:
        assert required in names


def test_keyword_detection_with_bbox(service):
    image = np.full((200, 600, 3), 255, dtype=np.uint8)
    lines = [OCRLine("Paid via eSewa wallet", 0.9,
                     [[10.0, 20.0], [300.0, 20.0], [300.0, 50.0], [10.0, 50.0]])]
    report = service.detect(image, evidence_id="E", case_id="C",
                            source_file="s.png", ocr_lines=lines, persist=False)
    assert "eSewa" in report.detected_brands
    hit = next(d for d in report.detections if d.brand == "eSewa")
    assert hit.detection_method == "ocr_keyword"
    assert hit.bbox == [10.0, 20.0, 300.0, 50.0]
    assert hit.detected_at
    assert 0.0 < hit.confidence <= 1.0


def test_colour_signature_detection(service, brand_image):
    report = service.detect(brand_image, evidence_id="E", case_id="C",
                            source_file="s.png", persist=False)
    esewa = [d for d in report.detections if d.brand == "eSewa"]
    assert esewa
    assert esewa[0].detection_method == "colour_signature"
    x0, y0, x1, y1 = esewa[0].bbox
    assert y0 < 10 and y1 > 60  # bbox covers the green header bar


def test_keyword_plus_colour_corroboration_boosts_confidence(service, brand_image):
    lines = [OCRLine("esewa balance rs 5,000", 0.9)]
    with_both = service.detect(brand_image, evidence_id="E", case_id="C",
                               source_file="s.png", ocr_lines=lines, persist=False)
    only_kw = service.detect(np.full_like(brand_image, 255), evidence_id="E",
                             case_id="C", source_file="s.png",
                             ocr_lines=lines, persist=False)
    both_conf = next(d.confidence for d in with_both.detections if d.brand == "eSewa")
    kw_conf = next(d.confidence for d in only_kw.detections if d.brand == "eSewa")
    assert both_conf > kw_conf


def test_report_persisted(service, fcfg, repo, brand_image):
    service.detect(brand_image, evidence_id="EVID_00003", case_id="CASE_0001",
                   source_file="s.png")
    stored = repo.load_latest("EVID_00003", fcfg.logo_report_name)
    assert stored is not None
    assert stored["report"]["brands_checked"]
