import { Box, useTheme } from "@mui/material";
import cytoscape, { type Core, type EdgeSingular, type NodeSingular } from "cytoscape";
import { useEffect, useRef } from "react";

import { nodeColor } from "@/theme/theme";
import type { RelationshipGraph } from "@/types";

import type { Selection } from "./GraphTab";

/**
 * Cytoscape renderer for the engine's relationship graph.
 * Pure presentation: nodes/edges/weights come straight from the artifact.
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
  const cyRef = useRef<Core | null>(null);
  const theme = useTheme();

  // Build / rebuild the graph instance when the artifact changes.
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...graph.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label || node.id.split(":").pop() || node.id,
            type: node.node_type,
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
            label: "data(label)",
            "font-size": 9,
            color: theme.palette.text.primary,
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-wrap": "ellipsis",
            "text-max-width": "110px",
            width: (el: NodeSingular) => (el.data("type") === "evidence" ? 34 : 22),
            height: (el: NodeSingular) => (el.data("type") === "evidence" ? 34 : 22),
            "border-width": 2,
            "border-color": theme.palette.background.paper,
          },
        },
        {
          selector: "edge",
          style: {
            width: (el: EdgeSingular) => Math.min(6, 1 + (el.data("weight") as number)),
            "line-color": theme.palette.mode === "dark" ? "#3a4a6e" : "#c3cde2",
            "curve-style": "bezier",
            "target-arrow-shape": graph.directed ? "triangle" : "none",
            "target-arrow-color": theme.palette.mode === "dark" ? "#3a4a6e" : "#c3cde2",
            opacity: 0.85,
          },
        },
        {
          selector: ".highlighted",
          style: {
            "border-color": "#ffd666",
            "border-width": 4,
            "z-index": 10,
          },
        },
        {
          selector: ".dimmed",
          style: { opacity: 0.12 },
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
        padding: 30,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 80,
      },
      wheelSensitivity: 0.2,
    });

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
    <Box
      ref={containerRef}
      sx={{
        height: 560,
        width: "100%",
        bgcolor: theme.palette.mode === "dark" ? "#0d1426" : "#f8faff",
      }}
      aria-label="Relationship graph canvas"
    />
  );
}
