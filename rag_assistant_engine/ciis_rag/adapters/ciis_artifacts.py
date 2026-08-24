"""Read current CIIE artifacts without coupling the RAG core to other engines."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping

from ..core.exceptions import ArtifactContractError
from ..core.models import (
    ArtifactSection,
    CaseKnowledgeBundle,
    EntityMention,
    EvidenceItem,
    Relationship,
    TimelineFact,
)


ARTIFACT_FILES = {
    "correlation": "correlation_analysis.json",
    "cross_case": "cross_case_correlation.json",
    "campaigns": "campaign_analysis.json",
    "suspects": "suspect_assessment.json",
    "timeline": "timeline_analysis.json",
    "graph": "graph.json",
    "graph_summary": "graph_summary.json",
    "graph_statistics": "graph_statistics.json",
    "analytics": "analytics.json",
    "priority": "case_priority.json",
    "report": "investigation_report.json",
    "analysis_manifest": "analysis_manifest.json",
}

_ARTIFACT_TITLES = {
    "correlation": "Evidence correlation analysis",
    "cross_case": "Cross-case correlation",
    "campaigns": "Campaign analysis",
    "suspects": "Suspect assessment",
    "analytics": "Investigation analytics",
    "priority": "Case priority assessment",
    "graph_summary": "Relationship graph summary",
    "graph_statistics": "Relationship graph statistics",
    "analysis_manifest": "Analysis provenance and configuration",
}


def _unwrap(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the report payload from a versioned artifact or a legacy object."""
    if not document:
        return {}
    report = document.get("report")
    return dict(report) if isinstance(report, Mapping) else dict(document)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactContractError(f"Cannot read JSON artifact '{path}': {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactContractError(f"Artifact '{path}' must contain a JSON object")
    return value


def _case_id(document: Mapping[str, Any]) -> str:
    payload = _unwrap(document)
    return str(payload.get("case_id") or document.get("case_id") or "")


def _validate_case(case_id: str, name: str, document: Mapping[str, Any]) -> None:
    artifact_case = _case_id(document)
    if artifact_case and artifact_case != case_id:
        raise ArtifactContractError(
            f"{name} belongs to {artifact_case}, not requested case {case_id}"
        )


def _entities(cleaning: Mapping[str, Any]) -> tuple[EntityMention, ...]:
    found: list[EntityMention] = []
    entity_groups = cleaning.get("entities") or {}
    if not isinstance(entity_groups, Mapping):
        return ()
    for entity_type, items in entity_groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, Mapping):
                value = str(item.get("value") or item.get("normalized") or "").strip()
                normalized = str(item.get("normalized") or value).strip()
            else:
                value = normalized = str(item).strip()
            if value:
                found.append(EntityMention(str(entity_type), value, normalized))
    unique = {(e.entity_type, e.normalized): e for e in found}
    return tuple(unique[key] for key in sorted(unique))


def _evidence(case_id: str, case_document: Mapping[str, Any]) -> tuple[EvidenceItem, ...]:
    result: list[EvidenceItem] = []
    rows = case_document.get("evidence") or []
    if not isinstance(rows, list):
        raise ArtifactContractError("case.evidence must be a list")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        cleaning = row.get("cleaning") if isinstance(row.get("cleaning"), Mapping) else {}
        risk = cleaning.get("risk_signals") or {}
        active_risk = tuple(sorted(
            str(name) for name, active in risk.items() if active
        )) if isinstance(risk, Mapping) else ()
        result.append(EvidenceItem(
            case_id=case_id,
            evidence_id=evidence_id,
            file_name=str(row.get("file_name") or row.get("original_file_name") or "unknown"),
            raw_text=str(row.get("raw_text") or ""),
            cleaned_text=str(cleaning.get("cleaned_text") or ""),
            upload_time=str(row.get("upload_time") or ""),
            file_hash=str(row.get("file_hash") or row.get("sha256_before") or ""),
            entities=_entities(cleaning),
            risk_signals=active_risk,
        ))
    return tuple(sorted(result, key=lambda item: item.evidence_id))


def _timeline(document: Mapping[str, Any]) -> tuple[TimelineFact, ...]:
    payload = _unwrap(document)
    events = payload.get("events") or payload.get("timeline") or []
    facts: dict[str, TimelineFact] = {}
    if not isinstance(events, list):
        return ()
    for event in events:
        if not isinstance(event, Mapping):
            continue
        evidence_id = str(event.get("evidence_id") or "").strip()
        if not evidence_id or evidence_id in facts:
            continue
        facts[evidence_id] = TimelineFact(
            evidence_id=evidence_id,
            timestamp=str(event.get("timestamp") or event.get("resolved_time") or ""),
            source=str(event.get("time_source") or event.get("timestamp_source") or "unresolved"),
            confidence=str(event.get("confidence") or "unknown"),
            inferred=bool(event.get("timestamp_inferred", event.get("inferred", False))),
        )
    return tuple(facts[key] for key in sorted(facts))


def _plausible_timeline(
    facts: tuple[TimelineFact, ...],
) -> tuple[tuple[TimelineFact, ...], tuple[str, ...]]:
    """Reject impossible dates before they become investigator-facing facts."""
    latest_year = datetime.now(timezone.utc).year + 1
    accepted: list[TimelineFact] = []
    rejected: list[str] = []
    for fact in facts:
        try:
            parsed = datetime.fromisoformat(fact.timestamp.replace("Z", "+00:00"))
        except ValueError:
            rejected.append(f"{fact.evidence_id}={fact.timestamp}")
            continue
        if parsed.year < 1970 or parsed.year > latest_year:
            rejected.append(f"{fact.evidence_id}={fact.timestamp}")
            continue
        accepted.append(fact)
    warnings = ()
    if rejected:
        warnings = (
            "Ignored implausible reconstructed timestamp(s): " + ", ".join(rejected),
        )
    return tuple(accepted), warnings


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _correlation_relationships(document: Mapping[str, Any]) -> list[Relationship]:
    payload = _unwrap(document)
    relationships: list[Relationship] = []
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, Mapping):
            continue
        strength = str(pair.get("relationship_strength") or "").upper()
        confidence = _confidence(pair.get("correlation_confidence"))
        if strength == "NO_RELATIONSHIP" or confidence <= 0:
            continue
        shared: list[str] = []
        for factor in pair.get("factors") or []:
            if not isinstance(factor, Mapping):
                continue
            factor_name = str(factor.get("factor") or "entity")
            for value in factor.get("supporting_evidence") or []:
                value_text = str(value).strip()
                if value_text:
                    shared.append(f"{factor_name}={value_text}")
        a = str(pair.get("evidence_a") or "")
        b = str(pair.get("evidence_b") or "")
        if a and b:
            relationships.append(Relationship(
                evidence_a=a,
                evidence_b=b,
                relationship_type="correlation",
                confidence=confidence,
                shared_entities=tuple(sorted(set(shared))),
                explanation=str(pair.get("explanation") or ""),
            ))
    return relationships


def _graph_relationships(document: Mapping[str, Any]) -> list[Relationship]:
    payload = _unwrap(document)
    relationships: list[Relationship] = []
    for edge in payload.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        edge_type = str(edge.get("edge_type") or edge.get("type") or "relationship")
        timestamp = str(edge.get("timestamp") or "")
        evidence_ids = [str(v) for v in edge.get("source_evidence_ids") or [] if v]

        # Legacy correlation graphs linked evidence directly and carried a
        # shared_entities array. Current graphs use prefixed node ids and carry
        # provenance in source_evidence_ids instead.
        if not evidence_ids:
            src = str(edge.get("source") or "").removeprefix("evidence:")
            tgt = str(edge.get("target") or "").removeprefix("evidence:")
            if src.startswith("EVID_") and tgt.startswith("EVID_"):
                evidence_ids = [src, tgt]

        shared: list[str] = []
        for entity in edge.get("shared_entities") or []:
            if isinstance(entity, Mapping):
                shared.append(
                    f"{entity.get('type', 'entity')}={entity.get('value', '')}"
                )
            elif entity:
                shared.append(str(entity))

        for a, b in combinations(sorted(set(evidence_ids)), 2):
            relationships.append(Relationship(
                evidence_a=a,
                evidence_b=b,
                relationship_type=edge_type,
                confidence=_confidence(edge.get("confidence", edge.get("weight", 0))),
                shared_entities=tuple(sorted(v for v in shared if not v.endswith("="))),
                explanation=str(edge.get("explanation") or ""),
                timestamp=timestamp,
            ))
    return relationships


def _deduplicate_relationships(items: list[Relationship]) -> tuple[Relationship, ...]:
    chosen: dict[tuple[str, str, str], Relationship] = {}
    for item in items:
        a, b = sorted((item.evidence_a, item.evidence_b))
        normalized = Relationship(
            evidence_a=a,
            evidence_b=b,
            relationship_type=item.relationship_type,
            confidence=item.confidence,
            shared_entities=item.shared_entities,
            explanation=item.explanation,
            timestamp=item.timestamp,
        )
        key = (a, b, normalized.relationship_type)
        previous = chosen.get(key)
        if previous is None or normalized.confidence > previous.confidence:
            chosen[key] = normalized
    return tuple(chosen[key] for key in sorted(chosen))


def _summary(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    graph_summary = _unwrap(artifacts.get("graph_summary"))
    graph_statistics = _unwrap(artifacts.get("graph_statistics"))
    correlation = _unwrap(artifacts.get("correlation"))
    return {
        "headline": graph_summary.get("headline", ""),
        "key_connectors": graph_summary.get("key_connectors", []),
        "observations": graph_summary.get("observations", []),
        "node_count": graph_statistics.get("node_count", 0),
        "edge_count": graph_statistics.get("edge_count", 0),
        "connected_components": graph_statistics.get("connected_components", 0),
        "related_pair_count": correlation.get("related_pair_count", 0),
        "strongest_pair": correlation.get("strongest_pair", ""),
    }


def _safe_id(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() else "_" for character in value.upper()
    )
    return "_".join(part for part in cleaned.split("_") if part) or "SECTION"


def _collect_evidence_ids(value: Any) -> tuple[str, ...]:
    """Collect provenance IDs carried anywhere inside an artifact section."""
    found: set[str] = set()

    def visit(item: Any, key: str = "") -> None:
        if isinstance(item, Mapping):
            for child_key, child in item.items():
                visit(child, str(child_key))
            return
        if isinstance(item, list):
            for child in item:
                visit(child, key)
            return
        if key in {
            "evidence_id", "evidence_a", "evidence_b", "source_evidence_ids",
            "evidence_ids", "supporting_evidence",
        }:
            text = str(item or "").strip()
            found.update(
                match.upper() for match in re.findall(
                    r"\bEVID_[A-Z0-9_-]+\b", text, re.IGNORECASE
                )
            )

    visit(value)
    return tuple(sorted(found))


def _section_text(title: str, value: Any) -> str:
    return (
        f"Section: {title}\n"
        + json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    )


def _artifact_sections(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[ArtifactSection, ...]:
    """Expose the complete investigator-facing findings without graph duplication."""
    sections: list[ArtifactSection] = []
    report = _unwrap(artifacts.get("report"))
    report_sections = report.get("sections") or {}
    if isinstance(report_sections, Mapping):
        for key, value in report_sections.items():
            if value in (None, "", [], {}):
                continue
            title = str(key).replace("_", " ").title()
            sections.append(ArtifactSection(
                source_id=f"REPORT_{_safe_id(str(key))}",
                source_kind="report_section",
                title=title,
                file_name=ARTIFACT_FILES["report"],
                text=_section_text(title, value),
                evidence_ids=_collect_evidence_ids(value),
            ))

        legal = report_sections.get("legal_basis") or {}
        if isinstance(legal, Mapping):
            for source in legal.get("sources") or []:
                if not isinstance(source, Mapping):
                    continue
                source_key = str(source.get("source_id") or source.get("title") or "legal")
                title = str(source.get("title") or "Primary legal source")
                sections.append(ArtifactSection(
                    source_id=f"SOURCE_{_safe_id(source_key)}",
                    source_kind="primary_legal_source",
                    title=title,
                    file_name=ARTIFACT_FILES["report"],
                    text=_section_text(title, source),
                    source_url=str(source.get("url") or ""),
                ))

    timeline = _unwrap(artifacts.get("timeline"))
    events = timeline.get("events") or timeline.get("timeline") or []
    if isinstance(events, list):
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                continue
            evidence_id = str(event.get("evidence_id") or "").strip()
            title = f"Timeline event for {evidence_id or index + 1}"
            sections.append(ArtifactSection(
                source_id=f"TIMELINE_{_safe_id(evidence_id or str(index + 1))}",
                source_kind="timeline_event",
                title=title,
                file_name=ARTIFACT_FILES["timeline"],
                text=_section_text(title, event),
                evidence_ids=_collect_evidence_ids(event),
            ))

    # These compact artifacts contain findings not guaranteed to appear in an
    # older generated report. The raw graph is intentionally excluded: its
    # typed relationships are already normalized onto evidence chunks.
    for key, title in _ARTIFACT_TITLES.items():
        payload = _unwrap(artifacts.get(key))
        if not payload:
            continue
        sections.append(ArtifactSection(
            source_id=f"ARTIFACT_{_safe_id(key)}",
            source_kind=f"{key}_artifact",
            title=title,
            file_name=ARTIFACT_FILES[key],
            text=_section_text(title, payload),
            evidence_ids=_collect_evidence_ids(payload),
        ))

    chosen: dict[str, ArtifactSection] = {}
    for section in sections:
        chosen.setdefault(section.source_id, section)
    return tuple(chosen[key] for key in sorted(chosen))


def _artifact_file_names(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Collect structured evidence/file associations from Phase-2 artifacts."""
    found: dict[str, set[str]] = {}
    timeline = _unwrap(artifacts.get("timeline"))
    for event in timeline.get("events") or timeline.get("timeline") or []:
        if not isinstance(event, Mapping):
            continue
        evidence_id = str(event.get("evidence_id") or "").strip()
        file_name = str(event.get("file_name") or "").strip()
        if evidence_id and file_name:
            found.setdefault(evidence_id, set()).add(file_name)

    graph = _unwrap(artifacts.get("graph"))
    for node in graph.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id") or "")
        if not node_id.startswith("evidence:"):
            continue
        properties = node.get("properties") or {}
        file_name = (
            str(properties.get("file_name") or "").strip()
            if isinstance(properties, Mapping) else ""
        )
        evidence_id = node_id.removeprefix("evidence:").strip()
        if evidence_id and file_name:
            found.setdefault(evidence_id, set()).add(file_name)
    return found


def _consistent_artifacts(
    evidence: tuple[EvidenceItem, ...],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Mapping[str, Any]], tuple[str, ...]]:
    """Fail closed when Phase-2 files refer to an older evidence generation."""
    current_names = {item.evidence_id: item.file_name for item in evidence}
    mismatches: list[str] = []
    for evidence_id, artifact_names in _artifact_file_names(artifacts).items():
        current_name = current_names.get(evidence_id)
        if current_name and artifact_names != {current_name}:
            mismatches.append(evidence_id)
    if mismatches:
        warning = (
            "Ignored stale Phase-2 artifacts because their evidence filenames do not "
            "match the current case records: " + ", ".join(sorted(set(mismatches)))
        )
        return {}, (warning,)

    current_ids = set(current_names)
    usable = dict(artifacts)
    warnings: list[str] = []

    # A lightweight upload refresh deliberately rebuilds correlation/timeline/
    # graph but not campaigns, priority or the report. Use the analysis
    # manifest to withhold those older high-level findings until full analysis
    # runs again, while keeping the newly uploaded evidence searchable now.
    manifest = _unwrap(artifacts.get("analysis_manifest"))
    manifest_ids = {
        str(item) for item in (manifest.get("evidence_ids") or []) if item
    }
    if manifest_ids and manifest_ids != current_ids:
        stale_full_analysis = {
            "analysis_manifest", "cross_case", "campaigns", "suspects",
            "analytics", "priority", "report",
        }
        for key in stale_full_analysis:
            usable.pop(key, None)
        warnings.append(
            "Ignored stale full-analysis artifacts because they predate the "
            "current evidence set; run case analysis to refresh them."
        )

    report = _unwrap(usable.get("report"))
    report_sections = report.get("sections") or {}
    evidence_summary = (
        report_sections.get("evidence_summary")
        if isinstance(report_sections, Mapping) else None
    )
    report_ids = {
        str(row.get("evidence_id"))
        for row in (evidence_summary or [])
        if isinstance(row, Mapping) and row.get("evidence_id")
    }
    if report_ids and report_ids != current_ids:
        usable.pop("report", None)
        warnings.append(
            "Ignored a stale investigation report because it does not cover the "
            "current evidence set; run case analysis to refresh it."
        )
    return usable, tuple(warnings)


def bundle_from_documents(
    case_document: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    source_hashes: Mapping[str, str] | None = None,
) -> CaseKnowledgeBundle:
    """Normalize current or legacy CIIE documents into one stable bundle."""
    artifacts = artifacts or {}
    case_id = str(case_document.get("case_id") or "").strip()
    if not case_id:
        raise ArtifactContractError("Case document is missing case_id")
    for name, artifact in artifacts.items():
        if artifact:
            _validate_case(case_id, name, artifact)
    evidence = _evidence(case_id, case_document)
    usable_artifacts, warnings = _consistent_artifacts(evidence, artifacts)
    timeline, timeline_warnings = _plausible_timeline(
        _timeline(usable_artifacts.get("timeline", {}))
    )
    relationships = _correlation_relationships(usable_artifacts.get("correlation", {}))
    relationships.extend(_graph_relationships(usable_artifacts.get("graph", {})))
    known_evidence_ids = {item.evidence_id for item in evidence}
    relationships = [
        relationship for relationship in relationships
        if relationship.evidence_a in known_evidence_ids
        and relationship.evidence_b in known_evidence_ids
        and relationship.evidence_a != relationship.evidence_b
    ]
    return CaseKnowledgeBundle(
        case_id=case_id,
        evidence=evidence,
        timeline=timeline,
        relationships=_deduplicate_relationships(relationships),
        artifact_sections=_artifact_sections(usable_artifacts),
        summary=_summary(usable_artifacts),
        source_hashes=dict(source_hashes or {}),
        warnings=warnings + timeline_warnings,
    )


def load_case_bundle(case_json: str | Path, artifact_dir: str | Path) -> CaseKnowledgeBundle:
    """Load a case JSON and whichever current Phase-2 artifacts are present."""
    case_path = Path(case_json).resolve()
    artifact_root = Path(artifact_dir).resolve()
    case_document = _load_json(case_path)
    artifacts: dict[str, dict[str, Any]] = {}
    hashes = {"case_json": _sha256(case_path)}
    for key, filename in ARTIFACT_FILES.items():
        path = artifact_root / filename
        if path.is_file():
            artifacts[key] = _load_json(path)
            hashes[key] = _sha256(path)
    return bundle_from_documents(case_document, artifacts, source_hashes=hashes)
