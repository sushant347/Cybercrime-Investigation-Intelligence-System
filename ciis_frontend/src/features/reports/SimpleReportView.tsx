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
import { Fragment } from "react";
import type { ReactNode } from "react";

import type { SimpleReport, SummaryRow } from "./reportModel";
import {
  connectionDiagramSvg,
  ocrConfidenceSvg,
  predictionRiskSvg,
} from "./reportCharts";

const BADGE_COLOR: Record<NonNullable<SummaryRow["badge"]>, string> = {
  good: "#1a7f5a",
  warn: "#a86612",
  bad: "#b3261e",
  neutral: "#4a5568",
};

const ACCENT = "#14532d";
const MONO = '"JetBrains Mono", ui-monospace, monospace';

function Section({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", p: { xs: 2, sm: 3 } }}>
      <Typography
        variant="subtitle2"
        sx={{
          color: ACCENT,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          mb: 1.5,
          fontWeight: 700,
        }}
      >
        {number}. {title}
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

function Svg({ markup }: { markup: string }) {
  if (!markup) return null;
  // Generated locally by reportCharts from engine values only (never from
  // user-controlled strings, which are escaped) and shared verbatim with the
  // downloadable HTML file so both renderings stay identical.
  return <Box sx={{ mt: 1.5 }} dangerouslySetInnerHTML={{ __html: markup }} />;
}

/**
 * Document-style rendering of the plain-language investigation report.
 * Every value comes from the stored engine report; this component only lays
 * it out. Section numbering mirrors the PDF and downloadable HTML exports.
 */
export function SimpleReportView({ report }: { report: SimpleReport }) {
  let n = 0;
  const next = () => ++n;

  return (
    <Paper variant="outlined" sx={{ overflow: "hidden" }}>
      {/* Letterhead */}
      <Box sx={{ p: { xs: 2, sm: 3 }, pb: 2 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
          flexWrap="wrap"
          useFlexGap
          spacing={1}
        >
          <Box>
            <Typography
              variant="overline"
              sx={{ color: "text.secondary", letterSpacing: "0.08em" }}
            >
              Cybercrime Investigation Intelligence System
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.25 }}>
              Investigation Report
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Case “{report.caseReference || report.caseId}” — assembled from
              stored, hash-verified findings only
            </Typography>
          </Box>
          <Box sx={{ textAlign: { sm: "right" } }}>
            {report.provenance && (
              <Typography variant="caption" sx={{ fontFamily: MONO, display: "block" }}>
                {report.provenance.reportId}
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              Version {report.reportVersion}
            </Typography>
          </Box>
        </Stack>
      </Box>

      <Section number={next()} title="Case Summary">
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
        <Section number={next()} title="Key Findings">
          <Stack spacing={1}>
            {report.findings.map((line, i) => (
              <Typography key={i} variant="body2">
                {i + 1}. {line}
              </Typography>
            ))}
          </Stack>
        </Section>
      )}

      {report.evidence.length > 0 && (
        <Section number={next()} title="Evidence & Chain of Custody">
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
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: MONO }}>
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
          <Svg markup={ocrConfidenceSvg(report.evidence)} />
        </Section>
      )}

      {report.connections.length > 0 && (
        <Section number={next()} title="How the Evidence Connects">
          <Svg markup={connectionDiagramSvg(report.evidence, report.connections)} />
          <Table size="small" sx={{ mt: 1.5 }}>
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
                  <TableCell sx={{ fontFamily: MONO, whiteSpace: "nowrap" }}>
                    {row.pair}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={row.strength} variant="outlined" />
                  </TableCell>
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

      {report.linkedCases.length > 0 && (
        <Section number={next()} title="Cross-Case Correlation">
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Identifiers from this case (phones, wallets, URLs…) were also
            observed in the cases below — these investigations may be related.
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Case</TableCell>
                <TableCell>Strength</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Shared With This Case</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.linkedCases.map((row) => (
                <TableRow key={row.caseId}>
                  <TableCell sx={{ fontFamily: MONO, whiteSpace: "nowrap" }}>
                    {row.caseId}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={row.strength} variant="outlined" />
                  </TableCell>
                  <TableCell>{row.confidence}</TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {row.sharedEntities}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {(report.modelPredictions.length > 0 || report.modelPredictionsNote) && (
        <Section number={next()} title="Model Prediction Results">
          {report.modelPredictionsNote ? (
            <Typography variant="body2" color="text.secondary">
              {report.modelPredictionsNote}
            </Typography>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Every URL and domain found in the evidence, classified by the
                threat model. Verdicts are recorded verbatim from the model
                output.
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Indicator</TableCell>
                    <TableCell>Verdict</TableCell>
                    <TableCell>Risk</TableCell>
                    <TableCell>Model Confidence</TableCell>
                    <TableCell>Source Model</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.modelPredictions.map((row) => (
                    <Fragment key={row.indicator}>
                      <TableRow>
                        <TableCell sx={{ fontFamily: MONO, wordBreak: "break-all" }}>
                          {row.indicator}
                        </TableCell>
                        <TableCell>
                          <Badge label={row.verdict} tone={row.verdictBad ? "bad" : "good"} />
                        </TableCell>
                        <TableCell>{row.risk}</TableCell>
                        <TableCell>{row.confidence}</TableCell>
                        <TableCell sx={{ fontFamily: MONO, fontSize: "0.72rem" }}>
                          {row.model}
                        </TableCell>
                      </TableRow>
                      {(row.facts.length > 0 || row.reasons.length > 0) && (
                        <TableRow>
                          {/* The verdict alone is not usable in a report — this
                              row carries the domain facts and the plain-language
                              reasons the model actually relied on. */}
                          <TableCell colSpan={5} sx={{ pt: 0, pb: 2, borderBottom: 0 }}>
                            {row.facts.length > 0 && (
                              <Stack
                                direction="row"
                                spacing={0.75}
                                flexWrap="wrap"
                                useFlexGap
                                sx={{ mb: row.reasons.length ? 1 : 0 }}
                              >
                                {row.facts.map((fact) => (
                                  <Chip
                                    key={fact.label}
                                    size="small"
                                    variant="outlined"
                                    color={fact.bad ? "error" : "default"}
                                    label={`${fact.label}: ${fact.value}`}
                                    sx={{ fontSize: "0.72rem" }}
                                  />
                                ))}
                              </Stack>
                            )}
                            {row.reasons.length > 0 && (
                              <Stack component="ul" sx={{ m: 0, pl: 2.5 }} spacing={0.25}>
                                {row.reasons.map((reason) => (
                                  <Typography
                                    key={reason}
                                    component="li"
                                    variant="caption"
                                    color="text.secondary"
                                  >
                                    {reason}
                                  </Typography>
                                ))}
                              </Stack>
                            )}
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
              <Svg markup={predictionRiskSvg(report.modelPredictions)} />
            </>
          )}
        </Section>
      )}

      {report.progression.length > 0 && (
        <Section number={next()} title="How the Scam Progressed">
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap alignItems="center">
            {report.progression.map((stage, i) => (
              <Stack key={stage} direction="row" spacing={0.5} alignItems="center">
                {i > 0 && (
                  <Typography color="text.disabled" sx={{ mx: 0.5 }}>
                    →
                  </Typography>
                )}
                <Chip
                  label={`${i + 1}. ${stage}`}
                  size="small"
                  sx={
                    i === 0
                      ? { bgcolor: ACCENT, color: "#fff", fontWeight: 600 }
                      : { bgcolor: "rgba(26,161,121,0.14)", color: ACCENT, fontWeight: 600 }
                  }
                />
              </Stack>
            ))}
          </Stack>
        </Section>
      )}

      {report.methodology.length > 0 && (
        <Section number={next()} title="Methodology">
          <Stack spacing={0.75}>
            {report.methodology.map((line, i) => (
              <Typography key={i} variant="body2" color="text.secondary">
                • {line}
              </Typography>
            ))}
          </Stack>
        </Section>
      )}

      {report.nextSteps.length > 0 && (
        <Section number={next()} title="Recommendations">
          <Stack spacing={1}>
            {report.nextSteps.map((line, i) => (
              <Typography key={i} variant="body2">
                {i + 1}. {line}
              </Typography>
            ))}
          </Stack>
        </Section>
      )}

      {/* Provenance & integrity footer */}
      <Box
        sx={{
          borderTop: 1,
          borderColor: "divider",
          p: { xs: 2, sm: 3 },
          bgcolor: "action.hover",
        }}
      >
        {report.provenance ? (
          <>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              {report.provenance.generator}
            </Typography>
            <Typography
              variant="caption"
              sx={{ fontFamily: MONO, display: "block", mt: 0.5, wordBreak: "break-all" }}
            >
              Evidence-set digest (SHA-256): {report.provenance.evidenceSetDigest}
            </Typography>
            {report.provenance.artifactHashes.map((h) => (
              <Typography
                key={h.name}
                variant="caption"
                color="text.secondary"
                sx={{ fontFamily: MONO, display: "block", wordBreak: "break-all" }}
              >
                {h.name}: {h.digest}
              </Typography>
            ))}
          </>
        ) : (
          <Typography variant="caption" color="text.secondary">
            Generated {report.generatedAt} · version {report.reportVersion} — every
            statement above references stored forensic findings.
          </Typography>
        )}
      </Box>
    </Paper>
  );
}
