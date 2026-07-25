import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import { Box, IconButton, Paper, Stack, Tooltip, useTheme } from "@mui/material";
import cytoscape, { type Core, type EdgeSingular, type NodeSingular } from "cytoscape";
import { useCallback, useEffect, useRef } from "react";

import { nodeColor } from "@/theme/theme";
import type { RelationshipGraph } from "@/types";

import type { Selection } from "./GraphTab";

/** Layout modes offered to the investigator. */
export type LayoutMode = "structure" | "force" | "circle";

/** Structural roles: everything else is an extracted-entity node. */
export const STRUCTURAL_TYPES = ["case", "evidence", "timeline_event"];

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

  /** Layout options per mode; all layouts are cytoscape built-ins. */
  const layoutOptions = useCallback(
    (mode: LayoutMode): cytoscape.LayoutOptions => {
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
      return {
        name: "cose",
        animate: false,
        padding: 46,
        nodeRepulsion: () => 14000,
        idealEdgeLength: () => 95,
      } as unknown as cytoscape.LayoutOptions;
    },
    [],
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

    const sizeFor = (type: string, deg: number) => {
      const base = type === "case" ? 46 : type === "evidence" ? 38 : 26;
      return base + Math.min(16, deg * 1.6);
    };

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
