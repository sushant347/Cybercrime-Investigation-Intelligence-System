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
}: {
  title: string;
  subheader?: string;
  data: { name: string; value: number }[];
  kind?: "bar" | "pie";
  /** Fixed Y-axis domain (e.g. [0, 100] for score charts). */
  domain?: [number, number];
}) {
  const theme = useTheme();

  // Recharts renders its own SVG text and tooltip surface, so it inherits
  // nothing from the MUI theme: axis ticks default to #666 and the tooltip to
  // a white card. On the dark canvas the ticks were barely legible and the
  // tooltip flashed a white rectangle. Both are handed theme colours instead.
  const axisTick = { fontSize: 11, fill: theme.palette.text.secondary };
  const tooltipStyle = {
    backgroundColor: theme.palette.background.paper,
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: 8,
    color: theme.palette.text.primary,
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
              <ChartTooltip contentStyle={tooltipStyle} itemStyle={{ color: theme.palette.text.primary }} />
              <Legend formatter={(v) => <span style={{ color: theme.palette.text.secondary }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer>
            <BarChart data={data} margin={{ left: 0, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
              <XAxis
                dataKey="name"
                tick={axisTick}
                stroke={theme.palette.divider}
                interval={0}
                angle={-18}
                textAnchor="end"
                height={60}
              />
              <YAxis
                allowDecimals={!!domain}
                domain={domain}
                tick={axisTick}
                stroke={theme.palette.divider}
              />
              <ChartTooltip
                contentStyle={tooltipStyle}
                itemStyle={{ color: theme.palette.text.primary }}
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
