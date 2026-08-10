from __future__ import annotations

import json
from types import SimpleNamespace

from rag_assistant_engine import cli
from rag_assistant_engine.ciis_rag.core.exceptions import GenerationTimeoutError


def test_expected_rag_failure_is_reported_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "_execute",
        lambda _args: (_ for _ in ()).throw(GenerationTimeoutError("too slow")),
    )

    exit_code = cli.main([
        "status",
        "--case-json", "case.json",
        "--artifact-dir", "artifacts",
    ])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert exit_code == 2
    assert payload == {
        "status": "error",
        "error_type": "GenerationTimeoutError",
        "detail": "too slow",
    }
    assert "Traceback" not in captured.err


def test_graph_entity_question_skips_vector_services(bundle, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_case_bundle", lambda *_args: bundle)
    monkeypatch.setattr(
        cli,
        "_services",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("deterministic graph query must not initialize Chroma")
        ),
    )
    args = SimpleNamespace(
        command="ask",
        question="Which entity has the most relationships?",
        case_json="case.json",
        artifact_dir="artifacts",
        storage_dir=None,
        model=None,
        ollama_host=None,
        top_k=None,
    )

    assert cli._execute(args) == 0

    response = json.loads(capsys.readouterr().out)
    assert response["insufficient_evidence"] is False
    assert "phone numbers: 9800000001" in response["answer"]
