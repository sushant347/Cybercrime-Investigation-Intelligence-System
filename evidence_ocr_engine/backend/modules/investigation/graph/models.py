"""Pydantic models for the Evidence Relationship Graph Engine (Module 2).

Node types: case, evidence, phone_number, email, url, domain, wallet,
bank_account, person, device, brand, social_media_account.
Edge types: shared_entity, temporal_relationship, threat_relationship,
metadata_relationship, behavioral_relationship (plus structural 'contains').
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str = Field(description="Stable unique id, e.g. 'phone:9812345678'")
    node_type: str
    label: str = ""
    properties: Dict[str, str] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str
    weight: float = Field(default=1.0, ge=0.0)
    explanation: str = ""


class RelationshipGraph(BaseModel):
    """Complete graph stored as ``graph.json``."""

    case_id: str
    directed: bool = False
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class GraphStatistics(BaseModel):
    """Stored as ``graph_statistics.json``."""

    case_id: str
    node_count: int = 0
    edge_count: int = 0
    nodes_by_type: Dict[str, int] = Field(default_factory=dict)
    edges_by_type: Dict[str, int] = Field(default_factory=dict)
    density: float = 0.0
    connected_components: int = 0
    largest_component_size: int = 0
    average_degree: float = 0.0
    top_hubs: List[Dict[str, str]] = Field(
        default_factory=list, description="Highest-degree nodes with degree"
    )


class GraphSummary(BaseModel):
    """Stored as ``graph_summary.json`` - narrative digest for investigators."""

    case_id: str
    headline: str = ""
    key_connectors: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
