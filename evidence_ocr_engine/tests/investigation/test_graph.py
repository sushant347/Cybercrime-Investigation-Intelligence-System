"""Module 2 tests - Evidence Relationship Graph Engine."""

from __future__ import annotations

import pytest

from backend.modules.investigation.correlation.service import CorrelationService
from backend.modules.investigation.graph.service import GraphService

from .conftest import CASE


@pytest.fixture()
def graph_and_stats(icfg, data, repo, audit):
    correlation = CorrelationService(icfg, data, repo, audit).analyze_case(
        CASE, persist=False)
    service = GraphService(icfg, data, repo, audit)
    graph = service.build(CASE, correlation)
    return graph, repo, icfg


def test_node_and_edge_types(graph_and_stats):
    graph, _, _ = graph_and_stats
    node_types = {n.node_type for n in graph.nodes}
    assert {"case", "evidence", "phone_number", "wallet", "url", "domain",
            "email", "brand", "device"} <= node_types
    edge_types = {e.edge_type for e in graph.edges}
    assert {"contains", "shared_entity", "temporal_relationship",
            "threat_relationship", "metadata_relationship",
            "behavioral_relationship"} <= edge_types


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
