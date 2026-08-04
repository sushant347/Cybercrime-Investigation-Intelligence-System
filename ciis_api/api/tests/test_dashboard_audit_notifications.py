"""F8: the dashboard / audit / notifications endpoints are now routed + served."""



def test_dashboard_endpoint_reachable(api, case):
    resp = api.get("/api/dashboard/")
    assert resp.status_code == 200
    body = resp.json()
    # Aggregates present (exact keys depend on the view; just prove it serves).
    assert isinstance(body, dict) and body


def test_audit_endpoint_reachable(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    resp = api.get("/api/audit/")
    assert resp.status_code == 200
    # Uploading evidence writes ActivityLog + processing_log rows.
    body = resp.json()
    assert "results" in body


def test_audit_filter_by_case(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    resp = api.get(f"/api/audit/?case_id={case_id}")
    assert resp.status_code == 200


def test_notifications_served_after_processing(uploaded_evidence, api):
    """Evidence processing broadcasts a notification — now readable via the API."""
    resp = api.get("/api/notifications/")
    assert resp.status_code == 200
    body = resp.json()
    assert "unread_count" in body
    assert "results" in body


def test_notifications_mark_read(uploaded_evidence, api):
    listing = api.get("/api/notifications/?unread=1").json()
    assert listing["unread_count"] >= 1  # processing-complete notification
    ids = [n["id"] for n in listing["results"]]
    resp = api.post("/api/notifications/mark-read/", {"ids": ids}, format="json")
    assert resp.status_code == 200
    assert resp.json()["marked_read"] == len(ids)
    # Now unread count drops.
    after = api.get("/api/notifications/?unread=1").json()
    assert after["unread_count"] < listing["unread_count"]
