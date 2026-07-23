import { Card, CardContent, CardHeader, Divider, Typography } from "@mui/material";
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
              <ChartTooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer>
            <BarChart data={data} margin={{ left: 0, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={60} />
              <YAxis allowDecimals={!!domain} domain={domain} tick={{ fontSize: 11 }} />
              <ChartTooltip />
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
