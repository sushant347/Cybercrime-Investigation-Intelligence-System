"""Module 2 - Evidence Relationship Graph Engine.

Converts case data + Module-1 correlations into a typed, structured graph:

* structural edges   case --contains--> evidence
* shared_entity      evidence --mentions--> entity node (phone/url/wallet/...)
* temporal           evidence <-> evidence acquired within the proximity window
* threat             entity node flagged by threat intelligence
* metadata           evidence <-> evidence sharing device/software metadata
* behavioral         evidence <-> evidence with strong Module-1 correlation

Outputs three artefacts (graph.json, graph_statistics.json,
graph_summary.json). Strictly visualization-independent: pure data for the
future dashboard phase. Pure-Python graph algorithms (no networkx needed).
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence, Set

from ...evidence.logger import get_logger
from ..audit import InvestigationAuditTrail
from ..config import InvestigationConfig
from ..correlation.models import CorrelationAnalysis
from ..data_access import CaseDataRepository, EvidenceContext
from ..repository import InvestigationReportRepository
from .models import (
    GraphEdge,
    GraphNode,
    GraphStatistics,
    GraphSummary,
    RelationshipGraph,
)

MODULE = "graph"


class GraphService:
    """Builds the typed evidence relationship graph for one case."""

    def __init__(
        self,
        config: InvestigationConfig,
        data: CaseDataRepository,
        repository: InvestigationReportRepository,
        audit: InvestigationAuditTrail,
    ) -> None:
        self._cfg = config
        self._data = data
        self._repo = repository
        self._audit = audit
        self._log = get_logger("investigation.graph")

    # ------------------------------------------------------------------ public

    def build(
        self,
        case_id: str,
        correlation: Optional[CorrelationAnalysis] = None,
        evidence: Optional[Sequence[EvidenceContext]] = None,
        *,
        persist: bool = True,
    ) -> RelationshipGraph:
        started = time.perf_counter()
        items = list(evidence) if evidence is not None \
            else self._data.load_case_evidence(case_id)

        nodes: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []

        self._add_node(nodes, f"case:{case_id}", "case", case_id)
        for context in items:
            evidence_node = f"evidence:{context.evidence_id}"
            self._add_node(nodes, evidence_node, "evidence", context.evidence_id,
                           {"file_name": context.file_name,
                            "upload_time": context.upload_time})
            edges.append(GraphEdge(
                source=f"case:{case_id}", target=evidence_node,
                edge_type="contains",
                explanation=f"{context.evidence_id} belongs to {case_id}",
            ))
            self._entity_edges(nodes, edges, context, evidence_node)
            self._brand_edges(nodes, edges, context, evidence_node)
            self._device_edges(nodes, edges, context, evidence_node)

        self._temporal_edges(edges, items)
        self._metadata_edges(edges, items)
        if correlation is not None:
            self._behavioral_edges(edges, correlation)

        graph = RelationshipGraph(case_id=case_id, nodes=list(nodes.values()),
                                  edges=edges)
        statistics = self._statistics(graph)
        summary = self._summary(graph, statistics)
        duration = round((time.perf_counter() - started) * 1000.0, 1)

        if persist:
            self._repo.save(case_id, self._cfg.graph_report_name, graph.model_dump())
            self._repo.save(case_id, self._cfg.graph_statistics_name,
                            statistics.model_dump())
            self._repo.save(case_id, self._cfg.graph_summary_name, summary.model_dump())
            self._audit.record(
                case_id, MODULE, "built",
                f"{statistics.node_count} nodes, {statistics.edge_count} edges, "
                f"{statistics.connected_components} component(s)",
                duration_ms=duration,
            )
        return graph

    # ------------------------------------------------------------ edge builders

    def _entity_edges(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge],
                      context: EvidenceContext, evidence_node: str) -> None:
        intel = self._data.threat_intel
        for entity_type, node_type in self._cfg.graph_entity_node_types.items():
            for value in sorted(set(context.entity_values(entity_type))):
                node_id = f"{node_type}:{value.lower()}"
                self._add_node(nodes, node_id, node_type, value)
                edges.append(GraphEdge(
                    source=evidence_node, target=node_id,
                    edge_type="shared_entity",
                    explanation=f"{context.evidence_id} mentions {value}",
                ))
                if intel.available and intel.is_malicious(value):
                    hit = intel.lookup(value) or {}
                    edges.append(GraphEdge(
                        source=node_id, target=evidence_node,
                        edge_type="threat_relationship",
                        weight=2.0,
                        explanation=(
                            f"{value} is flagged "
                            f"{hit.get('verdict', 'malicious')} by threat "
                            f"intelligence ({hit.get('source', 'indicator file')})"
                        ),
                    ))

    def _brand_edges(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge],
                     context: EvidenceContext, evidence_node: str) -> None:
        logos = context.forensics.get("logo_detections", {})
        for brand in logos.get("detected_brands", []):
            node_id = f"brand:{str(brand).lower()}"
            self._add_node(nodes, node_id, "brand", str(brand))
            edges.append(GraphEdge(
                source=evidence_node, target=node_id,
                edge_type="shared_entity",
                explanation=f"Brand '{brand}' detected inside "
                            f"{context.evidence_id} (Phase-1 logo detection)",
            ))

    def _device_edges(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge],
                      context: EvidenceContext, evidence_node: str) -> None:
        image = (context.forensics.get("metadata_report", {}) or {}).get("image") or {}
        device = str(image.get("device", "") or "").strip()
        if not device:
            return
        node_id = f"device:{device.lower()}"
        self._add_node(nodes, node_id, "device", device)
        edges.append(GraphEdge(
            source=evidence_node, target=node_id,
            edge_type="metadata_relationship",
            explanation=f"EXIF metadata of {context.evidence_id} names device "
                        f"'{device}'",
        ))

    def _temporal_edges(self, edges: List[GraphEdge],
                        items: Sequence[EvidenceContext]) -> None:
        window = self._cfg.timeline_proximity_hours
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                ta, tb = a.upload_datetime, b.upload_datetime
                if ta is None or tb is None:
                    continue
                hours = abs((ta - tb).total_seconds()) / 3600.0
                if hours <= window:
                    edges.append(GraphEdge(
                        source=f"evidence:{a.evidence_id}",
                        target=f"evidence:{b.evidence_id}",
                        edge_type="temporal_relationship",
                        weight=round(1.0 - hours / max(window, 1e-6), 4),
                        explanation=f"Acquired {hours:.1f}h apart "
                                    f"(window {window:.0f}h)",
                    ))

    def _metadata_edges(self, edges: List[GraphEdge],
                        items: Sequence[EvidenceContext]) -> None:
        def device_of(c: EvidenceContext) -> str:
            image = (c.forensics.get("metadata_report", {}) or {}).get("image") or {}
            return str(image.get("device", "") or "").strip().lower()

        for i, a in enumerate(items):
            for b in items[i + 1:]:
                device = device_of(a)
                if device and device == device_of(b):
                    edges.append(GraphEdge(
                        source=f"evidence:{a.evidence_id}",
                        target=f"evidence:{b.evidence_id}",
                        edge_type="metadata_relationship",
                        weight=1.5,
                        explanation=f"Same source device '{device}' in EXIF "
                                    "metadata of both items",
                    ))

    def _behavioral_edges(self, edges: List[GraphEdge],
                          correlation: CorrelationAnalysis) -> None:
        threshold = self._cfg.graph_behavioral_min_confidence
        for pair in correlation.pairs:
            if pair.correlation_confidence < threshold:
                continue
            edges.append(GraphEdge(
                source=f"evidence:{pair.evidence_a}",
                target=f"evidence:{pair.evidence_b}",
                edge_type="behavioral_relationship",
                weight=round(pair.correlation_confidence, 4),
                explanation=(
                    f"Module-1 correlation: {pair.relationship_strength} "
                    f"(confidence {pair.correlation_confidence:.2f}) - "
                    + "; ".join(pair.correlation_reasons[:2])
                ),
            ))

    # ------------------------------------------------------------- statistics

    def _statistics(self, graph: RelationshipGraph) -> GraphStatistics:
        nodes_by_type: Dict[str, int] = {}
        for node in graph.nodes:
            nodes_by_type[node.node_type] = nodes_by_type.get(node.node_type, 0) + 1
        edges_by_type: Dict[str, int] = {}
        degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        adjacency: Dict[str, Set[str]] = {node.id: set() for node in graph.nodes}
        for edge in graph.edges:
            edges_by_type[edge.edge_type] = edges_by_type.get(edge.edge_type, 0) + 1
            if edge.source in degree:
                degree[edge.source] += 1
            if edge.target in degree:
                degree[edge.target] += 1
            if edge.source in adjacency and edge.target in adjacency:
                adjacency[edge.source].add(edge.target)
                adjacency[edge.target].add(edge.source)

        components, largest = self._components(adjacency)
        n, e = len(graph.nodes), len(graph.edges)
        top = sorted(degree.items(), key=lambda kv: kv[1], reverse=True)
        top_hubs = [{"node": node_id, "degree": str(d)}
                    for node_id, d in top[: self._cfg.graph_top_hubs] if d > 0]
        return GraphStatistics(
            case_id=graph.case_id,
            node_count=n,
            edge_count=e,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            density=round(2.0 * e / (n * (n - 1)), 4) if n > 1 else 0.0,
            connected_components=components,
            largest_component_size=largest,
            average_degree=round(sum(degree.values()) / n, 3) if n else 0.0,
            top_hubs=top_hubs,
        )

    @staticmethod
    def _components(adjacency: Dict[str, Set[str]]) -> tuple[int, int]:
        seen: Set[str] = set()
        count, largest = 0, 0
        for start in adjacency:
            if start in seen:
                continue
            count += 1
            stack, size = [start], 0
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                size += 1
                stack.extend(adjacency[node] - seen)
            largest = max(largest, size)
        return count, largest

    def _summary(self, graph: RelationshipGraph,
                 statistics: GraphStatistics) -> GraphSummary:
        connectors = [
            hub["node"] for hub in statistics.top_hubs
            if not hub["node"].startswith(("case:", "evidence:"))
        ][:5]
        observations: List[str] = []
        threat_edges = statistics.edges_by_type.get("threat_relationship", 0)
        if threat_edges:
            observations.append(
                f"{threat_edges} threat-intelligence edge(s) link flagged "
                "indicators to evidence."
            )
        behavioral = statistics.edges_by_type.get("behavioral_relationship", 0)
        if behavioral:
            observations.append(
                f"{behavioral} strong behavioural link(s) derived from the "
                "weighted correlation engine."
            )
        if statistics.connected_components == 1 and statistics.node_count > 1:
            observations.append(
                "All entities and evidence form a single connected component - "
                "consistent with one coordinated activity."
            )
        return GraphSummary(
            case_id=graph.case_id,
            headline=(
                f"{statistics.node_count} nodes and {statistics.edge_count} "
                f"edges across {statistics.connected_components} component(s)"
            ),
            key_connectors=connectors,
            observations=observations,
        )

    @staticmethod
    def _add_node(nodes: Dict[str, GraphNode], node_id: str, node_type: str,
                  label: str, properties: Optional[Dict[str, str]] = None) -> None:
        if node_id not in nodes:
            nodes[node_id] = GraphNode(
                id=node_id, node_type=node_type, label=label,
                properties=properties or {},
            )
