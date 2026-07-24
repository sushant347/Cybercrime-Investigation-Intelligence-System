"""Unit tests for the NetworkX investigation GraphBuilder (Module 4 enhancement).

Run from the engine root:
    python -m pytest evidence_correlation_engine/tests/test_graph_builder.py -v
or without pytest:
    python evidence_correlation_engine/tests/test_graph_builder.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest

# Make the engine package importable regardless of CWD.
ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_ROOT not in sys.path:
    sys.path.insert(0, ENGINE_ROOT)

from graph_builder import EntityNormalizer, GraphBuildError, GraphBuilder  # noqa: E402


def _evidence(evidence_id: str, entities: dict, upload_time: str = "2026-06-15T09:00:00Z") -> dict:
    return {
        "case_id": "CASE_T",
        "evidence_id": evidence_id,
        "file_name": f"{evidence_id}.jpg",
        "upload_time": upload_time,
        "average_confidence": 0.95,
        "cleaning": {"entities": entities},
    }


def _case(*evidence: dict) -> dict:
    return {"case_id": "CASE_T", "evidence": list(evidence)}


class NodeCreationTests(unittest.TestCase):
    def test_add_node_returns_deterministic_id(self):
        b = GraphBuilder("CASE_T")
        n1 = b.add_node("phone", "9841122334", evidence_id="E1")
        n2 = b.add_node("phone", "9841122334", evidence_id="E2")
        self.assertEqual(n1, n2)
        self.assertEqual(b.graph.number_of_nodes(), 1)
        self.assertEqual(b.graph.nodes[n1]["evidence_ids"], {"E1", "E2"})

    def test_empty_value_raises(self):
        b = GraphBuilder("CASE_T")
        with self.assertRaises(GraphBuildError):
            b.add_node("phone", "   ")

    def test_node_types_from_entities(self):
        b = GraphBuilder("CASE_T")
        b.build_graph([_case(_evidence("E1", {
            "emails": [{"value": "a@x.com", "normalized": "a@x.com"}],
            "urls": [{"value": "http://Phish.io/login"}],
            "esewa_ids": [{"value": "rajesh.thapa99"}],
        }))])
        types = {d["node_type"] for _, d in b.graph.nodes(data=True)}
        self.assertEqual(types, {"evidence", "email", "url", "wallet"})


class EdgeCreationTests(unittest.TestCase):
    def test_evidence_contains_entity_edge(self):
        b = GraphBuilder("CASE_T")
        b.build_graph([_case(_evidence("E1", {
            "phones": [{"value": "9841122334"}],
        }))])
        rels = {d["relation"] for _, _, d in b.graph.edges(data=True)}
        self.assertIn("communicates_with", rels)  # phone -> communicates_with

    def test_add_edge_missing_endpoint_raises(self):
        b = GraphBuilder("CASE_T")
        b.add_node("phone", "9841122334")
        with self.assertRaises(GraphBuildError):
            b.add_edge("phone:9841122334", "email:missing", "linked_to")

    def test_multidigraph_allows_parallel_relations(self):
        b = GraphBuilder("CASE_T")
        a = b.add_node("evidence", "E1")
        c = b.add_node("evidence", "E2")
        b.add_edge(a, c, "temporal_relation")
        b.add_edge(a, c, "references")
        self.assertEqual(b.graph.number_of_edges(a, c), 2)


class DuplicateMergingTests(unittest.TestCase):
    def test_same_entity_across_evidence_is_one_node(self):
        b = GraphBuilder("CASE_T")
        b.build_graph([_case(
            _evidence("E1", {"emails": [{"value": "support@gmail.com"}]}),
            _evidence("E4", {"emails": [{"value": "SUPPORT@gmail.com"}]}),
            _evidence("E9", {"emails": [{"value": "support@gmail.com "}]}),
        )])
        email_nodes = [n for n, d in b.graph.nodes(data=True) if d["node_type"] == "email"]
        self.assertEqual(len(email_nodes), 1)
        self.assertEqual(b.graph.nodes[email_nodes[0]]["evidence_ids"], {"E1", "E4", "E9"})

    def test_url_normalization_collapses_variants(self):
        norm = EntityNormalizer()
        forms = ["HTTP://Example.com", "https://example.com/", "www.example.com", "example.com"]
        canon = {norm.normalize("url", f) for f in forms}
        self.assertEqual(canon, {"example.com"})

    def test_merge_duplicate_entities_noop_after_build(self):
        b = GraphBuilder("CASE_T")
        b.build_graph([_case(_evidence("E1", {"emails": [{"value": "a@x.com"}]}))])
        self.assertEqual(b.merge_duplicate_entities(), 0)


class AnalyticsTests(unittest.TestCase):
    def _shared_graph(self) -> GraphBuilder:
        # E1 and E2 share a wallet -> connected via that entity node.
        b = GraphBuilder("CASE_T")
        # E1 and E2 are 48h apart -> no temporal edge, so the ONLY link between
        # them is the shared wallet entity node. E3 is unrelated.
        b.build_graph([_case(
            _evidence("E1", {"esewa_ids": [{"value": "wallet1"}]}, "2026-06-15T09:00:00Z"),
            _evidence("E2", {"esewa_ids": [{"value": "wallet1"}]}, "2026-06-17T09:00:00Z"),
            _evidence("E3", {"phones": [{"value": "9800000000"}]}, "2026-06-25T09:00:00Z"),
        )])
        return b

    def test_connected_components(self):
        b = self._shared_graph()
        comps = b.connected_components()
        # E1+E2+wallet in one cluster; E3+phone in another.
        self.assertGreaterEqual(len(comps), 2)
        self.assertEqual(len(comps[0]), 3)

    def test_shortest_path_through_shared_entity(self):
        b = self._shared_graph()
        path = b.find_shortest_path("evidence:E1", "evidence:E2")
        self.assertEqual(path[0], "evidence:E1")
        self.assertEqual(path[-1], "evidence:E2")
        self.assertIn("wallet:wallet1", path)

    def test_centralities_return_scores_for_all_nodes(self):
        b = self._shared_graph()
        for fn in (b.degree_centrality, b.betweenness_centrality, b.closeness_centrality):
            scores = fn()
            self.assertEqual(set(scores), set(b.graph.nodes))

    def test_community_detection_returns_partitions(self):
        b = self._shared_graph()
        communities = b.community_detection()
        self.assertTrue(all(isinstance(c, list) for c in communities))
        flat = [n for c in communities for n in c]
        self.assertEqual(sorted(flat), sorted(b.graph.nodes))

    def test_isolated_nodes_detected(self):
        b = GraphBuilder("CASE_T")
        b.add_node("phone", "9841122334")  # added directly, no edges
        self.assertIn("phone:9841122334", b.find_isolated_nodes())


class SerializationTests(unittest.TestCase):
    def test_serialize_matches_frontend_contract(self):
        b = GraphBuilder("CASE_T")
        b.build_graph([_case(_evidence("E1", {
            "emails": [{"value": "a@x.com"}],
            "phones": [{"value": "9841122334"}],
        }))])
        out = b.serialize_graph()
        self.assertEqual(set(out), {"graph", "graph_statistics", "graph_summary"})

        graph = out["graph"]
        self.assertEqual(set(graph), {"case_id", "directed", "nodes", "edges"})
        for node in graph["nodes"]:
            self.assertEqual(set(node), {"id", "node_type", "label", "properties"})
            self.assertIsInstance(node["properties"], dict)
            self.assertTrue(all(isinstance(v, str) for v in node["properties"].values()))
        for edge in graph["edges"]:
            self.assertEqual(set(edge), {"source", "target", "edge_type", "weight", "explanation"})

        stats = out["graph_statistics"]
        for k in ("node_count", "edge_count", "nodes_by_type", "edges_by_type",
                  "density", "connected_components", "largest_component_size",
                  "average_degree", "top_hubs"):
            self.assertIn(k, stats)

        summary = out["graph_summary"]
        self.assertEqual(set(summary), {"case_id", "headline", "key_connectors", "observations"})

        # Must be JSON-serializable end to end.
        json.dumps(out)

    def test_rebuild_is_skipped_when_signature_unchanged(self):
        b = GraphBuilder("CASE_T")
        cases = [_case(_evidence("E1", {"phones": [{"value": "9841122334"}]}))]
        g1 = b.build_graph(cases)
        g2 = b.build_graph(cases)
        self.assertIs(g1, g2)  # cache hit -> same object, no rebuild


if __name__ == "__main__":
    unittest.main(verbosity=2)
