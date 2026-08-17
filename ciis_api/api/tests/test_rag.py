"""API contract for the case-scoped standalone RAG adapter."""

from __future__ import annotations

from api.exceptions import EngineUnavailable


def response_payload():
    return {
        "answer": "The timeline starts with EVID_00001. [TIMELINE_EVID_00001]",
        "insufficient_evidence": False,
        "cited_sources": [{
            "evidence_id": "TIMELINE_EVID_00001",
            "file_name": "timeline_analysis.json",
            "chunk_ids": ["CASE_TEST:artifact:TIMELINE_EVID_00001:000"],
            "source_kind": "timeline_event",
            "title": "Timeline event for EVID_00001",
            "url": "",
            "supporting_evidence_ids": ["EVID_00001"],
        }],
        "retrieved_sources": [],
        "evidence_breakdown": [],
        "shared_entity_links": [],
        "warnings": [],
    }


def test_assistant_status_is_case_scoped(api, case, monkeypatch):
    from api import engine

    monkeypatch.setattr(
        engine,
        "rag_status",
        lambda case_id: {
            "case_id": case_id,
            "available": True,
            "status": "fresh",
            "detail": "ready",
        },
    )
    response = api.get(f"/api/cases/{case['case_id']}/assistant/status/")

    assert response.status_code == 200
    assert response.json()["case_id"] == case["case_id"]
    assert response.json()["status"] == "fresh"


def test_assistant_question_returns_grounded_sources(api, case, monkeypatch):
    from api import engine

    seen = []
    monkeypatch.setattr(
        engine,
        "ask_rag",
        lambda case_id, question: seen.append((case_id, question)) or response_payload(),
    )
    response = api.post(
        f"/api/cases/{case['case_id']}/assistant/ask/",
        {"question": "What happened first?"},
        format="json",
    )

    assert response.status_code == 200
    assert seen == [(case["case_id"], "What happened first?")]
    assert response.json()["cited_sources"][0]["supporting_evidence_ids"] == [
        "EVID_00001"
    ]


def test_assistant_rejects_empty_or_oversized_question(api, case):
    endpoint = f"/api/cases/{case['case_id']}/assistant/ask/"
    assert api.post(endpoint, {"question": " "}, format="json").status_code == 400
    assert api.post(
        endpoint, {"question": "x" * 2001}, format="json"
    ).status_code == 400


def test_assistant_does_not_expose_another_case(api, monkeypatch):
    from api import engine

    monkeypatch.setattr(
        engine,
        "ask_rag",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    response = api.post(
        "/api/cases/CASE_UNKNOWN/assistant/ask/",
        {"question": "Summarize it"},
        format="json",
    )
    assert response.status_code == 404


def test_assistant_runtime_failure_is_a_clean_503(api, case, monkeypatch):
    from api import engine

    monkeypatch.setattr(
        engine,
        "ask_rag",
        lambda *_args: (_ for _ in ()).throw(
            EngineUnavailable("Ollama is not available.")
        ),
    )
    response = api.post(
        f"/api/cases/{case['case_id']}/assistant/ask/",
        {"question": "Summarize the case"},
        format="json",
    )
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Ollama is not available.",
        "code": "engine_unavailable",
    }


def test_unexpected_index_failure_cannot_fail_the_analysis_pipeline(
    api, monkeypatch
):
    from api import engine, rag_bridge

    monkeypatch.setattr(
        rag_bridge,
        "sync_case",
        lambda _case_id: (_ for _ in ()).throw(RuntimeError("broken index")),
    )

    result = engine._sync_rag_index("CASE_TEST")

    assert result["status"] == "unavailable"
    assert result["available"] is False
    assert "broken index" not in result["detail"]
