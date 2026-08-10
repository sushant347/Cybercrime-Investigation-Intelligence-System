"""Combine vector, lexical, exact-entity, and graph-neighbour retrieval."""

from __future__ import annotations

import re

from ..core.config import RAGConfig
from ..core.models import KnowledgeChunk, RetrievalHit
from ..indexing.repository import VectorStore
from .constraints import extract_query_constraints


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\w@.+:/-]{2,}", value.lower(), flags=re.UNICODE))


class RetrievalService:
    def __init__(self, config: RAGConfig, store: VectorStore) -> None:
        self._config = config
        self._store = store

    @staticmethod
    def _exact_entity_matches(query: str, chunk: KnowledgeChunk) -> int:
        lowered = query.lower()
        matches = 0
        for value in chunk.entity_values:
            normalized = value.strip().lower()
            if len(normalized) < 3:
                continue
            if re.fullmatch(r"[a-z0-9_]+", normalized):
                pattern = rf"(?<![a-z0-9_]){re.escape(normalized)}(?![a-z0-9_])"
                matches += int(bool(re.search(pattern, lowered)))
            else:
                matches += int(normalized in lowered)
        return matches

    def retrieve(self, case_id: str, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        query = query.strip()
        if not query:
            return []
        limit = top_k or self._config.top_k
        candidate_limit = max(limit, limit * self._config.candidate_multiplier)
        vector_hits = self._store.query(case_id, query, candidate_limit)
        all_chunks = self._store.list_chunks(case_id)
        query_tokens = _tokens(query)
        requested_evidence_ids = {
            item.normalized for item in extract_query_constraints(query)
            if item.kind == "evidence_id"
        }

        vector = {hit.chunk.chunk_id: hit for hit in vector_hits}
        ranked: dict[str, RetrievalHit] = {}
        for chunk in all_chunks:
            base = vector.get(chunk.chunk_id)
            vector_score = base.score if base else 0.0
            overlap = len(query_tokens & _tokens(chunk.text))
            lexical = overlap / max(1, len(query_tokens))
            entity_matches = self._exact_entity_matches(query, chunk)
            exact_evidence_id = chunk.evidence_id.upper() in requested_evidence_ids
            score = min(
                1.0,
                (0.65 * vector_score)
                + (0.35 * lexical)
                + (0.55 if entity_matches else 0.0)
                + (0.85 if exact_evidence_id else 0.0),
            )
            reasons: list[str] = []
            if base:
                reasons.append("semantic")
            if overlap:
                reasons.append("keyword")
            if entity_matches:
                reasons.append("exact_entity")
            if exact_evidence_id:
                reasons.append("exact_evidence_id")
            if score >= self._config.minimum_relevance:
                ranked[chunk.chunk_id] = RetrievalHit(
                    chunk=chunk,
                    score=score,
                    distance=base.distance if base else None,
                    reasons=tuple(reasons),
                )

        ordered = sorted(
            ranked.values(), key=lambda hit: (-hit.score, hit.chunk.chunk_id)
        )

        # Expand the strongest matches to directly correlated evidence. This
        # is deliberately bounded and never crosses the case-scoped store.
        best_by_evidence: dict[str, KnowledgeChunk] = {}
        for chunk in all_chunks:
            previous = best_by_evidence.get(chunk.evidence_id)
            if previous is None or chunk.chunk_index < previous.chunk_index:
                best_by_evidence[chunk.evidence_id] = chunk
        expanded = dict(ranked)
        for hit in ordered[:limit]:
            for related_id in hit.chunk.related_evidence_ids:
                neighbor = best_by_evidence.get(related_id)
                if neighbor is None:
                    continue
                score = hit.score * 0.72
                if neighbor.chunk_id in expanded:
                    existing = expanded[neighbor.chunk_id]
                    reasons = tuple(sorted(set(existing.reasons) | {"graph_neighbor"}))
                    expanded[neighbor.chunk_id] = RetrievalHit(
                        chunk=existing.chunk,
                        score=max(existing.score, score),
                        distance=existing.distance,
                        reasons=reasons,
                    )
                    continue
                if score >= self._config.minimum_relevance:
                    expanded[neighbor.chunk_id] = RetrievalHit(
                        chunk=neighbor,
                        score=score,
                        reasons=("graph_neighbor",),
                    )

        ordered = sorted(
            expanded.values(), key=lambda hit: (-hit.score, hit.chunk.chunk_id)
        )

        # Prefer evidence diversity before adding a second chunk from the same
        # document, so one long PDF cannot consume the entire context window.
        selected: list[RetrievalHit] = []
        deferred: list[RetrievalHit] = []
        seen_evidence: set[str] = set()
        for hit in ordered:
            if hit.chunk.evidence_id in seen_evidence:
                deferred.append(hit)
            else:
                selected.append(hit)
                seen_evidence.add(hit.chunk.evidence_id)
            if len(selected) == limit:
                return selected
        selected.extend(deferred[: max(0, limit - len(selected))])
        return selected
