"""Stable, integration-neutral contracts for the RAG engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EntityMention:
    entity_type: str
    value: str
    normalized: str


@dataclass(frozen=True)
class EvidenceItem:
    case_id: str
    evidence_id: str
    file_name: str
    raw_text: str
    cleaned_text: str
    upload_time: str
    file_hash: str
    entities: tuple[EntityMention, ...] = ()
    risk_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimelineFact:
    evidence_id: str
    timestamp: str
    source: str
    confidence: str
    inferred: bool


@dataclass(frozen=True)
class Relationship:
    evidence_a: str
    evidence_b: str
    relationship_type: str
    confidence: float
    shared_entities: tuple[str, ...] = ()
    explanation: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class ArtifactSection:
    """One investigator-facing section derived from a canonical CIIS artifact."""

    source_id: str
    source_kind: str
    title: str
    file_name: str
    text: str
    evidence_ids: tuple[str, ...] = ()
    entity_values: tuple[str, ...] = ()
    source_url: str = ""


@dataclass(frozen=True)
class CaseKnowledgeBundle:
    case_id: str
    evidence: tuple[EvidenceItem, ...]
    timeline: tuple[TimelineFact, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    artifact_sections: tuple[ArtifactSection, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
    source_hashes: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    case_id: str
    evidence_id: str
    file_name: str
    chunk_index: int
    text: str
    content_hash: str
    entity_values: tuple[str, ...] = ()
    related_evidence_ids: tuple[str, ...] = ()
    source_kind: str = "evidence"
    source_title: str = ""
    source_url: str = ""
    supporting_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalHit:
    chunk: KnowledgeChunk
    score: float
    distance: float | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndexSyncResult:
    case_id: str
    added_or_updated: int
    deleted: int
    unchanged: int
    total_chunks: int
    status: str


@dataclass(frozen=True)
class SourceReference:
    evidence_id: str
    file_name: str
    chunk_ids: tuple[str, ...]
    source_kind: str = "evidence"
    title: str = ""
    url: str = ""
    supporting_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceBreakdown:
    evidence_id: str
    file_name: str
    entities: tuple[str, ...]


@dataclass(frozen=True)
class SharedEvidenceLink:
    evidence_a: str
    evidence_b: str
    relationship_type: str
    confidence: float
    shared_entities: tuple[str, ...]


@dataclass(frozen=True)
class AssistantResponse:
    answer: str
    insufficient_evidence: bool
    cited_sources: tuple[SourceReference, ...]
    retrieved_sources: tuple[SourceReference, ...]
    evidence_breakdown: tuple[EvidenceBreakdown, ...]
    shared_entity_links: tuple[SharedEvidenceLink, ...]
    warnings: tuple[str, ...] = ()
