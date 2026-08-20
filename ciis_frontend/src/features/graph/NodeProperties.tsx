import { Box, LinearProgress, Stack, Tooltip, Typography } from "@mui/material";

import { formatDateTime } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { GraphNode } from "@/types";

/**
 * A node's stored properties, presented as findings rather than as a dump.
 *
 * The panel used to print `properties` verbatim — "betweenness centrality
 * 0.032081" — which is precise and unreadable: six decimal places of a graph
 * measure most investigators have never met, with nothing to compare it
 * against. Exactly the same numbers are shown here, each with the name of what
 * it measures, a sentence of plain English, and a bar scaled against the
 * highest value in this graph so "0.03" reads as "low" without the reader
 * having to know the theory.
 */

type MetricSpec = {
  label: string;
  /** One sentence, no jargon, describing what a high value would mean. */
  meaning: string;
};

/** Graph-analytics properties, in the order an investigator should read them. */
const METRICS: Array<[string, MetricSpec]> = [
  [
    "graph_importance",
    {
      label: "Overall importance",
      meaning:
        "How this item ranks once direct links, bridging and influence are blended together. This is the figure the graph uses to size and rank nodes.",
    },
  ],
  [
    "degree_centrality",
    {
      label: "Direct connections",
      meaning:
        "The share of everything else in the graph that connects straight to this item.",
    },
  ],
  [
    "betweenness_centrality",
    {
      label: "Bridge role",
      meaning:
        "How often the shortest route between two other items passes through this one. A high figure means removing it would break the picture into disconnected pieces.",
    },
  ],
  [
    "pagerank",
    {
      label: "Influence",
      meaning:
        "How much importance flows into this item. A link from something well-connected counts for more than a link from something isolated.",
    },
  ],
];

const METRIC_KEYS = new Set(METRICS.map(([key]) => key));
const COMMUNITY_KEYS = new Set(["community_id", "community_size"]);

/** Human label for a plain attribute key ("file_name" -> "File name"). */
const attributeLabel = (key: string) =>
  key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Dates are stored as ISO strings; everything else is shown as stored. */
function attributeValue(key: string, value: string): string {
  if (/(^|_)(time|timestamp|date|at)$/.test(key) && value.includes("T")) {
    const formatted = formatDateTime(value);
    return formatted || value;
  }
  return value;
}

/** One measure, with its raw value and a bar relative to this graph's maximum. */
function MetricRow({
  spec,
  value,
  max,
}: {
  spec: MetricSpec;
  value: number;
  max: number;
}) {
  // Scaled against the graph's own maximum: PageRank across 73 nodes is
  // ~0.014 at its largest, so an absolute 0–1 bar would read as empty for
  // every node and tell the investigator nothing.
  const relative = max > 0 ? Math.min(1, value / max) : 0;
  const color =
    relative >= 0.66 ? BRAND.critical : relative >= 0.33 ? BRAND.high : BRAND.primary;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {spec.label}
        </Typography>
        <Tooltip title={`Stored value: ${value}`}>
          <Typography
            variant="body2"
            sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, color }}
          >
            {value.toFixed(3)}
          </Typography>
        </Tooltip>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={relative * 100}
        sx={{
          height: 6,
          borderRadius: 3,
          my: 0.5,
          "& .MuiLinearProgress-bar": { bgcolor: color },
        }}
      />
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
        {spec.meaning}
      </Typography>
    </Box>
  );
}

export function NodeProperties({
  node,
  allNodes,
}: {
  node: GraphNode;
  allNodes: GraphNode[];
}) {
  const properties = node.properties ?? {};

  // Highest value of each measure anywhere in the graph, so every bar is
  // scaled against something the reader can name.
  const maxima = new Map<string, number>();
  for (const key of METRIC_KEYS) {
    let max = 0;
    for (const candidate of allNodes) {
      const raw = Number(candidate.properties?.[key]);
      if (Number.isFinite(raw) && raw > max) max = raw;
    }
    maxima.set(key, max);
  }

  const metrics = METRICS.filter(([key]) => {
    const raw = Number(properties[key]);
    return properties[key] !== undefined && Number.isFinite(raw);
  });

  const communityId = properties.community_id;
  const communitySize = Number(properties.community_size);

  const attributes = Object.entries(properties).filter(
    ([key, value]) => value && !METRIC_KEYS.has(key) && !COMMUNITY_KEYS.has(key),
  );

  return (
    <Stack spacing={2}>
      {attributes.length > 0 && (
        <Stack spacing={0.75}>
          {attributes.map(([key, value]) => (
            <Stack key={key} direction="row" spacing={1}>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ minWidth: 96, flexShrink: 0 }}
              >
                {attributeLabel(key)}
              </Typography>
              <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                {attributeValue(key, value)}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}

      {metrics.length > 0 && (
        <Box>
          <Typography variant="overline" color="text.secondary">
            Its place in the graph
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mb: 1.5 }}
          >
            Each bar compares this item against the highest-scoring item in this
            case&apos;s graph, so a full bar means &ldquo;the most of anything
            here&rdquo;, not a perfect score.
          </Typography>
          <Stack spacing={1.75}>
            {metrics.map(([key, spec]) => (
              <MetricRow
                key={key}
                spec={spec}
                value={Number(properties[key])}
                max={maxima.get(key) ?? 0}
              />
            ))}
          </Stack>
        </Box>
      )}

      {communityId && (
        <Box>
          <Typography variant="overline" color="text.secondary">
            Cluster
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Group {communityId}
            {Number.isFinite(communitySize) && communitySize > 0
              ? ` · ${communitySize} member${communitySize === 1 ? "" : "s"}`
              : ""}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            The engine groups items that link to each other more tightly than
            they link to the rest of the graph. Everything in this group tends
            to belong to the same thread of activity.
          </Typography>
        </Box>
      )}
    </Stack>
  );
}
