import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import { Box, IconButton, Paper, Stack, Tooltip, useTheme } from "@mui/material";
import cytoscape, {
  type Core,
  type Css,
  type EdgeSingular,
  type NodeSingular,
} from "cytoscape";
import fcose from "cytoscape-fcose";
import { useCallback, useEffect, useRef } from "react";

import { nodeColor } from "@/theme/theme";
import type { RelationshipGraph } from "@/types";

import type { Selection } from "./GraphTab";
import { STRUCTURAL_TYPES, type NodeSignals } from "./relevance";

// Registered once per module load. cytoscape.use() is safe to call more
// than once (Vite HMR re-evaluates this module on edit) - it just
// re-registers the same extension under the same name.
cytoscape.use(fcose);

/** Layout modes offered to the investigator. */
export type LayoutMode = "structure" | "force" | "circle";

/**
 * Node sizing model. Kept at module scope (rather than inline in the
 * cytoscape style) so layout code and style code read the same numbers.
 */
const NODE_BASE_SIZE: Record<string, number> = { case: 46, evidence: 38 };
const NODE_BASE_SIZE_DEFAULT = 26; // entities
const NODE_DEGREE_BONUS_MAX = 16; // matches Math.min(16, degree * 1.6)

/**
 * Past this many drawn nodes every entity label at once becomes a grey wall,
 * so only the case skeleton and the leads stay labelled until the
 * investigator zooms in past ZOOM_LABEL_ALL or hovers.
 */
const CROWDED_NODE_COUNT = 28;
const ZOOM_LABEL_ALL = 1.15;

/** Cytoscape node size: base-by-role, growing slightly with connectivity
 *  so hub entities read as important, capped so a busy node never dwarfs
 *  its neighbours. */
function sizeFor(type: string, degree: number): number {
  const base = NODE_BASE_SIZE[type] ?? NODE_BASE_SIZE_DEFAULT;
  return base + Math.min(NODE_DEGREE_BONUS_MAX, degree * 1.6);
}

/**
 * Visual language for engine edge types (legend is rendered in GraphTab).
 *
 * Every relation the correlation engine can emit needs an entry: an
 * unmapped type falls through to a plain grey line that appears in no
 * legend, which is how `cross_case_entity_match` — nearly half the edges on
 * a linked case — used to render as anonymous grey.
 */
export const EDGE_STYLES: Record<
  string,
  { color: string; style: "solid" | "dashed" | "dotted"; label: string }
> = {
  contains: { color: "#64748b", style: "solid", label: "Case contains evidence" },
  shared_entity: { color: "#00c2a8", style: "solid", label: "Evidence mentions entity" },
  temporal_relationship: { color: "#ff9f43", style: "dashed", label: "Close in time" },
  behavioral_relationship: { color: "#3d7eff", style: "dotted", label: "Correlated behaviour" },
  threat_relationship: { color: "#ff4d4f", style: "solid", label: "Threat-flagged entity" },
  cross_case_entity_match: {
    color: "#a970ff",
    style: "dashed",
    label: "Same entity in another case",
  },
  cross_case_relationship: {
    color: "#c084fc",
    style: "dashed",
    label: "Linked to another case",
  },
  cross_case: { color: "#a970ff", style: "dashed", label: "Link to another case" },
  timeline_event: { color: "#22d3ee", style: "dotted", label: "Timeline event" },
  linked_to: { color: "#64748b", style: "solid", label: "Related" },
  evidence_relationship: {
    color: "#2563eb",
    style: "solid",
    label: "Combined evidence relationship",
  },
};

const FALLBACK_EDGE = { color: "#64748b", style: "solid" as const, label: "Relationship" };

export function edgeStyle(edgeType: string) {
  return EDGE_STYLES[edgeType] ?? FALLBACK_EDGE;
}

/** Node shape per role — shape carries meaning independently of colour. */
export function nodeShape(type: string): Css.NodeShape {
  if (type === "case") return "diamond";
  if (type === "evidence") return "round-rectangle";
  if (type === "timeline_event") return "hexagon";
  return "ellipse";
}

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

function edgeElementId(edge: RelationshipGraph["edges"][number]): string {
  return `edge:${edge.source}|${edge.target}|${edge.edge_type}`;
}

function applySearchState(cy: Core, search: string) {
  cy.elements().removeClass("highlighted dimmed");
  const query = search.trim().toLowerCase();
  if (!query) return cy.collection();
  const matches = cy.nodes().filter((node) => {
    const label = String(node.data("label") ?? "").toLowerCase();
    const id = String(node.id()).toLowerCase();
    return label.includes(query) || id.includes(query);
  });
  if (matches.length === 0) return matches;
  cy.elements().addClass("dimmed");
  matches.removeClass("dimmed").addClass("highlighted show-label");
  matches.connectedEdges().removeClass("dimmed");
  matches.connectedEdges().connectedNodes().removeClass("dimmed").addClass("show-label");
  return matches;
}

/**
 * Human-readable caption for a node.
 * Evidence nodes are labelled by their file name (the thing an investigator
 * recognises) rather than the internal id; entities show their value.
 */
function displayLabel(
  type: string,
  label: string,
  id: string,
  properties: Record<string, string>,
): string {
  const raw = label || id.split(":").slice(1).join(":") || id;
  if (type === "case") return truncate(raw, 22);
  if (type === "evidence") return truncate(properties.file_name || raw, 24);
  return truncate(raw, 22);
}

/**
 * Cytoscape renderer for the engine's relationship graph.
 *
 * Pure presentation: every node, edge, weight and explanation comes from the
 * stored artifact. The view adds only readability — semantic layout, shape/
 * colour coding, neighbourhood focus on hover, and viewport controls.
 *
 * The `graph` it receives is already the filtered view (see `relevance.ts`),
 * so filtering rebuilds the instance and re-runs the layout over the real
 * node set. Hiding nodes with `display: none` after layout, as this used to
 * do, left the holes where they had been.
 */
export function GraphCanvas({
  graph,
  signals,
  search,
  layout,
  focusNodeId,
  viewportKey,
  onSelect,
}: {
  graph: RelationshipGraph;
  signals: Map<string, NodeSignals>;
  search: string;
  layout: LayoutMode;
  focusNodeId?: string | null;
  viewportKey?: string;
  onSelect: (selection: Selection) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const graphRef = useRef(graph);
  const signalsRef = useRef(signals);
  const onSelectRef = useRef(onSelect);
  const searchRef = useRef(search);
  const theme = useTheme();

  graphRef.current = graph;
  signalsRef.current = signals;
  onSelectRef.current = onSelect;
  searchRef.current = search;

  /** Layout options per mode, tuned for the node count actually drawn. */
  const layoutOptions = useCallback(
    (mode: LayoutMode, count: number): cytoscape.LayoutOptions => {
      if (mode === "structure") {
        // Case at the centre, evidence around it, entities furthest out —
        // mirrors how the investigation is actually structured. Spacing grows
        // with the node count: a fixed 34px gap that reads well at 20 nodes
        // packs 120 nodes into an unreadable band.
        return {
          name: "concentric",
          animate: false,
          padding: 46,
          minNodeSpacing: count > 90 ? 14 : count > 45 ? 22 : 34,
          spacingFactor: count > 90 ? 0.85 : 1,
          concentric: (node: NodeSingular) => {
            const type = node.data("type") as string;
            if (type === "case") return 3;
            if (type === "evidence") return 2;
            return 1;
          },
          // More rings once the outer ring would be overcrowded: entities
          // split by connectivity so hubs sit inside their own leaves.
          levelWidth: () => 1,
        } as cytoscape.LayoutOptions;
      }
      if (mode === "circle") {
        return {
          name: "circle",
          animate: false,
          padding: 46,
          avoidOverlap: true,
          // Ordering by role keeps evidence together on the ring instead of
          // interleaved with entities, which is the only way a single ring
          // stays interpretable past ~40 nodes.
          sort: (a: NodeSingular, b: NodeSingular) =>
            (b.data("degree") as number) - (a.data("degree") as number),
        } as cytoscape.LayoutOptions;
      }
      // "force": fcose, not cytoscape's built-in cose. cose has no overlap
      // avoidance at all; fcose's nodeDimensionsIncludeLabels folds each
      // node's rendered label into its physical size during the repulsion
      // simulation, so long entity labels push neighbours away instead of
      // sitting on top of them. randomize:false makes the initial
      // placement (BFS-based, not random) deterministic and reproducible
      // across reloads instead of shuffling every time.
      //
      // Repulsion and edge length scale down as the graph grows, otherwise a
      // 140-node case is flung so far apart that fitting it makes every node
      // a dot.
      const big = count > 70;
      return {
        name: "fcose",
        animate: false,
        randomize: false,
        fit: true,
        padding: 46,
        nodeDimensionsIncludeLabels: true,
        packComponents: true,
        quality: big ? "default" : "proof",
        nodeRepulsion: () => (big ? 5500 : 9000),
        idealEdgeLength: () => (big ? 70 : 100),
        nodeSeparation: big ? 55 : 90,
        gravity: big ? 0.4 : 0.25,
      } as unknown as cytoscape.LayoutOptions;
    },
    [],
  );

  // Build / rebuild the graph instance when the (already filtered) artifact
  // or the theme changes.
  useEffect(() => {
    if (!containerRef.current) return;

    // Degree drives node size so hubs read as important at a glance. It is
    // recomputed from the *drawn* edges: a node's importance in this view is
    // what this view shows, not what the full artifact holds.
    const degree = new Map<string, number>();
    graph.edges.forEach((e) => {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    });

    const crowded = graph.nodes.length > CROWDED_NODE_COUNT;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...graph.nodes.map((node) => {
          const sig = signals.get(node.id);
          const structural = (STRUCTURAL_TYPES as readonly string[]).includes(
            node.node_type,
          );
          const classes: string[] = [];
          if (
            !crowded ||
            structural ||
            (sig?.evidenceReach ?? 0) >= 3 ||
            sig?.threat ||
            sig?.crossCase
          ) {
            classes.push("show-label");
          }
          if (node.id === focusNodeId) classes.push("focus-root");
          return {
            data: {
              id: node.id,
              label: displayLabel(
                node.node_type,
                node.label,
                node.id,
                node.properties ?? {},
              ),
              type: node.node_type,
              degree: degree.get(node.id) ?? 0,
            },
            // On an overview, label the skeleton and only the strongest hubs.
            // Two-evidence leads remain visible but reveal their label on
            // hover; a focused neighbourhood is small enough to label all.
            classes: classes.join(" "),
          };
        }),
        ...graph.edges.map((edge, i) => ({
          data: {
            id: edgeElementId(edge),
            source: edge.source,
            target: edge.target,
              type: edge.edge_type,
              weight: edge.weight,
              label: edge.projection
                ? `${edge.projection.relationship_count} finding${
                    edge.projection.relationship_count === 1 ? "" : "s"
                  }`
                : "",
              index: i,
          },
          classes: edge.backbone ? "backbone" : "",
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (el: NodeSingular) =>
              nodeColor(el.data("type") as string),
            shape: (el: NodeSingular) => nodeShape(el.data("type") as string),
            label: "",
            color: theme.palette.text.primary,
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-wrap": "ellipsis",
            "text-max-width": "108px",
            "text-background-color": theme.palette.background.paper,
            "text-background-opacity": 0.82,
            "text-background-padding": "3px",
            "text-background-shape": "roundrectangle",
            width: (el: NodeSingular) =>
              sizeFor(el.data("type") as string, el.data("degree") as number),
            height: (el: NodeSingular) =>
              sizeFor(el.data("type") as string, el.data("degree") as number),
            "border-width": 2,
            "border-color": theme.palette.background.paper,
          },
        },
        {
          // Labels are opt-in per node so a dense case is readable; the
          // zoom handler below adds this class to everything once the
          // investigator is close enough for the text to fit.
          selector: "node.show-label",
          style: {
            label: "data(label)",
            "font-size": (el: NodeSingular) =>
              (STRUCTURAL_TYPES as readonly string[]).includes(
                el.data("type") as string,
              )
                ? 11
                : 9.5,
            "font-weight": (el: NodeSingular) =>
              (STRUCTURAL_TYPES as readonly string[]).includes(
                el.data("type") as string,
              )
                ? 700
                : 500,
          },
        },
        {
          selector: "edge",
          style: {
            width: (el: EdgeSingular) =>
              Math.min(4.5, 1.2 + (el.data("weight") as number)),
            "line-color": (el: EdgeSingular) =>
              edgeStyle(el.data("type") as string).color,
            "line-style": (el: EdgeSingular) =>
              edgeStyle(el.data("type") as string).style,
            "curve-style": "bezier",
            "target-arrow-shape": graph.directed ? "triangle" : "none",
            "target-arrow-color": (el: EdgeSingular) =>
              edgeStyle(el.data("type") as string).color,
            "arrow-scale": 0.85,
            // Thinner and fainter as the graph grows, so the lines read as
            // texture behind the nodes rather than competing with them.
            opacity: crowded ? 0.4 : 0.68,
          },
        },
        {
          // The backend's maximum-spanning forest preserves the strongest
          // route through every graph component. Make those key links easier
          // to trace without hiding any underlying forensic relationship.
          selector: "edge.backbone",
          style: {
            width: (el: EdgeSingular) =>
              Math.min(5.5, 2.4 + (el.data("weight") as number)),
            opacity: 0.92,
            "z-index": 4,
          },
        },
        {
          // Containment is useful structure, but it is not an investigative
          // finding. Keep the case skeleton visually behind shared entities,
          // threat flags, and cross-case relationships.
          selector: "edge[type = 'contains']",
          style: { width: 1, opacity: 0.18, "line-color": "#94a3b8" },
        },
        {
          selector: "edge[type = 'evidence_relationship']",
          style: {
            label: "data(label)",
            "font-size": 9,
            "font-weight": 700,
            color: theme.palette.text.secondary,
            "text-background-color": theme.palette.background.paper,
            "text-background-opacity": 0.92,
            "text-background-padding": "3px",
            "text-rotation": "autorotate",
            "line-color": EDGE_STYLES.evidence_relationship.color,
            opacity: 0.78,
          },
        },
        {
          selector: ".focus-root",
          style: {
            "border-color": theme.palette.warning.main,
            "border-width": 5,
            label: "data(label)",
            "z-index": 12,
          },
        },
        {
          selector: ".highlighted",
          style: { "border-color": "#ffd666", "border-width": 4, "z-index": 10 },
        },
        {
          selector: ".hover-focus",
          style: { opacity: 1, "z-index": 9, label: "data(label)" },
        },
        { selector: ".dimmed", style: { opacity: 0.08, label: "" } },
        {
          selector: ":selected",
          style: {
            "border-color": theme.palette.primary.main,
            "border-width": 4,
            "line-color": theme.palette.primary.main,
          },
        },
      ],
      layout: layoutOptions(layout, graph.nodes.length),
      wheelSensitivity: 0.2,
      maxZoom: 2.5,
      minZoom: 0.1,
      // Rendering hints keep a later switch from the small Evidence Map to the
      // Full graph smooth without recreating the Cytoscape core.
      hideEdgesOnViewport: true,
      textureOnViewport: true,
      motionBlur: false,
      pixelRatio: "auto",
    });
    cy.fit(undefined, 46);

    if (viewportKey) {
      try {
        const stored = window.localStorage.getItem(viewportKey);
        if (stored) {
          const viewport = JSON.parse(stored) as {
            zoom?: number;
            pan?: { x: number; y: number };
          };
          if (viewport.zoom && viewport.pan) {
            cy.viewport({ zoom: viewport.zoom, pan: viewport.pan });
          }
        }
      } catch {
        // A stale local preference must never stop the graph from rendering.
      }
    }

    let viewportTimer: number | undefined;
    if (viewportKey) {
      cy.on("zoom pan", () => {
        window.clearTimeout(viewportTimer);
        viewportTimer = window.setTimeout(() => {
          window.localStorage.setItem(
            viewportKey,
            JSON.stringify({ zoom: cy.zoom(), pan: cy.pan() }),
          );
        }, 180);
      });
    }

    cy.on("tap", "node", (event) => {
      const id = event.target.id() as string;
      const node = graphRef.current.nodes.find((n) => n.id === id);
      if (node) onSelectRef.current({ kind: "node", node });
    });
    cy.on("tap", "edge", (event) => {
      const index = event.target.data("index") as number;
      const edge = graphRef.current.edges[index];
      if (edge) onSelectRef.current({ kind: "edge", edge });
    });
    cy.on("tap", (event) => {
      if (event.target === cy) onSelectRef.current(null);
    });

    // Zooming in is a request for detail: reveal every label once the text
    // has room, and fall back to the curated set on the way out.
    cy.on("zoom", () => {
      if (cy.nodes().length <= CROWDED_NODE_COUNT) return;
      const all = cy.zoom() >= ZOOM_LABEL_ALL;
      cy.batch(() => {
        cy.nodes().forEach((n) => {
          if (all) n.addClass("show-label");
          else if (!n.scratch("_keepLabel")) n.removeClass("show-label");
        });
      });
    });
    cy.nodes(".show-label").forEach((n) => {
      n.scratch("_keepLabel", true);
    });

    // ---------------------------------------------------------------- hover
    const tooltip = tooltipRef.current;

    const placeTooltip = (x: number, y: number) => {
      if (!tooltip || !containerRef.current) return;
      const maxX = containerRef.current.clientWidth - tooltip.offsetWidth - 8;
      const maxY = containerRef.current.clientHeight - tooltip.offsetHeight - 8;
      tooltip.style.left = `${Math.max(8, Math.min(x + 16, Math.max(8, maxX)))}px`;
      tooltip.style.top = `${Math.max(8, Math.min(y + 16, Math.max(8, maxY)))}px`;
    };

    const showTooltip = (html: string, x: number, y: number) => {
      if (!tooltip) return;
      tooltip.innerHTML = html;
      tooltip.style.display = "block";
      placeTooltip(x, y);
    };
    const hideTooltip = () => {
      if (tooltip) tooltip.style.display = "none";
    };

    cy.on("mouseover", "node", (event) => {
      const nodeEl = event.target as NodeSingular;
      const id = nodeEl.id() as string;
      const currentGraph = graphRef.current;
      const source = currentGraph.nodes.find((n) => n.id === id);
      const hood = nodeEl.closedNeighborhood();
      cy.elements().not(hood).addClass("dimmed");
      hood.addClass("hover-focus");

      const links: string[] = [];
      let hidden = 0;
      currentGraph.edges.forEach((e) => {
        if (e.source !== id && e.target !== id) return;
        const otherId = e.source === id ? e.target : e.source;
        const other = currentGraph.nodes.find((n) => n.id === otherId);
        if (!other) return;
        if (links.length < 6) {
          links.push(
            `<div style="margin-top:2px"><span style="color:${
              edgeStyle(e.edge_type).color
            }">●</span> ${esc(
              truncate(other.label || otherId, 30),
            )} <span style="opacity:.6">${esc(
              e.edge_type.replace(/_/g, " "),
            )}</span></div>`,
          );
        } else {
          hidden += 1;
        }
      });

      const type = String(nodeEl.data("type"));
      const props = source?.properties ?? {};
      const propLines = Object.entries(props)
        .filter(([, v]) => v)
        .slice(0, 2)
        .map(
          ([k, v]) =>
            `<div style="opacity:.7">${esc(k.replace(/_/g, " "))}: ${esc(
              truncate(String(v), 34),
            )}</div>`,
        )
        .join("");

      const sig = signalsRef.current.get(id);
      const reachLine =
        sig && sig.evidenceReach >= 2
          ? `<div style="opacity:.75;margin-bottom:3px">Links ${sig.evidenceReach} pieces of evidence</div>`
          : "";

      showTooltip(
        `<div style="font-weight:700;margin-bottom:2px;word-break:break-all">${esc(
          source?.label ?? nodeEl.data("label"),
        )}</div>` +
          `<div style="color:${nodeColor(
            type,
          )};text-transform:uppercase;font-size:10px;letter-spacing:.05em;margin-bottom:4px">${esc(
            type.replace(/_/g, " "),
          )} · ${nodeEl.degree(false)} connection(s)</div>` +
          reachLine +
          propLines +
          (links.length
            ? `<div style="margin-top:5px;border-top:1px solid rgba(128,128,128,.25);padding-top:4px">${links.join(
                "",
              )}</div>`
            : "") +
          (hidden
            ? `<div style="opacity:.6;margin-top:2px">…and ${hidden} more — click to see all</div>`
            : ""),
        event.renderedPosition.x,
        event.renderedPosition.y,
      );
    });

    cy.on("mouseover", "edge", (event) => {
      const edgeEl = event.target as EdgeSingular;
      const currentGraph = graphRef.current;
      const edge = currentGraph.edges[edgeEl.data("index") as number];
      if (!edge) return;
      const focus = edgeEl.connectedNodes().union(edgeEl);
      cy.elements().not(focus).addClass("dimmed");
      focus.addClass("hover-focus");

      const src = currentGraph.nodes.find((n) => n.id === edge.source);
      const dst = currentGraph.nodes.find((n) => n.id === edge.target);
      const meta = edgeStyle(edge.edge_type);
      const confidence =
        edge.confidence ?? (edge.weight <= 1 ? edge.weight : undefined);

      showTooltip(
        `<div style="color:${meta.color};text-transform:uppercase;font-size:10px;letter-spacing:.05em;font-weight:700;margin-bottom:3px">${esc(
          meta.label,
        )}</div>` +
          `<div style="font-weight:600;margin-bottom:4px;word-break:break-all">${esc(
            truncate(src?.label ?? edge.source, 26),
          )} ↔ ${esc(truncate(dst?.label ?? edge.target, 26))}</div>` +
          (edge.explanation
            ? `<div style="margin-bottom:4px">${esc(edge.explanation)}</div>`
            : "") +
          `<div style="opacity:.7">weight ${esc(edge.weight)}${
            confidence !== undefined
              ? ` · confidence ${Math.round(confidence * 100)}%`
              : ""
          }${edge.timestamp ? ` · ${esc(String(edge.timestamp).slice(0, 16))}` : ""}</div>`,
        event.renderedPosition.x,
        event.renderedPosition.y,
      );
    });

    cy.on("mousemove", "node, edge", (event) => {
      if (tooltip && tooltip.style.display === "block") {
        placeTooltip(event.renderedPosition.x, event.renderedPosition.y);
      }
    });

    cy.on("mouseout", "node, edge", () => {
      cy.elements().removeClass("dimmed hover-focus");
      applySearchState(cy, searchRef.current);
      hideTooltip();
    });

    cyRef.current = cy;
    return () => {
      window.clearTimeout(viewportTimer);
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme.palette.mode, viewportKey]);

  // Update the existing Cytoscape core instead of destroying and recreating
  // it whenever a filter, expansion, or search changes the visible elements.
  // This preserves event handlers and the investigator's mental map while
  // avoiding a full renderer allocation on every interaction.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const degree = new Map<string, number>();
    graph.edges.forEach((edge) => {
      degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
      degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    });
    const crowded = graph.nodes.length > CROWDED_NODE_COUNT;
    const desiredNodeIds = new Set(graph.nodes.map((node) => node.id));
    const desiredEdgeIds = new Set(graph.edges.map(edgeElementId));
    let structureChanged = false;

    cy.batch(() => {
      cy.edges().forEach((element) => {
        if (!desiredEdgeIds.has(element.id())) {
          element.remove();
          structureChanged = true;
        }
      });
      cy.nodes().forEach((element) => {
        if (!desiredNodeIds.has(element.id())) {
          element.remove();
          structureChanged = true;
        }
      });

      graph.nodes.forEach((node) => {
        const sig = signals.get(node.id);
        const structural = (STRUCTURAL_TYPES as readonly string[]).includes(node.node_type);
        const classes: string[] = [];
        if (
          !crowded ||
          structural ||
          (sig?.evidenceReach ?? 0) >= 3 ||
          sig?.threat ||
          sig?.crossCase
        ) {
          classes.push("show-label");
        }
        if (node.id === focusNodeId) classes.push("focus-root");
        const data = {
          id: node.id,
          label: displayLabel(
            node.node_type,
            node.label,
            node.id,
            node.properties ?? {},
          ),
          type: node.node_type,
          degree: degree.get(node.id) ?? 0,
        };
        const existing = cy.getElementById(node.id);
        if (existing.empty()) {
          cy.add({ group: "nodes", data, classes: classes.join(" ") });
          structureChanged = true;
        } else {
          existing.data(data);
          existing.classes(classes.join(" "));
        }
      });

      graph.edges.forEach((edge, index) => {
        const id = edgeElementId(edge);
        const data = {
          id,
          source: edge.source,
          target: edge.target,
          type: edge.edge_type,
          weight: edge.weight,
          label: edge.projection
            ? `${edge.projection.relationship_count} finding${
                edge.projection.relationship_count === 1 ? "" : "s"
              }`
            : "",
          index,
        };
        const existing = cy.getElementById(id);
        if (existing.empty()) {
          cy.add({ group: "edges", data });
          structureChanged = true;
        } else {
          existing.data(data);
        }
      });

      cy.nodes().forEach((node) => {
        node.scratch("_keepLabel", node.hasClass("show-label"));
      });
    });

    if (structureChanged) {
      cy.layout(layoutOptions(layout, cy.nodes().length)).run();
      cy.fit(undefined, 46);
    }
  }, [graph, signals, focusNodeId, layoutOptions, theme.palette.mode]);

  // Re-run the layout when the investigator switches mode.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.layout(layoutOptions(layout, cy.nodes().length)).run();
    cy.fit(undefined, 46);
  }, [layout, layoutOptions]);

  // Search highlight (visual only — type filtering happens upstream so the
  // layout is computed over the nodes actually drawn).
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      applySearchState(cy, search);
    });

    // Bring the hits into view: on a large case the match is usually off
    // screen, and a highlight nobody can see is not a search result.
    const q = search.trim();
    if (q) {
      const matches = cy.nodes(".highlighted");
      if (matches.length > 0) cy.animate({ fit: { eles: matches.closedNeighborhood(), padding: 80 }, duration: 250 });
    }
  }, [search, graph]);

  const zoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  };
  const fitView = () => cyRef.current?.fit(undefined, 46);

  return (
    <Box sx={{ position: "relative" }}>
      <Box
        ref={containerRef}
        sx={{
          height: 560,
          width: "100%",
          bgcolor: theme.palette.mode === "dark" ? "#0d1426" : "#f8faff",
        }}
        aria-label="Relationship graph canvas"
      />

      {/* Viewport controls */}
      <Paper
        variant="outlined"
        sx={{ position: "absolute", top: 12, right: 12, zIndex: 5 }}
      >
        <Stack>
          <Tooltip title="Zoom in" placement="left">
            <IconButton size="small" onClick={() => zoomBy(1.3)}>
              <ZoomInIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom out" placement="left">
            <IconButton size="small" onClick={() => zoomBy(1 / 1.3)}>
              <ZoomOutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Fit to view" placement="left">
            <IconButton size="small" onClick={fitView}>
              <CenterFocusStrongIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Paper>

      {/* Hover tooltip — populated only with escaped engine-artifact values. */}
      <Box
        ref={tooltipRef}
        sx={{
          display: "none",
          position: "absolute",
          zIndex: 20,
          maxWidth: 300,
          p: 1.25,
          borderRadius: 2,
          fontSize: "0.78rem",
          lineHeight: 1.5,
          pointerEvents: "none",
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(18,26,46,0.97)"
              : "rgba(255,255,255,0.98)",
          border: 1,
          borderColor: "divider",
          boxShadow: 6,
          color: "text.primary",
        }}
      />
    </Box>
  );
}
