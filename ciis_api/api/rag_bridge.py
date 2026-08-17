"""Integrated adapter for the standalone, separately isolated RAG engine.

The platform environment never imports Chroma, Torch or sentence-transformers.
Instead it exchanges bounded JSON with ``rag_assistant_engine.cli`` through the
Python 3.12 interpreter selected by ``CIIS_RAG_PYTHON``. This preserves the
same adapter -> standalone flow used by the timeline/report architecture.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from django.conf import settings

from .exceptions import EngineUnavailable


log = logging.getLogger("ciis.rag")
_run_lock = threading.Lock()


def availability() -> dict[str, Any]:
    """Return a cheap configuration check without importing or loading models."""
    if not getattr(settings, "RAG_ENABLED", True):
        return {
            "available": False,
            "status": "disabled",
            "detail": "The case assistant is disabled by CIIS_RAG_ENABLED.",
        }
    root = Path(settings.RAG_ASSISTANT_ROOT)
    python = getattr(settings, "RAG_PYTHON", None)
    if not (root / "cli.py").is_file():
        return {
            "available": False,
            "status": "unavailable",
            "detail": "The standalone RAG engine directory is missing.",
        }
    if python is None or not Path(python).is_file():
        return {
            "available": False,
            "status": "unavailable",
            "detail": (
                "Configure CIIS_RAG_PYTHON with the Python executable from the "
                "separate RAG environment."
            ),
        }
    return {
        "available": True,
        "status": "configured",
        "detail": "The standalone RAG engine is configured.",
    }


def _case_paths(case_id: str) -> tuple[Path, Path]:
    # Imported lazily to avoid a module cycle: engine imports this adapter only
    # at the integration points that need it.
    from . import engine

    case_json = engine.evidence_config().json_dir / f"{case_id}.json"
    artifact_dir = engine.investigation_config().investigation_dir / case_id
    return case_json.resolve(), artifact_dir.resolve()


def _json_output(value: str) -> dict[str, Any]:
    value = (value or "").strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise EngineUnavailable(
            "The standalone RAG engine returned an invalid response."
        ) from exc
    if not isinstance(payload, dict):
        raise EngineUnavailable("The standalone RAG engine returned invalid JSON.")
    return payload


def _failure(stderr: str) -> EngineUnavailable:
    try:
        payload = _json_output(stderr)
    except EngineUnavailable:
        return EngineUnavailable("The standalone RAG engine did not complete.")
    error_type = str(payload.get("error_type") or "RAGError")
    detail = str(payload.get("detail") or "The RAG request failed.")
    # Expected provider messages are safe and useful. Artifact errors can carry
    # absolute workstation paths, so replace those with a stable public error.
    if error_type == "ArtifactContractError":
        detail = "Current case artifacts could not be validated for RAG indexing."
    return EngineUnavailable(f"{error_type}: {detail}")


def _run(case_id: str, command: str, question: str = "") -> dict[str, Any]:
    state = availability()
    if not state["available"]:
        raise EngineUnavailable(state["detail"])
    case_json, artifact_dir = _case_paths(case_id)
    if not case_json.is_file():
        raise EngineUnavailable(
            "No processed evidence is available for this case yet."
        )

    args = [
        str(settings.RAG_PYTHON),
        "-m", "rag_assistant_engine.cli",
        command,
    ]
    if command == "ask":
        args.append(question)
    args.extend([
        "--case-json", str(case_json),
        "--artifact-dir", str(artifact_dir),
        "--storage-dir", str(settings.RAG_STORAGE_DIR),
    ])
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["CIIS_RAG_STORAGE_DIR"] = str(settings.RAG_STORAGE_DIR)
    try:
        with _run_lock:
            completed = subprocess.run(
                args,
                cwd=str(Path(settings.BASE_DIR).parent),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.RAG_COMMAND_TIMEOUT,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise EngineUnavailable(
            f"The case assistant exceeded {settings.RAG_COMMAND_TIMEOUT} seconds."
        ) from exc
    except OSError as exc:
        log.warning("Could not start standalone RAG process: %s", exc)
        raise EngineUnavailable(
            "The configured RAG Python environment could not be started."
        ) from exc
    if completed.returncode != 0:
        raise _failure(completed.stderr)
    return _json_output(completed.stdout)


def status_case(case_id: str) -> dict[str, Any]:
    state = availability()
    if not state["available"]:
        return {"case_id": case_id, **state}
    try:
        payload = _run(case_id, "status")
    except EngineUnavailable as exc:
        return {
            "case_id": case_id,
            "available": False,
            "status": "unavailable",
            "detail": str(exc),
        }
    return {
        "available": True,
        "detail": "The case assistant is ready.",
        **payload,
    }


def sync_case(case_id: str) -> dict[str, Any]:
    """Best-effort pipeline hook; RAG can never fail evidence analysis."""
    state = availability()
    if not state["available"]:
        return {"case_id": case_id, **state}
    try:
        payload = _run(case_id, "build")
    except EngineUnavailable as exc:
        log.warning("RAG index refresh failed for %s: %s", case_id, exc)
        return {
            "case_id": case_id,
            "available": False,
            "status": "unavailable",
            "detail": str(exc),
        }
    return {"available": True, **payload}


def ask_case(case_id: str, question: str) -> dict[str, Any]:
    return _run(case_id, "ask", question=question)
