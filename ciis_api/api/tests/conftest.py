"""Shared fixtures for the API integration tests.

Design goals:
* **No PaddleOCR / no real images.** A tiny :class:`FakeOCR` returns canned
  forensic text (a phishing screenshot transcript) so the full Phase-1 chain
  runs deterministically in milliseconds.
* **Isolated storage per test.** Each test gets its own temporary
  ``EVIDENCE_STORAGE_DIR`` and the engine's ``lru_cache``d config/factories are
  cleared, so tests never touch the real ``storage/`` corpus.
* **Synchronous jobs.** The engine's background ``ThreadPoolExecutor`` is
  replaced with an inline runner so ``submit_*_job`` completes before the
  request returns and assertions are race-free.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest


# --------------------------------------------------------------------- fake OCR
#: Canned transcript containing one of every entity type the cleaning
#: extractor recognises (url, email, phone/esewa, otp) plus Nepali script,
#: so a single uploaded "image" exercises entity extraction end to end.
_FAKE_LINES = [
    ("URGENT!!! Your account will be suspended", 0.97),
    ("Verify now at http://nabil-verify.scam.top/login?id=99", 0.95),
    ("Contact supp0rt@fake-bank.com for help", 0.93),
    ("Send OTP 4521 to +9779812345678", 0.94),
    ("तपाईंको खाता निलम्बित छ।", 0.90),
]


class FakeOCR:
    """Deterministic in-memory OCR engine implementing ``BaseOCR``."""

    name = "fake-ocr"

    def recognize(self, image: np.ndarray):  # noqa: ARG002 - text is canned
        from backend.modules.evidence.models import OCRLine

        return [OCRLine(text=text, confidence=conf) for text, conf in _FAKE_LINES]

    def warmup(self) -> None:  # pragma: no cover - trivial
        return None


class _InlineExecutor:
    """Runs submitted callables immediately (no threads) for deterministic tests."""

    def submit(self, fn, *args, **kwargs):  # noqa: D401 - executor shim
        fn(*args, **kwargs)
        return None


def make_png(path: Path, size: int = 48) -> Path:
    """Write a tiny valid PNG the acquisition/preprocessing stages can load."""
    from PIL import Image

    Image.new("RGB", (size, size), (255, 255, 255)).save(path)
    return path


# ------------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def engine_env(tmp_path, monkeypatch):
    """Point the engine at throwaway storage and swap in fast/deterministic parts."""
    storage = tmp_path / "engine_storage"
    storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("EVIDENCE_STORAGE_DIR", str(storage))
    monkeypatch.setenv("EVIDENCE_OCR_LANG", "en")

    from api import engine

    # Fresh config/factories bound to the temp storage dir.
    for factory in (
        engine.evidence_config,
        engine.investigation_config,
        engine.report_repository,
        engine.case_registry,
    ):
        factory.cache_clear()

    cfg = engine.evidence_config()
    cfg.ensure_directories()

    # Build a real EvidencePipeline but with the canned OCR (no PaddleOCR).
    from backend.modules.evidence.pipeline import EvidencePipeline

    monkeypatch.setattr(
        engine, "_evidence_pipeline", lambda: EvidencePipeline(cfg, FakeOCR())
    )
    # A fresh orchestrator bound to the temp storage (bypass the module cache).
    from backend.modules.evidence.semantic.orchestrator import (
        EvidenceProcessingOrchestrator,
    )

    monkeypatch.setattr(
        engine, "_evidence_orchestrator", lambda: EvidenceProcessingOrchestrator(cfg)
    )
    # Run jobs synchronously so status is final when the request returns.
    monkeypatch.setattr(engine, "_executor", _InlineExecutor())

    # Platform records live in CSV/JSON under the same temp storage; start clean.
    from api import store

    store.clear_all()

    yield engine

    for factory in (
        engine.evidence_config,
        engine.investigation_config,
        engine.report_repository,
        engine.case_registry,
    ):
        factory.cache_clear()


@pytest.fixture
def api():
    """DRF test client with DB access enabled."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def case(api):
    """Create a case via intake and return its payload."""
    resp = api.post("/api/intake/", {"reference": "OP-TEST-001", "title": "Test case"})
    assert resp.status_code in (200, 201), resp.content
    return resp.json()


@pytest.fixture
def uploaded_evidence(api, case, tmp_path):
    """Upload one screenshot and return ``(case_id, job_json)`` after processing."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    png = make_png(tmp_path / "evidence.png")
    upload = SimpleUploadedFile(
        "evidence.png", png.read_bytes(), content_type="image/png"
    )
    resp = api.post(
        f"/api/cases/{case['case_id']}/evidence/upload/",
        {"file": upload, "notes": "phishing screenshot"},
        format="multipart",
    )
    assert resp.status_code == 202, resp.content
    return case["case_id"], resp.json()
