import {
  Box,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { ReactNode } from "react";

import type { SimpleReport, SummaryRow } from "./reportModel";

const BADGE_COLOR: Record<NonNullable<SummaryRow["badge"]>, string> = {
  good: "#1a7f5a",
  warn: "#a86612",
  bad: "#b3261e",
  neutral: "#4a5568",
};

const ACCENT = "#1aa179";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", p: { xs: 2, sm: 3 } }}>
      <Typography
        variant="subtitle2"
        sx={{
          color: ACCENT,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          mb: 1.5,
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

function Badge({ label, tone }: { label: string; tone: NonNullable<SummaryRow["badge"]> }) {
  return (
    <Chip
      label={label}
      size="small"
      sx={{ bgcolor: BADGE_COLOR[tone], color: "#fff", fontWeight: 700 }}
    />
  );
}

/**
 * The report an investigator actually reads: a summary table of verdicts,
 * then findings in plain sentences. Values come straight from the engine.
 */
export function SimpleReportView({ report }: { report: SimpleReport }) {
  return (
    <Paper variant="outlined" sx={{ overflow: "hidden" }}>
      <Box sx={{ bgcolor: ACCENT, color: "#fff", p: { xs: 2, sm: 3 } }}>
        <Typography variant="h6">Investigation Report</Typography>
        <Typography variant="body2" sx={{ opacity: 0.92 }}>
          {report.caseReference || report.caseId} · report version {report.reportVersion}
        </Typography>
      </Box>

      <Section title="Report Summary">
        <Table size="small">
          <TableBody>
            {report.summary.map((row) => (
              <TableRow key={row.label}>
                <TableCell
                  sx={{
                    width: { xs: "40%", sm: "34%" },
                    fontWeight: 600,
                    color: "text.secondary",
                    verticalAlign: "top",
                  }}
                >
                  {row.label}
                </TableCell>
                <TableCell>
                  {row.badge ? <Badge label={row.value} tone={row.badge} /> : row.value}
                  {row.hint && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                      {row.hint}
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>

      {report.findings.length > 0 && (
        <Section title="What We Found">
          <Stack spacing={1}>
            {report.findings.map((line, i) => (
              <Typography key={i} variant="body2">
                • {line}
              </Typography>
            ))}
          </Stack>
        </Section>
      )}

      {report.progression.length > 0 && (
        <Section title="How The Scam Progressed">
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap alignItems="center">
            {report.progression.map((stage, i) => (
              <Stack key={stage} direction="row" spacing={0.5} alignItems="center">
                {i > 0 && (
                  <Typography color="text.disabled" sx={{ mx: 0.5 }}>
                    →
                  </Typography>
                )}
                <Chip
                  label={stage}
                  size="small"
                  sx={{ bgcolor: "rgba(26,161,121,0.14)", color: ACCENT, fontWeight: 600 }}
                />
              </Stack>
            ))}
          </Stack>
        </Section>
      )}

      {report.evidence.length > 0 && (
        <Section title="Evidence Examined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>File</TableCell>
                <TableCell>Added</TableCell>
                <TableCell>Text Read</TableCell>
                <TableCell>Integrity</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.evidence.map((row) => (
                <TableRow key={row.evidenceId}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {row.file}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.evidenceId}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.acquired}</TableCell>
                  <TableCell>{row.textConfidence}</TableCell>
                  <TableCell>
                    <Badge label={row.integrity} tone={row.integrityOk ? "good" : "bad"} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {report.connections.length > 0 && (
        <Section title="Links Between Evidence">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Items</TableCell>
                <TableCell>Strength</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>What This Means</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.connections.map((row) => (
                <TableRow key={row.pair}>
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', whiteSpace: "nowrap" }}>
                    {row.pair}
                  </TableCell>
                  <TableCell>{row.strength}</TableCell>
                  <TableCell>{row.confidence}</TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {row.meaning}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {report.nextSteps.length > 0 && (
        <Section title="Recommended Next Steps">
          <Stack spacing={1}>
            {report.nextSteps.map((line, i) => (
              <Typography key={i} variant="body2">
                • {line}
              </Typography>
            ))}
          </Stack>
        </Section>
      )}
    </Paper>
  );
}
