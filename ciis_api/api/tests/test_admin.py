"""Admin role: shared-password auth, full case listing, and case deletion.

Deletion is the interesting one — it must purge the case *and* leave every
previously linked case consistent (no artifact still citing a deleted case).
"""


def _token(api) -> str:
    resp = api.post("/api/admin/login/", {"password": "hello123"}, format="json")
    assert resp.status_code == 200, resp.content
    return resp.json()["token"]


def _as_admin(api):
    api.credentials(HTTP_X_ADMIN_TOKEN=_token(api))
    return api


# ------------------------------------------------------------------- auth
def test_wrong_password_rejected(api):
    resp = api.post("/api/admin/login/", {"password": "nope"}, format="json")
    assert resp.status_code == 401
    assert "password" in resp.json()["detail"].lower()


def test_correct_password_returns_token(api):
    resp = api.post("/api/admin/login/", {"password": "hello123"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["token"] and resp.json()["role"] == "admin"


def test_admin_endpoints_require_a_token(api):
    assert api.get("/api/admin/cases/").status_code == 403
    assert api.get("/api/admin/session/").status_code == 403


def test_garbage_token_rejected(api):
    api.credentials(HTTP_X_ADMIN_TOKEN="not-a-real-token")
    assert api.get("/api/admin/cases/").status_code == 403


# ------------------------------------------------------------- case list
def test_admin_can_list_every_case(api, case):
    admin = _as_admin(api)
    body = admin.get("/api/admin/cases/").json()
    assert body["count"] >= 1
    ids = [c["case_id"] for c in body["cases"]]
    assert case["case_id"] in ids
    row = next(c for c in body["cases"] if c["case_id"] == case["case_id"])
    # the admin view carries what an administrator needs to decide on deletion
    for field in ("case_reference", "evidence_count", "analysed", "linked_case_ids"):
        assert field in row


# -------------------------------------------------------------- deletion
def test_delete_removes_case_everywhere(uploaded_evidence, api):
    case_id, _job = uploaded_evidence
    admin = _as_admin(api)

    assert admin.get(f"/api/cases/{case_id}/").status_code == 200
    resp = admin.delete(f"/api/admin/cases/{case_id}/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "deleted"
    assert body["evidence_removed"] >= 1

    # gone from the engine and from the admin listing
    assert admin.get(f"/api/cases/{case_id}/").status_code == 404
    listed = [c["case_id"] for c in admin.get("/api/admin/cases/").json()["cases"]]
    assert case_id not in listed


def test_delete_unknown_case_404(api):
    admin = _as_admin(api)
    assert admin.delete("/api/admin/cases/CASE_NOPE/").status_code == 404


def test_delete_purges_engine_storage(uploaded_evidence, api):
    """Evidence rows and per-case artifacts must actually leave the CSVs/disk."""
    case_id, _job = uploaded_evidence
    from api import engine

    assert engine.list_evidence(case_id), "fixture should have evidence"
    _as_admin(api).delete(f"/api/admin/cases/{case_id}/")

    assert engine.list_evidence(case_id) == []
    assert engine.get_case(case_id) is None
    assert not engine.investigation_config().case_dir(case_id).is_dir()


def test_cascade_rebuilds_the_graph_not_just_the_cross_case_artifact(monkeypatch):
    """A deleted case also has to leave the *graph* of every case that cited it.

    The relationship graph embeds cross-case nodes, so refreshing only the
    cross-case artifact left the investigation view still showing the deleted
    case. The cascade must therefore go through ``refresh_timeline_graph``,
    which recomputes correlation, cross-case, timeline and graph together.
    """
    from api import engine

    calls: dict[str, list[str]] = {"refresh": [], "report": []}

    class _FakePipeline:
        def refresh_timeline_graph(self, case_id):
            calls["refresh"].append(case_id)
            return {"cross_case": object()}

    class _FakeReporting:
        def __init__(self, *a, **kw):
            pass

        def regenerate_with_cross_case(self, case_id, cross_case):
            calls["report"].append(case_id)

    monkeypatch.setattr(engine, "_threat_intel_provider", lambda: None)
    monkeypatch.setattr(
        "ciis_timeline_report.pipeline.build_default_pipeline",
        lambda **kw: _FakePipeline(),
    )
    monkeypatch.setattr(
        "ciis_timeline_report.reporting.service.InvestigationReportService",
        _FakeReporting,
    )
    monkeypatch.setattr(
        "ciis_correlation.core.data_access.CaseDataRepository",
        lambda *a, **kw: type("_D", (), {"case_exists": lambda self, c: True})(),
    )

    assert engine._refresh_linked_cases(["CASE_SURVIVOR"]) == ["CASE_SURVIVOR"]
    assert calls["refresh"] == ["CASE_SURVIVOR"], (
        "the graph/timeline refresh path must run, not just cross-case"
    )
    assert calls["report"] == ["CASE_SURVIVOR"]
