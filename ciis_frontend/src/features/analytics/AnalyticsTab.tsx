import InsightsIcon from "@mui/icons-material/Insights";
import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
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

import { investigationApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { ValueCount } from "@/types";

const COLORS = [BRAND.primary, BRAND.accent, BRAND.high, BRAND.critical, BRAND.medium, BRAND.low, "#a970ff", "#f759ab"];

function recordToChart(record: Record<string, number>) {
  return Object.entries(record)
    .filter(([, v]) => typeof v === "number")
    .map(([name, value]) => ({ name: titleCase(name), value }));
}

function valueCountToChart(items: ValueCount[]) {
  return items.map((i) => ({ name: i.value, value: i.count }));
}

function ChartCard({
  title,
  subheader,
  data,
  kind = "bar",
}: {
  title: string;
  subheader?: string;
  data: { name: string; value: number }[];
  kind?: "bar" | "pie";
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
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
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
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <ChartTooltip />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

/** Module 8 - Analytics dashboard rendered from the analytics artifact. */
export function AnalyticsTab({ caseId }: { caseId: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["artifact", caseId, "analytics"],
    queryFn: () => investigationApi.analytics(caseId),
    retry: false,
  });

  if (isPending) return <DetailSkeleton />;
  const analytics = data?.report;
  if (!analytics) {
    return (
      <EmptyState
        icon={<InsightsIcon />}
        title="Analytics not generated"
        description="Run the investigation analysis to compute threat, entity, brand, wallet, campaign, timeline, and quality statistics."
      />
    );
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <ChartCard
          title="Threat Distribution"
          subheader="threat_statistics"
          data={recordToChart(analytics.threat_statistics)}
          kind="pie"
        />
        <ChartCard
          title="Entity Statistics"
          subheader="Occurrences per entity type"
          data={recordToChart(analytics.entity_statistics)}
        />
        <ChartCard
          title="Brand Statistics"
          subheader="Impersonated / referenced brands"
          data={valueCountToChart(analytics.brand_statistics)}
        />
        <ChartCard
          title="Wallet & Payment IDs"
          subheader="wallet_statistics"
          data={valueCountToChart(analytics.wallet_statistics)}
        />
        <ChartCard
          title="Top URLs"
          subheader="url_statistics"
          data={valueCountToChart(analytics.url_statistics)}
        />
        <ChartCard
          title="Campaign Statistics"
          subheader="campaign_statistics"
          data={recordToChart(analytics.campaign_statistics)}
        />
        <ChartCard
          title="Timeline Statistics"
          subheader="timeline_statistics"
          data={recordToChart(analytics.timeline_statistics)}
        />
        <ChartCard
          title="Evidence Quality"
          subheader="OCR & processing quality metrics"
          data={recordToChart(analytics.evidence_quality_statistics)}
        />
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Card sx={{ flex: 1, width: "100%" }}>
          <CardHeader title="Correlation Statistics" subheader="Raw engine metrics" />
          <Divider />
          <KeyValueTable data={analytics.correlation_statistics} />
        </Card>
        <Card sx={{ flex: 1, width: "100%" }}>
          <CardHeader title="Metadata Statistics" subheader="Raw engine metrics" />
          <Divider />
          <KeyValueTable data={analytics.metadata_statistics} />
        </Card>
      </Stack>

      {Object.keys(analytics.top_entities).length > 0 && (
        <Card>
          <CardHeader title="Top Entities by Type" subheader="Most frequent values the engine extracted" />
          <Divider />
          <CardContent>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              {Object.entries(analytics.top_entities).map(([type, values]) => (
                <Card key={type} variant="outlined" sx={{ flex: "1 1 240px" }}>
                  <CardHeader title={titleCase(type)} sx={{ pb: 0 }} />
                  <CardContent sx={{ pt: 1 }}>
                    {values.slice(0, 6).map((v) => (
                      <Stack key={v.value} direction="row" justifyContent="space-between" spacing={1}>
                        <Typography
                          variant="body2"
                          noWrap
                          title={v.value}
                          sx={{ fontFamily: '"JetBrains Mono", monospace', minWidth: 0 }}
                        >
                          {v.value}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          ×{v.count}
                        </Typography>
                      </Stack>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}
