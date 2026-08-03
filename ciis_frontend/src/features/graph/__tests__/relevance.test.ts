import { describe, expect, it } from "vitest";

import type { GraphEdge, GraphNode, RelationshipGraph } from "@/types";

import { buildGraphView, isUploadBatchEdge } from "../relevance";

const node = (id: string, node_type: string): GraphNode => ({
  id,
  node_type,
  label: id.split(":").slice(1).join(":") || id,
  properties: {},
});

const edge = (
  source: string,
  target: string,
  edge_type: string,
  over: Partial<GraphEdge> = {},
): GraphEdge => ({
  source,
  target,
  edge_type,
  weight: 1,
  explanation: "",
  ...over,
});

const graph = (nodes: GraphNode[], edges: GraphEdge[]): RelationshipGraph => ({
  case_id: "CASE_1",
  directed: false,
  nodes,
  edges,
});

/**
 * A miniature of the shape a real case takes: a case, three pieces of
 * evidence, one wallet seen in two of them (the lead), one phone seen in only
 * one (detail), a date (low identity), a mirrored timeline event, and the
 * upload-batch temporal edges the engine emits for every co-uploaded pair.
 */
function sample() {
  return graph(
    [
      node("case:CASE_1", "case"),
      node("evidence:EVID_1", "evidence"),
      node("evidence:EVID_2", "evidence"),
      node("evidence:EVID_3", "evidence"),
      node("wallet:9800000000", "wallet"),
      node("phone:9811111111", "phone_number"),
      node("date:10 june 2026", "date"),
      node("timeline_event:T1", "timeline_event"),
    ],
    [
      edge("case:CASE_1", "evidence:EVID_1", "contains"),
      edge("case:CASE_1", "evidence:EVID_2", "contains"),
      edge("case:CASE_1", "evidence:EVID_3", "contains"),
      edge("evidence:EVID_1", "wallet:9800000000", "shared_entity"),
      edge("evidence:EVID_2", "wallet:9800000000", "shared_entity"),
      edge("evidence:EVID_1", "phone:9811111111", "shared_entity"),
      edge("evidence:EVID_3", "date:10 june 2026", "shared_entity"),
      edge("evidence:EVID_1", "timeline_event:T1", "timeline_event"),
      edge("evidence:EVID_1", "evidence:EVID_2", "temporal_relationship", {
        timestamp_source: "upload_time_fallback",
      }),
      edge("evidence:EVID_2", "evidence:EVID_3", "temporal_relationship", {
        timestamp_source: "upload_time_fallback",
      }),
      edge("evidence:EVID_1", "evidence:EVID_3", "temporal_relationship", {
        timestamp_source: "content_time_only",
      }),
    ],
  );
}

const ids = (view: { nodes: GraphNode[] }) => view.nodes.map((n) => n.id).sort();

describe("buildGraphView", () => {
  it("keeps entities that bridge evidence and defers those that do not", () => {
    const view = buildGraphView(sample(), { density: "leads" });

    expect(ids(view)).toEqual([
      "case:CASE_1",
      "evidence:EVID_1",
      "evidence:EVID_2",
      "evidence:EVID_3",
      "wallet:9800000000", // seen in two pieces of evidence
    ]);
    // The single-mention phone and date are deferred, not lost.
    expect(view.hidden.singleMention).toBe(2);
    expect(view.totals.nodes).toBe(8);
  });

  it("keeps identifying one-offs at standard density but not bare dates", () => {
    const view = buildGraphView(sample(), { density: "standard" });

    expect(ids(view)).toContain("phone:9811111111");
    expect(ids(view)).not.toContain("date:10 june 2026");
    expect(view.hidden.lowIdentity).toBe(1);
  });

  it("draws the complete artifact at full density", () => {
    const view = buildGraphView(sample(), { density: "full" });
    expect(view.nodes).toHaveLength(8);
    expect(view.hidden.total).toBe(0);
  });

  it("leaves timeline events to the timeline tab", () => {
    const view = buildGraphView(sample(), { density: "standard" });
    expect(ids(view)).not.toContain("timeline_event:T1");
    expect(view.hidden.mirrored).toBe(1);
  });

  it("drops 'uploaded in the same batch' links but keeps real temporal ones", () => {
    const view = buildGraphView(sample(), { density: "full" });

    const temporal = view.edges.filter((e) => e.edge_type === "temporal_relationship");
    expect(temporal).toHaveLength(1);
    expect(temporal[0].timestamp_source).toBe("content_time_only");
    expect(view.uploadBatchEdges).toBe(2);
  });

  it("puts the upload-batch links back when asked", () => {
    const view = buildGraphView(sample(), {
      density: "full",
      includeUploadBatch: true,
    });
    expect(view.edges.filter((e) => e.edge_type === "temporal_relationship")).toHaveLength(3);
  });

  it("promotes a single-mention entity the engine flagged as a threat", () => {
    const g = sample();
    g.edges.push(edge("evidence:EVID_1", "phone:9811111111", "threat_relationship"));

    const view = buildGraphView(g, { density: "leads" });
    expect(ids(view)).toContain("phone:9811111111");
    expect(view.signals.get("phone:9811111111")?.threat).toBe(true);
  });

  it("promotes an identifying entity seen in another case", () => {
    const g = sample();
    g.edges.push(edge("evidence:EVID_1", "phone:9811111111", "cross_case_entity_match"));

    const view = buildGraphView(g, { density: "leads" });
    expect(ids(view)).toContain("phone:9811111111");
    expect(view.signals.get("phone:9811111111")?.crossCase).toBe(true);
  });

  it("does not treat a date shared with another case as a lead", () => {
    const g = sample();
    // Two cases mentioning "10 June 2026" is a coincidence, not a link — and
    // the engine emits a cross-case match for it all the same.
    g.edges.push(edge("evidence:EVID_3", "date:10 june 2026", "cross_case_entity_match"));

    const view = buildGraphView(g, { density: "leads" });
    expect(ids(view)).not.toContain("date:10 june 2026");
  });

  it("never draws an edge whose endpoint was deferred", () => {
    const view = buildGraphView(sample(), { density: "leads" });
    const drawn = new Set(view.nodes.map((n) => n.id));
    for (const e of view.edges) {
      expect(drawn.has(e.source)).toBe(true);
      expect(drawn.has(e.target)).toBe(true);
    }
  });

  it("caps a case too large for one screen, keeping the best-connected", () => {
    const nodes = [node("case:CASE_1", "case"), node("evidence:EVID_1", "evidence")];
    const edges: GraphEdge[] = [edge("case:CASE_1", "evidence:EVID_1", "contains")];
    // 30 wallets, each shared with a second piece of evidence so all qualify
    // as leads; the last one is shared far more widely than the rest.
    for (let i = 0; i < 30; i += 1) {
      nodes.push(node(`evidence:E${i}`, "evidence"));
      nodes.push(node(`wallet:W${i}`, "wallet"));
      edges.push(edge("evidence:EVID_1", `wallet:W${i}`, "shared_entity"));
      edges.push(edge(`evidence:E${i}`, `wallet:W${i}`, "shared_entity"));
    }
    nodes.push(node("wallet:HUB", "wallet"));
    for (let i = 0; i < 30; i += 1) {
      edges.push(edge(`evidence:E${i}`, "wallet:HUB", "shared_entity"));
    }

    const view = buildGraphView(graph(nodes, edges), { density: "leads", budget: 20 });

    expect(view.nodes).toHaveLength(20);
    expect(view.capped).toBe(true);
    expect(view.hidden.overBudget).toBe(nodes.length - 20);
    // The most widely shared wallet must survive the cap — it is the finding.
    expect(view.nodes.map((n) => n.id)).toContain("wallet:HUB");
  });

  it("honours the legend's type filters", () => {
    const view = buildGraphView(sample(), {
      density: "full",
      hiddenTypes: new Set(["wallet"]),
    });
    expect(ids(view)).not.toContain("wallet:9800000000");
    expect(view.hidden.byTypeFilter).toBe(1);
  });

  it("counts evidence reach so the panel can explain why an item is shown", () => {
    const view = buildGraphView(sample(), { density: "standard" });
    expect(view.signals.get("wallet:9800000000")?.evidenceReach).toBe(2);
    expect(view.signals.get("phone:9811111111")?.evidenceReach).toBe(1);
  });
});

describe("isUploadBatchEdge", () => {
  it("only matches temporal edges built from the upload-time fallback", () => {
    expect(
      isUploadBatchEdge(
        edge("a", "b", "temporal_relationship", { timestamp_source: "upload_time_fallback" }),
      ),
    ).toBe(true);
    expect(
      isUploadBatchEdge(
        edge("a", "b", "temporal_relationship", { timestamp_source: "content_time_only" }),
      ),
    ).toBe(false);
    expect(
      isUploadBatchEdge(
        edge("a", "b", "shared_entity", { timestamp_source: "upload_time_fallback" }),
      ),
    ).toBe(false);
  });
});
