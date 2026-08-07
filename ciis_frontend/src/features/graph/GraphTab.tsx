import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CenterFocusStrongIcon from "@mui/icons-material/CenterFocusStrong";
import FilterAltIcon from "@mui/icons-material/FilterAlt";
import HubIcon from "@mui/icons-material/Hub";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
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
import { useEffect, useMemo, useState } from "react";
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
  buildNeighborhoodView,
  DENSITY_LABELS,
  whyRelevant,
  type Density,
} from "./relevance";
import {
  buildCrossCaseView,
  buildEvidenceProjection,
  buildSearchGraphView,
  buildThreatView,
  filterGraphRelationships,
  GRAPH_MODES,
  type GraphMode,
  type TimestampFilter,
} from "./views";

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

const CONFIDENCE_LEVELS = [
  { value: 0, label: "All links", hint: "Include every stored relationship" },
  { value: 0.5, label: "50%+", hint: "Hide relationships below 50% confidence" },
  { value: 0.75, label: "75%+", hint: "Show stronger relationships only" },
] as const;

const TIMESTAMP_FILTERS: { value: TimestampFilter; label: string; hint: string }[] = [
  { value: "all", label: "Any time", hint: "Do not filter relationships by timestamp" },
  { value: "actual", label: "Actual", hint: "Only relationships with a non-inferred timestamp" },
  { value: "inferred", label: "Inferred", hint: "Only relationships whose timestamp was inferred" },
  { value: "unresolved", label: "No time", hint: "Only relationships without a resolved timestamp" },
];

interface GraphPreferences {
  mode?: GraphMode;
  density?: Density;
  layout?: LayoutMode;
  minimumConfidence?: number;
  timestampFilter?: TimestampFilter;
  hiddenTypes?: string[];
  hiddenEdgeTypes?: string[];
  expandedPairs?: string[];
  focusNodeId?: string | null;
}

function readGraphPreferences(caseId: string): GraphPreferences {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(`ciis:graph:${caseId}`) ?? "{}");
  } catch {
    return {};
  }
}

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
  const initialPreferences = useMemo(() => readGraphPreferences(caseId), [caseId]);
  const [search, setSearch] = useState("");
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(
    new Set(initialPreferences.hiddenTypes ?? []),
  );
  const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(
    new Set(initialPreferences.hiddenEdgeTypes ?? []),
  );
  const [selection, setSelection] = useState<Selection>(null);
  const [layout, setLayout] = useState<LayoutMode>(initialPreferences.layout ?? "force");
  const [density, setDensity] = useState<Density>(initialPreferences.density ?? "leads");
  const [mode, setMode] = useState<GraphMode>(initialPreferences.mode ?? "evidence");
  const [showUploadBatch, setShowUploadBatch] = useState(false);
  const [minimumConfidence, setMinimumConfidence] = useState(
    initialPreferences.minimumConfidence ?? 0,
  );
  const [timestampFilter, setTimestampFilter] = useState<TimestampFilter>(
    initialPreferences.timestampFilter ?? "all",
  );
  const [focusNodeId, setFocusNodeId] = useState<string | null>(
    initialPreferences.focusNodeId ?? null,
  );
  const [expandedPairs, setExpandedPairs] = useState<Set<string>>(
    new Set(initialPreferences.expandedPairs ?? []),
  );
  const [showFilters, setShowFilters] = useState(false);

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const preferences: GraphPreferences = {
      mode,
      density,
      layout,
      minimumConfidence,
      timestampFilter,
      hiddenTypes: [...hiddenTypes],
      hiddenEdgeTypes: [...hiddenEdgeTypes],
      expandedPairs: [...expandedPairs],
      focusNodeId,
    };
    window.localStorage.setItem(
      `ciis:graph:${caseId}`,
      JSON.stringify(preferences),
    );
  }, [
    caseId,
    mode,
    density,
    layout,
    minimumConfidence,
    timestampFilter,
    hiddenTypes,
    hiddenEdgeTypes,
    expandedPairs,
    focusNodeId,
  ]);

  const relationshipFilterResult = useMemo(
    () =>
      graph
        ? filterGraphRelationships(graph, { hiddenEdgeTypes, timestampFilter })
        : null,
    [graph, hiddenEdgeTypes, timestampFilter],
  );
  const filteredGraph = relationshipFilterResult?.graph ?? graph;

  /** The subset actually drawn, plus the accounting of what was held back. */
  const view = useMemo(
    () =>
      filteredGraph
        ? buildGraphView(filteredGraph, {
            density: mode === "full" ? "full" : density,
            hiddenTypes,
            includeUploadBatch: showUploadBatch,
            minimumConfidence,
          })
        : null,
    [filteredGraph, mode, density, hiddenTypes, showUploadBatch, minimumConfidence],
  );

  const modeView = useMemo(() => {
    if (!filteredGraph || !view) return null;
    let result: {
      nodes: GraphNode[];
      edges: GraphEdge[];
      hiddenNodes: number;
      hiddenEdges: number;
      message?: string;
    };
    if (mode === "evidence") {
      result = buildEvidenceProjection(filteredGraph, {
        expandedPairs,
        minimumConfidence,
        includeUploadBatch: showUploadBatch,
      });
    } else if (mode === "cross_case") {
      result = buildCrossCaseView(filteredGraph, minimumConfidence);
    } else if (mode === "threats") {
      result = buildThreatView(filteredGraph, minimumConfidence);
    } else {
      result = {
        nodes: view.nodes,
        edges: view.edges,
        hiddenNodes: view.hidden.total,
        hiddenEdges: view.belowConfidenceEdges,
      };
    }
    const nodes = result.nodes.filter((node) => !hiddenTypes.has(node.node_type));
    const visibleIds = new Set(nodes.map((node) => node.id));
    const edges = result.edges.filter(
      (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
    );
    return {
      ...result,
      nodes,
      edges,
      hiddenNodes: result.hiddenNodes + (result.nodes.length - nodes.length),
      hiddenEdges: result.hiddenEdges + (result.edges.length - edges.length),
    };
  }, [
    filteredGraph,
    view,
    mode,
    expandedPairs,
    minimumConfidence,
    showUploadBatch,
    hiddenTypes,
  ]);

  /** A one-hop view reveals detail only around the item being investigated. */
  const focusedView = useMemo(
    () =>
      filteredGraph &&
      focusNodeId &&
      filteredGraph.nodes.some((node) => node.id === focusNodeId)
        ? buildNeighborhoodView(filteredGraph, focusNodeId, {
            hiddenTypes,
            includeUploadBatch: showUploadBatch,
            minimumConfidence,
          })
        : null,
    [filteredGraph, focusNodeId, hiddenTypes, showUploadBatch, minimumConfidence],
  );

  const searchView = useMemo(
    () =>
      filteredGraph && search.trim()
        ? buildSearchGraphView(filteredGraph, search, { minimumConfidence })
        : null,
    [filteredGraph, search, minimumConfidence],
  );

  const displayNodes = searchView?.nodes ?? focusedView?.nodes ?? modeView?.nodes ?? [];
  const displayEdges = searchView?.edges ?? focusedView?.edges ?? modeView?.edges ?? [];

  /**
   * The artifact-shaped object handed to the canvas. Memoised deliberately:
   * the canvas rebuilds its cytoscape instance and re-runs the layout
   * whenever this identity changes, so a fresh object literal here would
   * tear the whole graph down and lay it out again on every keystroke in the
   * search box.
   */
  const canvasGraph = useMemo(
    () =>
      filteredGraph && view
        ? { ...filteredGraph, nodes: displayNodes, edges: displayEdges }
        : null,
    [filteredGraph, view, displayNodes, displayEdges],
  );

  /** Legend counts: drawn vs. present in the artifact, per type. */
  const nodeTypes = useMemo(() => {
    if (!graph) return [];
    const total = new Map<string, number>();
    graph.nodes.forEach((n) => total.set(n.node_type, (total.get(n.node_type) ?? 0) + 1));
    const drawn = new Map<string, number>();
    displayNodes.forEach((n) => drawn.set(n.node_type, (drawn.get(n.node_type) ?? 0) + 1));
    return [...total.entries()]
      .map(([type, count]) => ({ type, count, drawn: drawn.get(type) ?? 0 }))
      .sort((a, b) => b.count - a.count);
  }, [graph, displayNodes]);

  const edgeTypesPresent = useMemo(
    () => new Set(displayEdges.map((e) => e.edge_type)),
    [displayEdges],
  );
  const edgeTypes = useMemo(
    () => [...new Set(graph?.edges.map((edge) => edge.edge_type) ?? [])].sort(),
    [graph],
  );

  const focusedNode = useMemo(
    () => graph?.nodes.find((node) => node.id === focusNodeId) ?? null,
    [graph, focusNodeId],
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

  const toggleEdgeType = (type: string) => {
    setHiddenEdgeTypes((previous) => {
      const next = new Set(previous);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const selectMode = (next: GraphMode) => {
    setMode(next);
    setFocusNodeId(null);
    setSelection(null);
    setSearch("");
  };

  const applyPreset = (
    preset: "overview" | "strong" | "cross_case" | "threats" | "crypto" | "actual_time",
  ) => {
    setSearch("");
    setSelection(null);
    setFocusNodeId(null);
    setHiddenEdgeTypes(new Set());
    setTimestampFilter("all");
    setHiddenTypes(new Set());
    if (preset === "overview") {
      setMode("evidence");
      setMinimumConfidence(0);
      return;
    }
    if (preset === "strong") {
      setMode("entities");
      setDensity("leads");
      setMinimumConfidence(0.75);
      return;
    }
    if (preset === "cross_case") {
      setMode("cross_case");
      setMinimumConfidence(0.5);
      return;
    }
    if (preset === "threats") {
      setMode("threats");
      setMinimumConfidence(0);
      return;
    }
    if (preset === "actual_time") {
      setMode("evidence");
      setMinimumConfidence(0.5);
      setTimestampFilter("actual");
      return;
    }
    setMode("entities");
    setDensity("standard");
    setMinimumConfidence(0);
    const cryptoTypes = new Set([
      "case",
      "evidence",
      "wallet",
      "crypto_address",
      "blockchain_address",
      "transaction_hash",
    ]);
    setHiddenTypes(
      new Set(graph.nodes.map((node) => node.node_type).filter((type) => !cryptoTypes.has(type))),
    );
  };

  const toggleExpandedPair = (key: string) => {
    setExpandedPairs((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const summary = summaryQuery.data?.report;
  const stats = statsQuery.data?.report;

  /** Plain-English account of everything the view is holding back. */
  const heldBack: string[] = [];
  if (mode === "entities" || mode === "full") {
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
    if (view.belowConfidenceEdges)
      heldBack.push(`${view.belowConfidenceEdges} links below the confidence threshold`);
  }
  if (relationshipFilterResult?.hiddenEdges)
    heldBack.push(`${relationshipFilterResult.hiddenEdges} links hidden by relationship filters`);
  if (mode !== "entities" && mode !== "full" && modeView?.hiddenNodes)
    heldBack.push(`${modeView.hiddenNodes} items outside the selected graph view`);
  if (mode !== "entities" && mode !== "full" && modeView?.hiddenEdges)
    heldBack.push(`${modeView.hiddenEdges} links outside the selected graph view`);

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
            {stats?.analytics_engine && (
              <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ my: 1 }}>
                <Chip size="small" label={`${stats.community_count ?? 0} communities`} />
                <Chip size="small" label={`${stats.backbone_edge_count ?? 0} key links`} />
                <Chip size="small" label={`${stats.bridge_count ?? 0} bridges`} />
                <Chip size="small" variant="outlined" label={stats.analytics_engine} />
              </Stack>
            )}
            {summary.observations.map((obs, i) => (
              <Typography key={i} variant="body2" color="text.secondary">
                • {obs}
              </Typography>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Investigation view
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={mode}
              aria-label="Investigation graph view"
              onChange={(_, next: GraphMode | null) => next && selectMode(next)}
            >
              {GRAPH_MODES.map((option) => (
                <ToggleButton key={option.value} value={option.value} title={option.hint}>
                  {option.label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Stack>
          <Stack
            direction="row"
            spacing={0.75}
            alignItems="center"
            flexWrap="wrap"
            useFlexGap
            sx={{ mt: 1.25 }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
              Quick views
            </Typography>
            <Chip size="small" label="Overview" onClick={() => applyPreset("overview")} />
            <Chip size="small" label="Strongest leads" onClick={() => applyPreset("strong")} />
            <Chip size="small" label="Cross-case indicators" onClick={() => applyPreset("cross_case")} />
            <Chip size="small" label="Threat-flagged" onClick={() => applyPreset("threats")} />
            <Chip size="small" label="Crypto trail" onClick={() => applyPreset("crypto")} />
            <Chip size="small" label="Actual-time links" onClick={() => applyPreset("actual_time")} />
          </Stack>
        </Box>
        <Divider />
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          sx={{ p: 2 }}
          alignItems={{ md: "center" }}
        >
          <SearchField
            value={search}
            onSearch={(value) => {
              setSearch(value);
              if (value.trim()) setFocusNodeId(null);
            }}
            placeholder="Search the complete graph…"
            sx={{ minWidth: 240 }}
          />
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            {/* How much of the artifact to draw. */}
            {(mode === "entities" || mode === "full") && (
              <ToggleButtonGroup
                size="small"
                exclusive
                value={density}
                aria-label="Level of detail"
                onChange={(_, next: Density | null) => {
                  if (!next) return;
                  setDensity(next);
                  setFocusNodeId(null);
                }}
              >
                {DENSITY_LABELS.map((option) => (
                  <ToggleButton key={option.value} value={option.value} title={option.hint}>
                    {option.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            )}
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
            <Button
              size="small"
              variant={showFilters || hiddenTypes.size || hiddenEdgeTypes.size || timestampFilter !== "all" || minimumConfidence > 0 ? "contained" : "outlined"}
              startIcon={<FilterAltIcon />}
              onClick={() => setShowFilters((shown) => !shown)}
            >
              Filters
            </Button>
          </Stack>
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
            Showing {displayNodes.length} of {view.totals.nodes} items ·{" "}
            {displayEdges.length} of {view.totals.edges} links
            {stats ? ` · ${stats.connected_components} component(s)` : ""}
          </Typography>
        </Stack>
        <Divider />

        <Collapse in={showFilters}>
          <Box sx={{ px: 2, py: 1.5, bgcolor: "action.hover" }}>
            <Stack spacing={1.5}>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                  Minimum confidence
                </Typography>
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={minimumConfidence}
                  aria-label="Minimum relationship confidence"
                  onChange={(_, next: number | null) => next !== null && setMinimumConfidence(next)}
                >
                  {CONFIDENCE_LEVELS.map((option) => (
                    <ToggleButton key={option.value} value={option.value} title={option.hint}>
                      {option.label}
                    </ToggleButton>
                  ))}
                </ToggleButtonGroup>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                  Timestamp provenance
                </Typography>
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={timestampFilter}
                  aria-label="Timestamp provenance"
                  onChange={(_, next: TimestampFilter | null) => next && setTimestampFilter(next)}
                >
                  {TIMESTAMP_FILTERS.map((option) => (
                    <ToggleButton key={option.value} value={option.value} title={option.hint}>
                      {option.label}
                    </ToggleButton>
                  ))}
                </ToggleButtonGroup>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                  Item types — click to hide or show
                </Typography>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  {nodeTypes.map(({ type, count, drawn }) => {
                    const isHidden = hiddenTypes.has(type);
                    return (
                      <Chip
                        key={type}
                        size="small"
                        icon={<Box sx={{ display: "flex", pl: 0.75 }}><ShapeSwatch type={type} /></Box>}
                        label={`${titleCase(type.replace(/_/g, " "))} (${drawn === count ? count : `${drawn} of ${count}`})`}
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
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                  Relationship types — click to hide or show
                </Typography>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  {edgeTypes.map((type) => {
                    const hidden = hiddenEdgeTypes.has(type);
                    return (
                      <Chip
                        key={type}
                        size="small"
                        label={edgeStyle(type).label}
                        onClick={() => toggleEdgeType(type)}
                        variant={hidden ? "outlined" : "filled"}
                        sx={{
                          borderColor: edgeStyle(type).color,
                          color: hidden ? "text.disabled" : edgeStyle(type).color,
                          textDecoration: hidden ? "line-through" : undefined,
                        }}
                      />
                    );
                  })}
                </Stack>
              </Box>
              <Button
                size="small"
                variant="text"
                onClick={() => {
                  setHiddenTypes(new Set());
                  setHiddenEdgeTypes(new Set());
                  setTimestampFilter("all");
                  setMinimumConfidence(0);
                }}
                sx={{ alignSelf: "flex-start" }}
              >
                Reset filters
              </Button>
            </Stack>
          </Box>
          <Divider />
        </Collapse>

        {searchView && (
          <Alert
            severity={searchView.matches.length ? "info" : "warning"}
            action={
              <Button size="small" color="inherit" onClick={() => setSearch("")}>
                Clear search
              </Button>
            }
            sx={{ mx: 2, mt: 1.5 }}
          >
            {searchView.message}. Search temporarily reveals matching items and
            their immediate relationships regardless of the selected graph view.
          </Alert>
        )}

        {focusedNode && focusedView && (
          <Alert
            severity="info"
            icon={<CenterFocusStrongIcon />}
            action={
              <Button
                size="small"
                color="inherit"
                startIcon={<ArrowBackIcon />}
                onClick={() => setFocusNodeId(null)}
              >
                Back to overview
              </Button>
            }
            sx={{ mx: 2, mt: 1.5 }}
          >
            Focused on <b>{focusedNode.label || focusedNode.id}</b>: showing its{" "}
            {focusedView.totalNeighbors} direct connection
            {focusedView.totalNeighbors === 1 ? "" : "s"}
            {focusedView.hiddenNeighbors
              ? ` (${focusedView.hiddenNeighbors} lower-ranked connections held back)`
              : ""}
            . Select another item, or return to the overview when finished.
          </Alert>
        )}

        {/* What is being held back, and how to get it back. */}
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={1}
          alignItems={{ md: "center" }}
          sx={{ px: 2, py: 1.25 }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
            {searchView
              ? "Search mode is showing matches from the complete stored artifact."
              : focusedView
              ? "Focus mode shows one item and its immediate relationships; the stored graph is unchanged."
              : heldBack.length === 0
              ? modeView?.message ?? "Drawing everything the engine stored for this case."
              : `Not drawn: ${heldBack.join("; ")}. Use Full graph or reset the filters to include them.`}
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

        {view.capped && !focusedView && (mode === "entities" || mode === "full") && (
          <Alert severity="info" sx={{ mx: 2, mb: 1.5 }}>
            This case is larger than one screen can show clearly, so the{" "}
            {view.hidden.overBudget} least-connected items are held back. Search
            for a value to jump straight to it, or narrow the type filters below.
          </Alert>
        )}

        <Divider />
        <Stack direction={{ xs: "column", lg: "row" }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {displayNodes.length === 0 ? (
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
                focusNodeId={focusNodeId}
                viewportKey={`ciis:graph:viewport:${caseId}:${mode}`}
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
                  The default Evidence Map combines every phone, wallet, account,
                  timestamp and correlation between the same evidence pair into
                  one labelled line. Click that line to reveal the underlying findings.
                </Typography>
                <Stack spacing={0.75}>
                  {[
                    ["Hover", "highlights an item and lists what it links to"],
                    ["Click", "opens the item's full details and an Explore connections action"],
                    ["Explore", "shows only that item and its immediate relationships"],
                    ["Search", "searches the complete artifact, including hidden items"],
                    ["Views", "switches between evidence, entities, cross-case, threats and full data"],
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
                    <Button
                      size="small"
                      variant={focusNodeId === nodeId ? "outlined" : "contained"}
                      startIcon={
                        focusNodeId === nodeId ? (
                          <ArrowBackIcon />
                        ) : (
                          <CenterFocusStrongIcon />
                        )
                      }
                      onClick={() =>
                        setFocusNodeId((current) =>
                          current === nodeId ? null : nodeId,
                        )
                      }
                      sx={{ alignSelf: "flex-start" }}
                    >
                      {focusNodeId === nodeId
                        ? "Back to overview"
                        : `Explore ${connections.length} connection${
                            connections.length === 1 ? "" : "s"
                          }`}
                    </Button>
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
                              onClick={() => {
                                setSelection({ kind: "node", node: other });
                                if (focusNodeId) setFocusNodeId(other.id);
                              }}
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
                {selection.edge.projection ? (
                  <Stack spacing={1}>
                    <Typography variant="body2" color="text.secondary">
                      {selection.edge.projection.relationship_count} underlying finding
                      {selection.edge.projection.relationship_count === 1 ? "" : "s"}
                    </Typography>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {selection.edge.projection.relationship_types.map((type) => (
                        <Chip key={type} size="small" label={edgeStyle(type).label} variant="outlined" />
                      ))}
                    </Stack>
                    {selection.edge.projection.entity_ids.length > 0 && (
                      <>
                        <Typography variant="subtitle2">Shared entities</Typography>
                        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                          {selection.edge.projection.entity_ids.map((id) => {
                            const entity = graph.nodes.find((node) => node.id === id);
                            return (
                              <Chip
                                key={id}
                                size="small"
                                label={entity?.label || id}
                                onClick={() => entity && setSelection({ kind: "node", node: entity })}
                                clickable={Boolean(entity)}
                              />
                            );
                          })}
                        </Stack>
                      </>
                    )}
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => toggleExpandedPair(selection.edge.projection!.pair_key)}
                      sx={{ alignSelf: "flex-start" }}
                    >
                      {expandedPairs.has(selection.edge.projection.pair_key)
                        ? "Collapse shared entities"
                        : "Reveal shared entities"}
                    </Button>
                  </Stack>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Weight: {selection.edge.weight}
                  </Typography>
                )}
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
