import HubIcon from "@mui/icons-material/Hub";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { investigationApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { SearchField } from "@/components/common/SearchField";
import { nodeColor } from "@/theme/theme";
import type { GraphEdge, GraphNode } from "@/types";

import { GraphCanvas } from "./GraphCanvas";

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
          <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ flex: 1 }}>
            {nodeTypes.map(([type, count]) => (
              <Chip
                key={type}
                size="small"
                label={`${type} (${count})`}
                onClick={() => toggleType(type)}
                variant={hiddenTypes.has(type) ? "outlined" : "filled"}
                sx={{
                  bgcolor: hiddenTypes.has(type) ? "transparent" : `${nodeColor(type)}33`,
                  color: nodeColor(type),
                  borderColor: nodeColor(type),
                  fontWeight: 700,
                }}
              />
            ))}
          </Stack>
          {stats && (
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
              {stats.node_count} nodes · {stats.edge_count} edges ·{" "}
              {stats.connected_components} component(s)
            </Typography>
          )}
        </Stack>
        <Divider />
        <Stack direction={{ xs: "column", lg: "row" }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <GraphCanvas
              graph={graph}
              search={search}
              hiddenTypes={hiddenTypes}
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
              <Typography variant="body2" color="text.secondary">
                Click a node or edge to inspect its engine-provided details. Scroll to zoom,
                drag to pan.
              </Typography>
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
                {selection.edge.explanation && (
                  <Typography variant="body2">{selection.edge.explanation}</Typography>
                )}
              </Stack>
            )}
          </Box>
        </Stack>
      </Card>
    </Stack>
  );
}
