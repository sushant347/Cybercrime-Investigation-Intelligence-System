import DescriptionIcon from "@mui/icons-material/Description";
import GavelIcon from "@mui/icons-material/Gavel";
import HubIcon from "@mui/icons-material/Hub";
import SecurityIcon from "@mui/icons-material/Security";
import {
  Alert,
  Box,
  Button,
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
import { Link as RouterLink } from "react-router-dom";

import { investigationApi } from "@/api";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { CaseDetail, EvidenceRow, ValueCount } from "@/types";

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

/** Counts of each processing status across the case's evidence. */
function evidenceBreakdown(evidence: EvidenceRow[]) {
  const counts = { processed: 0, uploaded: 0, failed: 0, verified: 0 };
  for (const row of evidence) {
    if (row.status === "processed") counts.processed += 1;
    else if (row.status === "failed") counts.failed += 1;
    else counts.uploaded += 1;
    if (String(row.hash_verified) === "True") counts.verified += 1;
  }
  return counts;
}

/** Compact "identifier ×n" list used by the findings panel. */
function ValueList({ values, empty }: { values: ValueCount[]; empty: string }) {
  if (values.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {empty}
      </Typography>
    );
  }
  return (
    <Stack spacing={0.25}>
      {values.slice(0, 5).map((v) => (
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
    </Stack>
  );
}

/**
 * Case overview: what this case *is*, and what the engine has found so far.
 *
 * The previous version showed the workflow fields and the priority verdict and
 * nothing else, so the first screen of a case said nothing about its evidence,
 * its findings, or whether an analysis had even been run. It reads the stored
 * analytics artifact — the same artifact the Analytics tab renders — so every
 * number here is engine output, and it says plainly when there is none yet.
 */
export function CaseOverviewTab({ caseData }: { caseData: CaseDetail }) {
  const priority = caseData.priority;
  const evidence = caseData.evidence ?? [];
  const counts = evidenceBreakdown(evidence);

  // Analysis has not necessarily been run: a missing artifact is an expected
  // state, not an error, so failures are swallowed and reported as "not yet".
  const { data: analyticsDoc, isPending } = useQuery({
    queryKey: ["artifact", caseData.case_id, "analytics"],
    queryFn: () => investigationApi.analytics(caseData.case_id),
    retry: false,
  });

  const analytics = analyticsDoc?.report;
  const threat = analytics?.threat_statistics ?? {};
  const quality = analytics?.evidence_quality_statistics ?? {};
  const correlation = analytics?.correlation_statistics ?? {};
  const timeline = analytics?.timeline_statistics ?? {};
  const entityTotal = Object.values(analytics?.entity_statistics ?? {}).reduce(
    (sum, n) => sum + num(n),
    0,
  );
  const flagged = num(threat.malicious_indicators);
  const analysedItems = num(analytics?.evidence_count);
  const stale = !!analytics && analysedItems !== evidence.length;

  return (
    <Stack spacing={2}>
      {/* ------------------------------------------------ headline counters */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <StatCard
          label="Evidence"
          value={evidence.length}
          icon={<DescriptionIcon />}
          hint={
            `${counts.processed} processed · ${counts.uploaded} pending` +
            (counts.failed ? ` · ${counts.failed} failed` : "")
          }
        />
        <StatCard
          label="Entities Extracted"
          value={analytics ? entityTotal : "—"}
          color={BRAND.accent}
          icon={<HubIcon />}
          hint={
            analytics
              ? `${analytics.entity_types_found ?? 0} of ` +
                `${analytics.entity_types_supported ?? 0} identifier types`
              : "Run the analysis to populate"
          }
        />
        <StatCard
          label="Flagged Indicators"
          value={analytics ? flagged : "—"}
          color={flagged > 0 ? BRAND.high : BRAND.low}
          icon={<SecurityIcon />}
          hint={
            analytics
              ? num(threat.intel_available) > 0
                ? `${num(threat.indicators_checked)} checked · ${num(
                    threat.evidence_with_threats,
                  )} item(s) affected`
                : "No threat provider was available"
              : "Run the analysis to populate"
          }
        />
        <StatCard
          label="Priority"
          value={priority ? priority.priority_score.toFixed(1) : "—"}
          color={BRAND.primary}
          icon={<GavelIcon />}
          hint={
            priority
              ? `${priority.priority_level} · computed ${formatDateTime(
                  priority.computed_at,
                )}`
              : "No verdict yet"
          }
        />
      </Stack>

      {!isPending && !analytics && (
        <Alert
          severity="info"
          action={
            <Button
              component={RouterLink}
              to={`/cases/${caseData.case_id}/evidence`}
              size="small"
            >
              Evidence
            </Button>
          }
        >
          No analysis has been run for this case yet, so the findings below are
          empty. Upload evidence, then use <strong>Run Analysis</strong> to
          produce correlations, a timeline, threat verdicts and a report.
        </Alert>
      )}

      {stale && (
        <Alert severity="warning">
          The stored analysis covers {analysedItems} evidence item(s) but the
          case now holds {evidence.length}. Re-run the analysis so the findings
          include everything uploaded since.
        </Alert>
      )}

      {/* ------------------------------------------------------- two columns */}
      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="stretch">
        <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
          <Card>
            <CardHeader title="Case Details" titleTypographyProps={{ variant: "subtitle1" }} />
            <Divider />
            <KeyValueTable
              data={{
                case_id: caseData.case_id,
                case_reference: caseData.case_reference || "—",
                title: caseData.title || "—",
                description: caseData.description || "—",
                investigator_notes: caseData.investigator_notes || "—",
                status: caseData.status,
                assigned_to: caseData.assigned_to ?? "Unassigned",
                created_at: formatDateTime(caseData.created_at),
                last_updated: formatDateTime(caseData.updated_at),
                tags: caseData.tags.join(", ") || "—",
              }}
            />
          </Card>

          <Card>
            <CardHeader
              title="Evidence Integrity"
              subheader="Chain of custody across this case's items"
              titleTypographyProps={{ variant: "subtitle1" }}
            />
            <Divider />
            <CardContent>
              {evidence.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No evidence has been uploaded to this case yet.
                </Typography>
              ) : (
                <Stack spacing={1}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">Hash-verified on acquisition</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {counts.verified} / {evidence.length}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">Mean OCR confidence</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {analytics ? num(quality.mean_ocr_confidence).toFixed(2) : "—"}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">Highest forgery risk</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {analytics ? num(quality.max_forgery_score).toFixed(1) : "—"}
                    </Typography>
                  </Stack>
                  {counts.failed > 0 && (
                    <Alert severity="warning" sx={{ mt: 1 }}>
                      {counts.failed} item(s) failed processing. Unprocessed
                      items can be removed from the Evidence tab.
                    </Alert>
                  )}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Stack>

        <Stack spacing={2} sx={{ flex: 1, minWidth: 0 }}>
          <Card>
            <CardHeader
              title="Key Findings"
              subheader="Straight from the stored analysis artifact"
              titleTypographyProps={{ variant: "subtitle1" }}
            />
            <Divider />
            <CardContent>
              {!analytics ? (
                <Typography variant="body2" color="text.secondary">
                  Nothing yet — run the investigation analysis.
                </Typography>
              ) : (
                <Stack spacing={2}>
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      Payment identifiers
                    </Typography>
                    <ValueList
                      values={analytics.wallet_statistics ?? []}
                      empty="No wallet, bank or card identifier was found."
                    />
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      Links & domains
                    </Typography>
                    <ValueList
                      values={analytics.url_statistics ?? []}
                      empty="No URLs appeared in this case's evidence."
                    />
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      Flagged by threat intelligence
                    </Typography>
                    {(analytics.threat_indicators ?? []).length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        {num(threat.intel_available) > 0
                          ? "Every indicator checked came back clean."
                          : "No provider was available, so nothing was assessed."}
                      </Typography>
                    ) : (
                      <Stack spacing={0.5}>
                        {(analytics.threat_indicators ?? []).slice(0, 4).map((i) => (
                          <Tooltip key={i.value} title={i.reasons.join(" · ")}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <StatusChip
                                value={i.verdict === "malicious" ? "high" : "medium"}
                                label={i.verdict}
                              />
                              <Typography
                                variant="body2"
                                noWrap
                                sx={{
                                  fontFamily: '"JetBrains Mono", monospace',
                                  minWidth: 0,
                                }}
                              >
                                {i.value}
                              </Typography>
                            </Stack>
                          </Tooltip>
                        ))}
                      </Stack>
                    )}
                  </Box>
                  <Divider />
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`${num(correlation.related_pair_count)}/${num(
                        correlation.pair_count,
                      )} evidence pairs linked`}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`${num(timeline.event_count)} timeline event(s)`}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`${num(timeline.critical_event_count)} critical moment(s)`}
                    />
                  </Stack>
                </Stack>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader
              title="Case Priority"
              subheader="Computed by the Phase-2 prioritization engine"
              titleTypographyProps={{ variant: "subtitle1" }}
              action={priority && <StatusChip value={priority.priority_level} />}
            />
            <Divider />
            <CardContent>
              {!priority ? (
                <Typography variant="body2" color="text.secondary">
                  No priority verdict yet. Run the investigation analysis to
                  generate one.
                </Typography>
              ) : (
                <Stack spacing={2}>
                  <Stack direction="row" spacing={2} alignItems="baseline">
                    <Typography variant="h3">
                      {priority.priority_score.toFixed(1)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      / 100 · computed {formatDateTime(priority.computed_at)}
                    </Typography>
                  </Stack>

                  {priority.explanation && (
                    <Typography variant="body2">{priority.explanation}</Typography>
                  )}

                  {priority.investigation_recommendation && (
                    <Typography variant="body2" sx={{ fontStyle: "italic" }}>
                      Recommendation: {priority.investigation_recommendation}
                    </Typography>
                  )}

                  {priority.high_risk_indicators.length > 0 && (
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      {priority.high_risk_indicators.map((ind) => (
                        <StatusChip key={ind} value="high" label={ind} />
                      ))}
                    </Stack>
                  )}

                  <Divider />
                  <Typography variant="subtitle2">Score components</Typography>
                  {priority.components.map((component) => (
                    <Tooltip
                      key={component.name}
                      title={component.explanation || component.name}
                    >
                      <Stack spacing={0.5}>
                        <Stack direction="row" justifyContent="space-between">
                          <Typography variant="body2" sx={{ textTransform: "capitalize" }}>
                            {component.name.replace(/_/g, " ")}
                            {!component.available && " (unavailable)"}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {component.score.toFixed(1)} × {component.weight.toFixed(2)}
                          </Typography>
                        </Stack>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(100, component.score)}
                          sx={{ height: 6, borderRadius: 3 }}
                        />
                      </Stack>
                    </Tooltip>
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Stack>
      </Stack>
    </Stack>
  );
}
