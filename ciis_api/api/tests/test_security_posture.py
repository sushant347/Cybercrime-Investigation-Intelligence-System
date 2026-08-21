"""Table 6.8 row 1 — the ACTUAL security posture, proven by test.

The API is open-access by design (AUDIT.md, 2026-07-23):
``DEFAULT_PERMISSION_CLASSES = AllowAny`` and ``accounts.permissions.require``
is a documented no-op. The thesis row must state this honestly, not claim
"Blocked". These tests assert the real behavior — an unauthenticated request is
permitted (never 401/403) — so the table's claim is backed by a passing test
rather than an assumption.
"""


_DENIED = {401, 403}


def test_unauthenticated_intake_is_permitted(api):
    """No Authorization header -> creating/opening a case is allowed."""
    resp = api.post("/api/intake/", {"reference": "SEC-OPEN-1", "title": "x"})
    assert resp.status_code not in _DENIED
    assert resp.status_code in (200, 201), resp.content


def test_unauthenticated_artifact_and_analyze_are_permitted(api, case):
    """Investigation endpoints do not require a JWT (open access)."""
    case_id = case["case_id"]
    # artifact availability index
    idx = api.get(f"/api/cases/{case_id}/artifacts/")
    assert idx.status_code not in _DENIED
    # triggering analysis. 400 belongs in this list: the fixture case carries
    # no evidence, and the endpoint now rejects that with a validation error
    # rather than letting the pipeline fail deep inside. The security property
    # under test is the assertion above - the request is never 401/403 - and a
    # validation rejection is not an authorisation one.
    run = api.post(f"/api/cases/{case_id}/analyze/")
    assert run.status_code not in _DENIED
    assert run.status_code in (200, 202, 400, 404), run.content


def test_no_auth_header_is_actually_set(api):
    """Guard: the test client sends no credentials, so this really is unauth."""
    assert "HTTP_AUTHORIZATION" not in api._credentials
