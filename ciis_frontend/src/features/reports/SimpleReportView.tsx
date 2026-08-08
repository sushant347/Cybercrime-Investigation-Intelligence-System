import GavelIcon from "@mui/icons-material/Gavel";
import BalanceIcon from "@mui/icons-material/Balance";
import FactCheckIcon from "@mui/icons-material/FactCheck";
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
  useTheme,
} from "@mui/material";
import { Fragment } from "react";
import type { ReactNode } from "react";

import { toneColor } from "@/theme/theme";
import type { SimpleReport, SummaryRow } from "./reportModel";
import {
  connectionDiagramSvg,
  ocrConfidenceSvg,
  predictionRiskSvg,
  DARK_PALETTE,
  PRINT_PALETTE,
} from "./reportCharts";

const MONO = '"JetBrains Mono", ui-monospace, monospace';

/**
 * Resolve the report's semantic inks for the active mode.
 *
 * These were previously fixed print colours — a near-black green for headings
 * (`#14532d`) and a slate grey for neutral badges. Against the dark canvas
 * (`#0b1020`) those sat around 1.5:1, well under the 4.5:1 needed to be read
 * at body size, which is exactly the "dark text on dark theme" problem. The
 * light-mode values are unchanged, so printed and light-mode output looks
 * exactly as it did before.
 */
function useReportTones() {
  const theme = useTheme();
  const mode = theme.palette.mode === "dark" ? "dark" : "light";
  return {
    mode,
    accent: toneColor("accent", mode),
    badge: {
      good: toneColor("good", mode),
      warn: toneColor("warn", mode),
      bad: toneColor("bad", mode),
      neutral: toneColor("neutral", mode),
    } as Record<NonNullable<SummaryRow["badge"]>, string>,
  };
}

function Section({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: ReactNode;
}) {
  const { accent } = useReportTones();
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", p: { xs: 2, sm: 3 } }}>
      <Typography
        variant="subtitle2"
        sx={{
          color: accent,
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
  const { badge, mode } = useReportTones();
  const color = badge[tone];
  // In dark mode the tones are light inks, so a filled chip needs dark text to
  // stay legible; in light mode they are dark inks and need white.
  return (
    <Chip
      label={label}
      size="small"
      sx={{
        bgcolor: color,
        color: mode === "dark" ? "#0b1020" : "#fff",
        fontWeight: 700,
      }}
    />
  );
}

/**
 * One provision of the Act the findings engage.
 *
 * The previous rendering ran conduct, penalty and basis together as three
 * near-identical `<strong>`-prefixed sentences in one block, so the section
 * number, the offence, the sentence exposure and — most importantly — the
 * reason the provision is listed at all were all the same visual weight. An
 * officer checking this section reads it in a specific order: *which section,
 * why is it here, what does it carry*. The layout now follows that order.
 *
 * "Why this is engaged" gets the accent panel because it is the only part
 * tied to this case's actual findings; the other two are statute text that
 * would read identically in any report.
 */
function ProvisionCard({
  provision,
}: {
  provision: NonNullable<SimpleReport["legalBasis"]>["provisions"][number];
}) {
  const { accent, mode } = useReportTones();

  const Field = ({
    icon,
    label,
    children,
  }: {
    icon: ReactNode;
    label: string;
    children: ReactNode;
  }) => (
    <Stack direction="row" spacing={1.25} alignItems="flex-start">
      <Box sx={{ color: "text.disabled", display: "flex", mt: 0.25 }}>{icon}</Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography
          variant="caption"
          sx={{
            display: "block",
            textTransform: "uppercase",
            letterSpacing: "0.07em",
            fontWeight: 700,
            color: "text.secondary",
            mb: 0.25,
          }}
        >
          {label}
        </Typography>
        <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
          {children}
        </Typography>
      </Box>
    </Stack>
  );

  return (
    <Box
      sx={{
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        overflow: "hidden",
        transition: "border-color 160ms ease",
        "&:hover": { borderColor: accent },
      }}
    >
      {/* Citation header — the section number is the thing being looked up. */}
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
        sx={{
          p: 1.75,
          bgcolor: "action.hover",
          borderBottom: 1,
          borderColor: "divider",
        }}
      >
        <Box
          sx={{
            flexShrink: 0,
            px: 1.25,
            py: 0.5,
            borderRadius: 1,
            bgcolor: accent,
            color: mode === "dark" ? "#0b1020" : "#fff",
            fontFamily: MONO,
            fontWeight: 800,
            fontSize: "0.8rem",
            lineHeight: 1.5,
          }}
        >
          § {provision.section}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.35 }}>
            {provision.title}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontFamily: MONO, fontSize: "0.68rem" }}
          >
            {provision.citation}
          </Typography>
        </Box>
      </Stack>

      <Stack spacing={1.75} sx={{ p: 2 }}>
        <Field icon={<BalanceIcon fontSize="small" />} label="Conduct the section covers">
          {provision.conduct}
        </Field>
        <Field icon={<GavelIcon fontSize="small" />} label="Penalty on conviction">
          {provision.penalty}
        </Field>

        {/* The basis is the whole point: it is why this provision is listed at
            all, and it is what an officer checks first. */}
        <Box
          sx={{
            borderLeft: 3,
            borderColor: accent,
            borderRadius: 0.5,
            bgcolor: mode === "dark" ? "rgba(94,234,212,0.07)" : "rgba(20,83,45,0.05)",
            p: 1.5,
          }}
        >
          <Field icon={<FactCheckIcon fontSize="small" />} label="Why this case engages it">
            {provision.basis}
          </Field>

          {provision.evidence_ids.length > 0 && (
            <Stack
              direction="row"
              spacing={0.5}
              flexWrap="wrap"
              useFlexGap
              sx={{ mt: 1.5, pl: 4 }}
            >
              {provision.evidence_ids.map((id) => (
                <Chip
                  key={id}
                  label={id}
                  size="small"
                  variant="outlined"
                  sx={{ fontFamily: MONO, fontSize: "0.68rem" }}
                />
              ))}
            </Stack>
          )}
        </Box>
      </Stack>
    </Box>
  );
}

/**
 * The stages the scam moved through, as an ordered flow.
 *
 * Chips separated by arrows wrapped mid-sequence on narrow widths and lost
 * the sense of direction. A numbered rail keeps the order unambiguous however
 * it wraps, and the deepening tint carries the sense of escalation that the
 * flat chips did not.
 */
function ProgressionFlow({ stages }: { stages: string[] }) {
  const { accent, mode } = useReportTones();

  return (
    <Stack direction="row" flexWrap="wrap" useFlexGap sx={{ gap: 1 }}>
      {stages.map((stage, i) => {
        // Later stages sit deeper in the accent, so escalation is visible at a
        // glance without needing to read the labels in order.
        const weight = 0.1 + (i / Math.max(1, stages.length - 1)) * 0.5;
        return (
          <Stack
            key={stage}
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{
              px: 1.25,
              py: 0.75,
              borderRadius: 1,
              border: 1,
              borderColor: "divider",
              bgcolor:
                mode === "dark"
                  ? `rgba(94,234,212,${weight * 0.22})`
                  : `rgba(20,83,45,${weight * 0.14})`,
            }}
          >
            <Box
              sx={{
                width: 20,
                height: 20,
                flexShrink: 0,
                borderRadius: "50%",
                bgcolor: accent,
                color: mode === "dark" ? "#0b1020" : "#fff",
                fontSize: "0.7rem",
                fontWeight: 800,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {i + 1}
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {stage}
            </Typography>
          </Stack>
        );
      })}
    </Stack>
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
  // Screen-only: the downloadable HTML keeps the print inks (see reportCharts).
  const { mode } = useReportTones();
  const chartPalette = mode === "dark" ? DARK_PALETTE : PRINT_PALETTE;
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
              Cybercrime Investigation Intelligence Engine
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
          <Svg markup={ocrConfidenceSvg(report.evidence, chartPalette)} />
        </Section>
      )}

      {report.connections.length > 0 && (
        <Section number={next()} title="How the Evidence Connects">
          <Svg markup={connectionDiagramSvg(report.evidence, report.connections, chartPalette)} />
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
              <Svg markup={predictionRiskSvg(report.modelPredictions, chartPalette)} />
            </>
          )}
        </Section>
      )}

      {report.progression.length > 0 && (
        <Section number={next()} title="How the Scam Progressed">
          <ProgressionFlow stages={report.progression} />
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

      {report.legalBasis && (
        <Section number={next()} title="Statutory Basis">
          <Typography variant="body2" sx={{ mb: 2 }}>
            {report.legalBasis.summary}
          </Typography>

          <Stack spacing={2}>
            {report.legalBasis.provisions.map((provision) => (
              <ProvisionCard key={provision.section} provision={provision} />
            ))}
          </Stack>

          {/* Never rendered separately from the provisions above: the caveat is
              what stops the list being read as a charging decision. */}
          <Typography
            variant="caption"
            component="p"
            sx={{
              mt: 2,
              p: 1.5,
              borderRadius: 1,
              bgcolor: "action.hover",
              color: "text.secondary",
              lineHeight: 1.6,
            }}
          >
            {report.legalBasis.caveat}
          </Typography>
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
