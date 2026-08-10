"""Vector-store boundary with production Chroma and deterministic memory implementations."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from ..core.config import RAGConfig
from ..core.models import KnowledgeChunk, RetrievalHit


class VectorStore(Protocol):
    def list_chunks(self, case_id: str) -> list[KnowledgeChunk]: ...
    def upsert(self, case_id: str, chunks: list[KnowledgeChunk]) -> None: ...
    def delete(self, case_id: str, chunk_ids: list[str]) -> None: ...
    def query(self, case_id: str, query: str, limit: int) -> list[RetrievalHit]: ...


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\w@.+:/-]{2,}", value.lower(), flags=re.UNICODE))


class InMemoryVectorStore:
    """Small deterministic store used by tests and dependency-free experiments."""

    def __init__(self) -> None:
        self._chunks: dict[str, dict[str, KnowledgeChunk]] = defaultdict(dict)

    def list_chunks(self, case_id: str) -> list[KnowledgeChunk]:
        return list(self._chunks.get(case_id, {}).values())

    def upsert(self, case_id: str, chunks: list[KnowledgeChunk]) -> None:
        for chunk in chunks:
            if chunk.case_id != case_id:
                raise ValueError("Cannot place a chunk in another case's index")
            self._chunks[case_id][chunk.chunk_id] = chunk

    def delete(self, case_id: str, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self._chunks.get(case_id, {}).pop(chunk_id, None)

    def query(self, case_id: str, query: str, limit: int) -> list[RetrievalHit]:
        query_tokens = _tokens(query)
        hits: list[RetrievalHit] = []
        for chunk in self.list_chunks(case_id):
            content_tokens = _tokens(chunk.text)
            overlap = len(query_tokens & content_tokens)
            score = overlap / max(1, len(query_tokens))
            distance = (1.0 - score) if overlap else 10.0
            hits.append(RetrievalHit(chunk, score=score, distance=distance, reasons=("vector",)))
        return sorted(hits, key=lambda hit: (hit.distance or 0, hit.chunk.chunk_id))[:limit]


class ChromaVectorStore:
    """Case-scoped ChromaDB index. Chroma is derived storage, never source of truth."""

    def __init__(self, config: RAGConfig, embedding_function=None) -> None:
        self._config = config
        self._embedding_function = embedding_function
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import chromadb

            Path(self._config.index_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._config.index_dir))
        return self._client

    def _embedding(self):
        if self._embedding_function is None:
            from chromadb.utils import embedding_functions

            self._embedding_function = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self._config.embedding_model
                )
            )
        return self._embedding_function

    @staticmethod
    def collection_name(case_id: str) -> str:
        digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:24]
        return f"ciis_case_{digest}"

    def _collection(self, case_id: str):
        return self._ensure_client().get_or_create_collection(
            name=self.collection_name(case_id),
            embedding_function=self._embedding(),
            metadata={"case_id": case_id},
        )

    @staticmethod
    def _metadata(chunk: KnowledgeChunk) -> dict[str, str | int]:
        return {
            "case_id": chunk.case_id,
            "evidence_id": chunk.evidence_id,
            "file_name": chunk.file_name,
            "chunk_index": chunk.chunk_index,
            "content_hash": chunk.content_hash,
            "entity_values_json": json.dumps(chunk.entity_values),
            "related_evidence_ids_json": json.dumps(chunk.related_evidence_ids),
            "source_kind": chunk.source_kind,
        }

    @staticmethod
    def _chunk(chunk_id: str, text: str, metadata: dict) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=chunk_id,
            case_id=str(metadata.get("case_id") or ""),
            evidence_id=str(metadata.get("evidence_id") or ""),
            file_name=str(metadata.get("file_name") or "unknown"),
            chunk_index=int(metadata.get("chunk_index") or 0),
            text=text or "",
            content_hash=str(metadata.get("content_hash") or ""),
            entity_values=tuple(json.loads(metadata.get("entity_values_json") or "[]")),
            related_evidence_ids=tuple(json.loads(
                metadata.get("related_evidence_ids_json") or "[]"
            )),
            source_kind=str(metadata.get("source_kind") or "evidence"),
        )

    def list_chunks(self, case_id: str) -> list[KnowledgeChunk]:
        result = self._collection(case_id).get(
            where={"case_id": case_id}, include=["documents", "metadatas"]
        )
        ids = result.get("ids") or []
        documents = result.get("documents") or [""] * len(ids)
        metadatas = result.get("metadatas") or [{}] * len(ids)
        return [
            self._chunk(chunk_id, text, metadata or {})
            for chunk_id, text, metadata in zip(ids, documents, metadatas)
        ]

    def upsert(self, case_id: str, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        if any(chunk.case_id != case_id for chunk in chunks):
            raise ValueError("Cannot place a chunk in another case's collection")
        self._collection(case_id).upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[self._metadata(chunk) for chunk in chunks],
        )

    def delete(self, case_id: str, chunk_ids: list[str]) -> None:
        if chunk_ids:
            self._collection(case_id).delete(ids=chunk_ids)

    def query(self, case_id: str, query: str, limit: int) -> list[RetrievalHit]:
        collection = self._collection(case_id)
        count = collection.count()
        if not count:
            return []
        result = collection.query(
            query_texts=[query],
            n_results=min(limit, count),
            where={"case_id": case_id},
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            RetrievalHit(
                self._chunk(chunk_id, text, metadata or {}),
                score=1.0 / (1.0 + max(0.0, float(distance))),
                distance=float(distance),
                reasons=("vector",),
            )
            for chunk_id, text, metadata, distance in zip(
                ids, documents, metadatas, distances
            )
        ]
