"""Module 7 tests - Advanced File Integrity Analysis."""

from __future__ import annotations

import hashlib

import pytest
from PIL import Image

from backend.modules.evidence.forensics.integrity.service import FileIntegrityService


@pytest.fixture()
def service(fcfg, repo, audit, config):
    return FileIntegrityService(fcfg, repo, audit,
                                evidence_register_csv=config.evidence_csv)


def test_all_hashes_and_fingerprint_fields(service, tmp_path):
    source = tmp_path / "evidence.bin"
    payload = b"cybercrime evidence payload " * 100
    source.write_bytes(payload)

    report = service.fingerprint(source, evidence_id="EVID_00001",
                                 case_id="CASE_0001", persist=False)
    assert report.md5 == hashlib.md5(payload).hexdigest()
    assert report.sha1 == hashlib.sha1(payload).hexdigest()
    assert report.sha256 == hashlib.sha256(payload).hexdigest()
    assert report.sha512 == hashlib.sha512(payload).hexdigest()
    assert len(report.crc32) == 8
    assert report.file_size_bytes == len(payload)
    assert 0.0 <= report.entropy_bits_per_byte <= 8.0
    assert not report.high_entropy  # repetitive text is low entropy


def test_magic_number_detection_and_extension_check(service, tmp_path, text_image):
    png_path = tmp_path / "image.png"
    Image.fromarray(text_image).save(png_path)
    report = service.fingerprint(png_path, evidence_id="E", case_id="C",
                                 persist=False)
    assert report.magic_format == "PNG image"
    assert report.extension_matches_magic

    disguised = tmp_path / "image.jpg"  # PNG bytes with a JPG name
    disguised.write_bytes(png_path.read_bytes())
    report2 = service.fingerprint(disguised, evidence_id="E2", case_id="C",
                                  persist=False)
    assert report2.magic_format == "PNG image"
    assert not report2.extension_matches_magic


def test_acquisition_hash_cross_check(service, tmp_path):
    source = tmp_path / "file.txt"
    source.write_bytes(b"hello")
    good = hashlib.sha256(b"hello").hexdigest()
    ok = service.fingerprint(source, evidence_id="E", case_id="C",
                             acquisition_sha256=good, persist=False)
    assert ok.sha256_matches_acquisition is True
    bad = service.fingerprint(source, evidence_id="E", case_id="C",
                              acquisition_sha256="deadbeef", persist=False)
    assert bad.sha256_matches_acquisition is False


def test_duplicate_detection_via_fingerprint_index(service, tmp_path):
    source = tmp_path / "a.txt"
    source.write_bytes(b"identical content")
    first = service.fingerprint(source, evidence_id="EVID_00001",
                                case_id="CASE_0001")  # persisted -> indexed
    assert not first.is_duplicate

    copy = tmp_path / "b.txt"
    copy.write_bytes(b"identical content")
    second = service.fingerprint(copy, evidence_id="EVID_00002",
                                 case_id="CASE_0002")
    assert second.is_duplicate
    assert any(d.evidence_id == "EVID_00001" for d in second.duplicates)


def test_high_entropy_flag(service, tmp_path):
    import os
    source = tmp_path / "random.bin"
    source.write_bytes(os.urandom(64 * 1024))
    report = service.fingerprint(source, evidence_id="E", case_id="C",
                                 persist=False)
    assert report.high_entropy
