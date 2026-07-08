"""Tests for SHA-256 evidence hashing and verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from backend.modules.evidence.hash_service import HashService
from backend.modules.evidence.utils import HashVerificationError


@pytest.fixture()
def service() -> HashService:
    return HashService()


def test_sha256_matches_hashlib(tmp_path: Path, service: HashService) -> None:
    payload = b"forensic evidence bytes \xf0\x9f\x94\x92" * 1000
    path = tmp_path / "evidence.bin"
    path.write_bytes(payload)
    assert service.sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_verify_success_and_case_insensitive(tmp_path: Path, service: HashService) -> None:
    path = tmp_path / "a.txt"
    path.write_text("hello")
    digest = service.sha256_file(path)
    assert service.verify(path, digest)
    assert service.verify(path, digest.upper())


def test_verify_detects_tampering(tmp_path: Path, service: HashService) -> None:
    path = tmp_path / "a.txt"
    path.write_text("original")
    digest = service.sha256_file(path)
    path.write_text("tampered")
    assert not service.verify(path, digest)
    with pytest.raises(HashVerificationError):
        service.verify_or_raise(path, digest)


def test_empty_file_hash(tmp_path: Path, service: HashService) -> None:
    path = tmp_path / "empty.bin"
    path.touch()
    # Well-known SHA-256 of the empty string.
    assert service.sha256_file(path) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
