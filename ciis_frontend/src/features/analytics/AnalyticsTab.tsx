import InsightsIcon from "@mui/icons-material/Insights";
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";

import { investigationApi } from "@/api";
import { ChartCard } from "@/components/common/ChartCard";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatCard } from "@/components/common/StatCard";
import { titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { ValueCount } from "@/types";

type Point = { name: string; value: number };

/** Chart data from a ``{metric: number}`` record, dropping non-numerics. */
function recordToChart(record: Record<string, number> | undefined): Point[] {
  return Object.entries(record ?? {})
    .filter(([, v]) => typeof v === "number" && Number.isFinite(v))
    .map(([name, value]) => ({ name: titleCase(name), value }));
}

function valueCountToChart(items: ValueCount[] | undefined): Point[] {
  return (items ?? []).map((i) => ({ name: i.value, value: i.count }));
}

/** True when every value is zero — a chart here would render as a blank plot. */
const allZero = (points: Point[]) => points.length > 0 && points.every((p) => p.value === 0);

/**
 * A chart that explains itself when there is nothing to draw.
 *
 * The engine legitimately returns all-zero metrics (e.g. no threat intel
 * configured) and empty lists (e.g. no URLs in the evidence). Rendering a
 * chart for those produced an empty plot area that looked broken, so we show
 * a plain-language reason instead.
 */
function SmartChart({
  title,
  subheader,
  data,
  kind = "bar",
  emptyReason,
}: {
  title: string;
  subheader: string;
  data: Point[];
  kind?: "bar" | "pie";
  emptyReason: string;
}) {
  if (data.length === 0 || allZero(data)) {
    return (
      <Card sx={{ flex: "1 1 340px", minWidth: 0 }}>
        <CardHeader
          title={title}
          subheader={subheader}
          titleTypographyProps={{ variant: "subtitle1" }}
        />
        <Divider />
        <CardContent>
          <Stack spacing={1} alignItems="flex-start">
            <Chip size="small" label="Nothing found" variant="outlined" />
            <Typography variant="body2" color="text.secondary">
              {emptyReason}
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    );
  }
  return <ChartCard title={title} subheader={subheader} data={data} kind={kind} />;
}

/** A labelled 0-100% style bar for a single quality metric. */
function MetricBar({
  label,
  value,
  max,
  hint,
  invert = false,
}: {
  label: string;
  value: number;
  max: number;
  hint: string;
  invert?: boolean;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  // For risk-style metrics (forgery), high is bad; for quality, high is good.
  const good = invert ? pct < 40 : pct >= 70;
  const color = good ? BRAND.low : pct >= 40 ? BRAND.medium : BRAND.high;
  return (
    <Box sx={{ mb: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline">
        <Tooltip title={hint}>
          <Typography variant="body2">{label}</Typography>
        </Tooltip>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {value.toFixed(2)}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 8,
          borderRadius: 4,
          mt: 0.5,
          "& .MuiLinearProgress-bar": { bgcolor: color },
        }}
      />
    </Box>
  );
}

/**
 * Module 8 — Analytics, rendered from the stored analytics artifact.
 *
 * Every number is engine output. The layout leads with the headline counts,
 * then "what was found" (entities/brands/wallets/URLs), then the analysis
 * quality metrics — and each panel says plainly why it is empty rather than
 * drawing a blank chart.
 */
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
        description="Run the investigation analysis to compute entity, brand, wallet, campaign, timeline and quality statistics."
      />
    );
  }

  const entities = recordToChart(analytics.entity_statistics);
  const totalEntities = entities.reduce((sum, e) => sum + e.value, 0);
  const timeline = analytics.timeline_statistics ?? {};
  const campaign = analytics.campaign_statistics ?? {};
  const correlation = analytics.correlation_statistics ?? {};
  const quality = analytics.evidence_quality_statistics ?? {};
  const threat = analytics.threat_statistics ?? {};
  const metadata = analytics.metadata_statistics ?? {};

  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

  return (
    <Stack spacing={2}>
      {/* ---------------------------------------------------- headline */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <StatCard
          label="Evidence Items"
          value={num(analytics.evidence_count)}
          hint="Files analysed in this case"
        />
        <StatCard
          label="Entities Found"
          value={totalEntities}
          color={BRAND.accent}
          hint={`${entities.length} distinct type(s)`}
        />
        <StatCard
          label="Related Pairs"
          value={`${num(correlation.related_pair_count)}/${num(correlation.pair_count)}`}
          color={BRAND.primary}
          hint="Evidence pairs the engine linked"
        />
        <StatCard
          label="Timeline Events"
          value={num(timeline.event_count)}
          color={BRAND.high}
          hint={`${num(timeline.stage_count)} attack stage(s)`}
        />
      </Stack>

      {/* --------------------------------------------- what was found */}
      <Typography variant="subtitle2" color="text.secondary" sx={{ pt: 1 }}>
        WHAT THE ENGINE FOUND IN THE EVIDENCE
      </Typography>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <SmartChart
          title="Entity Types"
          subheader="How many of each identifier were extracted"
          data={entities}
          emptyReason="No entities were extracted — the evidence text contained no recognisable identifiers (phones, URLs, wallets, amounts…)."
        />
        <SmartChart
          title="Payment & Wallet IDs"
          subheader="eSewa / Khalti / bank identifiers"
          data={valueCountToChart(analytics.wallet_statistics)}
          emptyReason="No wallet or payment identifiers appeared in this case's evidence."
        />
        <SmartChart
          title="URLs"
          subheader="Web addresses seen in the evidence"
          data={valueCountToChart(analytics.url_statistics)}
          emptyReason="No URLs were found in this case's evidence."
        />
        <SmartChart
          title="Brands Referenced"
          subheader="Impersonated or mentioned brands"
          data={valueCountToChart(analytics.brand_statistics)}
          emptyReason="No known brand was detected. Brand detection needs a logo or a brand name in the recognised text."
        />
      </Stack>

      {/* ------------------------------------------------ top values */}
      {Object.keys(analytics.top_entities ?? {}).length > 0 && (
        <Card>
          <CardHeader
            title="Most Frequent Values"
            subheader="The actual identifiers the engine extracted, by type"
            titleTypographyProps={{ variant: "subtitle1" }}
          />
          <Divider />
          <CardContent>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              {Object.entries(analytics.top_entities).map(([type, values]) => (
                <Card key={type} variant="outlined" sx={{ flex: "1 1 260px" }}>
                  <CardHeader
                    title={titleCase(type)}
                    titleTypographyProps={{ variant: "subtitle2" }}
                    sx={{ pb: 0 }}
                  />
                  <CardContent sx={{ pt: 1 }}>
                    {values.slice(0, 6).map((v) => (
                      <Stack
                        key={v.value}
                        direction="row"
                        justifyContent="space-between"
                        spacing={1}
                      >
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

      {/* ------------------------------------------------- case shape */}
      <Typography variant="subtitle2" color="text.secondary" sx={{ pt: 1 }}>
        HOW THE CASE FITS TOGETHER
      </Typography>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <SmartChart
          title="Timeline"
          subheader="Events, stages and critical moments"
          data={recordToChart(timeline)}
          emptyReason="No timeline was reconstructed — evidence needs timestamps or dated content."
        />
        <SmartChart
          title="Campaigns"
          subheader="Clusters of coordinated evidence"
          data={recordToChart(campaign)}
          emptyReason="No campaign clusters formed. Campaigns need several evidence items sharing strong signals."
        />
        <SmartChart
          title="Correlation"
          subheader="Evidence-pair link strength"
          data={recordToChart(correlation)}
          emptyReason="Nothing to correlate — a case needs at least two evidence items."
        />
        <SmartChart
          title="Threat Intelligence"
          subheader="Indicators checked against threat data"
          data={recordToChart(threat)}
          kind="pie"
          emptyReason="No threat intelligence ran. It activates when the evidence contains URLs/domains and an indicator source or the ML classifier is enabled."
        />
      </Stack>

      {/* ------------------------------------------------ quality bars */}
      <Card>
        <CardHeader
          title="Evidence Quality & Integrity"
          subheader="How much the engine trusts what it read"
          titleTypographyProps={{ variant: "subtitle1" }}
        />
        <Divider />
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={4}>
            <Box sx={{ flex: 1 }}>
              <MetricBar
                label="Mean OCR confidence"
                value={num(quality.mean_ocr_confidence)}
                max={1}
                hint="How confident the OCR engine was in the text it read (0-1)."
              />
              <MetricBar
                label="Mean image quality"
                value={num(quality.mean_image_quality)}
                max={100}
                hint="Sharpness/contrast score of the uploaded images (0-100)."
              />
              <MetricBar
                label="Mean evidence confidence"
                value={num(quality.mean_evidence_confidence)}
                max={100}
                hint="Overall Phase-1 confidence in each evidence item (0-100)."
              />
            </Box>
            <Box sx={{ flex: 1 }}>
              <MetricBar
                label="Mean forgery risk"
                value={num(quality.mean_forgery_score)}
                max={100}
                hint="Tampering indicators found (0-100). Lower is better."
                invert
              />
              <MetricBar
                label="Highest forgery risk"
                value={num(quality.max_forgery_score)}
                max={100}
                hint="The most suspicious single item (0-100). Lower is better."
                invert
              />
              <Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}>
                <Typography variant="body2">Hash-verified items</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {num(quality.hash_verified_count)} / {num(analytics.evidence_count)}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" sx={{ mt: 1 }}>
                <Typography variant="body2">Items with EXIF metadata</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {num(metadata.evidence_with_exif)} / {num(analytics.evidence_count)}
                </Typography>
              </Stack>
            </Box>
          </Stack>
          {num(quality.mean_image_quality) === 0 &&
            num(quality.mean_evidence_confidence) === 0 && (
              <Alert severity="info" sx={{ mt: 2 }}>
                Image-quality and forgery scores are 0 because the Phase-1 forensic
                reports were not generated for this case's evidence (they run for
                image uploads). OCR confidence and hash verification are still real.
              </Alert>
            )}
        </CardContent>
      </Card>
    </Stack>
  );
}
