"""Coordinate index freshness, retrieval, generation, and deterministic evidence views."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol

from ..core.models import (
    AssistantResponse,
    CaseKnowledgeBundle,
    EvidenceBreakdown,
    Relationship,
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
    ("transaction IDs", (
        "transaction id", "transaction code", "transaction reference",
        "payment identifier", "payment reference",
    ), ("transaction_ids",)),
    ("amounts", ("amount", "money", "npr", "rupee"), ("money",)),
    ("phone numbers", ("phone", "mobile", "contact number"),
     ("phones", "phone_numbers", "whatsapp_numbers")),
    ("email addresses", ("email", "e-mail"), ("emails", "esewa_ids")),
    ("URLs/domains", ("url", "web link", "hyperlink", "domain", "website"),
     ("urls", "domains")),
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


def _conversation_reply(query: str) -> str | None:
    """Answer non-investigative courtesies without retrieval or generation.

    Greetings and requests for usage guidance contain no case claim that needs
    evidentiary support. Sending them through RAG both wastes CPU time and
    incorrectly turns the citation guard into an "insufficient evidence"
    warning. The deliberately narrow full-query matching prevents a real
    investigation question that happens to start with "hello" from bypassing
    evidence retrieval.
    """
    normalized = " ".join(query.lower().split()).strip(" .,!?:;-")
    if normalized in {
        "hello", "hello there", "hi", "hi there", "hey",
        "good morning", "good afternoon", "good evening",
    }:
        return (
            "Hello. I can help you examine this case's evidence, timeline, "
            "relationships, report findings, and applicable legal sources. "
            "Ask a case-specific question or choose one of the suggested prompts."
        )
    if normalized in {"help", "what can you do", "how can you help"}:
        return (
            "I can summarize stored findings, identify evidence relationships, "
            "explain timeline events and timestamp confidence, list extracted "
            "entities, and show source-backed legal or regulatory mappings."
        )
    if normalized in {"thanks", "thank you", "thank you very much"}:
        return "You're welcome. Ask another question whenever you are ready."
    return None


def _sources(hits: list[RetrievalHit]) -> tuple[SourceReference, ...]:
    grouped: dict[tuple[str, str, str, str, str], dict[str, set[str]]] = {}
    for hit in hits:
        key = (
            hit.chunk.evidence_id,
            hit.chunk.file_name,
            hit.chunk.source_kind,
            hit.chunk.source_title,
            hit.chunk.source_url,
        )
        entry = grouped.setdefault(key, {"chunks": set(), "evidence": set()})
        entry["chunks"].add(hit.chunk.chunk_id)
        entry["evidence"].update(hit.chunk.supporting_evidence_ids)
    return tuple(
        SourceReference(
            evidence_id=source_id,
            file_name=file_name,
            chunk_ids=tuple(sorted(values["chunks"])),
            source_kind=source_kind,
            title=title or file_name,
            url=url,
            supporting_evidence_ids=tuple(sorted(values["evidence"])),
        )
        for (source_id, file_name, source_kind, title, url), values
        in sorted(grouped.items())
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


def _bundle_sources(
    bundle: CaseKnowledgeBundle,
    source_ids: set[str],
    hits: list[RetrievalHit],
) -> tuple[SourceReference, ...]:
    """Resolve deterministic citations even when vector top-k omitted a source."""
    resolved = {
        source.evidence_id: source
        for source in _sources(hits)
        if source.evidence_id in source_ids
    }
    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    artifacts_by_id = {
        section.source_id: section for section in bundle.artifact_sections
    }
    for source_id in source_ids - set(resolved):
        evidence = evidence_by_id.get(source_id)
        if evidence is not None:
            resolved[source_id] = SourceReference(
                evidence_id=source_id,
                file_name=evidence.file_name,
                chunk_ids=(),
                source_kind="evidence",
                title=evidence.file_name,
                supporting_evidence_ids=(source_id,),
            )
            continue
        section = artifacts_by_id.get(source_id)
        if section is not None:
            resolved[source_id] = SourceReference(
                evidence_id=source_id,
                file_name=section.file_name,
                chunk_ids=(),
                source_kind=section.source_kind,
                title=section.title,
                url=section.source_url,
                supporting_evidence_ids=section.evidence_ids,
            )
    return tuple(resolved[source_id] for source_id in sorted(resolved))


def _timeline_extreme(query: str) -> str:
    lowered = query.lower()
    if not any(term in lowered for term in ("timeline", "event", "happened", "occurred")):
        return ""
    if any(term in lowered for term in ("earliest", "happened first", "first event")):
        return "first"
    if any(term in lowered for term in ("latest", "happened last", "last event", "most recent")):
        return "last"
    return ""


def _timestamp_key(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return datetime.max.replace(tzinfo=UTC)


def _timeline_source_id(bundle: CaseKnowledgeBundle, evidence_id: str) -> str:
    for section in bundle.artifact_sections:
        if (
            section.source_kind == "timeline_event"
            and evidence_id in section.evidence_ids
        ):
            return section.source_id
    return evidence_id


def _requested_relationship_types(query: str) -> set[str]:
    lowered = query.lower()
    relationship_terms = (
        "connect", "linked", "linking", "relationship", "share", "shared",
    )
    if not any(term in lowered for term in relationship_terms):
        return set()
    return {
        entity_type
        for _label, entity_types in _requested_entity_groups(query)
        for entity_type in entity_types
    }


def _is_top_connected_entity_question(query: str) -> bool:
    lowered = query.lower()
    return (
        "entity" in lowered
        and any(term in lowered for term in ("highest", "most", "top", "maximum"))
        and any(term in lowered for term in (
            "relationship", "relationships", "connected", "connections", "links",
        ))
    )


def _top_connected_entity(bundle: CaseKnowledgeBundle):
    """Rank typed entity values by distinct evidence-pair relationships."""
    known_entities = {
        f"{mention.entity_type}={mention.normalized}".casefold():
        f"{mention.entity_type}={mention.normalized}"
        for evidence in bundle.evidence
        for mention in evidence.entities
        if mention.entity_type and mention.normalized
    }
    pairs_by_entity: dict[str, set[tuple[str, str]]] = {}
    evidence_by_entity: dict[str, set[str]] = {}
    confidence_by_entity: dict[str, float] = {}
    for relationship in bundle.relationships:
        pair = tuple(sorted((relationship.evidence_a, relationship.evidence_b)))
        if len(pair) != 2 or not all(pair):
            continue
        for raw_entity in set(relationship.shared_entities):
            raw_entity = raw_entity.strip()
            entity = known_entities.get(raw_entity.casefold())
            # Correlation factors such as timeline_proximity and keyword
            # similarity can support an edge but are not extracted entities.
            if entity is None:
                continue
            pairs_by_entity.setdefault(entity, set()).add(pair)
            evidence_by_entity.setdefault(entity, set()).update(pair)
            confidence_by_entity[entity] = max(
                confidence_by_entity.get(entity, 0.0), relationship.confidence,
            )
    if not pairs_by_entity:
        return None
    entity = min(
        pairs_by_entity,
        key=lambda item: (
            -len(pairs_by_entity[item]),
            -len(evidence_by_entity[item]),
            -confidence_by_entity[item],
            item.lower(),
        ),
    )
    return (
        entity,
        pairs_by_entity[entity],
        evidence_by_entity[entity],
        confidence_by_entity[entity],
    )


def answer_without_retrieval(
    bundle: CaseKnowledgeBundle,
    query: str,
) -> AssistantResponse | None:
    """Return answers that need canonical artifacts but no vector retrieval."""
    conversation_reply = _conversation_reply(query)
    if conversation_reply is not None:
        return AssistantResponse(
            answer=conversation_reply,
            insufficient_evidence=False,
            cited_sources=(),
            retrieved_sources=(),
            evidence_breakdown=(),
            shared_entity_links=(),
            warnings=(),
        )
    if not _is_top_connected_entity_question(query):
        return None
    ranked_entity = _top_connected_entity(bundle)
    if ranked_entity is None:
        return AssistantResponse(
            answer=(
                "No typed entity is recorded as connecting two or more "
                "evidence items in this case."
            ),
            insufficient_evidence=True,
            cited_sources=(),
            retrieved_sources=(),
            evidence_breakdown=(),
            shared_entity_links=(),
            warnings=tuple(bundle.warnings),
        )
    entity, relationship_pairs, evidence_ids, highest_confidence = ranked_entity
    entity_type, separator, value = entity.partition("=")
    display = f"{entity_type.replace('_', ' ')}: {value}" if separator else entity
    citations = " ".join(
        f"[{evidence_id}]" for evidence_id in sorted(evidence_ids)
    )
    links = tuple(
        SharedEvidenceLink(
            evidence_a=relationship.evidence_a,
            evidence_b=relationship.evidence_b,
            relationship_type=relationship.relationship_type,
            confidence=relationship.confidence,
            shared_entities=(entity,),
        )
        for relationship in bundle.relationships
        if entity in relationship.shared_entities
    )
    return AssistantResponse(
        answer=(
            f"The most connected stored entity is {display}. It supports "
            f"{len(relationship_pairs)} distinct evidence relationship(s) "
            f"across {len(evidence_ids)} evidence item(s); the highest "
            f"supporting edge confidence is {highest_confidence:.3f}. {citations}"
        ),
        insufficient_evidence=False,
        cited_sources=_bundle_sources(bundle, evidence_ids, []),
        retrieved_sources=(),
        evidence_breakdown=_breakdown(bundle, evidence_ids),
        shared_entity_links=links,
        warnings=tuple(bundle.warnings),
    )


def _legal_basis_section(bundle: CaseKnowledgeBundle):
    for section in bundle.artifact_sections:
        if section.source_id != "REPORT_LEGAL_BASIS":
            continue
        _heading, separator, body = section.text.partition("\n")
        if not separator:
            return None, None
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return None, None
        return section, payload if isinstance(payload, dict) else None
    return None, None


def _is_legal_basis_question(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in (
        "legal", "law", "statute", "statutory", "section", "provision",
        "regulation", "regulatory", "guideline", "manual review",
    ))


def _is_findings_summary_question(query: str) -> bool:
    """True for a broad case-finding summary, not a request about one exhibit."""
    lowered = query.lower()
    finding_terms = ("finding", "findings", "case summary", "summarize the case")
    summary_terms = ("summarize", "summary", "strongest", "key", "main", "important")
    return (
        any(term in lowered for term in finding_terms)
        and any(term in lowered for term in summary_terms)
    )


def _executive_summary_section(bundle: CaseKnowledgeBundle):
    """Read the canonical report summary already computed by the pipeline."""
    for section in bundle.artifact_sections:
        if section.source_id != "REPORT_EXECUTIVE_SUMMARY":
            continue
        _heading, separator, body = section.text.partition("\n")
        if not separator:
            return None, ()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return None, ()
        if not isinstance(payload, list):
            return None, ()
        findings = tuple(
            " ".join(str(item).split())
            for item in payload
            if str(item).strip()
        )
        return section, findings
    return None, ()


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
        direct_answer = answer_without_retrieval(bundle, query)
        if direct_answer is not None:
            return direct_answer
        if sync_before_query:
            self._indexing.sync(bundle)
        hits = self._retrieval.retrieve(bundle.case_id, query)
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

        if not requested_ids and _is_findings_summary_question(query):
            summary_section, findings = _executive_summary_section(bundle)
            if summary_section is not None and findings:
                selected_findings = findings[:5]
                answer = "Strongest stored findings:\n" + "\n".join(
                    f"{index}. {finding}"
                    for index, finding in enumerate(selected_findings, start=1)
                )
                answer += f"\n[{summary_section.source_id}]"
                supporting_ids = set(summary_section.evidence_ids)
                supporting_ids.update(
                    match.upper()
                    for match in re.findall(
                        r"\bEVID_[A-Z0-9_-]+\b",
                        " ".join(selected_findings),
                        re.IGNORECASE,
                    )
                )
                return AssistantResponse(
                    answer=answer,
                    insufficient_evidence=False,
                    cited_sources=_bundle_sources(
                        bundle, {summary_section.source_id}, hits
                    ),
                    retrieved_sources=_sources(hits),
                    evidence_breakdown=_breakdown(bundle, supporting_ids),
                    shared_entity_links=_shared_links(bundle, supporting_ids),
                    warnings=tuple(bundle.warnings),
                )

        extreme = _timeline_extreme(query)
        resolved_events = [item for item in bundle.timeline if item.timestamp]
        if extreme and resolved_events:
            ordered_events = sorted(
                resolved_events,
                key=lambda item: (_timestamp_key(item.timestamp), item.evidence_id),
            )
            event = ordered_events[0 if extreme == "first" else -1]
            source_id = _timeline_source_id(bundle, event.evidence_id)
            inference_label = "inferred" if event.inferred else "actual/non-inferred"
            answer = (
                f"The {extreme} resolved timeline event is {event.evidence_id} at "
                f"{event.timestamp}. Its timestamp is {inference_label}; "
                f"source={event.source}; confidence={event.confidence}. "
                f"[{source_id}]"
            )
            return AssistantResponse(
                answer=answer,
                insufficient_evidence=False,
                cited_sources=_bundle_sources(bundle, {source_id}, hits),
                retrieved_sources=_sources(hits),
                evidence_breakdown=_breakdown(bundle, {event.evidence_id}),
                shared_entity_links=(),
                warnings=tuple(bundle.warnings),
            )

        relationship_types = _requested_relationship_types(query)
        if relationship_types:
            matching: list[tuple[Relationship, tuple[str, ...]]] = []
            for relationship in bundle.relationships:
                shared = tuple(
                    value for value in relationship.shared_entities
                    if value.partition("=")[0].strip().lower() in relationship_types
                )
                if shared:
                    matching.append((relationship, shared))

            strongest_by_pair: dict[
                tuple[str, str], tuple[Relationship, tuple[str, ...]]
            ] = {}
            for relationship, shared in matching:
                pair = tuple(sorted((relationship.evidence_a, relationship.evidence_b)))
                previous = strongest_by_pair.get(pair)
                if previous is None or relationship.confidence > previous[0].confidence:
                    strongest_by_pair[pair] = (relationship, shared)
            strongest = sorted(
                strongest_by_pair.values(),
                key=lambda item: (
                    -item[0].confidence,
                    item[0].evidence_a,
                    item[0].evidence_b,
                ),
            )[:5]
            if strongest:
                evidence_ids = {
                    evidence_id
                    for relationship, _shared in strongest
                    for evidence_id in (
                        relationship.evidence_a, relationship.evidence_b,
                    )
                }
                statements = [
                    (
                        f"{relationship.evidence_a} and {relationship.evidence_b} "
                        f"share {', '.join(shared)} "
                        f"(confidence {relationship.confidence:.3f})."
                    )
                    for relationship, shared in strongest
                ]
                citations = " ".join(
                    f"[{evidence_id}]" for evidence_id in sorted(evidence_ids)
                )
                return AssistantResponse(
                    answer=" ".join(statements) + " " + citations,
                    insufficient_evidence=False,
                    cited_sources=_bundle_sources(bundle, evidence_ids, hits),
                    retrieved_sources=_sources(hits),
                    evidence_breakdown=_breakdown(bundle, evidence_ids),
                    shared_entity_links=tuple(
                        SharedEvidenceLink(
                            evidence_a=relationship.evidence_a,
                            evidence_b=relationship.evidence_b,
                            relationship_type=relationship.relationship_type,
                            confidence=relationship.confidence,
                            shared_entities=shared,
                        )
                        for relationship, shared in strongest
                    ),
                    warnings=tuple(bundle.warnings),
                )
            return AssistantResponse(
                answer=(
                    "No stored evidence relationship contains the requested "
                    "shared entity type."
                ),
                insufficient_evidence=True,
                cited_sources=(),
                retrieved_sources=_sources(hits),
                evidence_breakdown=(),
                shared_entity_links=(),
                warnings=tuple(bundle.warnings),
            )

        if _is_legal_basis_question(query):
            legal_section, legal = _legal_basis_section(bundle)
            if legal_section is not None and legal is not None:
                provisions = [
                    str(item.get("citation") or (
                        f"Section {item.get('section')}: {item.get('title')}"
                    ))
                    for item in legal.get("provisions") or []
                    if isinstance(item, dict)
                ]
                manual_review = [
                    str(item.get("citation") or (
                        f"Section {item.get('section')}: {item.get('title')}"
                    ))
                    for item in legal.get("manual_review_provisions") or []
                    if isinstance(item, dict)
                ]
                guidance = [
                    str(item.get("citation") or item.get("title"))
                    for item in legal.get("investigative_guidance") or []
                    if isinstance(item, dict)
                ]
                parts = [
                    "Mapped statutory provisions: "
                    + ("; ".join(provisions) if provisions else "none mapped"),
                ]
                if manual_review:
                    parts.append(
                        "Provisions reserved for manual review: "
                        + "; ".join(manual_review)
                    )
                if guidance:
                    parts.append(
                        "Investigative or regulatory guidance (not an offence "
                        "finding): " + "; ".join(guidance)
                    )
                caveat = str(legal.get("caveat") or "").strip()
                if caveat:
                    parts.append("Required caveat: " + caveat)

                source_ids = {legal_section.source_id}
                source_ids.update(
                    section.source_id for section in bundle.artifact_sections
                    if section.source_kind == "primary_legal_source"
                )
                citations = " ".join(
                    f"[{source_id}]" for source_id in sorted(source_ids)
                )
                supporting_ids = set(legal_section.evidence_ids)
                return AssistantResponse(
                    answer=" ".join(parts) + " " + citations,
                    insufficient_evidence=not provisions and not guidance,
                    cited_sources=_bundle_sources(bundle, source_ids, hits),
                    retrieved_sources=_sources(hits),
                    evidence_breakdown=_breakdown(bundle, supporting_ids),
                    shared_entity_links=(),
                    warnings=tuple(bundle.warnings),
                )

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
