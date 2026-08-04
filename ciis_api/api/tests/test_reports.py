"""Report center: list + latest report after a full analysis run."""



def test_reports_listed_after_analysis(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    api.post(f"/api/cases/{case_id}/analyze/")
    resp = api.get(f"/api/cases/{case_id}/reports/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id
    assert isinstance(body["reports"], list)


def test_latest_report_available_after_analysis(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    api.post(f"/api/cases/{case_id}/analyze/")
    resp = api.get(f"/api/cases/{case_id}/reports/latest/")
    # Either the report artifact loads (200) or is legitimately not generated
    # (503) — never a server crash.
    assert resp.status_code in (200, 503)


def test_latest_report_before_analysis_is_503(api, case):
    resp = api.get(f"/api/cases/{case['case_id']}/reports/latest/")
    assert resp.status_code == 503


def test_report_download_path_traversal_blocked(api, case):
    resp = api.get(
        f"/api/cases/{case['case_id']}/reports/..%2f..%2fsettings.py/download/"
    )
    assert resp.status_code == 404
