"""Coordinate index freshness, retrieval, generation, and deterministic evidence views."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Protocol

from ..core.models import (
    AssistantResponse,
    CaseKnowledgeBundle,
    EvidenceBreakdown,
    RetrievalHit,
    SharedEvidenceLink,
    SourceReference,
)
from ..generation.citations import extract_cited_ids, validate_cited_ids
from ..generation.ollama import StructuredGeneration
from ..indexing.service import IndexService
from ..retrieval.service import RetrievalService
from ..retrieval.constraints import extract_query_constraints, missing_query_constraints


class AnswerGenerator(Protocol):
    def generate(self, query: str, hits: list[RetrievalHit]) -> StructuredGeneration: ...


_ENTITY_QUESTION_GROUPS = (
    ("transaction IDs", ("transaction id", "transaction code", "transaction reference"),
     ("transaction_ids",)),
    ("amounts", ("amount", "money", "npr", "rupee"), ("money",)),
    ("phone numbers", ("phone", "mobile", "contact number"),
     ("phones", "phone_numbers", "whatsapp_numbers")),
    ("email addresses", ("email", "e-mail"), ("emails", "esewa_ids")),
    ("URLs/domains", ("url", "link", "domain", "website"), ("urls", "domains")),
    ("bank accounts", ("bank account", "account number"), ("bank_accounts",)),
)


def _requested_entity_groups(query: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    lowered = query.lower()
    return tuple(
        (label, entity_types)
        for label, terms, entity_types in _ENTITY_QUESTION_GROUPS
        if any(term in lowered for term in terms)
    )


def _substantive_answer(answer: str) -> bool:
    without_ids = re.sub(r"\bEVID_[A-Z0-9_-]+\b", " ", answer, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:+/-]*", without_ids)
    return len(words) >= 3


def _sources(hits: list[RetrievalHit]) -> tuple[SourceReference, ...]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for hit in hits:
        grouped[(hit.chunk.evidence_id, hit.chunk.file_name)].append(hit.chunk.chunk_id)
    return tuple(
        SourceReference(evidence_id, file_name, tuple(sorted(set(chunk_ids))))
        for (evidence_id, file_name), chunk_ids in sorted(grouped.items())
    )


def _breakdown(
    bundle: CaseKnowledgeBundle,
    evidence_ids: set[str],
) -> tuple[EvidenceBreakdown, ...]:
    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    return tuple(
        EvidenceBreakdown(
            evidence_id=evidence_id,
            file_name=evidence_by_id[evidence_id].file_name,
            entities=tuple(sorted({
                f"{entity.entity_type}={entity.normalized}"
                for entity in evidence_by_id[evidence_id].entities
            })),
        )
        for evidence_id in sorted(evidence_ids)
        if evidence_id in evidence_by_id
    )


def _shared_links(
    bundle: CaseKnowledgeBundle,
    evidence_ids: set[str],
) -> tuple[SharedEvidenceLink, ...]:
    return tuple(
        SharedEvidenceLink(
            evidence_a=relationship.evidence_a,
            evidence_b=relationship.evidence_b,
            relationship_type=relationship.relationship_type,
            confidence=relationship.confidence,
            shared_entities=relationship.shared_entities,
        )
        for relationship in bundle.relationships
        if relationship.evidence_a in evidence_ids
        and relationship.evidence_b in evidence_ids
    )


class AssistantService:
    def __init__(
        self,
        indexing: IndexService,
        retrieval: RetrievalService,
        generator: AnswerGenerator,
    ) -> None:
        self._indexing = indexing
        self._retrieval = retrieval
        self._generator = generator

    def ask(
        self,
        bundle: CaseKnowledgeBundle,
        query: str,
        *,
        sync_before_query: bool = True,
    ) -> AssistantResponse:
        if sync_before_query:
            self._indexing.sync(bundle)
        hits = self._retrieval.retrieve(bundle.case_id, query)
        if not hits:
            return AssistantResponse(
                answer="No sufficiently relevant indexed evidence was found for this question.",
                insufficient_evidence=True,
                cited_sources=(),
                retrieved_sources=(),
                evidence_breakdown=(),
                shared_entity_links=(),
                warnings=tuple(bundle.warnings),
            )

        missing = missing_query_constraints(query, hits)
        if missing:
            requested = ", ".join(item.display for item in missing)
            return AssistantResponse(
                answer=(
                    "No retrieved evidence contains the exact requested value(s): "
                    f"{requested}. Similar values were not treated as matches."
                ),
                insufficient_evidence=True,
                cited_sources=(),
                retrieved_sources=_sources(hits),
                evidence_breakdown=(),
                shared_entity_links=(),
                warnings=tuple(bundle.warnings),
            )

        requested_ids = {
            item.normalized for item in extract_query_constraints(query)
            if item.kind == "evidence_id"
        }
        if len(requested_ids) == 2:
            links = _shared_links(bundle, requested_ids)
            cited_hits = [
                hit for hit in hits if hit.chunk.evidence_id in requested_ids
            ]
            if links:
                correlation_links = [
                    link for link in links if link.relationship_type == "correlation"
                ]
                strongest = max(
                    correlation_links or list(links),
                    key=lambda link: link.confidence,
                )
                basis = ", ".join(strongest.shared_entities) or (
                    "the stored typed graph relationship"
                )
                ordered_ids = sorted(requested_ids)
                citations = " ".join(f"[{item}]" for item in ordered_ids)
                answer = (
                    f"{', '.join(ordered_ids)} are connected by a recorded "
                    f"{strongest.relationship_type} relationship "
                    f"(confidence {strongest.confidence:.3f}). "
                    f"Recorded basis: {basis}. {citations}"
                )
                insufficient = False
            else:
                answer = (
                    "No stored relationship connects all explicitly requested "
                    "evidence IDs."
                )
                insufficient = True
            return AssistantResponse(
                answer=answer,
                insufficient_evidence=insufficient,
                cited_sources=_sources(cited_hits),
                retrieved_sources=_sources(hits),
                evidence_breakdown=_breakdown(bundle, requested_ids),
                shared_entity_links=links,
                warnings=tuple(bundle.warnings),
            )

        if len(requested_ids) == 1:
            evidence_id = next(iter(requested_ids))
            evidence = next(
                (item for item in bundle.evidence if item.evidence_id == evidence_id),
                None,
            )
            cited_hits = [
                hit for hit in hits if hit.chunk.evidence_id == evidence_id
            ]
            groups = _requested_entity_groups(query)
            if evidence is not None and groups:
                facts: list[str] = []
                for label, entity_types in groups:
                    values = sorted({
                        entity.normalized for entity in evidence.entities
                        if entity.entity_type in entity_types and entity.normalized
                    })
                    if values:
                        facts.append(f"{label}: {', '.join(values)}")
                if facts:
                    answer = (
                        f"Extracted values for {evidence_id}: {'; '.join(facts)}. "
                        f"[{evidence_id}]"
                    )
                    insufficient = False
                else:
                    answer = (
                        f"No requested extracted value is available for {evidence_id}."
                    )
                    insufficient = True
                return AssistantResponse(
                    answer=answer,
                    insufficient_evidence=insufficient,
                    cited_sources=_sources(cited_hits) if not insufficient else (),
                    retrieved_sources=_sources(hits),
                    evidence_breakdown=_breakdown(bundle, {evidence_id}),
                    shared_entity_links=(),
                    warnings=tuple(bundle.warnings),
                )

            lowered_query = query.lower()
            if any(term in lowered_query for term in ("when", "timestamp", "timeline date")):
                event = next(
                    (item for item in bundle.timeline if item.evidence_id == evidence_id),
                    None,
                )
                if event is not None and event.timestamp:
                    answer = (
                        f"The reconstructed timestamp for {evidence_id} is "
                        f"{event.timestamp}; source={event.source}; "
                        f"confidence={event.confidence}; inferred="
                        f"{str(event.inferred).lower()}. [{evidence_id}]"
                    )
                    insufficient = False
                else:
                    answer = f"No reconstructed timestamp is available for {evidence_id}."
                    insufficient = True
                return AssistantResponse(
                    answer=answer,
                    insufficient_evidence=insufficient,
                    cited_sources=_sources(cited_hits) if not insufficient else (),
                    retrieved_sources=_sources(hits),
                    evidence_breakdown=_breakdown(bundle, {evidence_id}),
                    shared_entity_links=(),
                    warnings=tuple(bundle.warnings),
                )

        generated = self._generator.generate(query, hits)
        candidates = {hit.chunk.evidence_id for hit in hits}
        explicit = validate_cited_ids(generated.citations, candidates)
        inline = extract_cited_ids(generated.answer, candidates)
        cited_ids = set(explicit) | inline
        missing_requested_citations = requested_ids - cited_ids
        invalid = sorted(set(generated.citations) - candidates)
        warnings: list[str] = list(bundle.warnings)
        if invalid:
            warnings.append("Discarded citations outside retrieved context: " + ", ".join(invalid))
        if missing_requested_citations:
            warnings.append(
                "Generated answer omitted requested evidence citation(s): "
                + ", ".join(sorted(missing_requested_citations))
            )

        insufficient = generated.insufficient_evidence
        answer = generated.answer
        non_substantive = not _substantive_answer(generated.answer)
        if non_substantive:
            warnings.append("Generated answer contained no substantive factual response")
        if (
            not cited_ids or missing_requested_citations or non_substantive
        ) and not insufficient:
            if not cited_ids:
                warnings.append("Generated answer had no verifiable evidence citation")
            insufficient = True
            answer = (
                "The generated response was withheld because it did not provide a "
                "substantive answer with all required evidence citations."
            )

        cited_hits = [hit for hit in hits if hit.chunk.evidence_id in cited_ids]
        breakdown = _breakdown(bundle, cited_ids)
        links = _shared_links(bundle, cited_ids)
        return AssistantResponse(
            answer=answer,
            insufficient_evidence=insufficient,
            cited_sources=_sources(cited_hits),
            retrieved_sources=_sources(hits),
            evidence_breakdown=breakdown,
            shared_entity_links=links,
            warnings=tuple(warnings),
        )
