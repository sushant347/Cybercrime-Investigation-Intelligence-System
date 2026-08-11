"""Local Ollama provider with structured failures and JSON output."""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from ..core.config import RAGConfig
from ..core.exceptions import (
    GenerationResponseError,
    GenerationTimeoutError,
    GenerationUnavailableError,
)
from ..core.models import RetrievalHit
from .prompts import build_messages


@dataclass(frozen=True)
class StructuredGeneration:
    answer: str
    citations: tuple[str, ...]
    insufficient_evidence: bool


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "insufficient_evidence": {"type": "boolean"},
    },
    "required": ["answer", "citations", "insufficient_evidence"],
    "additionalProperties": False,
}


def _loopback_host(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def parse_generation(content: str) -> StructuredGeneration:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip() if len(lines) > 2 else value
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise GenerationResponseError("Ollama response was not a JSON object")
        try:
            payload = json.loads(value[start:end + 1])
        except json.JSONDecodeError as exc:
            raise GenerationResponseError("Ollama returned malformed JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
        raise GenerationResponseError("Ollama response is missing a textual answer")
    citations = payload.get("citations") or []
    if not isinstance(citations, list):
        raise GenerationResponseError("Ollama citations must be a JSON array")
    return StructuredGeneration(
        answer=payload["answer"].strip(),
        citations=tuple(str(item) for item in citations),
        insufficient_evidence=bool(payload.get("insufficient_evidence", False)),
    )


class OllamaAnswerGenerator:
    def __init__(self, config: RAGConfig) -> None:
        self._config = config
        if not config.allow_remote_ollama and not _loopback_host(config.ollama_host):
            raise GenerationUnavailableError(
                "Remote Ollama hosts are disabled; set CIIS_RAG_ALLOW_REMOTE_OLLAMA=1 "
                "only for a trusted deployment"
            )

    def generate(self, query: str, hits: list[RetrievalHit]) -> StructuredGeneration:
        payload = json.dumps({
            "model": self._config.ollama_model,
            "messages": build_messages(query, hits),
            "stream": False,
            "format": _RESPONSE_SCHEMA,
            "think": self._config.ollama_think,
            "keep_alive": self._config.ollama_keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": self._config.ollama_num_predict,
            },
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self._config.ollama_host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.ollama_timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise GenerationTimeoutError(
                f"Ollama exceeded {self._config.ollama_timeout_seconds} seconds"
            ) from exc
        except urllib.error.HTTPError as exc:
            raise GenerationUnavailableError(
                f"Ollama returned HTTP {exc.code} for model {self._config.ollama_model}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GenerationUnavailableError(
                f"Cannot reach Ollama at {self._config.ollama_host}; ensure it is running "
                f"and pull model '{self._config.ollama_model}'"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GenerationResponseError("Ollama returned an invalid response body") from exc
        content = (body.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise GenerationResponseError("Ollama response did not contain message content")
        return parse_generation(content)
