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

import { investigationApi } from "@/api";
import { ChartCard } from "@/components/common/ChartCard";
import { EmptyState } from "@/components/common/EmptyState";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { titleCase } from "@/lib/format";
import type { ValueCount } from "@/types";

function recordToChart(record: Record<string, number>) {
  return Object.entries(record)
    .filter(([, v]) => typeof v === "number")
    .map(([name, value]) => ({ name: titleCase(name), value }));
}

function valueCountToChart(items: ValueCount[]) {
  return items.map((i) => ({ name: i.value, value: i.count }));
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
