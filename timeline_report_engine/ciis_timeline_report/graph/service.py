"""Module 2 - Evidence Relationship Graph Engine.

Converts case data + Module-1 correlations into a typed, structured graph:

* structural edges   case --contains--> evidence
* shared_entity      evidence --mentions--> entity node (phone/url/wallet/...)
* temporal           evidence <-> evidence occurring within the proximity window
* threat             entity node flagged by threat intelligence
* metadata           evidence <-> evidence sharing device/software metadata
* behavioral         evidence <-> evidence with strong Module-1 correlation

Outputs three artefacts (graph.json, graph_statistics.json,
graph_summary.json). Strictly visualization-independent: pure data enriched
with NetworkX centrality, community, bridge, and graph-backbone analytics.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import networkx as nx

from backend.modules.evidence.logger import get_logger
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.correlation.models import CorrelationAnalysis, CrossCaseCorrelation
from ciis_correlation.core.data_access import CaseDataRepository, EvidenceContext
from ciis_correlation.core.repository import InvestigationReportRepository
from ciis_correlation.core.text import count_of
from ..timeline.models import TimelineAnalysis
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
        timeline: Optional[TimelineAnalysis] = None,
        cross_case: Optional[CrossCaseCorrelation] = None,
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

        self._timeline_event_edges(nodes, edges, timeline)
        self._cross_case_edges(nodes, edges, case_id, cross_case)
        self._temporal_edges(edges, items, timeline)
        self._metadata_edges(edges, items)
        if correlation is not None:
            self._behavioral_edges(edges, correlation)

        edges = self._finalize_edges(edges, timeline)
        graph = RelationshipGraph(case_id=case_id, nodes=list(nodes.values()),
                                  edges=edges)
        nx_metrics = self._enrich_with_networkx(graph)
        statistics = self._statistics(graph, nx_metrics)
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
                f"{count_of(statistics.connected_components, 'component')}",
                duration_ms=duration,
            )
        return graph

    # ------------------------------------------------------------ edge builders

    def _entity_edges(self, nodes: Dict[str, GraphNode], edges: List[GraphEdge],
                      context: EvidenceContext, evidence_node: str) -> None:
        intel = self._data.threat_intel
        entity_types = sorted({entity.entity_type for entity in context.entities})
        for entity_type in entity_types:
            node_type = self._cfg.graph_entity_node_types.get(
                entity_type, self._fallback_node_type(entity_type)
            )
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

    def _timeline_event_edges(
        self,
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        timeline: Optional[TimelineAnalysis],
    ) -> None:
        if timeline is None:
            return
        for event in timeline.events:
            event_node = f"timeline_event:{event.case_id or timeline.case_id}:{event.evidence_id}"
            self._add_node(
                nodes,
                event_node,
                "timeline_event",
                event.description or event.evidence_id,
                {
                    "timestamp": event.timestamp,
                    "time_source": event.time_source,
                    "timestamp_inferred": str(event.timestamp_inferred).lower(),
                },
            )
            edges.append(GraphEdge(
                source=f"evidence:{event.evidence_id}",
                target=event_node,
                edge_type="timeline_event",
                confidence=self._confidence_number(event.confidence),
                source_evidence_ids=event.source_evidence_ids or [event.evidence_id],
                timestamp=event.timestamp,
                timestamp_source=event.time_source,
                timestamp_inferred=event.timestamp_inferred,
                explanation=f"Reconstructed event for {event.evidence_id}",
            ))

    def _cross_case_edges(
        self,
        nodes: Dict[str, GraphNode],
        edges: List[GraphEdge],
        case_id: str,
        cross_case: Optional[CrossCaseCorrelation],
    ) -> None:
        if cross_case is None:
            return
        for link in cross_case.links:
            other_case_node = f"case:{link.other_case_id}"
            self._add_node(nodes, other_case_node, "case", link.other_case_id)
            edges.append(GraphEdge(
                source=f"case:{case_id}", target=other_case_node,
                edge_type="cross_case_relationship",
                confidence=link.match_confidence,
                source_evidence_ids=sorted(set(
                    link.this_evidence_ids + link.other_evidence_ids
                )),
                explanation=link.match_reason,
            ))
            for match in link.matched_entities:
                node_type = self._cfg.graph_entity_node_types.get(
                    match.entity_type, self._fallback_node_type(match.entity_type)
                )
                entity_node = f"{node_type}:{match.value.lower()}"
                self._add_node(nodes, entity_node, node_type, match.value)
                for other_evidence_id in match.other_evidence_ids:
                    other_evidence_node = f"evidence:{other_evidence_id}"
                    self._add_node(
                        nodes, other_evidence_node, "evidence", other_evidence_id,
                        {"case_id": link.other_case_id},
                    )
                    edges.append(GraphEdge(
                        source=other_case_node,
                        target=other_evidence_node,
                        edge_type="contains",
                        confidence=link.match_confidence,
                        source_evidence_ids=[other_evidence_id],
                        explanation=(
                            f"{other_evidence_id} belongs to {link.other_case_id}"
                        ),
                    ))
                    edges.append(GraphEdge(
                        source=other_evidence_node,
                        target=entity_node,
                        edge_type="cross_case_entity_match",
                        confidence=link.match_confidence,
                        source_evidence_ids=sorted(set(
                            match.this_evidence_ids + match.other_evidence_ids
                        )),
                        explanation=(
                            f"{match.entity_type} '{match.value}' matches evidence "
                            f"across {case_id} and {link.other_case_id}"
                        ),
                    ))

    def _temporal_edges(self, edges: List[GraphEdge],
                        items: Sequence[EvidenceContext],
                        timeline: Optional[TimelineAnalysis] = None) -> None:
        window = self._cfg.timeline_proximity_hours
        reconstructed = {
            event.evidence_id: event
            for event in (timeline.events if timeline is not None else [])
        }
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                event_a = reconstructed.get(a.evidence_id)
                event_b = reconstructed.get(b.evidence_id)
                # Two files uploaded together describe the investigator's
                # workflow, not the crime chronology. Retaining all such pairs
                # created O(n^2) noise and made every batch look connected.
                if event_a is None or event_b is None:
                    continue
                if "upload_time_fallback" in {
                    event_a.time_source, event_b.time_source
                }:
                    continue
                ta = self._parse_timestamp(event_a.timestamp)
                tb = self._parse_timestamp(event_b.timestamp)
                if ta is None or tb is None:
                    continue
                hours = abs((ta - tb).total_seconds()) / 3600.0
                if hours <= window:
                    edges.append(GraphEdge(
                        source=f"evidence:{a.evidence_id}",
                        target=f"evidence:{b.evidence_id}",
                        edge_type="temporal_relationship",
                        weight=round(1.0 - hours / max(window, 1e-6), 4),
                        confidence=round(1.0 - hours / max(window, 1e-6), 4),
                        source_evidence_ids=[a.evidence_id, b.evidence_id],
                        timestamp=(
                            event_a.timestamp if ta <= tb else event_b.timestamp
                        ),
                        timestamp_source=(
                            event_a.time_source
                            if event_a.time_source == event_b.time_source
                            else "mixed_content_timestamps"
                        ),
                        timestamp_inferred=(
                            event_a.timestamp_inferred or event_b.timestamp_inferred
                        ),
                        explanation=f"Occurred {hours:.1f}h apart "
                                    f"using reconstructed event time "
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
                confidence=round(pair.correlation_confidence, 4),
                source_evidence_ids=[pair.evidence_a, pair.evidence_b],
                explanation=(
                    f"Module-1 correlation: {pair.relationship_strength} "
                    f"(confidence {pair.correlation_confidence:.2f}) - "
                    + "; ".join(pair.correlation_reasons[:2])
                ),
            ))

    def _finalize_edges(
        self,
        edges: List[GraphEdge],
        timeline: Optional[TimelineAnalysis],
    ) -> List[GraphEdge]:
        """Fill provenance/timestamp fields and prevent duplicate edges."""
        event_by_evidence = {
            event.evidence_id: event
            for event in (timeline.events if timeline is not None else [])
        }
        unique: Dict[tuple[str, str, str], GraphEdge] = {}
        for edge in edges:
            evidence_ids = list(edge.source_evidence_ids)
            for endpoint in (edge.source, edge.target):
                if endpoint.startswith("evidence:"):
                    evidence_ids.append(endpoint.split(":", 1)[1])
            evidence_ids = sorted(set(filter(None, evidence_ids)))
            event = next(
                (event_by_evidence[eid] for eid in evidence_ids
                 if eid in event_by_evidence and event_by_evidence[eid].timestamp),
                None,
            )
            if not edge.timestamp and event is not None:
                edge.timestamp = event.timestamp
                edge.timestamp_source = event.time_source
                edge.timestamp_inferred = event.timestamp_inferred
            edge.source_evidence_ids = evidence_ids
            edge.confidence = min(1.0, max(0.0, edge.confidence))
            endpoints = tuple(sorted((edge.source, edge.target)))
            key = (endpoints[0], endpoints[1], edge.edge_type)
            existing = unique.get(key)
            if existing is None or edge.confidence > existing.confidence:
                unique[key] = edge
        return list(unique.values())

    @staticmethod
    def _fallback_node_type(entity_type: str) -> str:
        aliases = {"people": "person", "amounts": "amount", "dates": "date",
                   "times": "time", "otps": "otp"}
        return aliases.get(entity_type, entity_type[:-1] if entity_type.endswith("s") else entity_type)

    @staticmethod
    def _confidence_number(confidence: str) -> float:
        return {"high": 1.0, "medium": 0.7, "low": 0.4}.get(confidence, 0.4)

    @staticmethod
    def _parse_timestamp(value: str):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------- statistics

    def _pagerank(
        self, projected: "nx.Graph", degree: Dict[str, float]
    ) -> Dict[str, float]:
        """PageRank that survives a broken SciPy stack.

        ``nx.pagerank`` delegates to a SciPy sparse solver. SciPy arrives here
        as a transitive dependency, so a wheel built for a different NumPy
        major fails on *import* with ``AttributeError`` on a removed alias
        rather than ``ImportError`` - and an uncaught one used to cost the case
        its entire relationship graph. That is an environment fault, not a
        graph fault, so fall back rather than fail: NetworkX ships an
        equivalent pure-Python power iteration that yields the same ranking
        without SciPy. Degree centrality is the last resort, used only when
        the iteration genuinely cannot converge.
        """
        try:
            return nx.pagerank(projected, weight="weight")
        except nx.PowerIterationFailedConvergence:
            self._log.warning("pagerank did not converge; using degree centrality")
            return dict(degree)
        except Exception as exc:  # noqa: BLE001 - environment, not graph, fault
            self._log.warning(
                "SciPy-backed pagerank unavailable (%s); "
                "using the pure-Python power iteration", exc,
            )

        pure_python = getattr(
            nx.algorithms.link_analysis.pagerank_alg, "_pagerank_python", None
        )
        if pure_python is None:
            return dict(degree)
        try:
            return pure_python(projected, weight="weight")
        except Exception as exc:  # noqa: BLE001 - keep the graph, lose one metric
            self._log.warning("pagerank unavailable (%s); using degree centrality", exc)
            return dict(degree)

    def _enrich_with_networkx(self, graph: RelationshipGraph) -> Dict[str, object]:
        """Derive centrality, communities and a readable graph backbone.

        NetworkX operates on a simple analytical projection because the
        forensic artifact may hold several typed edges between the same pair.
        The artifact itself remains unchanged except for additive metrics and
        ``backbone`` flags; no relationship is discarded.
        """
        projected = nx.Graph()
        projected.add_nodes_from(node.id for node in graph.nodes)
        best_edge: Dict[tuple[str, str], tuple[int, float]] = {}
        for index, edge in enumerate(graph.edges):
            if edge.source == edge.target:
                continue
            pair = tuple(sorted((edge.source, edge.target)))
            # Structural links keep isolated evidence attached to its case,
            # but must not overpower actual investigative relationships when
            # deriving communities, paths and the simplified backbone.
            type_weight = {
                "contains": 0.08,
                "timeline_event": 0.12,
                "shared_entity": 0.85,
                "temporal_relationship": 0.70,
                "metadata_relationship": 0.80,
                "behavioral_relationship": 0.90,
                "threat_relationship": 1.00,
                "cross_case_relationship": 1.00,
                "cross_case_entity_match": 1.00,
            }.get(edge.edge_type, 0.65)
            score = max(
                0.001,
                min(1.0, edge.confidence) * type_weight,
            )
            current = best_edge.get(pair)
            if current is None or score > current[1]:
                best_edge[pair] = (index, score)
            if projected.has_edge(*pair):
                strongest = max(projected[pair[0]][pair[1]]["weight"], score)
                projected[pair[0]][pair[1]]["weight"] = strongest
                projected[pair[0]][pair[1]]["distance"] = 1.0 / strongest
            else:
                projected.add_edge(*pair, weight=score, distance=1.0 / score)

        degree = (
            nx.degree_centrality(projected)
            if len(projected) > 1
            else {node_id: 0.0 for node_id in projected}
        )
        if projected.number_of_edges():
            pagerank = self._pagerank(projected, degree)
            if len(projected) <= 250:
                betweenness = nx.betweenness_centrality(
                    projected, normalized=True, weight="distance"
                )
            else:
                betweenness = nx.betweenness_centrality(
                    projected, k=min(64, len(projected)), normalized=True,
                    weight="distance", seed=42
                )
            communities = list(
                nx.community.greedy_modularity_communities(projected, weight="weight")
            )
        else:
            pagerank = {node_id: 0.0 for node_id in projected}
            betweenness = {node_id: 0.0 for node_id in projected}
            communities = [{node_id} for node_id in projected]

        community_by_node: Dict[str, int] = {}
        community_sizes: Dict[int, int] = {}
        ordered_communities = sorted(
            communities,
            key=lambda group: (-len(group), min(group) if group else ""),
        )
        for community_id, members in enumerate(ordered_communities, start=1):
            community_sizes[community_id] = len(members)
            for node_id in members:
                community_by_node[node_id] = community_id

        max_pagerank = max(pagerank.values(), default=0.0) or 1.0
        importance: Dict[str, float] = {}
        node_by_id = {node.id: node for node in graph.nodes}
        for node_id in projected:
            normalized_pagerank = pagerank.get(node_id, 0.0) / max_pagerank
            value = min(
                1.0,
                0.45 * normalized_pagerank
                + 0.35 * betweenness.get(node_id, 0.0)
                + 0.20 * degree.get(node_id, 0.0),
            )
            importance[node_id] = value
            community_id = community_by_node.get(node_id, 0)
            node_by_id[node_id].properties.update({
                "degree_centrality": f"{degree.get(node_id, 0.0):.6f}",
                "betweenness_centrality": f"{betweenness.get(node_id, 0.0):.6f}",
                "pagerank": f"{pagerank.get(node_id, 0.0):.6f}",
                "graph_importance": f"{value:.6f}",
                "community_id": str(community_id),
                "community_size": str(community_sizes.get(community_id, 1)),
            })

        forest = nx.maximum_spanning_tree(projected, weight="weight")
        for raw_pair in forest.edges():
            representative = best_edge.get(tuple(sorted(raw_pair)))
            if representative is not None:
                graph.edges[representative[0]].backbone = True
        critical_types = {
            "threat_relationship",
            "cross_case_relationship",
            "cross_case_entity_match",
        }
        for edge in graph.edges:
            if edge.edge_type in critical_types:
                edge.backbone = True

        components = list(nx.connected_components(projected))
        bridges = list(nx.bridges(projected)) if projected.number_of_edges() else []
        return {
            "components": len(components),
            "largest_component": max((len(group) for group in components), default=0),
            "importance": importance,
            "community_count": len(ordered_communities),
            "bridge_count": len(bridges),
            "backbone_edge_count": sum(edge.backbone for edge in graph.edges),
        }

    def _statistics(
        self,
        graph: RelationshipGraph,
        nx_metrics: Dict[str, object],
    ) -> GraphStatistics:
        nodes_by_type: Dict[str, int] = {}
        for node in graph.nodes:
            nodes_by_type[node.node_type] = nodes_by_type.get(node.node_type, 0) + 1
        edges_by_type: Dict[str, int] = {}
        degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        for edge in graph.edges:
            edges_by_type[edge.edge_type] = edges_by_type.get(edge.edge_type, 0) + 1
            if edge.source in degree:
                degree[edge.source] += 1
            if edge.target in degree:
                degree[edge.target] += 1
        n, e = len(graph.nodes), len(graph.edges)
        top = sorted(degree.items(), key=lambda kv: kv[1], reverse=True)
        top_hubs = [{"node": node_id, "degree": str(d)}
                    for node_id, d in top[: self._cfg.graph_top_hubs] if d > 0]
        importance = dict(nx_metrics.get("importance", {}))
        node_by_id = {node.id: node for node in graph.nodes}
        return GraphStatistics(
            case_id=graph.case_id,
            node_count=n,
            edge_count=e,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            density=round(2.0 * e / (n * (n - 1)), 4) if n > 1 else 0.0,
            connected_components=int(nx_metrics.get("components", 0)),
            largest_component_size=int(nx_metrics.get("largest_component", 0)),
            average_degree=round(sum(degree.values()) / n, 3) if n else 0.0,
            top_hubs=top_hubs,
            community_count=int(nx_metrics.get("community_count", 0)),
            bridge_count=int(nx_metrics.get("bridge_count", 0)),
            backbone_edge_count=int(nx_metrics.get("backbone_edge_count", 0)),
            analytics_engine=f"networkx-{nx.__version__}",
            top_central_nodes=[
                {
                    "node": node_id,
                    "importance": f"{score:.6f}",
                    "community": node_by_id[node_id].properties.get(
                        "community_id", "0"
                    ),
                }
                for node_id, score in sorted(
                    importance.items(), key=lambda item: (-item[1], item[0])
                )[: self._cfg.graph_top_hubs]
            ],
        )

    def _summary(self, graph: RelationshipGraph,
                 statistics: GraphStatistics) -> GraphSummary:
        connectors = [
            node["node"] for node in statistics.top_central_nodes
            if not node["node"].startswith(("case:", "evidence:", "timeline_event:"))
        ][:5]
        observations: List[str] = []
        if statistics.community_count:
            observations.append(
                f"NetworkX identified {count_of(statistics.community_count, 'community')} "
                f"and retained {count_of(statistics.backbone_edge_count, 'key edge')} "
                "for simplified investigation views."
            )
        if statistics.bridge_count:
            observations.append(
                f"{count_of(statistics.bridge_count, 'bridge connection')} can separate "
                "otherwise distinct portions of the relationship graph."
            )
        threat_edges = statistics.edges_by_type.get("threat_relationship", 0)
        if threat_edges:
            observations.append(
                f"{count_of(threat_edges, 'threat-intelligence edge')} link flagged "
                "indicators to evidence."
            )
        behavioral = statistics.edges_by_type.get("behavioral_relationship", 0)
        if behavioral:
            observations.append(
                f"{count_of(behavioral, 'strong behavioural link')} derived from the "
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
                f"edges across {count_of(statistics.connected_components, 'component')}"
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
