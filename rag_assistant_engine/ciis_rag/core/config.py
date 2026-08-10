"""Environment-backed standalone RAG configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_ENGINE_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


@dataclass(frozen=True)
class RAGConfig:
    """All runtime choices that affect indexing or answer generation."""

    storage_dir: Path = _ENGINE_ROOT / "storage"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ollama_model: str = "gemma3:1b"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: int = 300
    ollama_think: bool = False
    ollama_num_predict: int = 256
    ollama_keep_alive: str = "10m"
    top_k: int = 5
    candidate_multiplier: int = 3
    minimum_relevance: float = 0.18
    chunk_size_chars: int = 2400
    chunk_overlap_chars: int = 240
    allow_remote_ollama: bool = False

    @classmethod
    def from_env(cls) -> "RAGConfig":
        config = cls(
            storage_dir=Path(os.environ.get(
                "CIIS_RAG_STORAGE_DIR", str(_ENGINE_ROOT / "storage")
            )),
            embedding_model=os.environ.get(
                "CIIS_RAG_EMBEDDING_MODEL",
                "paraphrase-multilingual-MiniLM-L12-v2",
            ),
            ollama_model=os.environ.get("CIIS_RAG_OLLAMA_MODEL", "gemma3:1b"),
            ollama_host=os.environ.get(
                "CIIS_RAG_OLLAMA_HOST", "http://127.0.0.1:11434"
            ).rstrip("/"),
            ollama_timeout_seconds=int(os.environ.get("CIIS_RAG_TIMEOUT", "300")),
            ollama_think=_env_bool("CIIS_RAG_OLLAMA_THINK"),
            ollama_num_predict=int(os.environ.get(
                "CIIS_RAG_OLLAMA_NUM_PREDICT", "256"
            )),
            ollama_keep_alive=os.environ.get(
                "CIIS_RAG_OLLAMA_KEEP_ALIVE", "10m"
            ).strip(),
            top_k=int(os.environ.get("CIIS_RAG_TOP_K", "5")),
            candidate_multiplier=int(os.environ.get(
                "CIIS_RAG_CANDIDATE_MULTIPLIER", "3"
            )),
            minimum_relevance=float(os.environ.get(
                "CIIS_RAG_MINIMUM_RELEVANCE", "0.18"
            )),
            chunk_size_chars=int(os.environ.get("CIIS_RAG_CHUNK_SIZE", "2400")),
            chunk_overlap_chars=int(os.environ.get("CIIS_RAG_CHUNK_OVERLAP", "240")),
            allow_remote_ollama=_env_bool("CIIS_RAG_ALLOW_REMOTE_OLLAMA"),
        )
        config.validate()
        return config

    @property
    def index_dir(self) -> Path:
        return self.storage_dir / "chroma"

    @property
    def manifest_dir(self) -> Path:
        return self.storage_dir / "manifests"

    def validate(self) -> None:
        if self.top_k < 1:
            raise ValueError("CIIS_RAG_TOP_K must be at least 1")
        if self.candidate_multiplier < 1:
            raise ValueError("CIIS_RAG_CANDIDATE_MULTIPLIER must be at least 1")
        if not 0.0 <= self.minimum_relevance <= 1.0:
            raise ValueError("CIIS_RAG_MINIMUM_RELEVANCE must be between 0 and 1")
        if self.chunk_size_chars < 400:
            raise ValueError("CIIS_RAG_CHUNK_SIZE must be at least 400")
        if not 0 <= self.chunk_overlap_chars < self.chunk_size_chars:
            raise ValueError("CIIS_RAG_CHUNK_OVERLAP must be smaller than chunk size")
        if self.ollama_timeout_seconds < 1:
            raise ValueError("CIIS_RAG_TIMEOUT must be positive")
        if self.ollama_num_predict < 1:
            raise ValueError("CIIS_RAG_OLLAMA_NUM_PREDICT must be positive")
        if not self.ollama_keep_alive:
            raise ValueError("CIIS_RAG_OLLAMA_KEEP_ALIVE must not be empty")
