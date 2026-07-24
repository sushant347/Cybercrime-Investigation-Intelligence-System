"""
Module 4 (enhanced) - NetworkX Investigation Graph Builder
==========================================================
Cybercrime Investigation Intelligence System (CIIS)

This module introduces a `networkx.MultiDiGraph`-backed investigation graph as
the backbone of the Evidence Correlation Engine. It sits in the pipeline
immediately after Entity Extraction:

    Entity Extraction  ->  NetworkX Graph Builder  ->  Evidence Correlation
                                                    ->  Timeline / Campaign
                                                    ->  Suspect / Analytics
                                                    ->  Report Generation

Design notes
------------
* It **consumes** the entities already produced by the OCR/entity-extraction
  pipeline (the ``cleaning.entities`` block on each evidence item). It never
  re-extracts and never mutates OCR or extraction logic.
* Duplicate entities are merged automatically: a deterministic node id derived
  from ``(entity_type, normalized_value)`` means the same wallet/URL/phone that
  appears in three evidence items becomes **one** node with **three** evidence
  links.
* The builder is framework-agnostic. ``serialize_graph()`` emits JSON that is
  byte-compatible with the existing React frontend contract
  (``RelationshipGraph`` / ``GraphStatistics`` / ``GraphSummary``), so it drops
  straight into the current Django/DRF artifact endpoints.

The public surface (``GraphBuilder``) is intentionally small and reusable so
downstream modules (Timeline, Campaign, Suspect, Report) can share one graph
instance instead of each re-deriving relationships.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from typing import Any, Iterable, Mapping, Optional, Sequence

try:
    import networkx as nx
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "networkx is required for the investigation graph. "
        "Install it with `pip install networkx>=3.0`."
    ) from exc


logger = logging.getLogger("ciis.graph_builder")


# --------------------------------------------------------------------------- #
# Configuration / taxonomy
# --------------------------------------------------------------------------- #

#: Raw ``cleaning.entities`` key  ->  canonical graph node_type.
#: node_type strings match the frontend legend palette (theme.ts NODE_COLORS).
ENTITY_TYPE_MAP: dict[str, str] = {
    "urls": "url",
    "social_media_urls": "social_account",
    "emails": "email",
    "domains": "domain",
    "ipv4": "ip",
    "ipv6": "ip",
    "mac_addresses": "device",
    "phones": "phone",
    "whatsapp_numbers": "social_account",
    "telegram_usernames": "social_account",
    "facebook_usernames": "social_account",
    "instagram_usernames": "social_account",
    "bank_accounts": "bank_account",
    "esewa_ids": "wallet",
    "khalti_ids": "wallet",
    "imepay_ids": "wallet",
    "eth_wallets": "wallet",
    "btc_wallets": "wallet",
    "hashes_sha256": "hash",
    "hashes_sha1": "hash",
    "hashes_md5": "hash",
    "hashes_sha512": "hash",
    "cve_ids": "cve",
    "qr_codes": "qr_code",
    "transaction_ids": "transaction_id",
}

#: node_type  ->  edge relation used for the directed ``evidence -> entity`` link.
#: (SOLID/OCP: extend this table to add relation semantics without touching code.)
CONTAINS_RELATION: dict[str, str] = {
    "url": "references",
    "social_account": "communicates_with",
    "email": "communicates_with",
    "domain": "resolves_to",
    "ip": "resolves_to",
    "device": "belongs_to",
    "phone": "communicates_with",
    "bank_account": "transfers_to",
    "wallet": "transfers_to",
    "transaction_id": "transfers_to",
    "hash": "references",
    "cve": "references",
    "qr_code": "references",
    "person": "belongs_to",
    "organization": "belongs_to",
}

DEFAULT_TEMPORAL_PROXIMITY_HOURS = 24.0

#: node types that most often *are* a suspect / actor for prioritisation.
SUSPECT_LIKE_TYPES = frozenset({"phone", "email", "wallet", "social_account", "person"})


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #

class GraphBuildError(RuntimeError):
    """Raised when the investigation graph cannot be constructed."""


# --------------------------------------------------------------------------- #
# Entity normalization  (single responsibility -> injectable)
# --------------------------------------------------------------------------- #

class EntityNormalizer:
    """Normalises raw entity values so duplicates collapse onto one node.

    Kept as its own object (rather than free functions) so alternative
    normalisation strategies can be dependency-injected into ``GraphBuilder``
    for testing or locale-specific rules.
    """

    _URL_SCHEME = re.compile(r"^[a-z]+://", re.IGNORECASE)
    _TRAILING = re.compile(r"[/#?]+$")

    def normalize(self, node_type: str, value: str) -> str:
        """Return a canonical, comparable form of ``value`` for ``node_type``."""
        text = (value or "").strip()
        if not text:
            return text

        if node_type in {"url", "social_account"}:
            return self._normalize_url(text)
        if node_type in {"domain", "email", "ip", "hash", "cve"}:
            return text.lower()
        if node_type == "phone":
            return re.sub(r"[^\d+]", "", text)
        # wallets, bank accounts, transaction ids: case-insensitive, keep chars
        return text.lower()

    def _normalize_url(self, text: str) -> str:
        text = self._URL_SCHEME.sub("", text)
        text = text.lower()
        if text.startswith("www."):
            text = text[4:]
        text = self._TRAILING.sub("", text)
        return text


# --------------------------------------------------------------------------- #
# Serializable value objects
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class NodeRef:
    """Where an entity node was observed (one evidence occurrence)."""

    case_id: str
    evidence_id: str
    entity_type: str
    raw_value: str
    confidence: float


# --------------------------------------------------------------------------- #
# The graph builder
# --------------------------------------------------------------------------- #

class GraphBuilder:
    """Builds and analyses a `networkx.MultiDiGraph` investigation graph.

    A MultiDiGraph is used deliberately: relationships are *directed*
    (evidence -> entity), and the same pair of nodes may be joined by *multiple*
    relationship types (e.g. ``communicates_with`` and ``temporal_relation``).

    Typical use::

        builder = GraphBuilder(case_id="CASE_0021")
        builder.build_graph(cases)
        artifacts = builder.serialize_graph()   # frontend-ready JSON

    The instance is reusable: downstream modules can call the analytics methods
    (``degree_centrality``, ``community_detection``, ``find_shortest_path`` ...)
    against the already-built graph rather than rebuilding it.
    """

    def __init__(
        self,
        case_id: str = "MULTI_CASE",
        *,
        normalizer: Optional[EntityNormalizer] = None,
        temporal_proximity_hours: float = DEFAULT_TEMPORAL_PROXIMITY_HOURS,
        directed: bool = True,
    ) -> None:
        self.case_id = case_id
        self._normalizer = normalizer or EntityNormalizer()
        self._temporal_hours = float(temporal_proximity_hours)
        self._directed = directed
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph(case_id=case_id, directed=directed)
        self._build_signature: Optional[str] = None
        self._analytics_cache: dict[str, Any] = {}

    # ---- construction ---------------------------------------------------- #

    def add_node(
        self,
        node_type: str,
        value: str,
        *,
        confidence: float = 1.0,
        case_id: str = "",
        evidence_id: str = "",
        label: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Add (or merge into) a node and return its deterministic id.

        Calling this repeatedly with the same normalised ``value`` merges the
        occurrences onto a single node while accumulating every evidence
        reference — this is the automatic duplicate-entity resolution.
        """
        normalized = self._normalizer.normalize(node_type, value)
        if not normalized:
            raise GraphBuildError(f"Empty value for node_type={node_type!r}")

        node_id = f"{node_type}:{normalized}" if node_type != "evidence" else f"evidence:{value}"

        if self.graph.has_node(node_id):
            data = self.graph.nodes[node_id]
            data["confidence"] = max(data.get("confidence", 0.0), confidence)
            refs: set = data.setdefault("evidence_ids", set())
            if evidence_id:
                refs.add(evidence_id)
            cases: set = data.setdefault("case_ids", set())
            if case_id:
                cases.add(case_id)
            if metadata:
                data.setdefault("metadata", {}).update(dict(metadata))
        else:
            self.graph.add_node(
                node_id,
                node_type=node_type,
                value=normalized,
                label=label or (value if node_type == "evidence" else normalized),
                confidence=confidence,
                case_ids={case_id} if case_id else set(),
                evidence_ids={evidence_id} if evidence_id else set(),
                metadata=dict(metadata or {}),
            )
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        confidence: float = 1.0,
        reason: str = "",
        evidence_id: str = "",
        timestamp: Optional[str] = None,
        weight: float = 1.0,
    ) -> None:
        """Add a directed, typed relationship edge.

        ``key=relation`` means two nodes may hold several parallel edges of
        different relation types (MultiDiGraph semantics) but never duplicate
        the *same* relation.
        """
        if not self.graph.has_node(source) or not self.graph.has_node(target):
            raise GraphBuildError(
                f"Cannot add edge {relation}: missing endpoint(s) {source!r}->{target!r}"
            )
        if self.graph.has_edge(source, target, key=relation):
            data = self.graph.edges[source, target, relation]
            data["weight"] += weight
            data["confidence"] = max(data["confidence"], confidence)
        else:
            self.graph.add_edge(
                source,
                target,
                key=relation,
                relation=relation,
                edge_type=relation,
                confidence=confidence,
                reason=reason,
                evidence_id=evidence_id,
                timestamp=timestamp,
                weight=weight,
            )

    def build_graph(self, cases: Sequence[Mapping[str, Any]]) -> "nx.MultiDiGraph":
        """Construct the investigation graph from one or more case documents.

        Steps:
          1. add an ``evidence`` node per evidence item;
          2. add/merge a typed node per extracted entity (dedup automatic);
          3. link ``evidence --relation--> entity`` (``contains`` family);
          4. add ``temporal_relation`` edges between evidence close in time.
        """
        signature = self._signature(cases)
        if signature == self._build_signature and self.graph.number_of_nodes():
            logger.info("Graph unchanged (signature match) - skipping rebuild.")
            return self.graph

        # fresh build
        self.graph = nx.MultiDiGraph(case_id=self.case_id, directed=self._directed)
        self._analytics_cache.clear()

        evidence_times: dict[str, Optional[datetime]] = {}

        for case in cases:
            case_id = str(case.get("case_id", "UNKNOWN_CASE"))
            for evidence in case.get("evidence", []):
                evidence_id = str(evidence.get("evidence_id", "UNKNOWN_EVID"))
                ev_node = self.add_node(
                    "evidence",
                    evidence_id,
                    case_id=case_id,
                    evidence_id=evidence_id,
                    label=evidence.get("file_name") or evidence_id,
                    confidence=float(evidence.get("average_confidence", 1.0) or 1.0),
                    metadata={
                        "file_name": evidence.get("file_name", ""),
                        "upload_time": evidence.get("upload_time", ""),
                        "ocr_engine": evidence.get("ocr_engine", ""),
                    },
                )
                evidence_times[ev_node] = self._parse_time(evidence.get("upload_time"))

                entities = evidence.get("cleaning", {}).get("entities", {}) or {}
                self._ingest_entities(case_id, evidence_id, ev_node, entities)

        self._add_temporal_edges(evidence_times)

        self._build_signature = signature
        logger.info(
            "Built investigation graph: %d nodes, %d edges.",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return self.graph

    def _ingest_entities(
        self,
        case_id: str,
        evidence_id: str,
        ev_node: str,
        entities: Mapping[str, Any],
    ) -> None:
        for raw_type, items in entities.items():
            node_type = ENTITY_TYPE_MAP.get(raw_type)
            if node_type is None or not isinstance(items, Iterable):
                continue
            relation = CONTAINS_RELATION.get(node_type, "contains")
            for item in items:
                value, confidence = self._read_entity_item(item)
                if not value:
                    continue
                try:
                    ent_node = self.add_node(
                        node_type,
                        value,
                        confidence=confidence,
                        case_id=case_id,
                        evidence_id=evidence_id,
                        metadata={"source_entity_key": raw_type},
                    )
                except GraphBuildError:
                    continue
                self.add_edge(
                    ev_node,
                    ent_node,
                    relation,
                    confidence=confidence,
                    reason=f"{node_type} extracted from {evidence_id}",
                    evidence_id=evidence_id,
                    weight=1.0,
                )

    @staticmethod
    def _read_entity_item(item: Any) -> tuple[str, float]:
        if isinstance(item, Mapping):
            value = item.get("normalized") or item.get("value") or ""
            confidence = float(item.get("confidence", 1.0) or 1.0)
            return str(value).strip(), confidence
        return str(item).strip(), 1.0

    def merge_duplicate_entities(self) -> int:
        """Merge nodes that share ``(node_type, value)`` after normalisation.

        Duplicate resolution already happens at ``add_node`` time via the
        deterministic id, so under normal construction this is a no-op. It is
        exposed for the case where nodes were added through other paths (e.g.
        an imported subgraph) and returns the number of nodes removed.
        """
        buckets: dict[tuple[str, str], list[str]] = {}
        for node_id, data in self.graph.nodes(data=True):
            key = (data.get("node_type", ""), data.get("value", ""))
            buckets.setdefault(key, []).append(node_id)

        removed = 0
        for (node_type, value), ids in buckets.items():
            if len(ids) < 2:
                continue
            canonical = ids[0]
            for dup in ids[1:]:
                self._absorb(dup, canonical)
                removed += 1
        if removed:
            self._analytics_cache.clear()
            logger.info("Merged %d duplicate entity node(s).", removed)
        return removed

    def _absorb(self, dup: str, canonical: str) -> None:
        cdata = self.graph.nodes[canonical]
        ddata = self.graph.nodes[dup]
        cdata.setdefault("evidence_ids", set()).update(ddata.get("evidence_ids", set()))
        cdata.setdefault("case_ids", set()).update(ddata.get("case_ids", set()))
        for _, tgt, key, edata in list(self.graph.out_edges(dup, keys=True, data=True)):
            self.graph.add_edge(canonical, tgt, key=key, **edata)
        for src, _, key, edata in list(self.graph.in_edges(dup, keys=True, data=True)):
            self.graph.add_edge(src, canonical, key=key, **edata)
        self.graph.remove_node(dup)

    def _add_temporal_edges(self, evidence_times: Mapping[str, Optional[datetime]]) -> None:
        timed = [(nid, ts) for nid, ts in evidence_times.items() if ts is not None]
        for (a, ta), (b, tb) in combinations(timed, 2):
            delta_h = abs((ta - tb).total_seconds()) / 3600.0
            if delta_h <= self._temporal_hours:
                weight = max(0.1, 1.0 - delta_h / self._temporal_hours)
                self.add_edge(
                    a,
                    b,
                    "temporal_relation",
                    confidence=weight,
                    reason=f"uploaded within {delta_h:.1f}h",
                    weight=weight,
                    timestamp=ta.isoformat(),
                )

    # ---- undirected simple projection (for centrality/components/community) - #

    def _projection(self) -> nx.Graph:
        """Simple undirected projection with summed weights (cached)."""
        cached = self._analytics_cache.get("_projection")
        if cached is not None:
            return cached
        simple = nx.Graph()
        simple.add_nodes_from(self.graph.nodes(data=True))
        for u, v, data in self.graph.edges(data=True):
            if u == v:
                continue
            w = float(data.get("weight", 1.0))
            if simple.has_edge(u, v):
                simple[u][v]["weight"] += w
            else:
                simple.add_edge(u, v, weight=w)
        self._analytics_cache["_projection"] = simple
        return simple

    # ---- analytics ------------------------------------------------------- #

    def connected_components(self) -> list[list[str]]:
        """Weakly-connected investigation clusters (largest first)."""
        comps = [sorted(c) for c in nx.connected_components(self._projection())]
        comps.sort(key=len, reverse=True)
        return comps

    def find_isolated_nodes(self) -> list[str]:
        """Nodes with no relationships at all."""
        return sorted(nx.isolates(self._projection()))

    def find_shortest_path(self, source: str, target: str) -> list[str]:
        """Shortest relationship path between two nodes ([] if unreachable)."""
        proj = self._projection()
        if source not in proj or target not in proj:
            raise GraphBuildError(f"Unknown node in path query: {source!r} / {target!r}")
        try:
            return nx.shortest_path(proj, source, target)
        except nx.NetworkXNoPath:
            return []

    def degree_centrality(self) -> dict[str, float]:
        return self._centrality("degree", nx.degree_centrality)

    def betweenness_centrality(self) -> dict[str, float]:
        return self._centrality("betweenness", nx.betweenness_centrality)

    def closeness_centrality(self) -> dict[str, float]:
        return self._centrality("closeness", nx.closeness_centrality)

    def _centrality(self, name: str, fn) -> dict[str, float]:
        key = f"centrality:{name}"
        if key not in self._analytics_cache:
            proj = self._projection()
            self._analytics_cache[key] = fn(proj) if proj.number_of_nodes() else {}
        return self._analytics_cache[key]

    def community_detection(self) -> list[list[str]]:
        """Greedy-modularity communities (suspicious clusters), largest first."""
        proj = self._projection()
        if proj.number_of_edges() == 0:
            return [[n] for n in proj.nodes()]
        try:
            from networkx.algorithms.community import greedy_modularity_communities

            communities = greedy_modularity_communities(proj, weight="weight")
        except Exception:  # pragma: no cover - fallback for tiny/edge graphs
            communities = nx.connected_components(proj)
        result = [sorted(c) for c in communities]
        result.sort(key=len, reverse=True)
        return result

    # ---- investigation feature extraction -------------------------------- #

    def _top_of_types(self, degree: Mapping[str, float], types: Iterable[str]) -> Optional[str]:
        typeset = set(types)
        candidates = [
            (nid, degree.get(nid, 0.0))
            for nid, data in self.graph.nodes(data=True)
            if data.get("node_type") in typeset
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda kv: kv[1])[0]

    def investigation_features(self) -> dict[str, Any]:
        """High-level, human-facing findings used by the report generator."""
        degree = self.degree_centrality()
        components = self.connected_components()
        communities = self.community_detection()

        def label_of(node_id: Optional[str]) -> Optional[str]:
            if not node_id or node_id not in self.graph:
                return None
            data = self.graph.nodes[node_id]
            return data.get("label") or data.get("value")

        return {
            "most_connected_suspect": label_of(self._top_of_types(degree, SUSPECT_LIKE_TYPES)),
            "most_reused_phishing_url": label_of(self._top_of_types(degree, {"url"})),
            "most_common_wallet": label_of(self._top_of_types(degree, {"wallet"})),
            "most_connected_phone": label_of(self._top_of_types(degree, {"phone"})),
            "largest_campaign_size": len(communities[0]) if communities else 0,
            "investigation_clusters": len(components),
            "shared_infrastructure": [
                label_of(nid)
                for nid, data in self.graph.nodes(data=True)
                if data.get("node_type") in {"domain", "ip", "url"}
                and len(data.get("evidence_ids", set())) >= 2
            ][:10],
        }

    # ---- summaries & serialization --------------------------------------- #

    def generate_graph_summary(self) -> dict[str, Any]:
        """A short, report-ready narrative summary (frontend ``GraphSummary``)."""
        features = self.investigation_features()
        components = self.connected_components()
        degree = self.degree_centrality()

        key_connectors = [
            self.graph.nodes[nid].get("label") or self.graph.nodes[nid].get("value")
            for nid, _ in sorted(degree.items(), key=lambda kv: kv[1], reverse=True)
            if self.graph.nodes[nid].get("node_type") != "evidence"
        ][:5]

        observations: list[str] = []
        if features["most_connected_suspect"]:
            observations.append(
                f"Most connected actor is {features['most_connected_suspect']}."
            )
        if features["most_common_wallet"]:
            observations.append(
                f"Wallet {features['most_common_wallet']} appears across multiple evidence items."
            )
        if features["most_reused_phishing_url"]:
            observations.append(
                f"URL {features['most_reused_phishing_url']} is the most reused link."
            )
        observations.append(
            f"{len(components)} investigation cluster(s); "
            f"largest suspicious community has {features['largest_campaign_size']} member(s)."
        )
        if not observations:
            observations.append("No significant cross-evidence relationships detected.")

        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()
        headline = (
            f"{node_count} entities and {edge_count} relationships across "
            f"{len(components)} cluster(s)."
        )
        return {
            "case_id": self.case_id,
            "headline": headline,
            "key_connectors": [c for c in key_connectors if c],
            "observations": observations,
        }

    def graph_statistics(self) -> dict[str, Any]:
        """Structural statistics (frontend ``GraphStatistics`` contract)."""
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()

        nodes_by_type: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("node_type", "unknown")
            nodes_by_type[t] = nodes_by_type.get(t, 0) + 1

        edges_by_type: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            t = data.get("relation", "unknown")
            edges_by_type[t] = edges_by_type.get(t, 0) + 1

        components = self.connected_components()
        degree = self.degree_centrality()
        top_hubs = [
            {
                "id": nid,
                "label": str(self.graph.nodes[nid].get("label", nid)),
                "node_type": str(self.graph.nodes[nid].get("node_type", "")),
                "degree_centrality": f"{score:.4f}",
            }
            for nid, score in sorted(degree.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ]
        avg_degree = (
            sum(d for _, d in self._projection().degree()) / node_count if node_count else 0.0
        )
        return {
            "case_id": self.case_id,
            "node_count": node_count,
            "edge_count": edge_count,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
            "density": round(nx.density(self.graph), 6) if node_count > 1 else 0.0,
            "connected_components": len(components),
            "largest_component_size": len(components[0]) if components else 0,
            "average_degree": round(avg_degree, 4),
            "top_hubs": top_hubs,
        }

    def serialize_graph(self) -> dict[str, Any]:
        """Emit the full artifact bundle in the React frontend contract.

        Returns a dict with three keys matching the existing artifact endpoints::

            {"graph": RelationshipGraph,
             "graph_statistics": GraphStatistics,
             "graph_summary": GraphSummary}
        """
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            props: dict[str, str] = {
                "value": str(data.get("value", "")),
                "confidence": f"{float(data.get('confidence', 1.0)):.3f}",
                "evidence_count": str(len(data.get("evidence_ids", set()))),
                "case_ids": ", ".join(sorted(data.get("case_ids", set()))),
                "evidence_ids": ", ".join(sorted(data.get("evidence_ids", set()))),
            }
            for k, v in (data.get("metadata") or {}).items():
                if v:
                    props[str(k)] = str(v)
            nodes.append(
                {
                    "id": node_id,
                    "node_type": data.get("node_type", "unknown"),
                    "label": str(data.get("label") or data.get("value") or node_id),
                    "properties": props,
                }
            )

        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            edges.append(
                {
                    "source": src,
                    "target": tgt,
                    "edge_type": data.get("relation", "linked_to"),
                    "weight": round(float(data.get("weight", 1.0)), 4),
                    "explanation": data.get("reason", ""),
                }
            )

        relationship_graph = {
            "case_id": self.case_id,
            "directed": self._directed,
            "nodes": nodes,
            "edges": edges,
        }
        return {
            "graph": relationship_graph,
            "graph_statistics": self.graph_statistics(),
            "graph_summary": self.generate_graph_summary(),
        }

    # ---- helpers --------------------------------------------------------- #

    @staticmethod
    def _parse_time(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _signature(cases: Sequence[Mapping[str, Any]]) -> str:
        """Stable content hash of the input, used to skip needless rebuilds."""
        hasher = hashlib.sha256()
        for case in cases:
            hasher.update(str(case.get("case_id", "")).encode())
            for ev in case.get("evidence", []):
                hasher.update(str(ev.get("evidence_id", "")).encode())
                hasher.update(json.dumps(
                    ev.get("cleaning", {}).get("entities", {}), sort_keys=True
                ).encode())
                hasher.update(str(ev.get("upload_time", "")).encode())
        return hasher.hexdigest()


__all__ = [
    "GraphBuilder",
    "EntityNormalizer",
    "GraphBuildError",
    "ENTITY_TYPE_MAP",
    "CONTAINS_RELATION",
]
