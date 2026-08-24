"""Public API for the standalone CIIE RAG engine."""

from .assistant.service import AssistantService
from .core.config import RAGConfig
from .core.models import AssistantResponse, CaseKnowledgeBundle

__all__ = ["AssistantResponse", "AssistantService", "CaseKnowledgeBundle", "RAGConfig"]
