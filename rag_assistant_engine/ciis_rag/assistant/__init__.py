"""Top-level standalone RAG orchestration."""

from .service import AssistantService, answer_without_retrieval

__all__ = ["AssistantService", "answer_without_retrieval"]
