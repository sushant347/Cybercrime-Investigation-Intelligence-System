import type { GraphEdge, GraphNode, RelationshipGraph } from "@/types";

/**
 * Relevance model for the relationship graph.
 *
 * The engine emits *everything* it found. That is correct for an artifact —
 * nothing should be thrown away on disk — but it is not a picture. Eight
 * uploads already produce ~80 nodes and ~230 edges; fifty uploads produce a
 * hairball in which the one wallet address that ties the case together is
 * indistinguishable from a date string OCR'd out of a letterhead.
 *
 * So the canvas renders a *view* of the artifact, chosen by one rule:
 *
 *     the graph's job is to show what CONNECTS evidence.
 *
 * An entity mentioned in a single piece of evidence connects nothing — it is
 * a property of that evidence, and the evidence detail page is where it
 * belongs. An entity mentioned in two or more is a lead. That single rule
 * removes roughly half the nodes in a real case without losing one link.
 *
 * Nothing here mutates the artifact, and every hidden item is counted and
 * reported to the investigator — a forensic tool must never quietly drop
 * evidence, only defer it.
 */

/** How much of the artifact to draw. */
export type Density = "leads" | "standard" | "full";

export const DENSITY_LABELS: {
  value: Density;
  label: string;
  hint: string;
}[] = [
  {
    value: "leads",
    label: "Leads",
    hint: "Only entities that appear in two or more pieces of evidence, plus anything threat-flagged or seen in another case — the things that actually link this case together.",
  },
  {
    value: "standard",
    label: "Standard",
    hint: "Leads plus every identifying entity (phones, emails, wallets, accounts, domains). Hides one-off dates, times and amounts.",
  },
  {
    value: "full",
    label: "Everything",
    hint: "The complete stored artifact, including single-mention detail. Expect a dense picture on a large case.",
  },
];

/** Structural roles — the skeleton of the case, never filtered out. */
export const STRUCTURAL_TYPES = ["case", "evidence"] as const;

/**
 * Entity types with no identity of their own. A date read off a document is
 * not a suspect; two documents sharing "10 June 2026" are not connected in
 * any meaningful sense. Kept when they genuinely bridge evidence, dropped
 * from the default view otherwise.
 */
const LOW_IDENTITY_TYPES = new Set(["date", "time", "money", "amount", "keyword"]);

/**
 * Types with no identity whatsoever. Two cases sharing "10 June 2026" or the
 * word "urgent" is a coincidence, not a link, so a cross-case match on one of
 * these must not promote it to a lead the way a shared wallet address does.
 * Only a threat flag or genuine reach across several pieces of evidence will.
 */
const NO_IDENTITY_TYPES = new Set(["date", "time", "keyword"]);

/**
 * Timeline events are already the entire subject of the Timeline tab, drawn
 * there on a real time axis. Repeating them here as unlabelled hexagons adds
 * a node and an edge per event and explains nothing the other tab does not
 * explain better.
 */
const MIRRORED_TYPES = new Set(["timeline_event"]);

/** Edges that promote a node to a lead regardless of how many evidence it touches. */
const THREAT_EDGES = new Set(["threat_relationship"]);
const CROSS_CASE_EDGES = new Set(["cross_case_entity_match", "cross_case_relationship"]);

/**
 * A `temporal_relationship` derived from `upload_time_fallback` says the two
 * files were *uploaded* in the same batch — an artifact of the investigator's
 * own workflow, not of the crime. It is emitted for pairs, so it grows
 * quadratically with the upload count and is the single largest source of
 * meaningless line-crossing on a big case. Temporal edges built from a real
 * timestamp found *inside* the evidence are kept: those are findings.
 */
export function isUploadBatchEdge(edge: GraphEdge): boolean {
  return (
    edge.edge_type === "temporal_relationship" &&
    edge.timestamp_source === "upload_time_fallback"
  );
}

/** Per-node signals used for scoring and for the "why is this here" caption. */
export interface NodeSignals {
  /** Distinct pieces of evidence this node is connected to. */
  evidenceReach: number;
  /** Total edges (after noise removal). */
  degree: number;
  /** Touched by a threat_relationship edge. */
  threat: boolean;
  /** Seen in at least one other case. */
  crossCase: boolean;
  /** Backend NetworkX importance score, when present in a regenerated artifact. */
  backendImportance: number;
  communityId: string;
  /** Ranking score; higher is more worth drawing. */
  score: number;
}

export interface GraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  signals: Map<string, NodeSignals>;
  /** Nodes present in the artifact but not drawn, by reason. */
  hidden: {
    singleMention: number;
    lowIdentity: number;
    mirrored: number;
    overBudget: number;
    byTypeFilter: number;
    total: number;
  };
  /** Edges dropped as upload-batch noise. */
  uploadBatchEdges: number;
  /** Edges below the investigator's selected confidence threshold. */
  belowConfidenceEdges: number;
  /** True when the budget cap trimmed the view. */
  capped: boolean;
  /** Totals from the untouched artifact, for honest "showing X of Y" copy. */
  totals: { nodes: number; edges: number };
}

/**
 * Above this many drawn nodes no layout is readable at 560px tall, so the
 * lowest-scoring entities are held back rather than drawn into a smear. The
 * investigator is told the count and can lift it with the density control.
 */
export const NODE_BUDGET = 140;

/**
 * A consistent confidence value for presentation-side filtering.
 *
 * New artifacts carry an explicit confidence. Older artifacts only have a
 * normalised weight, so retain that as a backwards-compatible fallback. A
 * count-like weight above one is not a low-confidence relationship.
 */
export function confidenceOf(edge: GraphEdge): number {
  if (edge.confidence !== undefined) return edge.confidence;
  return edge.weight <= 1 ? edge.weight : 1;
}

/**
 * Score a node for the "which of these do I draw" decision.
 *
 * Reach across evidence dominates everything else: an entity in five
 * documents is the spine of the case. Threat and cross-case flags are strong
 * additive boosts because they are the engine telling us it already found
 * something. Low-identity types are damped so a date never outranks a wallet
 * at equal reach.
 */
function scoreOf(
  type: string,
  reach: number,
  degree: number,
  threat: boolean,
  crossCase: boolean,
  backendImportance: number,
): number {
  if (type === "case") return 1e6;
  if (type === "evidence") return 1e5;
  let score = reach * 100 + degree * 4;
  if (threat) score += 400;
  if (crossCase) score += 250;
  score += backendImportance * 600;
  if (LOW_IDENTITY_TYPES.has(type)) score *= 0.35;
  return score;
}

/**
 * Reduce the stored artifact to the view to draw.
 *
 * @param hiddenTypes  node types the investigator switched off in the legend
 * @param includeUploadBatch  keep the upload-batch temporal edges
 */
export function buildGraphView(
  graph: RelationshipGraph,
  {
    density,
    hiddenTypes = new Set<string>(),
    includeUploadBatch = false,
    minimumConfidence = 0,
    budget = NODE_BUDGET,
  }: {
    density: Density;
    hiddenTypes?: Set<string>;
    includeUploadBatch?: boolean;
    minimumConfidence?: number;
    budget?: number;
  },
): GraphView {
  const totals = { nodes: graph.nodes.length, edges: graph.edges.length };
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const typeOf = (id: string) => byId.get(id)?.node_type ?? "";

  // ------------------------------------------------------------ edge pass
  const uploadBatch = graph.edges.filter(isUploadBatchEdge);
  const withoutUploadNoise = includeUploadBatch
    ? graph.edges
    : graph.edges.filter((e) => !isUploadBatchEdge(e));
  const belowConfidenceEdges = withoutUploadNoise.filter(
    (edge) => confidenceOf(edge) < minimumConfidence,
  ).length;
  const liveEdges = withoutUploadNoise.filter(
    (edge) => confidenceOf(edge) >= minimumConfidence,
  );

  // ----------------------------------------------------------- node signals
  const reach = new Map<string, Set<string>>();
  const degree = new Map<string, number>();
  const threat = new Set<string>();
  const crossCase = new Set<string>();

  const touch = (id: string, otherId: string) => {
    degree.set(id, (degree.get(id) ?? 0) + 1);
    if (typeOf(otherId) === "evidence") {
      let set = reach.get(id);
      if (!set) reach.set(id, (set = new Set()));
      set.add(otherId);
    }
  };

  for (const edge of liveEdges) {
    touch(edge.source, edge.target);
    touch(edge.target, edge.source);
    if (THREAT_EDGES.has(edge.edge_type)) {
      threat.add(edge.source);
      threat.add(edge.target);
    }
    if (CROSS_CASE_EDGES.has(edge.edge_type)) {
      crossCase.add(edge.source);
      crossCase.add(edge.target);
    }
  }

  const signals = new Map<string, NodeSignals>();
  for (const node of graph.nodes) {
    const r = reach.get(node.id)?.size ?? 0;
    const d = degree.get(node.id) ?? 0;
    const t = threat.has(node.id);
    const c = crossCase.has(node.id);
    const backendImportance = Number(node.properties.graph_importance ?? 0) || 0;
    signals.set(node.id, {
      evidenceReach: r,
      degree: d,
      threat: t,
      crossCase: c,
      backendImportance,
      communityId: node.properties.community_id ?? "",
      score: scoreOf(node.node_type, r, d, t, c, backendImportance),
    });
  }

  // ------------------------------------------------------------ node pass
  const hidden = {
    singleMention: 0,
    lowIdentity: 0,
    mirrored: 0,
    overBudget: 0,
    byTypeFilter: 0,
    total: 0,
  };

  const kept: GraphNode[] = [];
  for (const node of graph.nodes) {
    const sig = signals.get(node.id)!;
    const type = node.node_type;

    if (hiddenTypes.has(type)) {
      hidden.byTypeFilter += 1;
      continue;
    }
    if (density === "full") {
      kept.push(node);
      continue;
    }
    if ((STRUCTURAL_TYPES as readonly string[]).includes(type)) {
      kept.push(node);
      continue;
    }
    if (MIRRORED_TYPES.has(type)) {
      hidden.mirrored += 1;
      continue;
    }

    // A lead: bridges evidence, or the engine already flagged it.
    const isLead =
      sig.evidenceReach >= 2 ||
      sig.threat ||
      (sig.crossCase && !NO_IDENTITY_TYPES.has(type));
    if (isLead) {
      kept.push(node);
      continue;
    }
    if (density === "leads") {
      hidden.singleMention += 1;
      continue;
    }
    // "standard": keep identifying one-offs, drop dates/times/amounts.
    if (LOW_IDENTITY_TYPES.has(type)) {
      hidden.lowIdentity += 1;
      continue;
    }
    kept.push(node);
  }

  // ---------------------------------------------------------- budget cap
  //
  // Ranking purely by score would fill the budget with the case skeleton:
  // a hundred-upload case has a hundred evidence nodes, all of which outrank
  // every entity by construction, and the view would be a hundred documents
  // and nothing joining them — precisely backwards. So the skeleton gets a
  // share of the budget rather than first refusal, and each side hands back
  // whatever it does not need.
  const STRUCTURAL_SHARE = 0.6;
  let visible = kept;
  let capped = false;
  if (kept.length > budget) {
    capped = true;
    const byScore = (a: GraphNode, b: GraphNode) =>
      signals.get(b.id)!.score - signals.get(a.id)!.score;
    const structural = kept
      .filter((n) => (STRUCTURAL_TYPES as readonly string[]).includes(n.node_type))
      .sort(byScore);
    const entities = kept
      .filter((n) => !(STRUCTURAL_TYPES as readonly string[]).includes(n.node_type))
      .sort(byScore);

    const structuralSlots = Math.min(
      structural.length,
      Math.max(1, Math.round(budget * STRUCTURAL_SHARE)),
    );
    const entitySlots = Math.min(entities.length, budget - structuralSlots);
    // Give the skeleton any slots the entities left on the table.
    const finalStructuralSlots = Math.min(structural.length, budget - entitySlots);

    visible = [
      ...structural.slice(0, finalStructuralSlots),
      ...entities.slice(0, entitySlots),
    ];
    hidden.overBudget = kept.length - visible.length;
  }

  const visibleIds = new Set(visible.map((n) => n.id));
  const edges = liveEdges.filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
  );

  hidden.total =
    hidden.singleMention +
    hidden.lowIdentity +
    hidden.mirrored +
    hidden.overBudget +
    hidden.byTypeFilter;

  return {
    nodes: visible,
    edges,
    signals,
    hidden,
    uploadBatchEdges: uploadBatch.length,
    belowConfidenceEdges,
    capped,
    totals,
  };
}

export interface NeighborhoodView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Direct neighbours before the readable focus cap is applied. */
  totalNeighbors: number;
  /** Direct neighbours omitted by filters or the readable focus cap. */
  hiddenNeighbors: number;
}

/**
 * Build a small, one-hop investigation view around a selected item.
 *
 * This is progressive disclosure rather than a new finding: all nodes and
 * relationships still come from the stored graph. Focusing evidence reveals
 * its single-mention entities too, while mirrored timeline events remain on
 * the Timeline tab where their ordering is meaningful.
 */
export function buildNeighborhoodView(
  graph: RelationshipGraph,
  focusNodeId: string,
  {
    hiddenTypes = new Set<string>(),
    includeUploadBatch = false,
    minimumConfidence = 0,
    budget = 60,
  }: {
    hiddenTypes?: Set<string>;
    includeUploadBatch?: boolean;
    minimumConfidence?: number;
    budget?: number;
  } = {},
): NeighborhoodView {
  const focus = graph.nodes.find((node) => node.id === focusNodeId);
  if (!focus) {
    return { nodes: [], edges: [], totalNeighbors: 0, hiddenNeighbors: 0 };
  }

  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const signalView = buildGraphView(graph, {
    density: "full",
    includeUploadBatch,
    minimumConfidence,
    budget: Math.max(graph.nodes.length, 1),
  });

  const incident = graph.edges.filter((edge) => {
    if (edge.source !== focusNodeId && edge.target !== focusNodeId) return false;
    if (!includeUploadBatch && isUploadBatchEdge(edge)) return false;
    return confidenceOf(edge) >= minimumConfidence;
  });

  const candidateIds = new Set<string>();
  for (const edge of incident) {
    const otherId = edge.source === focusNodeId ? edge.target : edge.source;
    const other = byId.get(otherId);
    if (!other) continue;
    if (hiddenTypes.has(other.node_type)) continue;
    if (MIRRORED_TYPES.has(other.node_type)) continue;
    candidateIds.add(otherId);
  }

  const totalNeighbors = candidateIds.size;
  const rankedIds = [...candidateIds].sort((a, b) => {
    const scoreDifference =
      (signalView.signals.get(b)?.score ?? 0) -
      (signalView.signals.get(a)?.score ?? 0);
    if (scoreDifference !== 0) return scoreDifference;
    return a.localeCompare(b);
  });
  const visibleNeighborIds = new Set(rankedIds.slice(0, Math.max(0, budget - 1)));
  const visibleIds = new Set([focusNodeId, ...visibleNeighborIds]);

  return {
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges: incident.filter(
      (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
    ),
    totalNeighbors,
    hiddenNeighbors: Math.max(0, totalNeighbors - visibleNeighborIds.size),
  };
}

/** One-line explanation of why a node earned its place, for the detail panel. */
export function whyRelevant(sig: NodeSignals | undefined, type: string): string {
  if (!sig) return "";
  if (type === "case") return "The case itself";
  if (type === "evidence") return "A piece of evidence in this case";
  const parts: string[] = [];
  if (sig.evidenceReach >= 2) {
    parts.push(`appears in ${sig.evidenceReach} pieces of evidence`);
  } else if (sig.evidenceReach === 1) {
    parts.push("appears in one piece of evidence");
  }
  if (sig.threat) parts.push("threat-flagged by the engine");
  if (sig.crossCase) parts.push("also seen in another case");
  if (sig.backendImportance >= 0.5) parts.push("ranked as a key graph connector");
  if (sig.communityId) parts.push(`community ${sig.communityId}`);
  return parts.length ? parts.join(" · ") : "no recorded links";
}
