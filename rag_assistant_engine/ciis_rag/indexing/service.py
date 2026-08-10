"""Incremental, hash-driven synchronization of derived RAG chunks."""

from __future__ import annotations

from ..core.config import RAGConfig
from ..core.models import CaseKnowledgeBundle, IndexSyncResult
from ..documents.builder import CHUNKING_VERSION, build_chunks
from .manifest import MANIFEST_SCHEMA_VERSION, IndexManifest, ManifestRepository
from .repository import VectorStore


class IndexService:
    def __init__(
        self,
        config: RAGConfig,
        store: VectorStore,
        manifests: ManifestRepository,
    ) -> None:
        self._config = config
        self._store = store
        self._manifests = manifests

    def _desired(self, bundle: CaseKnowledgeBundle):
        chunks = build_chunks(bundle, self._config)
        return chunks, {chunk.chunk_id: chunk.content_hash for chunk in chunks}

    def status(self, bundle: CaseKnowledgeBundle) -> str:
        chunks, hashes = self._desired(bundle)
        manifest = self._manifests.load(bundle.case_id)
        existing_ids = {chunk.chunk_id for chunk in self._store.list_chunks(bundle.case_id)}
        desired_ids = {chunk.chunk_id for chunk in chunks}
        if manifest is None:
            return "missing"
        if (
            manifest.schema_version != MANIFEST_SCHEMA_VERSION
            or manifest.embedding_model != self._config.embedding_model
            or manifest.chunking_version != CHUNKING_VERSION
            or manifest.source_hashes != bundle.source_hashes
            or manifest.chunk_hashes != hashes
            or existing_ids != desired_ids
        ):
            return "stale"
        return "fresh"

    def sync(self, bundle: CaseKnowledgeBundle) -> IndexSyncResult:
        chunks, desired_hashes = self._desired(bundle)
        manifest = self._manifests.load(bundle.case_id)
        force_reindex = (
            manifest is None
            or manifest.schema_version != MANIFEST_SCHEMA_VERSION
            or manifest.embedding_model != self._config.embedding_model
            or manifest.chunking_version != CHUNKING_VERSION
        )
        existing = {
            chunk.chunk_id: chunk for chunk in self._store.list_chunks(bundle.case_id)
        }
        desired = {chunk.chunk_id: chunk for chunk in chunks}
        changed = [
            chunk for chunk_id, chunk in desired.items()
            if force_reindex
            or chunk_id not in existing
            or existing[chunk_id].content_hash != chunk.content_hash
        ]
        deleted = sorted(set(existing) - set(desired))
        self._store.delete(bundle.case_id, deleted)
        self._store.upsert(bundle.case_id, changed)
        self._manifests.save(IndexManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            case_id=bundle.case_id,
            embedding_model=self._config.embedding_model,
            chunking_version=CHUNKING_VERSION,
            source_hashes=dict(bundle.source_hashes),
            chunk_hashes=desired_hashes,
        ))
        unchanged = len(desired) - len(changed)
        return IndexSyncResult(
            case_id=bundle.case_id,
            added_or_updated=len(changed),
            deleted=len(deleted),
            unchanged=unchanged,
            total_chunks=len(desired),
            status="updated" if changed or deleted else "fresh",
        )
