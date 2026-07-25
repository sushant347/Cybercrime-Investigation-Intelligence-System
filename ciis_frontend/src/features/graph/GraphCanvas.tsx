import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import { Box, IconButton, Paper, Stack, Tooltip, useTheme } from "@mui/material";
import cytoscape, {
  type Core,
  type EdgeSingular,
  type NodeSingular,
  type Position,
} from "cytoscape";
import fcose from "cytoscape-fcose";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { nodeColor } from "@/theme/theme";
import type { GraphNode, RelationshipGraph } from "@/types";

import type { Selection } from "./GraphTab";

// Registered once per module load. cytoscape.use() is safe to call more
// than once (Vite HMR re-evaluates this module on edit) - it just
// re-registers the same extension under the same name.
cytoscape.use(fcose);

/** Layout modes offered to the investigator. */
export type LayoutMode = "bipartite" | "force" | "structure" | "circle";

/** Structural roles: everything else is an extracted-entity node. */
export const STRUCTURAL_TYPES = ["case", "evidence", "timeline_event"];

/**
 * Node sizing model, shared by the cytoscape style function (`sizeFor`
 * below) and the bipartite row-spacing math. Defined once so the two can
 * never drift apart and silently reintroduce overlap - the bug this
 * comment is here to prevent already happened once while building this
 * feature (row height was tuned against the node circle alone and missed
 * that the label sits below it).
 */
const NODE_BASE_SIZE: Record<string, number> = { case: 46, evidence: 38 };
const NODE_BASE_SIZE_DEFAULT = 26; // entities
const NODE_DEGREE_BONUS_MAX = 16; // matches Math.min(16, degree * 1.6)
const NODE_MAX_DIAMETER =
  Math.max(...Object.values(NODE_BASE_SIZE), NODE_BASE_SIZE_DEFAULT) +
  NODE_DEGREE_BONUS_MAX;

/** Cytoscape node size: base-by-role, growing slightly with connectivity
 *  so hub entities read as important, capped so a busy node never dwarfs
 *  its neighbours. */
function sizeFor(type: string, degree: number): number {
  const base = NODE_BASE_SIZE[type] ?? NODE_BASE_SIZE_DEFAULT;
  return base + Math.min(NODE_DEGREE_BONUS_MAX, degree * 1.6);
}

/** Vertical space one row needs so a node's label (rendered below it via
 *  text-valign:bottom / text-margin-y / the label background pill) cannot
 *  reach into the node placed in the next row down. Every term here
 *  mirrors an actual style value in the cytoscape node style below -
 *  see the inline comments there if either ever changes. */
const LABEL_MARGIN_Y = 6; // "text-margin-y"
const LABEL_TEXT_HEIGHT = 11 * 1.2; // max font-size (11) * ~1.2 line-height
const LABEL_PILL_PADDING = 3 * 2; // "text-background-padding": "3px", both edges
const ROW_SAFETY_BUFFER = 10; // extra breathing room, purely cosmetic

/**
 * Minimum centre-to-centre row spacing with zero overlap, for any node
 * mix this graph can produce: worst case is two max-size nodes stacked,
 * where the upper one's label must still clear the lower one's node.
 */
const BIPARTITE_ROW_HEIGHT = Math.ceil(
  NODE_MAX_DIAMETER + // upper node's own radius + lower node's own radius
    LABEL_MARGIN_Y +
    LABEL_TEXT_HEIGHT +
    LABEL_PILL_PADDING +
    ROW_SAFETY_BUFFER,
);

/**
 * Deterministic two-column layout: evidence (+case, +timeline events) on
 * the left, every extracted entity on the right, one row each. This is the
 * graph's natural shape - it is fundamentally bipartite (evidence mentions
 * entities) - so laying it out as two columns instead of running physics
 * on it guarantees zero node OR label overlap, and is stable across
 * reloads, which a force simulation can never promise.
 */
export function bipartiteRowPositions(
  nodes: GraphNode[],
): Record<string, Position> {
  const left = nodes
    .filter((n) => STRUCTURAL_TYPES.includes(n.node_type))
    .sort((a, b) => {
      if (a.node_type !== b.node_type) {
        // case first, then evidence, then timeline events
        return STRUCTURAL_TYPES.indexOf(a.node_type) - STRUCTURAL_TYPES.indexOf(b.node_type);
      }
      return a.label.localeCompare(b.label);
    });
  const right = nodes
    .filter((n) => !STRUCTURAL_TYPES.includes(n.node_type))
    .sort((a, b) =>
      a.node_type === b.node_type
        ? a.label.localeCompare(b.label)
        : a.node_type.localeCompare(b.node_type),
    );

  const topPad = 40;
  const leftX = 160;
  const rightX = 560;
  const positions: Record<string, Position> = {};
  left.forEach((n, i) => {
    positions[n.id] = { x: leftX, y: topPad + i * BIPARTITE_ROW_HEIGHT };
  });
  right.forEach((n, i) => {
    positions[n.id] = { x: rightX, y: topPad + i * BIPARTITE_ROW_HEIGHT };
  });
  return positions;
}

/** Visual language for engine edge types (legend is rendered in GraphTab). */
export const EDGE_STYLES: Record<
  string,
  { color: string; style: "solid" | "dashed" | "dotted"; label: string }
> = {
  contains: { color: "#64748b", style: "solid", label: "Case contains evidence" },
  shared_entity: { color: "#00c2a8", style: "solid", label: "Evidence mentions entity" },
  temporal_relationship: { color: "#ff9f43", style: "dashed", label: "Close in time" },
  behavioral_relationship: { color: "#3d7eff", style: "dotted", label: "Correlated behaviour" },
  threat_relationship: { color: "#ff4d4f", style: "solid", label: "Threat-flagged entity" },
  cross_case: { color: "#a970ff", style: "dashed", label: "Link to another case" },
};

const FALLBACK_EDGE = { color: "#64748b", style: "solid" as const, label: "Relationship" };

export function edgeStyle(edgeType: string) {
  return EDGE_STYLES[edgeType] ?? FALLBACK_EDGE;
}

/** Node shape per role — shape carries meaning independently of colour. */
export function nodeShape(type: string): string {
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
 */
export function GraphCanvas({
  graph,
  search,
  hiddenTypes,
  layout,
  onSelect,
}: {
  graph: RelationshipGraph;
  search: string;
  hiddenTypes: Set<string>;
  layout: LayoutMode;
  onSelect: (selection: Selection) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const theme = useTheme();

  const bipartitePositions = useMemo(
    () => bipartiteRowPositions(graph.nodes),
    [graph.nodes],
  );

  /** Layout options per mode. */
  const layoutOptions = useCallback(
    (mode: LayoutMode): cytoscape.LayoutOptions => {
      if (mode === "bipartite") {
        // Preset (explicit) positions — the only mode with a mathematical
        // overlap guarantee, since nothing is simulated.
        return {
          name: "preset",
          fit: true,
          padding: 46,
          positions: (node: NodeSingular) => bipartitePositions[node.id()],
        } as unknown as cytoscape.LayoutOptions;
      }
      if (mode === "structure") {
        // Case at the centre, evidence around it, entities furthest out —
        // mirrors how the investigation is actually structured.
        return {
          name: "concentric",
          animate: false,
          padding: 46,
          minNodeSpacing: 34,
          concentric: (node: NodeSingular) => {
            const type = node.data("type") as string;
            if (type === "case") return 3;
            if (type === "evidence") return 2;
            return 1;
          },
          levelWidth: () => 1,
        } as cytoscape.LayoutOptions;
      }
      if (mode === "circle") {
        return {
          name: "circle",
          animate: false,
          padding: 46,
          avoidOverlap: true,
        } as cytoscape.LayoutOptions;
      }
      // "force": fcose, not cytoscape's built-in cose. cose has no overlap
      // avoidance at all; fcose's nodeDimensionsIncludeLabels folds each
      // node's rendered label into its physical size during the repulsion
      // simulation, so long entity labels push neighbours away instead of
      // sitting on top of them. randomize:false makes the initial
      // placement (BFS-based, not random) deterministic and reproducible
      // across reloads instead of shuffling every time.
      return {
        name: "fcose",
        animate: false,
        randomize: false,
        fit: true,
        padding: 46,
        nodeDimensionsIncludeLabels: true,
        packComponents: true,
        nodeRepulsion: () => 9000,
        idealEdgeLength: () => 100,
        nodeSeparation: 90,
      } as unknown as cytoscape.LayoutOptions;
    },
    [bipartitePositions],
  );

  // Build / rebuild the graph instance when the artifact or theme changes.
  useEffect(() => {
    if (!containerRef.current) return;

    // Degree drives node size so hubs read as important at a glance.
    const degree = new Map<string, number>();
    graph.edges.forEach((e) => {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...graph.nodes.map((node) => ({
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
        })),
        ...graph.edges.map((edge, i) => ({
          data: {
            id: `e${i}`,
            source: edge.source,
            target: edge.target,
            type: edge.edge_type,
            weight: edge.weight,
            index: i,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (el: NodeSingular) =>
              nodeColor(el.data("type") as string),
            shape: (el: NodeSingular) => nodeShape(el.data("type") as string),
            label: "data(label)",
            "font-size": (el: NodeSingular) =>
              STRUCTURAL_TYPES.includes(el.data("type") as string) ? 11 : 9.5,
            "font-weight": (el: NodeSingular) =>
              STRUCTURAL_TYPES.includes(el.data("type") as string) ? 700 : 500,
            color: theme.palette.text.primary,
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-wrap": "ellipsis",
            "text-max-width": "108px",
            "text-background-color": theme.palette.background.paper,
            "text-background-opacity": 0.82,
            "text-background-padding": "3px",
            "text-background-shape": "round-rectangle",
            width: (el: NodeSingular) =>
              sizeFor(el.data("type") as string, el.data("degree") as number),
            height: (el: NodeSingular) =>
              sizeFor(el.data("type") as string, el.data("degree") as number),
            "border-width": 2,
            "border-color": theme.palette.background.paper,
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
            opacity: 0.68,
          },
        },
        {
          selector: ".highlighted",
          style: { "border-color": "#ffd666", "border-width": 4, "z-index": 10 },
        },
        { selector: ".hover-focus", style: { opacity: 1, "z-index": 9 } },
        { selector: ".dimmed", style: { opacity: 0.08 } },
        {
          selector: ":selected",
          style: {
            "border-color": theme.palette.primary.main,
            "border-width": 4,
            "line-color": theme.palette.primary.main,
          },
        },
      ],
      layout: layoutOptions(layout),
      wheelSensitivity: 0.2,
      maxZoom: 2.5,
      minZoom: 0.1,
    });
    cy.fit(undefined, 46);

    cy.on("tap", "node", (event) => {
      const id = event.target.id() as string;
      const node = graph.nodes.find((n) => n.id === id);
      if (node) onSelect({ kind: "node", node });
    });
    cy.on("tap", "edge", (event) => {
      const index = event.target.data("index") as number;
      const edge = graph.edges[index];
      if (edge) onSelect({ kind: "edge", edge });
    });
    cy.on("tap", (event) => {
      if (event.target === cy) onSelect(null);
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
      const source = graph.nodes.find((n) => n.id === id);
      const hood = nodeEl.closedNeighborhood();
      cy.elements().not(hood).addClass("dimmed");
      hood.addClass("hover-focus");

      const links: string[] = [];
      let hidden = 0;
      graph.edges.forEach((e) => {
        if (e.source !== id && e.target !== id) return;
        const otherId = e.source === id ? e.target : e.source;
        const other = graph.nodes.find((n) => n.id === otherId);
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

      showTooltip(
        `<div style="font-weight:700;margin-bottom:2px;word-break:break-all">${esc(
          source?.label ?? nodeEl.data("label"),
        )}</div>` +
          `<div style="color:${nodeColor(
            type,
          )};text-transform:uppercase;font-size:10px;letter-spacing:.05em;margin-bottom:4px">${esc(
            type.replace(/_/g, " "),
          )} · ${nodeEl.degree(false)} connection(s)</div>` +
          propLines +
          (links.length
            ? `<div style="margin-top:5px;border-top:1px solid rgba(128,128,128,.25);padding-top:4px">${links.join(
                "",
              )}</div>`
            : "") +
          (hidden ? `<div style="opacity:.6;margin-top:2px">…and ${hidden} more</div>` : ""),
        event.renderedPosition.x,
        event.renderedPosition.y,
      );
    });

    cy.on("mouseover", "edge", (event) => {
      const edgeEl = event.target as EdgeSingular;
      const edge = graph.edges[edgeEl.data("index") as number];
      if (!edge) return;
      const focus = edgeEl.connectedNodes().union(edgeEl);
      cy.elements().not(focus).addClass("dimmed");
      focus.addClass("hover-focus");

      const src = graph.nodes.find((n) => n.id === edge.source);
      const dst = graph.nodes.find((n) => n.id === edge.target);
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
      hideTooltip();
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, theme.palette.mode]);

  // Re-run the layout when the investigator switches mode.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.layout(layoutOptions(layout)).run();
    cy.fit(undefined, 46);
  }, [layout, layoutOptions]);

  // Search highlight + type filtering (visual only).
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("highlighted dimmed");

      cy.nodes().forEach((node) => {
        const hidden = hiddenTypes.has(node.data("type") as string);
        node.style("display", hidden ? "none" : "element");
      });

      const q = search.trim().toLowerCase();
      if (q) {
        const matches = cy.nodes().filter((node) => {
          const label = String(node.data("label") ?? "").toLowerCase();
          const id = String(node.id()).toLowerCase();
          return label.includes(q) || id.includes(q);
        });
        if (matches.length > 0) {
          cy.elements().addClass("dimmed");
          matches.removeClass("dimmed").addClass("highlighted");
          matches.connectedEdges().removeClass("dimmed");
          matches.connectedEdges().connectedNodes().removeClass("dimmed");
        }
      }
    });
  }, [search, hiddenTypes]);

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
