"""Adapters from external artifact schemas into stable RAG contracts."""

from .ciis_artifacts import bundle_from_documents, load_case_bundle

__all__ = ["bundle_from_documents", "load_case_bundle"]
