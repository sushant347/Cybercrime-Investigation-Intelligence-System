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
import { StatusChip } from "@/components/common/StatusChip";
import { titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { ThreatIndicator, ValueCount } from "@/types";

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

/** Human label for each payment rail the extractor can produce. */
const RAIL_LABELS: Record<string, string> = {
  esewa_ids: "eSewa",
  khalti_ids: "Khalti",
  imepay_ids: "IME Pay",
  bank_accounts: "Bank accounts",
  card_numbers: "Payment cards",
  eth_wallets: "Ethereum wallets",
  btc_wallets: "Bitcoin wallets",
};

/**
 * Payment identifiers, by rail and by frequency.
 *
 * This panel was empty on every case ever analysed: the engine looked up an
 * entity type ("wallets") that its own extractor never produced, so eSewa,
 * Khalti and bank identifiers sitting in the evidence were never counted. It
 * now shows the actual identifiers — the thing an investigator follows — split
 * by the rail they belong to.
 */
function PaymentCard({
  merged,
  byRail,
}: {
  merged: ValueCount[];
  byRail: Record<string, ValueCount[]>;
}) {
  const rails = Object.entries(byRail).filter(([, values]) => values.length > 0);

  if (merged.length === 0) {
    return (
      <Card sx={{ flex: "1 1 340px", minWidth: 0 }}>
        <CardHeader
          title="Payment & Wallet IDs"
          subheader="eSewa / Khalti / IME Pay / bank / card"
          titleTypographyProps={{ variant: "subtitle1" }}
        />
        <Divider />
        <CardContent>
          <Stack spacing={1} alignItems="flex-start">
            <Chip size="small" label="Nothing found" variant="outlined" />
            <Typography variant="body2" color="text.secondary">
              No payment identifier was extracted from this case's evidence.
              Wallet ids are recognised next to their label (&quot;Khalti ID&quot;,
              &quot;eSewa ID&quot;, &quot;Account No.&quot;), including on the
              line below it as receipts print them.
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ flex: "1 1 340px", minWidth: 0 }}>
      <CardHeader
        title="Payment & Wallet IDs"
        subheader={`${merged.length} identifier(s) across ${rails.length} rail(s)`}
        titleTypographyProps={{ variant: "subtitle1" }}
      />
      <Divider />
      <CardContent>
        <Stack spacing={2}>
          {rails.map(([rail, values]) => (
            <Box key={rail}>
              <Typography variant="subtitle2" color="text.secondary">
                {RAIL_LABELS[rail] ?? titleCase(rail)}
              </Typography>
              {values.map((v) => (
                <Stack
                  key={`${rail}-${v.value}`}
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
            </Box>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * Threat intelligence: the verdict *and* the grounds for it.
 *
 * A pie of counters could not distinguish "checked and clean" from "never
 * checked", which is the difference between an exonerating finding and no
 * finding at all — so the panel names the provider, counts the verdicts, and
 * lists each flagged indicator with the reasons it was flagged.
 */
function ThreatCard({
  statistics,
  indicators,
  source,
}: {
  statistics: Record<string, number>;
  indicators: ThreatIndicator[];
  source: string;
}) {
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
  const available = num(statistics.intel_available) > 0;
  const checked = num(statistics.indicators_checked);

  return (
    <Card sx={{ flex: "1 1 340px", minWidth: 0 }}>
      <CardHeader
        title="Threat Intelligence"
        subheader={
          available
            ? `${checked} indicator(s) checked · source: ${source || "unknown"}`
            : "No provider was available"
        }
        titleTypographyProps={{ variant: "subtitle1" }}
      />
      <Divider />
      <CardContent>
        {!available ? (
          <Stack spacing={1} alignItems="flex-start">
            <Chip size="small" label="Not checked" variant="outlined" />
            <Typography variant="body2" color="text.secondary">
              No threat provider answered, so the links in this evidence have
              not been assessed. This is not the same as finding them safe.
            </Typography>
          </Stack>
        ) : checked === 0 ? (
          <Stack spacing={1} alignItems="flex-start">
            <Chip size="small" label="Nothing to check" variant="outlined" />
            <Typography variant="body2" color="text.secondary">
              This case's evidence contains no URLs or domains to assess.
            </Typography>
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <StatusChip
                value="high"
                label={`${num(statistics.malicious_indicators)} malicious`}
              />
              <StatusChip
                value="medium"
                label={`${num(statistics.suspicious_indicators)} suspicious`}
              />
              <StatusChip
                value="low"
                label={`${num(statistics.benign_indicators)} benign`}
              />
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {num(statistics.evidence_with_threats)} of the case's evidence
              items contain a flagged indicator.
            </Typography>
            {indicators.slice(0, 5).map((indicator) => (
              <Box key={indicator.value}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <StatusChip
                    value={indicator.verdict === "malicious" ? "high" : "medium"}
                    label={indicator.verdict}
                  />
                  <Typography
                    variant="body2"
                    noWrap
                    title={indicator.value}
                    sx={{ fontFamily: '"JetBrains Mono", monospace', minWidth: 0 }}
                  >
                    {indicator.value}
                  </Typography>
                </Stack>
                {indicator.reasons.length > 0 && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="div"
                    sx={{ pl: 0.5 }}
                  >
                    {indicator.reasons.slice(0, 3).join(" · ")}
                  </Typography>
                )}
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * A "n of total" bar for count metrics (hash-verified, EXIF coverage).
 *
 * These were bare "0 / 8" text rows, visually inconsistent with the metric
 * bars beside them and — worse — a zero looked like a failure even when zero
 * is the expected value (screenshots have no EXIF). ``neutralWhenZero`` keeps
 * the bar grey in that case instead of alarming red.
 */
function RatioBar({
  label,
  value,
  total,
  hint,
  neutralWhenZero = false,
}: {
  label: string;
  value: number;
  total: number;
  hint: string;
  neutralWhenZero?: boolean;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  const color =
    value === 0 && neutralWhenZero
      ? undefined // theme default: informational, not a warning
      : pct >= 99
        ? BRAND.low
        : pct >= 50
          ? BRAND.medium
          : BRAND.high;
  return (
    <Box sx={{ mb: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline">
        <Tooltip title={hint}>
          <Typography variant="body2">{label}</Typography>
        </Tooltip>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {value} / {total}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={Math.min(100, pct)}
        sx={{
          height: 8,
          borderRadius: 4,
          mt: 0.5,
          ...(color && { "& .MuiLinearProgress-bar": { bgcolor: color } }),
        }}
      />
    </Box>
  );
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
          subheader={
            analytics.entity_types_supported
              ? `${analytics.entity_types_found ?? entities.length} of ` +
                `${analytics.entity_types_supported} searched types present`
              : "How many of each identifier were extracted"
          }
          data={entities}
          emptyReason="No entities were extracted — the evidence text contained no recognisable identifiers (phones, URLs, wallets, amounts…)."
        />
        <PaymentCard
          merged={analytics.wallet_statistics ?? []}
          byRail={analytics.wallet_statistics_by_rail ?? {}}
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
        <ThreatCard
          statistics={threat}
          indicators={analytics.threat_indicators ?? []}
          source={analytics.threat_source ?? ""}
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
                hint="Average certainty of the text the OCR read, 0 to 1. The engine flags
                  individual lines below 0.50 as unreliable."
              />
              <MetricBar
                label="Mean image quality"
                value={num(quality.mean_image_quality)}
                max={100}
                hint="Average sharpness and contrast of the uploaded images, 0-100.
                  Higher means the engine had a clean image to read from."
              />
              <MetricBar
                label="Mean evidence confidence"
                value={num(quality.mean_evidence_confidence)}
                max={100}
                hint="How far Phase 1 trusts each item overall, 0-100, combining image
                  quality, OCR certainty and the forgery checks."
              />
            </Box>
            <Box sx={{ flex: 1 }}>
              <MetricBar
                label="Mean forgery risk"
                value={num(quality.mean_forgery_score)}
                max={100}
                hint="Average tampering score across every item, 0-100. Lower is better."
                invert
              />
              <MetricBar
                label="Highest forgery risk"
                value={num(quality.max_forgery_score)}
                max={100}
                hint="The most suspicious single item, 0-100. At 50 or above the engine
                    raises it as a possible-tampering indicator."
                invert
              />
              <Box sx={{ mt: 2 }}>
                <RatioBar
                  label="Hash-verified items"
                  value={num(quality.hash_verified_count)}
                  total={num(analytics.evidence_count)}
                  hint="Items whose SHA-256 is unchanged since acquisition. This is the
                    chain-of-custody guarantee, so it should always be full."
                />
                <RatioBar
                  label="Items with EXIF metadata"
                  value={num(metadata.evidence_with_exif)}
                  total={num(analytics.evidence_count)}
                  neutralWhenZero
                  hint="Camera metadata inside the file: device, capture time, sometimes
                    GPS. Screenshots and PDFs never carry it, so 0 is normal here."
                />
                <RatioBar
                  label="Items with a metadata report"
                  value={num(metadata.evidence_with_metadata_report)}
                  total={num(analytics.evidence_count)}
                  hint="Items the Phase-1 metadata module examined. If this is 0,
                    forensics never ran — re-run the analysis."
                />
              </Box>
              {num(metadata.evidence_with_exif) === 0 &&
                num(metadata.evidence_with_metadata_report) > 0 && (
                  <Typography variant="caption" color="text.secondary" component="div">
                    No EXIF found: this evidence is screenshots/documents, which
                    never carry camera metadata. Device attribution must come
                    from other sources (account records, device seizure).
                  </Typography>
                )}
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
