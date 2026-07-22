"""Module 2 tests - Evidence Relationship Graph Engine."""

from __future__ import annotations

import pytest

from backend.modules.investigation.correlation.service import CorrelationService
from backend.modules.investigation.correlation.models import (
    CrossCaseCorrelation,
    CrossCaseEntityMatch,
    CrossCaseLink,
)
from backend.modules.investigation.graph.service import GraphService
from backend.modules.investigation.timeline.service import TimelineService

from .conftest import CASE


@pytest.fixture()
def graph_and_stats(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False)
    service = GraphService(icfg, data, repo, audit)
    timeline = TimelineService(icfg, data, repo, audit).analyze(
        CASE, correlation=correlation, persist=False
    )
    graph = service.build(CASE, correlation, timeline=timeline)
    return graph, repo, icfg


def test_node_and_edge_types(graph_and_stats):
    graph, _, _ = graph_and_stats
    node_types = {n.node_type for n in graph.nodes}
    assert {"case", "evidence", "phone_number", "wallet", "url", "domain",
            "email", "brand", "device", "timeline_event"} <= node_types
    edge_types = {e.edge_type for e in graph.edges}
    assert {"contains", "shared_entity", "temporal_relationship",
            "threat_relationship", "metadata_relationship",
            "behavioral_relationship", "timeline_event"} <= edge_types


def test_shared_entity_nodes_are_deduplicated(graph_and_stats):
    graph, _, _ = graph_and_stats
    phone_nodes = [n for n in graph.nodes if n.node_type == "phone_number"]
    assert len(phone_nodes) == 1  # 9812345678 appears in A and B -> one node
    mentions = [e for e in graph.edges
                if e.target == phone_nodes[0].id and e.edge_type == "shared_entity"]
    assert len(mentions) == 2


def test_every_edge_is_explained(graph_and_stats):
    graph, _, _ = graph_and_stats
    assert all(e.explanation for e in graph.edges)


def test_every_edge_has_provenance_confidence_and_timestamp_contract(graph_and_stats):
    graph, _, _ = graph_and_stats
    assert all(0.0 <= edge.confidence <= 1.0 for edge in graph.edges)
    assert all(isinstance(edge.source_evidence_ids, list) for edge in graph.edges)
    assert all(edge.timestamp_source for edge in graph.edges)
    signatures = [(edge.source, edge.target, edge.edge_type) for edge in graph.edges]
    assert len(signatures) == len(set(signatures))


def test_matching_entity_connects_evidence_across_cases(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False
    )
    timeline = TimelineService(icfg, data, repo, audit).analyze(
        CASE, correlation=correlation, persist=False
    )
    cross_case = CrossCaseCorrelation(
        case_id=CASE,
        related_case_ids=["CASE_OTHER"],
        link_count=1,
        links=[CrossCaseLink(
            other_case_id="CASE_OTHER",
            match_confidence=0.9,
            relationship_strength="STRONG",
            this_evidence_ids=["EVID_A"],
            other_evidence_ids=["EVID_OTHER"],
            match_reason="shared phone",
            matched_entities=[CrossCaseEntityMatch(
                entity_type="phones",
                value="9812345678",
                weight=1.0,
                this_evidence_ids=["EVID_A"],
                other_evidence_ids=["EVID_OTHER"],
            )],
        )],
    )
    graph = GraphService(icfg, data, repo, audit).build(
        CASE,
        correlation,
        timeline=timeline,
        cross_case=cross_case,
        persist=False,
    )
    assert any(node.id == "case:CASE_OTHER" for node in graph.nodes)
    assert any(node.id == "evidence:EVID_OTHER" for node in graph.nodes)
    cross_edges = [
        edge for edge in graph.edges
        if edge.edge_type == "cross_case_entity_match"
    ]
    assert len(cross_edges) == 1
    assert cross_edges[0].target == "phone_number:9812345678"
    assert set(cross_edges[0].source_evidence_ids) == {"EVID_A", "EVID_OTHER"}


def test_three_artifacts_persisted(graph_and_stats):
    _, repo, icfg = graph_and_stats
    stats = repo.load_latest(CASE, icfg.graph_statistics_name)
    summary = repo.load_latest(CASE, icfg.graph_summary_name)
    graph_doc = repo.load_latest(CASE, icfg.graph_report_name)
    assert graph_doc and stats and summary
    report = stats["report"]
    assert report["node_count"] == len(graph_doc["report"]["nodes"])
    assert report["connected_components"] >= 1
    assert report["top_hubs"]
    assert summary["report"]["headline"]
