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
  FormControlLabel,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
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
  edgeStyle,
  GraphCanvas,
  nodeShape,
  type LayoutMode,
} from "./GraphCanvas";
import {
  buildGraphView,
  DENSITY_LABELS,
  whyRelevant,
  type Density,
} from "./relevance";

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
    value: "structure",
    label: "Structure",
    hint: "Case at the centre, evidence around it, entities on the outer ring",
  },
  {
    value: "force",
    label: "Clusters",
    hint: "Force-directed with overlap avoidance (fcose) — related items group together. Best on a large case.",
  },
  { value: "circle", label: "Circle", hint: "All nodes on one ring, busiest first — good for spotting hubs" },
];

export type Selection =
  | { kind: "node"; node: GraphNode }
  | { kind: "edge"; edge: GraphEdge }
  | null;

/**
 * Module 6 - Relationship graph viewer.
 *
 * Renders the engine-generated graph artifact: no layout-side inference, no
 * computed relationships. What the view *does* decide is how much of the
 * artifact to draw at once — see `relevance.ts`. A fifty-upload case holds
 * several hundred nodes, and drawing all of them produces a picture that
 * hides the two or three entities the case actually turns on. Everything held
 * back is counted and reported, and one control puts it all back.
 */
export function GraphTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState("");
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<Selection>(null);
  const [layout, setLayout] = useState<LayoutMode>("structure");
  const [density, setDensity] = useState<Density>("standard");
  const [showUploadBatch, setShowUploadBatch] = useState(false);

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

  /** The subset actually drawn, plus the accounting of what was held back. */
  const view = useMemo(
    () =>
      graph
        ? buildGraphView(graph, {
            density,
            hiddenTypes,
            includeUploadBatch: showUploadBatch,
          })
        : null,
    [graph, density, hiddenTypes, showUploadBatch],
  );

  /**
   * The artifact-shaped object handed to the canvas. Memoised deliberately:
   * the canvas rebuilds its cytoscape instance and re-runs the layout
   * whenever this identity changes, so a fresh object literal here would
   * tear the whole graph down and lay it out again on every keystroke in the
   * search box.
   */
  const canvasGraph = useMemo(
    () => (graph && view ? { ...graph, nodes: view.nodes, edges: view.edges } : null),
    [graph, view],
  );

  /** Legend counts: drawn vs. present in the artifact, per type. */
  const nodeTypes = useMemo(() => {
    if (!graph) return [];
    const total = new Map<string, number>();
    graph.nodes.forEach((n) => total.set(n.node_type, (total.get(n.node_type) ?? 0) + 1));
    const drawn = new Map<string, number>();
    view?.nodes.forEach((n) => drawn.set(n.node_type, (drawn.get(n.node_type) ?? 0) + 1));
    return [...total.entries()]
      .map(([type, count]) => ({ type, count, drawn: drawn.get(type) ?? 0 }))
      .sort((a, b) => b.count - a.count);
  }, [graph, view]);

  const edgeTypesPresent = useMemo(
    () => new Set(view?.edges.map((e) => e.edge_type) ?? []),
    [view],
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
  if (!graph || !view || !canvasGraph) {
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

  /** Plain-English account of everything the view is holding back. */
  const heldBack: string[] = [];
  if (view.hidden.singleMention)
    heldBack.push(
      `${view.hidden.singleMention} entities mentioned in only one piece of evidence`,
    );
  if (view.hidden.lowIdentity)
    heldBack.push(`${view.hidden.lowIdentity} one-off dates, times and amounts`);
  if (view.hidden.mirrored)
    heldBack.push(`${view.hidden.mirrored} timeline events (see the Timeline tab)`);
  if (view.hidden.byTypeFilter)
    heldBack.push(`${view.hidden.byTypeFilter} hidden by the type filters above`);
  if (view.hidden.overBudget)
    heldBack.push(`${view.hidden.overBudget} beyond the readable limit for one screen`);

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
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            {/* How much of the artifact to draw. */}
            <ToggleButtonGroup
              size="small"
              exclusive
              value={density}
              aria-label="Level of detail"
              onChange={(_, next: Density | null) => next && setDensity(next)}
            >
              {DENSITY_LABELS.map((option) => (
                <ToggleButton key={option.value} value={option.value} title={option.hint}>
                  {option.label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={layout}
              aria-label="Layout"
              onChange={(_, next: LayoutMode | null) => next && setLayout(next)}
            >
              {LAYOUT_LABELS.map((option) => (
                <ToggleButton key={option.value} value={option.value} title={option.hint}>
                  {option.label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Stack>
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
            Showing {view.nodes.length} of {view.totals.nodes} items ·{" "}
            {view.edges.length} of {view.totals.edges} links
            {stats ? ` · ${stats.connected_components} component(s)` : ""}
          </Typography>
        </Stack>
        <Divider />

        {/* What is being held back, and how to get it back. */}
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={1}
          alignItems={{ md: "center" }}
          sx={{ px: 2, py: 1.25 }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
            {heldBack.length === 0
              ? "Drawing everything the engine stored for this case."
              : `Not drawn: ${heldBack.join("; ")}. Switch to “Everything” to include them.`}
          </Typography>
          {view.uploadBatchEdges > 0 && (
            <Tooltip title="These links only mean two files were uploaded in the same batch — an artifact of how the evidence was collected, not of the crime. They grow with every upload and are the main cause of a tangled graph.">
              <FormControlLabel
                sx={{ mr: 0 }}
                control={
                  <Switch
                    size="small"
                    checked={showUploadBatch}
                    onChange={(e) => setShowUploadBatch(e.target.checked)}
                    inputProps={{ "aria-label": "Show links between files uploaded together" }}
                  />
                }
                label={
                  <Typography variant="caption" color="text.secondary">
                    Show {view.uploadBatchEdges} “uploaded together” links
                  </Typography>
                }
              />
            </Tooltip>
          )}
        </Stack>

        {view.capped && (
          <Alert severity="info" sx={{ mx: 2, mb: 1.5 }}>
            This case is larger than one screen can show clearly, so the{" "}
            {view.hidden.overBudget} least-connected items are held back. Search
            for a value to jump straight to it, or narrow the type filters below.
          </Alert>
        )}

        <Divider />

        {/* Node legend — doubles as a filter: click a type to show/hide it. */}
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mb: 1 }}
          >
            What you are looking at — each shape is one item the engine found.
            Click a type to hide or show it. A count like “5 of 9” means four are
            held back at this level of detail.
          </Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
            {nodeTypes.map(({ type, count, drawn }) => {
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
                  label={`${titleCase(type.replace(/_/g, " "))} (${
                    drawn === count ? count : `${drawn} of ${count}`
                  })`}
                  onClick={() => toggleType(type)}
                  variant={isHidden ? "outlined" : "filled"}
                  sx={{
                    bgcolor: isHidden ? "transparent" : `${nodeColor(type)}26`,
                    color: isHidden ? "text.disabled" : nodeColor(type),
                    borderColor: nodeColor(type),
                    fontWeight: 700,
                    opacity: !isHidden && drawn === 0 ? 0.45 : 1,
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
            {view.nodes.length === 0 ? (
              <Box sx={{ height: 560, display: "grid", placeItems: "center", p: 4 }}>
                <Typography variant="body2" color="text.secondary" align="center">
                  Every item is hidden by the current filters. Turn a type back on
                  above, or switch the level of detail to “Everything”.
                </Typography>
              </Box>
            ) : (
              <GraphCanvas
                graph={canvasGraph}
                signals={view.signals}
                search={search}
                layout={layout}
                onSelect={setSelection}
              />
            )}
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
                <Typography variant="body2" color="text.secondary">
                  By default the canvas draws the items that <b>link evidence
                  together</b>. Something mentioned in a single document is a
                  detail of that document, and lives on its evidence page.
                </Typography>
                <Stack spacing={0.75}>
                  {[
                    ["Hover", "highlights an item and lists what it links to"],
                    ["Click", "opens the engine's full details on that item"],
                    ["Search", "finds a value, zooms to it and dims the rest"],
                    ["Detail", "Leads / Standard / Everything changes how much is drawn"],
                    ["Scroll / drag", "zooms and pans; zoom in to reveal every label"],
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
            {selection?.kind === "node" &&
              (() => {
                // The complete record for this node, drawn from the *full*
                // artifact rather than the filtered view: the canvas may be
                // showing a summary, but the detail panel never should.
                const nodeId = selection.node.id;
                const connections = graph.edges
                  .filter((e) => e.source === nodeId || e.target === nodeId)
                  .map((e) => {
                    const otherId = e.source === nodeId ? e.target : e.source;
                    const other = graph.nodes.find((n) => n.id === otherId);
                    return other ? { edge: e, other } : null;
                  })
                  .filter((c): c is { edge: GraphEdge; other: GraphNode } => c !== null);
                const why = whyRelevant(
                  view.signals.get(nodeId),
                  selection.node.node_type,
                );
                return (
                  <Stack spacing={1}>
                    <Chip
                      size="small"
                      label={selection.node.node_type.replace(/_/g, " ")}
                      sx={{
                        alignSelf: "flex-start",
                        bgcolor: `${nodeColor(selection.node.node_type)}33`,
                        color: nodeColor(selection.node.node_type),
                        fontWeight: 700,
                      }}
                    />
                    <Typography
                      variant="subtitle1"
                      sx={{ wordBreak: "break-all", fontWeight: 700 }}
                    >
                      {selection.node.label || selection.node.id}
                    </Typography>
                    {why && (
                      <Typography variant="body2" color="text.secondary">
                        {why}
                      </Typography>
                    )}
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ wordBreak: "break-all" }}
                    >
                      {selection.node.id} · {connections.length} connection
                      {connections.length === 1 ? "" : "s"}
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
                    {Object.entries(selection.node.properties)
                      .filter(([, value]) => value)
                      .map(([key, value]) => (
                        <Stack key={key} direction="row" spacing={1}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ minWidth: 90, flexShrink: 0 }}
                          >
                            {key.replace(/_/g, " ")}
                          </Typography>
                          <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                            {value}
                          </Typography>
                        </Stack>
                      ))}
                    {connections.length > 0 && (
                      <>
                        <Divider sx={{ my: 0.5 }} />
                        <Typography variant="subtitle2">Connected to</Typography>
                        <Stack spacing={0.75}>
                          {connections.map(({ edge, other }, i) => (
                            <Stack
                              key={`${other.id}:${i}`}
                              direction="row"
                              spacing={1}
                              alignItems="flex-start"
                              onClick={() => setSelection({ kind: "node", node: other })}
                              sx={{
                                cursor: "pointer",
                                borderRadius: 1,
                                px: 0.75,
                                py: 0.5,
                                mx: -0.75,
                                "&:hover": { bgcolor: "action.hover" },
                              }}
                            >
                              <Box sx={{ pt: 0.4 }}>
                                <ShapeSwatch type={other.node_type} />
                              </Box>
                              <Box sx={{ minWidth: 0 }}>
                                <Typography
                                  variant="body2"
                                  sx={{ fontWeight: 600, wordBreak: "break-all" }}
                                >
                                  {other.label || other.id}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  <Box
                                    component="span"
                                    sx={{ color: edgeStyle(edge.edge_type).color }}
                                  >
                                    ●
                                  </Box>{" "}
                                  {edge.edge_type.replace(/_/g, " ")}
                                  {edge.confidence !== undefined && edge.confidence !== null
                                    ? ` · ${Math.round(edge.confidence * 100)}%`
                                    : ""}
                                </Typography>
                                {edge.explanation && (
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    sx={{ display: "block" }}
                                  >
                                    {edge.explanation}
                                  </Typography>
                                )}
                              </Box>
                            </Stack>
                          ))}
                        </Stack>
                      </>
                    )}
                  </Stack>
                );
              })()}
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
        {/* Edge legend — only the relationship types actually drawn. */}
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
