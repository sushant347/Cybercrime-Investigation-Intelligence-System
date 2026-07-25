import { Box, useTheme } from "@mui/material";
import cytoscape, { type Core, type EdgeSingular, type NodeSingular } from "cytoscape";
import { useEffect, useRef } from "react";

import { nodeColor } from "@/theme/theme";
import type { RelationshipGraph } from "@/types";

import type { Selection } from "./GraphTab";

/** Visual language for engine edge types (shared with the legend in GraphTab). */
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

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Cytoscape renderer for the engine's relationship graph.
 * Pure presentation: nodes/edges/weights come straight from the artifact.
 * Hovering a node highlights its neighbourhood and shows what it connects
 * to; hovering an edge shows the engine's explanation of the correlation.
 */
export function GraphCanvas({
  graph,
  search,
  hiddenTypes,
  onSelect,
}: {
  graph: RelationshipGraph;
  search: string;
  hiddenTypes: Set<string>;
  onSelect: (selection: Selection) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const theme = useTheme();

  // Build / rebuild the graph instance when the artifact changes.
  useEffect(() => {
    if (!containerRef.current) return;

    // Node degree drives sizing so hub entities are visually prominent.
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
            label: node.label || node.id.split(":").pop() || node.id,
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
            "background-color": (el: NodeSingular) => nodeColor(el.data("type") as string),
            shape: (el: NodeSingular) => {
              const t = el.data("type") as string;
              if (t === "case") return "diamond";
              if (t === "evidence") return "round-rectangle";
              if (t === "timeline_event") return "hexagon";
              return "ellipse";
            },
            label: "data(label)",
            "font-size": 10,
            "font-weight": (el: NodeSingular) =>
              (el.data("type") as string) === "evidence" ? 700 : 400,
            color: theme.palette.text.primary,
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-wrap": "ellipsis",
            "text-max-width": "120px",
            "text-background-color": theme.palette.background.paper,
            "text-background-opacity": 0.75,
            "text-background-padding": "2px",
            "text-background-shape": "round-rectangle",
            width: (el: NodeSingular) => {
              const t = el.data("type") as string;
              const base = t === "case" ? 34 : t === "evidence" ? 30 : 20;
              return base + Math.min(14, (el.data("degree") as number) * 1.5);
            },
            height: (el: NodeSingular) => {
              const t = el.data("type") as string;
              const base = t === "case" ? 34 : t === "evidence" ? 30 : 20;
              return base + Math.min(14, (el.data("degree") as number) * 1.5);
            },
            "border-width": 2,
            "border-color": theme.palette.background.paper,
          },
        },
        {
          selector: "edge",
          style: {
            width: (el: EdgeSingular) =>
              Math.min(5, 1.25 + (el.data("weight") as number)),
            "line-color": (el: EdgeSingular) => edgeStyle(el.data("type") as string).color,
            "line-style": (el: EdgeSingular) => edgeStyle(el.data("type") as string).style,
            "curve-style": "bezier",
            "target-arrow-shape": graph.directed ? "triangle" : "none",
            "target-arrow-color": (el: EdgeSingular) =>
              edgeStyle(el.data("type") as string).color,
            opacity: 0.7,
          },
        },
        {
          selector: ".highlighted",
          style: { "border-color": "#ffd666", "border-width": 4, "z-index": 10 },
        },
        {
          selector: ".hover-focus",
          style: { opacity: 1, "z-index": 9 },
        },
        {
          selector: ".dimmed",
          style: { opacity: 0.1 },
        },
        {
          selector: ":selected",
          style: {
            "border-color": theme.palette.primary.main,
            "border-width": 4,
            "line-color": theme.palette.primary.main,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 40,
        nodeRepulsion: () => 12000,
        idealEdgeLength: () => 90,
      },
      wheelSensitivity: 0.2,
      // A sparse 4-node graph must not zoom into planet-sized circles.
      maxZoom: 1.6,
      minZoom: 0.15,
    });
    cy.fit(undefined, 40);

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

    const showTooltip = (html: string, x: number, y: number) => {
      if (!tooltip) return;
      tooltip.innerHTML = html;
      tooltip.style.display = "block";
      const rect = containerRef.current?.getBoundingClientRect();
      const maxX = (rect?.width ?? 600) - tooltip.offsetWidth - 8;
      const maxY = (rect?.height ?? 400) - tooltip.offsetHeight - 8;
      tooltip.style.left = `${Math.max(8, Math.min(x + 14, maxX))}px`;
      tooltip.style.top = `${Math.max(8, Math.min(y + 14, maxY))}px`;
    };
    const hideTooltip = () => {
      if (tooltip) tooltip.style.display = "none";
    };

    cy.on("mouseover", "node", (event) => {
      const node = event.target as NodeSingular;
      const id = node.id() as string;
      // Emphasise the neighbourhood.
      const hood = node.closedNeighborhood();
      cy.elements().not(hood).addClass("dimmed");
      hood.addClass("hover-focus");

      // What this node connects to, grouped from the artifact itself.
      const links: string[] = [];
      graph.edges.forEach((e) => {
        if (e.source !== id && e.target !== id) return;
        const otherId = e.source === id ? e.target : e.source;
        const other = graph.nodes.find((n) => n.id === otherId);
        if (other && links.length < 6) {
          links.push(
            `<span style="color:${edgeStyle(e.edge_type).color}">●</span> ` +
              `${esc(other.label || otherId)} <span style="opacity:.65">(${esc(
                e.edge_type.replace(/_/g, " "),
              )})</span>`,
          );
        }
      });
      const extra = (node.degree(false) ?? 0) > 6 ? `<div style="opacity:.65">…and ${node.degree(false) - 6} more</div>` : "";
      const type = String(node.data("type"));
      showTooltip(
        `<div style="font-weight:700;margin-bottom:2px">${esc(node.data("label"))}</div>` +
          `<div style="color:${nodeColor(type)};text-transform:uppercase;font-size:10px;letter-spacing:.05em;margin-bottom:4px">${esc(type.replace(/_/g, " "))} · ${node.degree(false)} connection(s)</div>` +
          links.join("<br>") +
          extra,
        event.renderedPosition.x,
        event.renderedPosition.y,
      );
    });

    cy.on("mouseover", "edge", (event) => {
      const edgeEl = event.target as EdgeSingular;
      const edge = graph.edges[edgeEl.data("index") as number];
      if (!edge) return;
      edgeEl.connectedNodes().addClass("hover-focus");
      cy.elements().not(edgeEl.connectedNodes().union(edgeEl)).addClass("dimmed");
      const src = graph.nodes.find((n) => n.id === edge.source);
      const dst = graph.nodes.find((n) => n.id === edge.target);
      const meta = edgeStyle(edge.edge_type);
      const confidence =
        edge.confidence ?? (edge.weight <= 1 ? edge.weight : undefined);
      showTooltip(
        `<div style="color:${meta.color};text-transform:uppercase;font-size:10px;letter-spacing:.05em;font-weight:700;margin-bottom:2px">${esc(meta.label)}</div>` +
          `<div style="font-weight:600;margin-bottom:4px">${esc(src?.label ?? edge.source)} ↔ ${esc(dst?.label ?? edge.target)}</div>` +
          (edge.explanation
            ? `<div style="margin-bottom:4px">${esc(edge.explanation)}</div>`
            : "") +
          `<div style="opacity:.7">weight ${esc(edge.weight)}${
            confidence !== undefined
              ? ` · confidence ${Math.round(confidence * 100)}%`
              : ""
          }${edge.timestamp ? ` · ${esc(edge.timestamp).slice(0, 16)}` : ""}</div>`,
        event.renderedPosition.x,
        event.renderedPosition.y,
      );
    });

    cy.on("mousemove", "node, edge", (event) => {
      if (tooltip && tooltip.style.display === "block") {
        const rect = containerRef.current?.getBoundingClientRect();
        const maxX = (rect?.width ?? 600) - tooltip.offsetWidth - 8;
        const maxY = (rect?.height ?? 400) - tooltip.offsetHeight - 8;
        tooltip.style.left = `${Math.max(8, Math.min(event.renderedPosition.x + 14, maxX))}px`;
        tooltip.style.top = `${Math.max(8, Math.min(event.renderedPosition.y + 14, maxY))}px`;
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
          bgcolor: theme.palette.mode === "dark" ? "rgba(18,26,46,0.97)" : "rgba(255,255,255,0.98)",
          border: 1,
          borderColor: "divider",
          boxShadow: 6,
          color: "text.primary",
        }}
      />
    </Box>
  );
}
