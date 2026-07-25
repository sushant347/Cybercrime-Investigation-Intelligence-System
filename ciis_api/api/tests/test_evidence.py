"""Evidence upload path — including the F1 proof that the FULL Phase-1 chain
(OCR -> cleaning -> enhancement -> semantic -> entity extraction) runs for
web-uploaded evidence, not OCR only."""
import pytest



def test_upload_returns_job_and_completes(uploaded_evidence, api):
    case_id, job = uploaded_evidence
    # Inline executor => job is already final when the request returned.
    status = api.get(f"/api/jobs/{job['id']}/").json()
    assert status["status"] == "completed", status
    assert status["evidence_id"]


def test_upload_extracts_entities(uploaded_evidence, api):
    """The single most important F1 assertion: entities.csv is populated."""
    case_id, job = uploaded_evidence
    from api import engine

    entities_csv = engine.evidence_config().storage_dir / "entities.csv"
    assert entities_csv.is_file(), "cleaning stage never wrote entities.csv"
    rows = entities_csv.read_text(encoding="utf-8").splitlines()
    assert len(rows) > 1, "no entity rows produced by the API upload path"
    body = entities_csv.read_text(encoding="utf-8")
    assert "nabil-verify.scam.top" in body  # url entity from the fake transcript
    # The job detail should report the extracted-entity count (F1 contract).
    status = api.get(f"/api/jobs/{job['id']}/").json()
    assert "entities" in status["detail"].lower()


def test_upload_is_idempotent_on_reprocess(api, case, tmp_path):
    """Re-uploading to the same case must not duplicate entity rows."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from api import engine
    from api.tests.conftest import make_png

    def upload(name):
        png = make_png(tmp_path / name)
        f = SimpleUploadedFile(name, png.read_bytes(), content_type="image/png")
        r = api.post(
            f"/api/cases/{case['case_id']}/evidence/upload/",
            {"file": f, "notes": ""}, format="multipart",
        )
        assert r.status_code == 202, r.content

    entities_csv = engine.evidence_config().storage_dir / "entities.csv"
    upload("a.png")
    after_first = len(entities_csv.read_text(encoding="utf-8").splitlines())
    upload("b.png")  # re-cleans the whole case (both items)
    after_second = len(entities_csv.read_text(encoding="utf-8").splitlines())
    # Two distinct evidence items => more rows than one, but NOT triple-counted.
    assert after_second == 2 * (after_first - 1) + 1  # header counted once


def test_upload_rejects_unsupported_type(api, case, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    bad = SimpleUploadedFile("evil.exe", b"MZ\x00\x00", content_type="application/octet-stream")
    resp = api.post(
        f"/api/cases/{case['case_id']}/evidence/upload/",
        {"file": bad, "notes": ""}, format="multipart",
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_upload_rejects_oversized(api, case):
    """A supported-type file over the 50 MB limit is rejected with 400.

    Table 6.8 row 4 (oversized/malformed upload): this is the oversized half,
    complementing test_upload_rejects_unsupported_type (the malformed half).
    The extension is valid (.png) so the size branch at
    ciis_api/api/views/evidence.py:55 is what does the rejecting, not the
    type check above it.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    from api import engine

    limit = engine.evidence_config().max_file_size_bytes
    oversized = SimpleUploadedFile(
        "big.png", b"\x00" * (limit + 1), content_type="image/png"
    )
    resp = api.post(
        f"/api/cases/{case['case_id']}/evidence/upload/",
        {"file": oversized, "notes": ""}, format="multipart",
    )
    assert resp.status_code == 400
    assert "50 MB" in resp.json()["detail"]


def test_upload_to_missing_case_404(api, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from api.tests.conftest import make_png

    png = make_png(tmp_path / "x.png")
    f = SimpleUploadedFile("x.png", png.read_bytes(), content_type="image/png")
    resp = api.post(
        "/api/cases/CASE_9999/evidence/upload/",
        {"file": f, "notes": ""}, format="multipart",
    )
    assert resp.status_code == 404


def test_evidence_detail_exposes_ocr(uploaded_evidence, api):
    case_id, job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{job['id']}/").json()["evidence_id"]
    resp = api.get(f"/api/cases/{case_id}/evidence/{evidence_id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["record"]["evidence_id"] == evidence_id
    assert body["ocr"] is not None


# --------------------------------------------------------------- forensics
def test_upload_generates_phase1_forensic_reports(uploaded_evidence, api):
    """Phase-1 forensics must run on upload, not just OCR + entities.

    Without this the analytics quality/brand/forgery panels and the forgery
    component of the priority score read zero on every case in the system,
    because ``storage/forensics/`` was never written at all.
    """
    case_id, job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{job['id']}/").json()["evidence_id"]

    detail = api.get(f"/api/cases/{case_id}/evidence/{evidence_id}/").json()
    forensics = detail["forensics"]
    assert forensics, "no Phase-1 forensic artifacts were produced"
    # Integrity + confidence run for every file type; the image ones too here.
    names = " ".join(forensics.keys()).lower()
    assert "fingerprint" in names or "integrity" in names
    assert "confidence" in names


# ----------------------------------------------------------------- deletion
def test_processed_evidence_cannot_be_deleted(uploaded_evidence, api):
    """Processed evidence is part of the case record: 409, and it survives."""
    case_id, job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{job['id']}/").json()["evidence_id"]

    resp = api.delete(f"/api/cases/{case_id}/evidence/{evidence_id}/")
    assert resp.status_code == 409, resp.content
    assert resp.json()["processing_state"]["processed"] is True
    assert api.get(f"/api/cases/{case_id}/evidence/{evidence_id}/").status_code == 200


def test_unprocessed_evidence_can_be_deleted(api, case):
    """An item that produced nothing can be withdrawn by the investigator."""
    from api import engine
    import csv

    case_id = case["case_id"]
    cfg = engine.evidence_config()
    # A register row with no OCR text, no entities and no forensic reports -
    # what an upload that failed before processing leaves behind.
    with open(cfg.evidence_csv, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "evidence_id", "case_id", "original_file_name", "stored_file_name",
            "file_extension", "file_size_bytes", "sha256_before", "sha256_after",
            "hash_verified", "upload_time", "processing_time", "status",
            "investigator_notes",
        ])
        if cfg.evidence_csv.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({
            "evidence_id": "EVID_STUCK", "case_id": case_id,
            "original_file_name": "half-upload.png",
            "stored_file_name": "EVID_STUCK__x__half-upload.png",
            "file_extension": ".png", "file_size_bytes": "12",
            "sha256_before": "f" * 64, "sha256_after": "", "hash_verified": "",
            "upload_time": "2026-07-06T09:00:00.000Z", "processing_time": "",
            "status": "failed", "investigator_notes": "",
        })

    detail = api.get(f"/api/cases/{case_id}/evidence/EVID_STUCK/").json()
    assert detail["deletable"] is True

    resp = api.delete(f"/api/cases/{case_id}/evidence/EVID_STUCK/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["deleted"] is True
    assert api.get(f"/api/cases/{case_id}/evidence/EVID_STUCK/").status_code == 404


def test_deleting_unknown_evidence_is_404(api, case):
    resp = api.delete(f"/api/cases/{case['case_id']}/evidence/EVID_NOPE/")
    assert resp.status_code == 404
