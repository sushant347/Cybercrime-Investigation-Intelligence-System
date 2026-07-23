import ArticleIcon from "@mui/icons-material/Article";
import DownloadIcon from "@mui/icons-material/Download";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import FlagIcon from "@mui/icons-material/Flag";
import HubIcon from "@mui/icons-material/Hub";
import InventoryIcon from "@mui/icons-material/Inventory2";
import TimelineIcon from "@mui/icons-material/Timeline";
import VisibilityIcon from "@mui/icons-material/Visibility";
import {
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
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";

import { investigationApi, reportsApi } from "@/api";
import { ChartCard } from "@/components/common/ChartCard";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { StatCard } from "@/components/common/StatCard";
import { formatBytes, formatDateTime, titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type {
  InvestigationReport,
  ReportCorrelationSection,
  ReportEvidenceRow,
  ReportTimelineSection,
} from "@/types";

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: BRAND.critical,
  HIGH: BRAND.high,
  MEDIUM: BRAND.medium,
  LOW: BRAND.low,
};

/** Engine stores empty report sections as explanatory strings. */
function structured<T>(section: T | string | null | undefined): T | null {
  return section && typeof section === "object" ? (section as T) : null;
}

function BulletCard({
  title,
  subheader,
  items,
}: {
  title: string;
  subheader?: string;
  items: string[];
}) {
  if (items.length === 0) return null;
  return (
    <Card sx={{ flex: 1, minWidth: 0 }}>
      <CardHeader title={title} subheader={subheader} />
      <Divider />
      <CardContent>
        <Stack spacing={1}>
          {items.map((line, i) => (
            <Typography key={i} variant="body2">
              • {line}
            </Typography>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

/** Report rendered from the latest investigation_report artifact. Every
 *  number, chart, and sentence is engine output — nothing is computed here. */
function ReportView({ caseId, report }: { caseId: string; report: InvestigationReport }) {
  const sections = report.sections;
  const correlation = structured<ReportCorrelationSection>(sections.correlation_analysis);
  const timeline = structured<ReportTimelineSection>(sections.timeline_analysis);
  const quality = structured<Record<string, number>>(sections.evidence_quality_summary);
  const evidenceRows: ReportEvidenceRow[] = Array.isArray(sections.evidence_summary)
    ? sections.evidence_summary
    : [];

  // Priority artifact carries the weighted component scores behind the verdict.
  const priorityQuery = useQuery({
    queryKey: ["artifact", caseId, "priority"],
    queryFn: () => investigationApi.priority(caseId),
    retry: false,
  });
  const priority = priorityQuery.data?.report;
  const priorityColor = priority ? PRIORITY_COLORS[priority.priority_level] : undefined;

  const strengthChart = correlation
    ? Object.entries(correlation.strength_distribution).map(([name, value]) => ({
        name: titleCase(name.toLowerCase()),
        value,
      }))
    : [];
  const qualityChart = quality
    ? Object.entries(quality)
        .filter(([, v]) => typeof v === "number")
        .map(([name, value]) => ({ name: titleCase(name), value }))
    : [];
  const ocrChart = evidenceRows.map((row) => ({
    name: row.evidence_id,
    value: Math.round(row.ocr_confidence * 100),
  }));
  const priorityChart = (priority?.components ?? [])
    .filter((c) => c.available)
    .map((c) => ({ name: titleCase(c.name), value: c.score }));

  return (
    <Stack spacing={2}>
      {/* Headline verdicts */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <StatCard
          label="Evidence Items"
          value={sections.case_overview.evidence_count}
          icon={<InventoryIcon />}
          hint={`Types: ${sections.case_overview.file_types.join(", ") || "—"}`}
        />
        <StatCard
          label="Related Pairs"
          value={correlation ? `${correlation.related_pair_count}/${correlation.pair_count}` : "—"}
          icon={<HubIcon />}
          color={BRAND.accent}
          hint="Correlated of analysed"
        />
        <StatCard
          label="Case Priority"
          value={priority ? `${priority.priority_score}/100` : "—"}
          icon={<FlagIcon />}
          color={priorityColor}
          hint={priority?.priority_level}
        />
        <StatCard
          label="Timeline Span"
          value={
            timeline
              ? `${timeline.stage_progression.length} stages`
              : "—"
          }
          icon={<TimelineIcon />}
          color={BRAND.primary}
          hint={timeline?.progression_consistent === false ? "Non-canonical order" : undefined}
        />
      </Stack>

      <BulletCard
        title="Executive Summary"
        subheader="Generated by the Phase-2 reporting module"
        items={sections.executive_summary}
      />

      {/* Charts — all values read verbatim from stored artifacts */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        {priorityChart.length > 0 && (
          <ChartCard
            title="Priority Score Breakdown"
            subheader="Weighted components behind the engine's priority verdict (0–100)"
            data={priorityChart}
            domain={[0, 100]}
          />
        )}
        {strengthChart.length > 0 && (
          <ChartCard
            title="Correlation Strength Distribution"
            subheader="Evidence-pair relationships by strength band"
            data={strengthChart}
            kind="pie"
          />
        )}
        {ocrChart.length > 0 && (
          <ChartCard
            title="OCR Confidence by Evidence"
            subheader="Phase-1 recognition confidence (%)"
            data={ocrChart}
            domain={[0, 100]}
          />
        )}
        {qualityChart.length > 0 && (
          <ChartCard
            title="Evidence Quality Summary"
            subheader="Aggregate Phase-1 quality metrics"
            data={qualityChart}
          />
        )}
      </Stack>

      {/* Scam progression */}
      {timeline && (
        <Card>
          <CardHeader title="Attack Progression" subheader={timeline.summary} />
          <Divider />
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              {timeline.stage_progression.map((stage, i) => (
                <Fragment key={stage}>
                  {i > 0 && (
                    <Typography variant="body2" color="text.secondary">
                      →
                    </Typography>
                  )}
                  <Chip label={titleCase(stage)} color={i === 0 ? "primary" : undefined} />
                </Fragment>
              ))}
            </Stack>
            {timeline.milestones.length > 0 && (
              <Stack spacing={0.75} sx={{ mt: 2 }}>
                {timeline.milestones.map((m, i) => (
                  <Stack key={i} direction="row" spacing={1.5} alignItems="baseline">
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ fontFamily: '"JetBrains Mono", monospace', whiteSpace: "nowrap" }}
                    >
                      {formatDateTime(m.timestamp)}
                    </Typography>
                    <Typography variant="body2">{m.description}</Typography>
                  </Stack>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      )}

      {/* Key relationships */}
      {correlation && correlation.top_relationships.length > 0 && (
        <Card>
          <CardHeader
            title="Key Evidence Relationships"
            subheader="Strongest correlations found by the weighted correlation engine"
          />
          <Divider />
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pair</TableCell>
                <TableCell>Strength</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Engine Explanation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {correlation.top_relationships.map((rel) => (
                <TableRow key={rel.pair} hover>
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', whiteSpace: "nowrap" }}>
                    {rel.pair}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={rel.strength} variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <ConfidenceBar value={rel.confidence} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {rel.explanation}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Chain of custody */}
      {evidenceRows.length > 0 && (
        <Card>
          <CardHeader
            title="Evidence & Chain of Custody"
            subheader="SHA-256 verification status per item"
          />
          <Divider />
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Evidence</TableCell>
                <TableCell>File</TableCell>
                <TableCell>Acquired</TableCell>
                <TableCell>OCR Confidence</TableCell>
                <TableCell>Hash</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {evidenceRows.map((row) => (
                <TableRow key={row.evidence_id} hover>
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    {row.evidence_id}
                  </TableCell>
                  <TableCell>{row.file_name}</TableCell>
                  <TableCell>{formatDateTime(row.upload_time)}</TableCell>
                  <TableCell>
                    <ConfidenceBar value={row.ocr_confidence} />
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      icon={<FactCheckIcon />}
                      label={row.hash_verified ? "Verified" : "FAILED"}
                      color={row.hash_verified ? "success" : "error"}
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="stretch">
        <BulletCard
          title="Investigation Conclusion"
          subheader="Engine-derived findings"
          items={sections.investigation_conclusion}
        />
        <BulletCard
          title="Recommendations"
          subheader={priority?.investigation_recommendation}
          items={sections.recommendations}
        />
      </Stack>
    </Stack>
  );
}

/** Module 9 - Report center: visual report + versioned report history. */
export function ReportsTab({ caseId }: { caseId: string }) {
  const [preview, setPreview] = useState<{ fileName: string; content: string } | null>(null);
  const [jsonPreview, setJsonPreview] = useState(false);

  const listQuery = useQuery({
    queryKey: ["reports", caseId],
    queryFn: () => reportsApi.list(caseId),
  });
  const latestQuery = useQuery({
    queryKey: ["report-latest", caseId],
    queryFn: () => reportsApi.latest(caseId),
    retry: false,
  });

  if (listQuery.isPending) return <TableSkeleton />;

  const reports = listQuery.data?.reports ?? [];
  if (reports.length === 0) {
    return (
      <EmptyState
        icon={<ArticleIcon />}
        title="No reports generated"
        description="Run the investigation analysis — the Phase-2 report generator produces a versioned JSON + Markdown report for this case."
      />
    );
  }

  const download = async (fileName: string) => {
    const blob = await reportsApi.downloadBlob(caseId, fileName);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openPreview = async (fileName: string) => {
    const content = await reportsApi.previewMarkdown(caseId, fileName);
    setPreview({ fileName, content });
  };

  return (
    <Stack spacing={2}>
      {latestQuery.data && (
        <Card variant="outlined" sx={{ bgcolor: "transparent" }}>
          <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
            <Stack
              direction="row"
              spacing={2}
              alignItems="center"
              justifyContent="space-between"
              flexWrap="wrap"
              useFlexGap
            >
              <Typography variant="body2" color="text.secondary">
                Latest report · generated {formatDateTime(latestQuery.data.generated_at)} · version{" "}
                {latestQuery.data.report_version} · schema {latestQuery.data.schema_version}
              </Typography>
              <Button size="small" startIcon={<VisibilityIcon />} onClick={() => setJsonPreview(true)}>
                Raw JSON
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      {latestQuery.data && <ReportView caseId={caseId} report={latestQuery.data.report} />}

      <Card>
        <CardHeader
          title="Report History"
          subheader="Every stored version — reports are never overwritten"
        />
        <Divider />
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>File</TableCell>
              <TableCell>Format</TableCell>
              <TableCell>Generated</TableCell>
              <TableCell>Size</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {reports.map((report) => (
              <TableRow key={report.file_name} hover>
                <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                  {report.file_name}
                </TableCell>
                <TableCell>
                  <Chip size="small" label={report.format} variant="outlined" />
                </TableCell>
                <TableCell>
                  {report.generated_at
                    ? formatDateTime(report.generated_at)
                    : formatDateTime(new Date(report.modified_at * 1000).toISOString())}
                </TableCell>
                <TableCell>{formatBytes(report.size_bytes)}</TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    {report.format === "markdown" && (
                      <Button
                        size="small"
                        startIcon={<VisibilityIcon />}
                        onClick={() => void openPreview(report.file_name)}
                      >
                        Preview
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => void download(report.file_name)}
                    >
                      Download
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Markdown preview */}
      <Dialog open={!!preview} onClose={() => setPreview(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
          {preview?.fileName}
        </DialogTitle>
        <DialogContent dividers>
          <Box
            component="pre"
            sx={{
              m: 0,
              whiteSpace: "pre-wrap",
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: "0.82rem",
              lineHeight: 1.7,
            }}
          >
            {preview?.content}
          </Box>
        </DialogContent>
        <DialogActions>
          {preview && (
            <Button startIcon={<DownloadIcon />} onClick={() => void download(preview.fileName)}>
              Download
            </Button>
          )}
          <Button onClick={() => setPreview(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Latest JSON preview */}
      <Dialog open={jsonPreview} onClose={() => setJsonPreview(false)} maxWidth="md" fullWidth>
        <DialogTitle>Latest Investigation Report (JSON)</DialogTitle>
        <DialogContent dividers>
          {latestQuery.data && <JsonViewer data={latestQuery.data} maxHeight={560} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setJsonPreview(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
