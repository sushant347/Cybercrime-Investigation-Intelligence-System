from __future__ import annotations

import json

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
