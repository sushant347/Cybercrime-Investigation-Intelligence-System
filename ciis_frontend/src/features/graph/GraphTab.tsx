import HubIcon from "@mui/icons-material/Hub";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { investigationApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { SearchField } from "@/components/common/SearchField";
import { formatDateTime, titleCase } from "@/lib/format";
import { nodeColor } from "@/theme/theme";
import type { GraphEdge, GraphNode } from "@/types";

import {
  EDGE_STYLES,
  GraphCanvas,
  nodeShape,
  type LayoutMode,
} from "./GraphCanvas";

/** CSS clip-path previews mirroring the cytoscape node shapes. */
const SHAPE_CSS: Record<string, string> = {
  diamond: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)",
  hexagon: "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)",
};

function ShapeSwatch({ type }: { type: string }) {
  const shape = nodeShape(type);
  return (
    <Box
      sx={{
        width: 15,
        height: 15,
        flexShrink: 0,
        bgcolor: nodeColor(type),
        borderRadius: shape === "ellipse" ? "50%" : shape === "round-rectangle" ? "3px" : 0,
        clipPath: SHAPE_CSS[shape],
      }}
    />
  );
}

const LAYOUT_LABELS: { value: LayoutMode; label: string; hint: string }[] = [
  {
    value: "bipartite",
    label: "Shared entities",
    hint: "Evidence in one column, entities in the other — the default, clearest view. Never overlaps.",
  },
  {
    value: "force",
    label: "Clusters",
    hint: "Force-directed with overlap avoidance (fcose) — related items group together",
  },
  {
    value: "structure",
    label: "Concentric",
    hint: "Case at the centre, evidence around it, entities on the outer ring",
  },
  { value: "circle", label: "Circle", hint: "All nodes on one ring — good for spotting hubs" },
];

export type Selection =
  | { kind: "node"; node: GraphNode }
  | { kind: "edge"; edge: GraphEdge }
  | null;

/**
 * Module 6 - Relationship graph viewer.
 * Renders the engine-generated graph artifact verbatim: no layout-side
 * inference, no computed relationships - pure visualization.
 */
export function GraphTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState("");
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<Selection>(null);
  const [layout, setLayout] = useState<LayoutMode>("bipartite");

  const graphQuery = useQuery({
    queryKey: ["artifact", caseId, "graph"],
    queryFn: () => investigationApi.graph(caseId),
    retry: false,
  });
  const summaryQuery = useQuery({
    queryKey: ["artifact", caseId, "graph_summary"],
    queryFn: () => investigationApi.graphSummary(caseId),
    retry: false,
  });
  const statsQuery = useQuery({
    queryKey: ["artifact", caseId, "graph_statistics"],
    queryFn: () => investigationApi.graphStatistics(caseId),
    retry: false,
  });

  const graph = graphQuery.data?.report;

  const nodeTypes = useMemo(() => {
    const counts = new Map<string, number>();
    graph?.nodes.forEach((n) => counts.set(n.node_type, (counts.get(n.node_type) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [graph]);

  const edgeTypesPresent = useMemo(
    () => new Set(graph?.edges.map((e) => e.edge_type) ?? []),
    [graph],
  );

  /** Structural node types; anything else is an extracted-entity node. */
  const hasEntityNodes = useMemo(
    () =>
      graph?.nodes.some(
        (n) => !["case", "evidence", "timeline_event"].includes(n.node_type),
      ) ?? false,
    [graph],
  );
  const evidenceNodeCount = useMemo(
    () => graph?.nodes.filter((n) => n.node_type === "evidence").length ?? 0,
    [graph],
  );

  if (graphQuery.isPending) return <DetailSkeleton />;
  if (!graph) {
    return (
      <EmptyState
        icon={<HubIcon />}
        title="Relationship graph not generated"
        description='Run the investigation analysis to build the relationship graph (evidence, phones, emails, URLs, domains, wallets, accounts, devices, persons, brands).'
      />
    );
  }

  const toggleType = (type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const summary = summaryQuery.data?.report;
  const stats = statsQuery.data?.report;

  return (
    <Stack spacing={2}>
      {!hasEntityNodes && evidenceNodeCount > 0 && (
        <Alert severity="info">
          This stored graph contains no entity nodes (phones, URLs, wallets,
          amounts…). If entities have been extracted from the evidence — or the
          engine has been updated — run the analysis again to regenerate the
          graph with entity relationships included.
        </Alert>
      )}
      {summary?.headline && (
        <Card>
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {summary.headline}
            </Typography>
            {summary.observations.map((obs, i) => (
              <Typography key={i} variant="body2" color="text.secondary">
                • {obs}
              </Typography>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          sx={{ p: 2 }}
          alignItems={{ md: "center" }}
        >
          <SearchField
            value={search}
            onSearch={setSearch}
            placeholder="Search nodes (value, label, id)…"
            sx={{ minWidth: 240 }}
          />
          <ToggleButtonGroup
            size="small"
            exclusive
            value={layout}
            onChange={(_, next: LayoutMode | null) => next && setLayout(next)}
          >
            {LAYOUT_LABELS.map((option) => (
              <ToggleButton key={option.value} value={option.value} title={option.hint}>
                {option.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <Box sx={{ flex: 1 }} />
          {stats && (
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
              {stats.node_count} nodes · {stats.edge_count} edges ·{" "}
              {stats.connected_components} component(s)
            </Typography>
          )}
        </Stack>
        <Divider />

        {/* Node legend — doubles as a filter: click a type to show/hide it. */}
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mb: 1 }}
          >
            What you are looking at — each circle is one item the engine found.
            Click a type to hide or show it.
          </Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
            {nodeTypes.map(([type, count]) => {
              const isHidden = hiddenTypes.has(type);
              return (
                <Chip
                  key={type}
                  size="small"
                  icon={
                    <Box sx={{ display: "flex", pl: 0.75 }}>
                      <ShapeSwatch type={type} />
                    </Box>
                  }
                  label={`${titleCase(type.replace(/_/g, " "))} (${count})`}
                  onClick={() => toggleType(type)}
                  variant={isHidden ? "outlined" : "filled"}
                  sx={{
                    bgcolor: isHidden ? "transparent" : `${nodeColor(type)}26`,
                    color: isHidden ? "text.disabled" : nodeColor(type),
                    borderColor: nodeColor(type),
                    fontWeight: 700,
                    textDecoration: isHidden ? "line-through" : undefined,
                  }}
                />
              );
            })}
          </Stack>
        </Box>
        <Divider />
        <Stack direction={{ xs: "column", lg: "row" }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <GraphCanvas
              graph={graph}
              search={search}
              hiddenTypes={hiddenTypes}
              layout={layout}
              onSelect={setSelection}
            />
          </Box>
          <Box
            sx={{
              width: { xs: "100%", lg: 340 },
              borderLeft: { lg: 1 },
              borderTop: { xs: 1, lg: 0 },
              borderColor: { xs: "divider", lg: "divider" },
              p: 2,
              maxHeight: 560,
              overflow: "auto",
            }}
          >
            {!selection && (
              <Stack spacing={1.25}>
                <Typography variant="subtitle2">How to read this graph</Typography>
                <Typography variant="body2" color="text.secondary">
                  Lines show how the engine connected things. A line between two
                  pieces of evidence means they share something — the same phone
                  number, wallet, amount, or a close acquisition time.
                </Typography>
                <Stack spacing={0.75}>
                  {[
                    ["Hover", "highlights an item and lists what it links to"],
                    ["Click", "opens the engine's full details on that item"],
                    ["Search", "finds a value and dims everything unrelated"],
                    ["Scroll / drag", "zooms and pans; use the buttons to refit"],
                  ].map(([action, meaning]) => (
                    <Stack key={action} direction="row" spacing={1}>
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 700, minWidth: 92, flexShrink: 0 }}
                      >
                        {action}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {meaning}
                      </Typography>
                    </Stack>
                  ))}
                </Stack>
              </Stack>
            )}
            {selection?.kind === "node" && (
              <Stack spacing={1}>
                <Chip
                  size="small"
                  label={selection.node.node_type}
                  sx={{
                    alignSelf: "flex-start",
                    bgcolor: `${nodeColor(selection.node.node_type)}33`,
                    color: nodeColor(selection.node.node_type),
                    fontWeight: 700,
                  }}
                />
                <Typography variant="subtitle1" sx={{ wordBreak: "break-all", fontWeight: 700 }}>
                  {selection.node.label || selection.node.id}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ wordBreak: "break-all" }}>
                  {selection.node.id}
                </Typography>
                {selection.node.node_type === "evidence" && (
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<OpenInNewIcon />}
                    component={RouterLink}
                    to={`/cases/${caseId}/evidence/${selection.node.label || selection.node.id.split(":").pop()}`}
                    sx={{ alignSelf: "flex-start" }}
                  >
                    Open evidence
                  </Button>
                )}
                {Object.entries(selection.node.properties).map(([key, value]) => (
                  <Stack key={key} direction="row" spacing={1}>
                    <Typography variant="body2" color="text.secondary" sx={{ minWidth: 90 }}>
                      {key}
                    </Typography>
                    <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                      {value}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            )}
            {selection?.kind === "edge" && (
              <Stack spacing={1}>
                <Chip size="small" label={selection.edge.edge_type} color="primary" sx={{ alignSelf: "flex-start" }} />
                <Typography variant="body2" sx={{ fontFamily: '"JetBrains Mono", monospace', wordBreak: "break-all" }}>
                  {selection.edge.source} → {selection.edge.target}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Weight: {selection.edge.weight}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Confidence: {((selection.edge.confidence ?? Math.min(selection.edge.weight, 1)) * 100).toFixed(0)}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Timestamp: {selection.edge.timestamp
                    ? `${formatDateTime(selection.edge.timestamp)}${selection.edge.timestamp_inferred ? " (inferred)" : ""}`
                    : "Unresolved"}
                </Typography>
                {(selection.edge.source_evidence_ids?.length ?? 0) > 0 && (
                  <Stack spacing={0.5}>
                    <Typography variant="body2" color="text.secondary">
                      Source evidence:
                    </Typography>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {selection.edge.source_evidence_ids?.map((id) => (
                        <Chip
                          key={id}
                          size="small"
                          label={id}
                          component={RouterLink}
                          to={`/cases/${caseId}/evidence/${id}`}
                          clickable
                          variant="outlined"
                        />
                      ))}
                    </Stack>
                  </Stack>
                )}
                {selection.edge.explanation && (
                  <Typography variant="body2">{selection.edge.explanation}</Typography>
                )}
              </Stack>
            )}
          </Box>
        </Stack>
        <Divider />
        {/* Edge legend — only the relationship types present in this graph. */}
        <Stack
          direction="row"
          spacing={2}
          flexWrap="wrap"
          useFlexGap
          sx={{ px: 2, py: 1.25 }}
        >
          {Object.entries(EDGE_STYLES)
            .filter(([type]) => edgeTypesPresent.has(type))
            .map(([type, meta]) => (
              <Stack key={type} direction="row" spacing={0.75} alignItems="center">
                <Box
                  sx={{
                    width: 26,
                    height: 0,
                    borderTop: 3,
                    borderColor: meta.color,
                    borderTopStyle: meta.style,
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {meta.label}
                </Typography>
              </Stack>
            ))}
          <Typography variant="caption" color="text.disabled" sx={{ ml: "auto" }}>
            Hover a node or line for details · scroll to zoom · drag to pan
          </Typography>
        </Stack>
      </Card>
    </Stack>
  );
}
