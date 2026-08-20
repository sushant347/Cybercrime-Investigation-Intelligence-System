import DescriptionIcon from "@mui/icons-material/Description";
import EditIcon from "@mui/icons-material/Edit";
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
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

import { casesApi, investigationApi } from "@/api";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiClient";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { StatCard } from "@/components/common/StatCard";
import { PriorityBreakdown } from "./PriorityBreakdown";
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

/**
 * Rename dialog.
 *
 * Only the title is editable here. Description and tags were dropped from the
 * case view: they are free-text platform metadata with no bearing on any
 * forensic finding, they duplicated what the case reference and the evidence
 * already convey, and in practice they sat empty on every case. Investigator
 * notes are unaffected — those are entered per evidence item at upload and
 * belong to the evidence record, not the case.
 */
function EditDetailsDialog({
  caseData,
  open,
  onClose,
}: {
  caseData: CaseDetail;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(caseData.title ?? "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => casesApi.update(caseData.case_id, { title: title.trim() }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["case", caseData.case_id] });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Rename case</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            autoFocus
            helperText="The case reference is fixed; this is the working title."
          />
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={save.isPending} onClick={() => save.mutate()}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * One group of extracted identifiers.
 *
 * Values are rendered as discrete rows rather than a run-on list so an
 * identifier can be picked out at a glance, and the count of anything beyond
 * the visible five is stated explicitly — the previous version truncated
 * silently, so a case with forty wallets looked like a case with five.
 */
function ValueList({ values, empty }: { values: ValueCount[]; empty: string }) {
  if (values.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {empty}
      </Typography>
    );
  }
  const shown = values.slice(0, 5);
  const hidden = values.length - shown.length;

  return (
    <Stack spacing={0.5}>
      {shown.map((v) => (
        <Stack
          key={v.value}
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
          sx={{
            px: 1,
            py: 0.5,
            borderRadius: 1,
            bgcolor: "action.hover",
            minWidth: 0,
          }}
        >
          <Typography
            variant="body2"
            noWrap
            title={v.value}
            sx={{ fontFamily: '"JetBrains Mono", monospace', minWidth: 0 }}
          >
            {v.value}
          </Typography>
          <Chip
            size="small"
            label={`×${v.count}`}
            sx={{ height: 20, fontWeight: 700, flexShrink: 0 }}
          />
        </Stack>
      ))}
      {hidden > 0 && (
        <Typography variant="caption" color="text.secondary">
          + {hidden} more — see the Analytics tab for the full list
        </Typography>
      )}
    </Stack>
  );
}

/** Section heading inside the findings panel, with the group's total. */
function FindingGroup({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.75 }}>
        <Typography variant="overline" color="text.secondary" sx={{ lineHeight: 1.4 }}>
          {title}
        </Typography>
        {count > 0 && (
          <Chip
            size="small"
            label={count}
            variant="outlined"
            sx={{ height: 18, fontSize: 11, fontWeight: 700 }}
          />
        )}
      </Stack>
      {children}
    </Box>
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
  const noted = evidence.filter((row) => (row.investigator_notes || "").trim());
  const { hasPermission } = useAuth();
  const [editOpen, setEditOpen] = useState(false);

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
            <CardHeader
              title="Case Details"
              titleTypographyProps={{ variant: "subtitle1" }}
              action={
                hasPermission("case.manage") && (
                  <Tooltip title="Rename this case">
                    <IconButton size="small" onClick={() => setEditOpen(true)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )
              }
            />
            <Divider />
            <KeyValueTable
              data={{
                case_id: caseData.case_id,
                case_reference: caseData.case_reference || "—",
                title: caseData.title || "—",
                status: caseData.status,
                created_at: formatDateTime(caseData.created_at),
                last_updated: formatDateTime(caseData.updated_at),
              }}
            />
          </Card>

          <Card>
            <CardHeader
              title="Investigator Notes"
              subheader="Chain-of-custody notes recorded at upload"
              titleTypographyProps={{ variant: "subtitle1" }}
            />
            <Divider />
            <CardContent>
              {/*
                These notes belong to the *evidence item*, not the case: they
                are typed in the upload dialog and stored on the custody row.
                This panel used to render the case-level note instead - a field
                only ever set when a case is created through the API - so every
                note an investigator wrote at upload appeared to vanish.
              */}
              {noted.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No notes recorded. Notes typed in the upload dialog are stored
                  against that evidence item and appear here.
                </Typography>
              ) : (
                <Stack spacing={1.5}>
                  {noted.map((row) => (
                    <Box key={row.evidence_id}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                      >
                        {row.evidence_id} · {row.original_file_name}
                      </Typography>
                      <Typography variant="body2">{row.investigator_notes}</Typography>
                    </Box>
                  ))}
                </Stack>
              )}
            </CardContent>
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
                  <FindingGroup
                    title="Payment identifiers"
                    count={(analytics.wallet_statistics ?? []).length}
                  >
                    <ValueList
                      values={analytics.wallet_statistics ?? []}
                      empty="No wallet, bank or card identifier was found."
                    />
                  </FindingGroup>
                  <FindingGroup
                    title="Links & domains"
                    count={(analytics.url_statistics ?? []).length}
                  >
                    <ValueList
                      values={analytics.url_statistics ?? []}
                      empty="No URLs appeared in this case's evidence."
                    />
                  </FindingGroup>
                  <FindingGroup
                    title="Flagged by threat intelligence"
                    count={(analytics.threat_indicators ?? []).length}
                  >
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
                        {(analytics.threat_indicators ?? []).length > 4 && (
                          <Typography variant="caption" color="text.secondary">
                            + {(analytics.threat_indicators ?? []).length - 4} more
                            — see the Analytics tab for the full list
                          </Typography>
                        )}
                      </Stack>
                    )}
                  </FindingGroup>
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
              subheader="How urgently this case needs attention, and why"
              titleTypographyProps={{ variant: "subtitle1" }}
            />
            <Divider />
            <CardContent>
              {!priority ? (
                <Typography variant="body2" color="text.secondary">
                  No priority verdict yet. Run the investigation analysis to
                  generate one.
                </Typography>
              ) : (
                <PriorityBreakdown priority={priority} />
              )}
            </CardContent>
          </Card>
        </Stack>
      </Stack>

      {editOpen && (
        <EditDetailsDialog
          caseData={caseData}
          open={editOpen}
          onClose={() => setEditOpen(false)}
        />
      )}
    </Stack>
  );
}
