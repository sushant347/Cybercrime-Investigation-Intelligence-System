import type { GraphEdge, GraphNode, RelationshipGraph } from "@/types";

import { confidenceOf, isUploadBatchEdge } from "./relevance";

export type GraphMode = "evidence" | "entities" | "cross_case" | "threats" | "full";
export type TimestampFilter = "all" | "actual" | "inferred" | "unresolved";

export const GRAPH_MODES: {
  value: GraphMode;
  label: string;
  hint: string;
}[] = [
  {
    value: "evidence",
    label: "Evidence map",
    hint: "One node per evidence item and one combined link per related pair",
  },
  {
    value: "entities",
    label: "Entity map",
    hint: "Evidence and the phones, accounts, wallets, URLs and other entities it contains",
  },
  {
    value: "cross_case",
    label: "Cross-case",
    hint: "Only findings that connect this case to another case",
  },
  {
    value: "threats",
    label: "Threats",
    hint: "Threat-intelligence hits and the evidence that contains them",
  },
  {
    value: "full",
    label: "Full graph",
    hint: "The complete technical artifact, intended for advanced review",
  },
];

export interface RelationshipFilterOptions {
  hiddenEdgeTypes?: Set<string>;
  timestampFilter?: TimestampFilter;
}

export interface DisplayGraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hiddenNodes: number;
  hiddenEdges: number;
  message?: string;
}

const STRUCTURAL_NODE_TYPES = new Set(["case", "evidence"]);
const MIRRORED_NODE_TYPES = new Set(["timeline_event"]);
const CROSS_CASE_EDGE_TYPES = new Set([
  "cross_case_entity_match",
  "cross_case_relationship",
  "cross_case",
]);
const THREAT_EDGE_TYPES = new Set(["threat_relationship"]);
const PROJECTION_NOISE_TYPES = new Set(["date", "time", "money", "amount", "otp", "keyword"]);

function graphImportance(node: GraphNode | undefined): number {
  return Number(node?.properties.graph_importance ?? 0) || 0;
}

export function pairKey(a: string, b: string): string {
  return [a, b].sort().join("|");
}

export function edgePassesRelationshipFilters(
  edge: GraphEdge,
  {
    hiddenEdgeTypes = new Set<string>(),
    timestampFilter = "all",
  }: RelationshipFilterOptions = {},
): boolean {
  if (hiddenEdgeTypes.has(edge.edge_type)) return false;
  if (timestampFilter === "all") return true;
  if (timestampFilter === "actual") {
    return Boolean(edge.timestamp) && !edge.timestamp_inferred;
  }
  if (timestampFilter === "inferred") return Boolean(edge.timestamp_inferred);
  return !edge.timestamp;
}

export function filterGraphRelationships(
  graph: RelationshipGraph,
  options: RelationshipFilterOptions,
): { graph: RelationshipGraph; hiddenEdges: number } {
  const edges = graph.edges.filter((edge) =>
    edgePassesRelationshipFilters(edge, options),
  );
  return {
    graph: { ...graph, edges },
    hiddenEdges: graph.edges.length - edges.length,
  };
}

interface AggregateAccumulator {
  source: string;
  target: string;
  relationshipTypes: Set<string>;
  entityIds: Set<string>;
  sourceEdgeIndexes: Set<number>;
  confidences: number[];
  explanations: string[];
  timestamps: string[];
  hasInferredTimestamp: boolean;
}

function localEvidenceIds(graph: RelationshipGraph): string[] {
  const caseId = `case:${graph.case_id}`;
  const fromContainment = graph.edges
    .filter((edge) => edge.edge_type === "contains" && edge.source === caseId)
    .map((edge) => edge.target)
    .filter((id) => id.startsWith("evidence:"));
  if (fromContainment.length > 0) return [...new Set(fromContainment)];
  return graph.nodes
    .filter(
      (node) =>
        node.node_type === "evidence" &&
        (!node.properties.case_id || node.properties.case_id === graph.case_id),
    )
    .map((node) => node.id);
}

function addContribution(
  aggregates: Map<string, AggregateAccumulator>,
  a: string,
  b: string,
  edge: GraphEdge,
  edgeIndex: number,
  entityId?: string,
) {
  if (a === b) return;
  const [source, target] = [a, b].sort();
  const key = pairKey(source, target);
  let aggregate = aggregates.get(key);
  if (!aggregate) {
    aggregate = {
      source,
      target,
      relationshipTypes: new Set(),
      entityIds: new Set(),
      sourceEdgeIndexes: new Set(),
      confidences: [],
      explanations: [],
      timestamps: [],
      hasInferredTimestamp: false,
    };
    aggregates.set(key, aggregate);
  }
  aggregate.relationshipTypes.add(edge.edge_type);
  if (entityId) aggregate.entityIds.add(entityId);
  aggregate.sourceEdgeIndexes.add(edgeIndex);
  aggregate.confidences.push(confidenceOf(edge));
  if (edge.explanation) aggregate.explanations.push(edge.explanation);
  if (edge.timestamp) aggregate.timestamps.push(edge.timestamp);
  aggregate.hasInferredTimestamp ||= Boolean(edge.timestamp_inferred);
}

/**
 * Project the complete bipartite graph into an investigator-friendly evidence
 * map. Repeated entities and direct correlations become one evidence-pair
 * link; expanding a pair restores its underlying entity nodes and edges.
 */
export function buildEvidenceProjection(
  graph: RelationshipGraph,
  {
    expandedPairs = new Set<string>(),
    minimumConfidence = 0,
    includeUploadBatch = false,
    evidenceBudget = 120,
  }: {
    expandedPairs?: Set<string>;
    minimumConfidence?: number;
    includeUploadBatch?: boolean;
    evidenceBudget?: number;
  } = {},
): DisplayGraphView {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const localIds = new Set(localEvidenceIds(graph));
  const liveEdges = graph.edges
    .map((edge, index) => ({ edge, index }))
    .filter(({ edge }) => includeUploadBatch || !isUploadBatchEdge(edge))
    .filter(({ edge }) => confidenceOf(edge) >= minimumConfidence);

  const aggregates = new Map<string, AggregateAccumulator>();

  // Direct evidence-to-evidence findings such as behavioural and temporal links.
  for (const { edge, index } of liveEdges) {
    if (localIds.has(edge.source) && localIds.has(edge.target)) {
      addContribution(aggregates, edge.source, edge.target, edge, index);
    }
  }

  // Shared entity nodes produce evidence pairs. One entity appearing in five
  // documents contributes to each of the ten evidence relationships it proves.
  for (const entity of graph.nodes) {
    if (STRUCTURAL_NODE_TYPES.has(entity.node_type) || MIRRORED_NODE_TYPES.has(entity.node_type)) {
      continue;
    }
    // Dates, times, round amounts and OTP-shaped values may legitimately be
    // stored as entities, but sharing one must not create an evidence-pair
    // relationship in the investigator's default map.
    if (PROJECTION_NOISE_TYPES.has(entity.node_type)) continue;
    const mentions = liveEdges.filter(
      ({ edge }) =>
        (edge.source === entity.id && localIds.has(edge.target)) ||
        (edge.target === entity.id && localIds.has(edge.source)),
    );
    const evidence = [...new Set(mentions.map(({ edge }) =>
      localIds.has(edge.source) ? edge.source : edge.target,
    ))];
    for (let i = 0; i < evidence.length; i += 1) {
      for (let j = i + 1; j < evidence.length; j += 1) {
        const contributions = mentions.filter(({ edge }) =>
          [evidence[i], evidence[j]].some(
            (evidenceId) => edge.source === evidenceId || edge.target === evidenceId,
          ),
        );
        for (const { edge, index } of contributions) {
          addContribution(
            aggregates,
            evidence[i],
            evidence[j],
            edge,
            index,
            entity.id,
          );
        }
      }
    }
  }

  const evidenceDegree = new Map<string, number>();
  for (const aggregate of aggregates.values()) {
    evidenceDegree.set(aggregate.source, (evidenceDegree.get(aggregate.source) ?? 0) + 1);
    evidenceDegree.set(aggregate.target, (evidenceDegree.get(aggregate.target) ?? 0) + 1);
  }
  const rankedEvidence = [...localIds].sort((a, b) => {
    const importanceDifference =
      graphImportance(byId.get(b)) - graphImportance(byId.get(a));
    if (importanceDifference !== 0) return importanceDifference;
    return (evidenceDegree.get(b) ?? 0) - (evidenceDegree.get(a) ?? 0) ||
      a.localeCompare(b);
  });
  const visibleEvidenceIds = new Set(rankedEvidence.slice(0, evidenceBudget));
  const nodes = graph.nodes.filter(
    (node) => node.node_type === "evidence" && visibleEvidenceIds.has(node.id),
  );
  const edges: GraphEdge[] = [];

  for (const [key, aggregate] of aggregates) {
    if (!visibleEvidenceIds.has(aggregate.source) || !visibleEvidenceIds.has(aggregate.target)) {
      continue;
    }
    const entityIds = [...aggregate.entityIds];
    const types = [...aggregate.relationshipTypes].sort();
    const confidence = aggregate.confidences.length
      ? aggregate.confidences.reduce((sum, value) => sum + value, 0) /
        aggregate.confidences.length
      : 1;
    const relationshipCount = Math.max(
      types.length,
      entityIds.length + types.filter((type) => type !== "shared_entity").length,
    );
    edges.push({
      source: aggregate.source,
      target: aggregate.target,
      edge_type: "evidence_relationship",
      weight: Math.max(1, relationshipCount),
      confidence,
      source_evidence_ids: [
        aggregate.source.replace(/^evidence:/, ""),
        aggregate.target.replace(/^evidence:/, ""),
      ],
      timestamp: aggregate.timestamps.sort()[0] ?? "",
      timestamp_source: aggregate.timestamps.length ? "aggregated" : "unresolved",
      timestamp_inferred: aggregate.hasInferredTimestamp,
      explanation: `${relationshipCount} finding${relationshipCount === 1 ? "" : "s"} connect these evidence items`,
      projection: {
        pair_key: key,
        relationship_count: relationshipCount,
        relationship_types: types,
        entity_ids: entityIds,
        source_edge_indexes: [...aggregate.sourceEdgeIndexes].sort((a, b) => a - b),
      },
    });

    if (expandedPairs.has(key)) {
      for (const entityId of entityIds) {
        const entity = byId.get(entityId);
        if (entity && !nodes.some((node) => node.id === entity.id)) nodes.push(entity);
      }
      for (const { edge } of liveEdges) {
        if (!entityIds.includes(edge.source) && !entityIds.includes(edge.target)) continue;
        const endpoints = new Set([edge.source, edge.target]);
        if (
          endpoints.has(aggregate.source) ||
          endpoints.has(aggregate.target)
        ) {
          edges.push(edge);
        }
      }
    }
  }

  return {
    nodes,
    edges,
    hiddenNodes: Math.max(0, localIds.size - visibleEvidenceIds.size),
    hiddenEdges: Math.max(0, graph.edges.length - liveEdges.length),
    message: `${aggregates.size} evidence relationship${aggregates.size === 1 ? "" : "s"} summarised from the complete graph`,
  };
}

function buildFlaggedView(
  graph: RelationshipGraph,
  edgeTypes: Set<string>,
  minimumConfidence: number,
  contextEdgeTypes: Set<string>,
): DisplayGraphView {
  const seedEdges = graph.edges.filter(
    (edge) => edgeTypes.has(edge.edge_type) && confidenceOf(edge) >= minimumConfidence,
  );
  const visibleIds = new Set<string>();
  seedEdges.forEach((edge) => {
    visibleIds.add(edge.source);
    visibleIds.add(edge.target);
  });

  // Add one contextual hop so a flagged entity is shown beside its evidence
  // and an external evidence item is shown beside its case.
  const contextEdges = graph.edges.filter((edge) => {
    if (confidenceOf(edge) < minimumConfidence) return false;
    if (!contextEdgeTypes.has(edge.edge_type)) return false;
    return visibleIds.has(edge.source) || visibleIds.has(edge.target);
  });
  contextEdges.forEach((edge) => {
    visibleIds.add(edge.source);
    visibleIds.add(edge.target);
  });
  const edges = graph.edges.filter(
    (edge) =>
      visibleIds.has(edge.source) &&
      visibleIds.has(edge.target) &&
      (edgeTypes.has(edge.edge_type) || contextEdges.includes(edge)),
  );

  return {
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges,
    hiddenNodes: graph.nodes.length - visibleIds.size,
    hiddenEdges: graph.edges.length - edges.length,
  };
}

export function buildCrossCaseView(
  graph: RelationshipGraph,
  minimumConfidence = 0,
): DisplayGraphView {
  return buildFlaggedView(
    graph,
    CROSS_CASE_EDGE_TYPES,
    minimumConfidence,
    new Set(["contains", "shared_entity"]),
  );
}

export function buildThreatView(
  graph: RelationshipGraph,
  minimumConfidence = 0,
): DisplayGraphView {
  return buildFlaggedView(
    graph,
    THREAT_EDGE_TYPES,
    minimumConfidence,
    new Set(["contains"]),
  );
}

export interface SearchGraphView extends DisplayGraphView {
  matches: GraphNode[];
}

/** Search the complete artifact and reveal matches plus one contextual hop. */
export function buildSearchGraphView(
  graph: RelationshipGraph,
  query: string,
  {
    minimumConfidence = 0,
    resultBudget = 12,
    nodeBudget = 80,
  }: {
    minimumConfidence?: number;
    resultBudget?: number;
    nodeBudget?: number;
  } = {},
): SearchGraphView {
  const q = query.trim().toLowerCase();
  if (!q) {
    return { nodes: [], edges: [], matches: [], hiddenNodes: 0, hiddenEdges: 0 };
  }
  const matches = graph.nodes
    .filter((node) =>
      [node.id, node.label, ...Object.values(node.properties)].some((value) =>
        String(value ?? "").toLowerCase().includes(q),
      ),
    )
    .slice(0, resultBudget);
  const visibleIds = new Set(matches.map((node) => node.id));
  const candidateEdges = graph.edges
    .filter((edge) => confidenceOf(edge) >= minimumConfidence)
    .filter((edge) => visibleIds.has(edge.source) || visibleIds.has(edge.target));
  for (const edge of candidateEdges) {
    if (visibleIds.size >= nodeBudget) break;
    visibleIds.add(edge.source);
    visibleIds.add(edge.target);
  }
  const edges = candidateEdges.filter(
    (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
  );
  return {
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges,
    matches,
    hiddenNodes: Math.max(0, graph.nodes.length - visibleIds.size),
    hiddenEdges: Math.max(0, graph.edges.length - edges.length),
    message: matches.length
      ? `${matches.length} matching item${matches.length === 1 ? "" : "s"} found in the complete artifact`
      : "No matching item in the complete artifact",
  };
}
