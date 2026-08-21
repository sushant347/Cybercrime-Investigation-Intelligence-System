"""Phase-2 analysis: run analysis on an enriched case and read artifacts."""



def _run_analysis(api, case_id):
    resp = api.post(f"/api/cases/{case_id}/analyze/")
    assert resp.status_code in (200, 202), resp.content
    return resp.json()


def test_analyze_generates_artifacts(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{job['id']}/").json()
    assert status["status"] == "completed", status
    index = api.get(f"/api/cases/{case_id}/artifacts/")
    assert index.status_code == 200
    assert index.json()["artifacts"]["analysis_manifest"] is True

    manifest = api.get(
        f"/api/cases/{case_id}/artifacts/analysis_manifest/"
    ).json()["report"]
    assert manifest["status"] == "completed"
    assert manifest["input_quality"] == "complete"
    assert manifest["graph_analytics"].startswith("networkx-")
    assert manifest["semantic_validator"] in {"xlm-roberta-base", "heuristic"}


def test_analysis_refreshes_the_case_assistant_index(
    uploaded_evidence, api, monkeypatch
):
    from api import engine

    case_id, _ = uploaded_evidence
    refreshed = []
    monkeypatch.setattr(
        engine,
        "_sync_rag_index",
        lambda value: refreshed.append(value) or {"status": "updated"},
    )

    job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{job['id']}/").json()

    assert status["status"] == "completed"
    assert refreshed == [case_id]
    assert "rag_index=updated" in status["detail"]


def test_analysis_with_missing_original_is_partial_but_keeps_artifacts(
    uploaded_evidence, api
):
    """Stored OCR can drive Phase 2, but custody loss must remain visible."""
    from api import engine

    case_id, upload_job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{upload_job['id']}/").json()["evidence_id"]
    row = engine.get_evidence(evidence_id)
    engine.original_path(row).unlink()

    analysis_job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{analysis_job['id']}/").json()

    assert status["status"] == "completed_with_warnings", status
    assert "Original evidence files unavailable for 1 item(s)" in status["detail"]
    assert str(engine.evidence_config().originals_dir) not in status["detail"]
    assert api.get(
        f"/api/cases/{case_id}/artifacts/timeline/"
    ).status_code == 200


def test_phase2_module_failure_is_partial_success(api, uploaded_evidence, monkeypatch):
    from api import engine
    from ciis_timeline_report import pipeline as pipeline_module

    class PartialPipeline:
        def analyze_case(self, _case_id):
            return {"failures": ["graph: synthetic failure"]}

    monkeypatch.setattr(
        pipeline_module,
        "build_default_pipeline",
        lambda **_kwargs: PartialPipeline(),
    )
    monkeypatch.setattr(engine, "_threat_intel_provider", lambda: None)

    case_id, _ = uploaded_evidence
    job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{job['id']}/").json()

    assert status["status"] == "completed_with_warnings", status
    assert "Phase-2 graph: synthetic failure" in status["detail"]


def test_unhandled_analysis_failure_is_failed(api, uploaded_evidence, monkeypatch):
    from api import engine
    from ciis_timeline_report import pipeline as pipeline_module

    class BrokenPipeline:
        def analyze_case(self, _case_id):
            raise RuntimeError("synthetic pipeline crash")

    monkeypatch.setattr(
        pipeline_module,
        "build_default_pipeline",
        lambda **_kwargs: BrokenPipeline(),
    )
    monkeypatch.setattr(engine, "_threat_intel_provider", lambda: None)

    case_id, _ = uploaded_evidence
    job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{job['id']}/").json()

    assert status["status"] == "failed", status
    assert status["error"] == "synthetic pipeline crash"


def test_strict_quality_gate_blocks_analysis_with_missing_original(
    uploaded_evidence, api, settings
):
    from api import engine

    case_id, upload_job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{upload_job['id']}/").json()["evidence_id"]
    engine.original_path(engine.get_evidence(evidence_id)).unlink()
    settings.ANALYSIS_INPUT_POLICY = "strict"

    analysis_job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{analysis_job['id']}/").json()

    assert status["status"] == "failed", status
    assert "quality gate blocked" in status["error"].lower()
    manifest = api.get(
        f"/api/cases/{case_id}/artifacts/analysis_manifest/"
    ).json()["report"]
    assert manifest["status"] == "failed_quality_gate"
    assert manifest["input_quality"] == "partial"


def test_strict_quality_gate_blocks_tampered_original(
    uploaded_evidence, api, settings
):
    from api import engine

    case_id, upload_job = uploaded_evidence
    evidence_id = api.get(f"/api/jobs/{upload_job['id']}/").json()["evidence_id"]
    original = engine.original_path(engine.get_evidence(evidence_id))
    original.write_bytes(original.read_bytes() + b"tampered-after-acquisition")
    settings.ANALYSIS_INPUT_POLICY = "strict"

    analysis_job = _run_analysis(api, case_id)
    status = api.get(f"/api/jobs/{analysis_job['id']}/").json()

    assert status["status"] == "failed", status
    assert "sha-256 no longer matches acquisition" in status["error"].lower()
    manifest = api.get(
        f"/api/cases/{case_id}/artifacts/analysis_manifest/"
    ).json()["report"]
    assert manifest["status"] == "failed_quality_gate"


def test_artifact_before_analysis_is_unavailable(api, case):
    # No analysis run yet -> artifact loader reports 503 (not generated).
    resp = api.get(f"/api/cases/{case['case_id']}/artifacts/correlation/")
    assert resp.status_code == 503


def test_unknown_artifact_key(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    _run_analysis(api, case_id)
    resp = api.get(f"/api/cases/{case_id}/artifacts/not_a_real_key/")
    assert resp.status_code == 503


def test_analysis_artifact_roundtrip(uploaded_evidence, api):
    case_id, _ = uploaded_evidence
    _run_analysis(api, case_id)
    # At least one Phase-2 artifact should now load successfully.
    ok = 0
    for key in ("correlation", "graph", "timeline", "analytics"):
        r = api.get(f"/api/cases/{case_id}/artifacts/{key}/")
        if r.status_code == 200:
            ok += 1
    assert ok >= 1, "no Phase-2 artifact was generated by /analyze/"
