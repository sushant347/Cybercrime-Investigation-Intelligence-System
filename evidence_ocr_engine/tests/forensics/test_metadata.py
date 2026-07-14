"""Module 6 tests - Forensic Metadata Extraction."""

from __future__ import annotations

import zipfile

import pytest
from PIL import Image

from backend.modules.evidence.forensics.metadata.service import MetadataExtractionService


@pytest.fixture()
def service(fcfg, repo, audit):
    return MetadataExtractionService(fcfg, repo, audit)


def test_image_exif_extraction(service, tmp_path, text_image):
    source = tmp_path / "photo.jpg"
    img = Image.fromarray(text_image)
    exif = img.getexif()
    exif[271] = "TestMake"          # Make
    exif[272] = "TestModel X100"    # Model
    exif[305] = "TestSoftware 1.0"  # Software
    exif[306] = "2026:01:15 10:30:00"  # DateTime
    img.save(source, exif=exif)

    report = service.extract(source, evidence_id="EVID_00001",
                             case_id="CASE_0001", persist=False)
    assert report.file_type == "image"
    assert report.image is not None and report.image.has_exif
    assert report.image.camera_make == "TestMake"
    assert report.image.camera_model == "TestModel X100"
    assert report.image.device == "TestMake TestModel X100"
    assert report.image.software == "TestSoftware 1.0"
    assert report.filesystem.file_size_bytes > 0
    # software note surfaces in consistency notes
    assert any("TestSoftware" in n for n in report.consistency_notes)


def test_image_without_exif_notes_absence(service, tmp_path, text_image):
    source = tmp_path / "screenshot.png"
    Image.fromarray(text_image).save(source)
    report = service.extract(source, evidence_id="E", case_id="C", persist=False)
    assert report.image is not None and not report.image.has_exif
    assert any("no EXIF" in n or "EXIF" in n for n in report.consistency_notes)


def test_office_docx_properties(service, tmp_path):
    """Build a minimal OOXML container by hand - no python-docx required."""
    source = tmp_path / "statement.docx"
    core = (
        '<?xml version="1.0"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/">'
        "<dc:creator>Alice Investigator</dc:creator>"
        "<cp:lastModifiedBy>Bob Editor</cp:lastModifiedBy>"
        "<cp:revision>7</cp:revision>"
        "<dcterms:created>2026-01-01T00:00:00Z</dcterms:created>"
        "<dcterms:modified>2026-02-01T00:00:00Z</dcterms:modified>"
        "</cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Company>ACME Corp</Company><Application>TestWriter</Application>"
        "</Properties>"
    )
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)
        archive.writestr("word/document.xml", "<w/>")

    report = service.extract(source, evidence_id="E", case_id="C", persist=False)
    assert report.file_type == "office"
    office = report.office
    assert office is not None
    assert office.author == "Alice Investigator"
    assert office.last_modified_by == "Bob Editor"
    assert office.revision_number == "7"
    assert office.company == "ACME Corp"
    assert any("author" in n.lower() for n in report.consistency_notes)


def test_persistence(service, fcfg, repo, tmp_path, text_image):
    source = tmp_path / "img.png"
    Image.fromarray(text_image).save(source)
    service.extract(source, evidence_id="EVID_00004", case_id="CASE_0001")
    assert repo.load_latest("EVID_00004", fcfg.metadata_report_name) is not None
