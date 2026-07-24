"""Intake: reference -> stable case id, create-then-reopen semantics."""
import pytest

pytestmark = pytest.mark.django_db


def test_intake_creates_case(api):
    resp = api.post("/api/intake/", {"reference": "OP-ALPHA", "title": "Alpha"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] is True
    assert body["case_id"]


def test_same_reference_reopens_same_case(api):
    first = api.post("/api/intake/", {"reference": "OP-BETA"}).json()
    second = api.post("/api/intake/", {"reference": "OP-BETA"})
    assert second.status_code == 200  # reopened, not created
    body = second.json()
    assert body["created"] is False
    assert body["case_id"] == first["case_id"]


def test_intake_requires_reference(api):
    resp = api.post("/api/intake/", {"reference": "   "})
    assert resp.status_code == 400


def test_case_detail_after_intake(api, case):
    resp = api.get(f"/api/cases/{case['case_id']}/")
    assert resp.status_code == 200
    assert resp.json()["case_id"] == case["case_id"]
