import { describe, expect, it } from "vitest";

import type { GraphEdge, GraphNode, RelationshipGraph } from "@/types";

import {
  buildCrossCaseView,
  buildEvidenceProjection,
  buildSearchGraphView,
  buildThreatView,
  edgePassesRelationshipFilters,
  filterGraphRelationships,
  pairKey,
} from "../views";

const node = (
  id: string,
  node_type: string,
  label = id.split(":").slice(1).join(":"),
  properties: Record<string, string> = {},
): GraphNode => ({ id, node_type, label, properties });

const edge = (
  source: string,
  target: string,
  edge_type: string,
  overrides: Partial<GraphEdge> = {},
): GraphEdge => ({
  source,
  target,
  edge_type,
  weight: 1,
  confidence: 1,
  explanation: "",
  ...overrides,
});

function sample(): RelationshipGraph {
  return {
    case_id: "CASE_1",
    directed: false,
    nodes: [
      node("case:CASE_1", "case"),
      node("evidence:E1", "evidence", "bank.png", { file_name: "bank.png" }),
      node("evidence:E2", "evidence", "chat.png", { file_name: "chat.png" }),
      node("evidence:E3", "evidence", "receipt.pdf", { file_name: "receipt.pdf" }),
      node("wallet:W1", "wallet", "W1"),
      node("phone:P1", "phone_number", "P1"),
      node("url:BAD", "url", "https://bad.test"),
      node("timeline_event:T1", "timeline_event", "event"),
    ],
    edges: [
      edge("case:CASE_1", "evidence:E1", "contains"),
      edge("case:CASE_1", "evidence:E2", "contains"),
      edge("case:CASE_1", "evidence:E3", "contains"),
      edge("evidence:E1", "wallet:W1", "shared_entity"),
      edge("evidence:E2", "wallet:W1", "shared_entity"),
      edge("evidence:E1", "phone:P1", "shared_entity"),
      edge("evidence:E2", "phone:P1", "shared_entity"),
      edge("evidence:E1", "url:BAD", "shared_entity"),
      edge("url:BAD", "evidence:E1", "threat_relationship"),
      edge("evidence:E1", "evidence:E2", "behavioral_relationship", {
        confidence: 0.8,
      }),
      edge("evidence:E2", "evidence:E3", "temporal_relationship", {
        confidence: 0.4,
        timestamp: "2026-06-10T10:00:00Z",
        timestamp_inferred: true,
      }),
      edge("evidence:E1", "timeline_event:T1", "timeline_event"),
    ],
  };
}

describe("buildEvidenceProjection", () => {
  it("combines repeated findings into one evidence-pair edge", () => {
    const view = buildEvidenceProjection(sample());
    const relationship = view.edges.find(
      (item) => item.source === "evidence:E1" && item.target === "evidence:E2",
    );

    expect(view.nodes.every((item) => item.node_type === "evidence")).toBe(true);
    expect(relationship?.edge_type).toBe("evidence_relationship");
    expect(relationship?.projection?.entity_ids.sort()).toEqual([
      "phone:P1",
      "wallet:W1",
    ]);
    expect(relationship?.projection?.relationship_types).toContain(
      "behavioral_relationship",
    );
    expect(view.edges.filter((item) => item.source === "evidence:E1" && item.target === "evidence:E2")).toHaveLength(1);
  });

  it("reveals only the shared entities for an expanded evidence pair", () => {
    const key = pairKey("evidence:E1", "evidence:E2");
    const view = buildEvidenceProjection(sample(), {
      expandedPairs: new Set([key]),
    });

    expect(view.nodes.map((item) => item.id)).toContain("wallet:W1");
    expect(view.nodes.map((item) => item.id)).toContain("phone:P1");
    expect(view.nodes.map((item) => item.id)).not.toContain("url:BAD");
    expect(view.edges.some((item) => item.edge_type === "shared_entity")).toBe(true);
  });

  it("honours confidence filtering and keeps the stronger pair", () => {
    const view = buildEvidenceProjection(sample(), { minimumConfidence: 0.75 });
    expect(view.edges.some((item) =>
      [item.source, item.target].includes("evidence:E3"),
    )).toBe(false);
    expect(view.edges.some((item) =>
      item.source === "evidence:E1" && item.target === "evidence:E2",
    )).toBe(true);
  });

  it("caps evidence by connectivity and reports the omitted count", () => {
    const view = buildEvidenceProjection(sample(), { evidenceBudget: 2 });
    expect(view.nodes).toHaveLength(2);
    expect(view.hiddenNodes).toBe(1);
  });

  it("does not infer evidence relationships from shared low-identity values", () => {
    const graph = sample();
    graph.nodes.push(node("date:2026-06-10", "date", "10 June 2026"));
    graph.edges.push(
      edge("evidence:E2", "date:2026-06-10", "shared_entity"),
      edge("evidence:E3", "date:2026-06-10", "shared_entity"),
    );

    const view = buildEvidenceProjection(graph);
    const relationship = view.edges.find((item) =>
      [item.source, item.target].includes("evidence:E2") &&
      [item.source, item.target].includes("evidence:E3"),
    );
    // E2/E3 already have a real temporal relationship in this fixture, but
    // the shared calendar date must not be represented as another finding.
    expect(relationship?.projection?.entity_ids).not.toContain("date:2026-06-10");
  });

  it("uses backend graph importance when an evidence budget is applied", () => {
    const graph = sample();
    const important = graph.nodes.find((item) => item.id === "evidence:E3")!;
    important.properties.graph_importance = "0.99";

    const view = buildEvidenceProjection(graph, { evidenceBudget: 1 });
    expect(view.nodes.map((item) => item.id)).toEqual(["evidence:E3"]);
  });
});

describe("special investigation views", () => {
  it("shows threat findings with their immediate evidence context", () => {
    const view = buildThreatView(sample());
    expect(view.nodes.map((item) => item.id)).toContain("url:BAD");
    expect(view.nodes.map((item) => item.id)).toContain("evidence:E1");
    expect(view.edges.map((item) => item.edge_type)).toContain("threat_relationship");
  });

  it("shows cross-case findings and contextual case/evidence nodes", () => {
    const graph = sample();
    graph.nodes.push(node("case:CASE_2", "case"), node("evidence:OTHER", "evidence"));
    graph.edges.push(
      edge("case:CASE_1", "case:CASE_2", "cross_case_relationship"),
      edge("case:CASE_2", "evidence:OTHER", "contains"),
    );

    const view = buildCrossCaseView(graph);
    expect(view.nodes.map((item) => item.id)).toContain("case:CASE_2");
    expect(view.nodes.map((item) => item.id)).toContain("evidence:OTHER");
  });
});

describe("complete artifact search", () => {
  it("finds hidden properties and adds one contextual hop", () => {
    const view = buildSearchGraphView(sample(), "bank.png");
    expect(view.matches.map((item) => item.id)).toEqual(["evidence:E1"]);
    expect(view.nodes.map((item) => item.id)).toContain("wallet:W1");
    expect(view.edges.length).toBeGreaterThan(0);
  });

  it("returns an explicit empty result", () => {
    const view = buildSearchGraphView(sample(), "does-not-exist");
    expect(view.matches).toHaveLength(0);
    expect(view.nodes).toHaveLength(0);
  });
});

describe("relationship filters", () => {
  it("distinguishes actual, inferred, and unresolved timestamps", () => {
    const actual = edge("a", "b", "linked_to", { timestamp: "2026-01-01", timestamp_inferred: false });
    const inferred = edge("a", "b", "linked_to", { timestamp: "2026-01-01", timestamp_inferred: true });
    const unresolved = edge("a", "b", "linked_to");

    expect(edgePassesRelationshipFilters(actual, { timestampFilter: "actual" })).toBe(true);
    expect(edgePassesRelationshipFilters(inferred, { timestampFilter: "inferred" })).toBe(true);
    expect(edgePassesRelationshipFilters(unresolved, { timestampFilter: "unresolved" })).toBe(true);
  });

  it("removes selected relationship types without mutating the artifact", () => {
    const graph = sample();
    const result = filterGraphRelationships(graph, {
      hiddenEdgeTypes: new Set(["contains"]),
    });
    expect(result.graph.edges.some((item) => item.edge_type === "contains")).toBe(false);
    expect(graph.edges.some((item) => item.edge_type === "contains")).toBe(true);
  });
});
