"""Tests for the forensic evidence acquisition (upload) service."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.evidence.csv_storage import EvidenceRepository, ProcessingLogRepository
from backend.modules.evidence.hash_service import HashService
from backend.modules.evidence.upload import EvidenceUploader
from backend.modules.evidence.utils import (
    FileTooLargeError,
    PermissionDeniedError,
    UnsupportedFormatError,
)


@pytest.fixture()
def uploader(config: EvidenceConfig) -> EvidenceUploader:
    return EvidenceUploader(
        config, HashService(), EvidenceRepository(config), ProcessingLogRepository(config)
    )


def test_upload_preserves_original_and_verifies_hash(
    uploader: EvidenceUploader, sample_image: Path, config: EvidenceConfig
) -> None:
    original_bytes = sample_image.read_bytes()
    record = uploader.upload(sample_image, "CASE_0001", notes="seized phone")

    # Original untouched.
    assert sample_image.exists()
    assert sample_image.read_bytes() == original_bytes
    # Copy stored under a unique name, bit-identical to the original.
    stored = uploader.stored_path(record)
    assert stored.exists() and stored.parent == config.originals_dir
    assert stored.read_bytes() == original_bytes
    # Chain-of-custody metadata.
    assert record.evidence_id == "EVID_00001"
    assert record.sha256_before == HashService().sha256_file(sample_image)
    assert record.status == "uploaded"
    assert record.investigator_notes == "seized phone"
    assert record.upload_time  # timestamp recorded


def test_upload_generates_unique_stored_names(
    uploader: EvidenceUploader, sample_image: Path
) -> None:
    first = uploader.upload(sample_image, "CASE_0001")
    second = uploader.upload(sample_image, "CASE_0001")
    assert first.stored_file_name != second.stored_file_name
    assert first.evidence_id != second.evidence_id


def test_upload_rejects_unsupported_format(uploader: EvidenceUploader, tmp_path: Path) -> None:
    bad = tmp_path / "malware.exe"
    bad.write_bytes(b"MZ...")
    with pytest.raises(UnsupportedFormatError):
        uploader.upload(bad, "CASE_0001")


def test_upload_rejects_missing_file(uploader: EvidenceUploader, tmp_path: Path) -> None:
    with pytest.raises(PermissionDeniedError):
        uploader.upload(tmp_path / "nope.png", "CASE_0001")


def test_upload_rejects_oversized_file(config: EvidenceConfig, tmp_path: Path) -> None:
    small_cfg = EvidenceConfig(
        **{**config.__dict__, "max_file_size_bytes": 10}  # 10-byte limit
    )
    uploader = EvidenceUploader(
        small_cfg, HashService(), EvidenceRepository(small_cfg), ProcessingLogRepository(small_cfg)
    )
    big = tmp_path / "big.png"
    big.write_bytes(b"x" * 100)
    with pytest.raises(FileTooLargeError):
        uploader.upload(big, "CASE_0001")


def test_upload_rejects_empty_file(uploader: EvidenceUploader, tmp_path: Path) -> None:
    empty = tmp_path / "empty.png"
    empty.touch()
    with pytest.raises(UnsupportedFormatError):
        uploader.upload(empty, "CASE_0001")
