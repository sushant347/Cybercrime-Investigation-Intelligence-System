"""Public API for the standalone CIIS RAG engine."""

from .assistant.service import AssistantService
from .core.config import RAGConfig
from .core.models import AssistantResponse, CaseKnowledgeBundle

__all__ = ["AssistantResponse", "AssistantService", "CaseKnowledgeBundle", "RAGConfig"]
