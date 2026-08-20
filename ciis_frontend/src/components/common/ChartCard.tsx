import { Card, CardContent, CardHeader, Divider, Typography, useTheme } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { BRAND } from "@/theme/theme";

export const CHART_COLORS = [
  BRAND.primary,
  BRAND.accent,
  BRAND.high,
  BRAND.critical,
  BRAND.medium,
  BRAND.low,
  "#a970ff",
  "#f759ab",
];

/**
 * Bar/pie chart card for engine-produced metrics. Purely presentational —
 * data must come straight from a stored artifact, never client-side math.
 */
export function ChartCard({
  title,
  subheader,
  data,
  kind = "bar",
  domain,
  valueLabel = "Count",
}: {
  title: string;
  subheader?: string;
  data: { name: string; value: number }[];
  kind?: "bar" | "pie";
  /** Fixed Y-axis domain (e.g. [0, 100] for score charts). */
  domain?: [number, number];
  /**
   * What a bar/slice actually counts. Without it the tooltip prints the raw
   * series key — "value : 11" — which names nothing the reader recognises.
   */
  valueLabel?: string;
}) {
  const theme = useTheme();

  /**
   * Recharts ships light-mode defaults: a white tooltip card with #666 label
   * text, and #666 axis ticks. Against the dark theme that is grey on grey —
   * the hovered value was the least readable text on the page. Every chart
   * surface is pinned to the theme's own palette instead, so both themes stay
   * legible.
   */
  const tickStyle = { fontSize: 11, fill: theme.palette.text.secondary };
  const axisStroke = theme.palette.divider;
  const tooltipProps = {
    contentStyle: {
      background: theme.palette.background.paper,
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: 8,
      boxShadow: theme.shadows[3],
      fontSize: 12,
    },
    labelStyle: {
      color: theme.palette.text.primary,
      fontWeight: 700,
      marginBottom: 4,
    },
    itemStyle: { color: theme.palette.text.primary },
    formatter: (value: number) => [value, valueLabel] as [number, string],
  };

  return (
    <Card sx={{ flex: "1 1 420px", minWidth: 0 }}>
      <CardHeader title={title} subheader={subheader} />
      <Divider />
      <CardContent sx={{ height: 300 }}>
        {data.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No data in this artifact.
          </Typography>
        ) : kind === "pie" ? (
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={95}>
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <ChartTooltip {...tooltipProps} />
              <Legend wrapperStyle={{ color: theme.palette.text.secondary, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer>
            <BarChart data={data} margin={{ left: 0, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={axisStroke} opacity={0.6} />
              <XAxis
                dataKey="name"
                tick={tickStyle}
                stroke={axisStroke}
                interval={0}
                angle={-18}
                textAnchor="end"
                height={60}
              />
              <YAxis
                allowDecimals={!!domain}
                domain={domain}
                tick={tickStyle}
                stroke={axisStroke}
              />
              <ChartTooltip
                {...tooltipProps}
                cursor={{ fill: theme.palette.action.hover }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
