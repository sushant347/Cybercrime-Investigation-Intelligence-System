import {
  Box,
  Chip,
  Link,
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

import { EntityChip, entityTypeLabel } from "@/components/common/EntityChip";
import { KeyFindings } from "./KeyFindings";
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

/**
 * The report view is styled after a printed document, and its accent was the
 * dark green a document uses on white paper. Rendered on the app's dark
 * surfaces it came out at a 1.9:1 contrast ratio — the section headings were
 * effectively invisible, which is why parts of this report could not be read.
 * The paper tone is kept for light mode and swapped for one that carries on
 * dark, so the same design reads in both.
 */
const ACCENT_ON_LIGHT = "#14532d";
const ACCENT_ON_DARK = "#4ade80";

function useReportAccent(): string {
  const theme = useTheme();
  return theme.palette.mode === "dark" ? ACCENT_ON_DARK : ACCENT_ON_LIGHT;
}
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
  const accent = useReportAccent();
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
  return (
    <Chip
      label={label}
      size="small"
      sx={{ bgcolor: BADGE_COLOR[tone], color: "#fff", fontWeight: 700 }}
    />
  );
}

function Svg({ markup }: { markup: string }) {
  const theme = useTheme();
  if (!markup) return null;
  // Generated locally by reportCharts from engine values only (never from
  // user-controlled strings, which are escaped).
  //
  // The diagrams are drawn in printed-document ink and declare each colour as
  // a CSS variable with that ink as the fallback. Binding the variables to the
  // active theme here is what keeps the evidence-id labels and the bar tracks
  // legible on the dark surface, where the fixed palette rendered them at
  // barely above the background tone.
  const dark = theme.palette.mode === "dark";
  return (
    <Box
      sx={{
        mt: 1.5,
        "--ciis-chart-ink": theme.palette.text.primary,
        "--ciis-chart-muted": theme.palette.text.secondary,
        "--ciis-chart-track": dark
          ? "rgba(148,163,204,0.18)"
          : "#edf2f7",
        "--ciis-chart-node-fill": dark ? "rgba(74,222,128,0.16)" : "#f0fdf4",
        "--ciis-chart-node-stroke": dark ? ACCENT_ON_DARK : ACCENT_ON_LIGHT,
        "--ciis-chart-weak": theme.palette.text.secondary,
        // The document reds and ambers are mixed for white paper and fall to
        // ~2.6:1 on the dark surface; the dark theme takes its own tones.
        "--ciis-chart-strong": dark ? "#ff6b63" : "#b3261e",
        "--ciis-chart-moderate": dark ? "#f0a94a" : "#a86612",
        "--ciis-chart-good": dark ? "#3ddc97" : "#1a7f5a",
      }}
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  );
}

function splitMethod(line: string): { stage: string; method: string } {
  const divider = line.indexOf(":");
  if (divider < 0) return { stage: "Analysis", method: line };
  return {
    stage: line.slice(0, divider).replace(/^Phase\s+\d+\s*-\s*/i, ""),
    method: line.slice(divider + 1).trim(),
  };
}

/**
 * Document-style rendering of the plain-language investigation report.
 * Every value comes from the stored engine report; this component only lays
 * it out. Section numbering mirrors the PDF and downloadable HTML exports.
 */
/**
 * The identifiers two cases have in common, grouped by kind.
 *
 * A strong cross-case link can share thirty identifiers; as prose that is a
 * wall, so they are grouped by type and shown as the same chips the
 * investigation view uses. Nothing is dropped — a long group states its
 * remainder rather than trailing off.
 */
function SharedEntityList({
  entities,
}: {
  entities: { entityType: string; value: string }[];
}) {
  if (entities.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No shared identifier was recorded.
      </Typography>
    );
  }

  const byType = new Map<string, string[]>();
  for (const entity of entities) {
    const bucket = byType.get(entity.entityType) ?? [];
    bucket.push(entity.value);
    byType.set(entity.entityType, bucket);
  }
  const PER_TYPE = 4;

  return (
    <Stack spacing={0.75}>
      {[...byType.entries()].map(([type, values]) => {
        const shown = values.slice(0, PER_TYPE);
        const hidden = values.length - shown.length;
        return (
          <Box key={type}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ fontWeight: 700, display: "block" }}
            >
              {entityTypeLabel(type)} ({values.length})
            </Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.25 }}>
              {shown.map((value) => (
                <EntityChip key={value} entityType={type} value={value} size="small" />
              ))}
              {hidden > 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ alignSelf: "center" }}>
                  +{hidden} more
                </Typography>
              )}
            </Stack>
          </Box>
        );
      })}
    </Stack>
  );
}

export function SimpleReportView({ report }: { report: SimpleReport }) {
  const accent = useReportAccent();
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
          <KeyFindings findings={report.findings} />
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
                <TableCell>Entities</TableCell>
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
                  <TableCell>{row.entityCount}</TableCell>
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
                      {row.basis || row.meaning}
                    </Typography>
                    {row.basis && (
                      <Typography variant="caption" color="text.secondary">
                        Interpretation: {row.meaning}
                      </Typography>
                    )}
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
                  <TableCell sx={{ minWidth: 260 }}>
                    <SharedEntityList entities={row.sharedEntities} />
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
                      ? { bgcolor: accent, color: "#08130c", fontWeight: 700 }
                      : { bgcolor: "rgba(26,161,121,0.16)", color: accent, fontWeight: 600 }
                  }
                />
              </Stack>
            ))}
          </Stack>
        </Section>
      )}

      {report.timelineEvents.length > 0 && (
        <Section number={next()} title="Chronological Events">
          {report.timelineReliability && (
            <Box sx={{ mb: 1.5, p: 1.25, bgcolor: "action.hover", borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {report.timelineReliability}
              </Typography>
            </Box>
          )}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Resolved time</TableCell>
                <TableCell>Evidence</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Stages</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.timelineEvents.map((event, index) => (
                <TableRow key={`${event.evidenceId}-${index}`} hover>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>{event.timestamp}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{event.file}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: MONO }}>
                      {event.evidenceId}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{event.source}</Typography>
                    <Typography variant="caption" color="text.secondary">{event.confidence}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={event.fallback ? "Upload fallback" : event.inferred ? "Inferred" : "Actual"}
                      color={event.fallback ? "default" : event.inferred ? "warning" : "success"}
                      variant="outlined"
                    />
                    {event.critical && <Chip size="small" label="Critical" color="error" sx={{ ml: 0.5 }} />}
                  </TableCell>
                  <TableCell>{event.stages.join(", ") || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {report.methodology.length > 0 && (
        <Section number={next()} title="Methodology">
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>Stage</TableCell><TableCell>Method and stored output</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {report.methodology.map((line, i) => {
                const row = splitMethod(line);
                return (
                  <TableRow key={i}>
                    <TableCell sx={{ fontWeight: 700, width: "28%" }}>{row.stage}</TableCell>
                    <TableCell>{row.method}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Section>
      )}

      {report.legalBasis && (
        <Section number={next()} title="Statutory Basis">
          <Typography variant="body2" sx={{ mb: 2 }}>
            {report.legalBasis.summary}
          </Typography>

          <Stack spacing={2}>
            {report.legalBasis.provisions.map((provision) => (
              <Box
                key={provision.section}
                sx={{
                  border: 1,
                  borderColor: "divider",
                  borderLeft: 3,
                  borderLeftColor: accent,
                  borderRadius: 1,
                  p: 2,
                }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  Section {provision.section} — {provision.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {provision.citation}
                </Typography>

                <Table size="small" sx={{ mt: 1 }}>
                  <TableBody>
                    {[
                      ["Conduct", provision.conduct],
                      ["Penalty", provision.penalty],
                      ["Evidence-based match", provision.basis],
                    ].map(([label, value]) => (
                      <TableRow key={label}>
                        <TableCell sx={{ width: 150, fontWeight: 700, verticalAlign: "top" }}>
                          {label}
                        </TableCell>
                        <TableCell>{value}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {provision.evidence_ids.length > 0 && (
                  <Stack
                    direction="row"
                    spacing={0.5}
                    flexWrap="wrap"
                    useFlexGap
                    sx={{ mt: 1.5 }}
                  >
                    {provision.evidence_ids.map((id) => (
                      <Chip key={id} label={id} size="small" variant="outlined" />
                    ))}
                  </Stack>
                )}
              </Box>
            ))}
          </Stack>

          {(report.legalBasis.investigative_guidance?.length ?? 0) > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Evidentiary and regulatory follow-up
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Preservation and investigative actions—not findings that an institution
                violated a rule.
              </Typography>

              <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                {report.legalBasis.investigative_guidance?.map((item) => (
                  <Box
                    key={`${item.source_id}-${item.control_ids.join("-")}`}
                    sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 2 }}
                  >
                    <Stack
                      direction={{ xs: "column", sm: "row" }}
                      spacing={1}
                      justifyContent="space-between"
                    >
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          {item.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {item.citation}
                        </Typography>
                      </Box>
                      <Chip
                        size="small"
                        label={item.status.replaceAll("_", " ")}
                        variant="outlined"
                      />
                    </Stack>
                    <Table size="small" sx={{ mt: 1 }}>
                      <TableBody>
                        {[
                          ["Expectation", item.expectation],
                          ["Why relevant", item.basis],
                          ["Action", item.recommended_action],
                          ["Applicability", item.applicability],
                        ].map(([label, value]) => (
                          <TableRow key={label}>
                            <TableCell sx={{ width: 130, fontWeight: 700, verticalAlign: "top" }}>
                              {label}
                            </TableCell>
                            <TableCell>{value}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {item.evidence_ids.length > 0 && (
                      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                        {item.evidence_ids.map((id) => (
                          <Chip key={id} label={id} size="small" variant="outlined" />
                        ))}
                      </Stack>
                    )}
                  </Box>
                ))}
              </Stack>
            </Box>
          )}

          {(report.legalBasis.manual_review_provisions?.length ?? 0) > 0 && (
            <Box sx={{ mt: 3, p: 2, borderRadius: 1, bgcolor: "action.hover" }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Provisions requiring manual review
              </Typography>
              <Typography variant="caption" color="text.secondary">
                The current evidence model does not automatically assess these sections.
              </Typography>
              <Stack spacing={0.75} sx={{ mt: 1 }}>
                {report.legalBasis.manual_review_provisions?.map((item) => (
                  <Typography key={item.section} variant="body2">
                    <strong>Section {item.section} — {item.title}.</strong> {item.reason}
                  </Typography>
                ))}
              </Stack>
            </Box>
          )}

          {(report.legalBasis.sources?.length ?? 0) > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Primary sources
              </Typography>
              <Stack spacing={0.75} sx={{ mt: 0.75 }}>
                {report.legalBasis.sources?.map((source) => (
                  <Typography key={source.source_id} variant="caption" color="text.secondary">
                    <Link href={source.url} target="_blank" rel="noopener noreferrer">
                      {source.authority} — {source.title}
                    </Link>{" "}
                    · {source.usage} {source.note}
                  </Typography>
                ))}
              </Stack>
            </Box>
          )}

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
          <Table size="small">
            <TableHead><TableRow><TableCell>#</TableCell><TableCell>Investigator action</TableCell></TableRow></TableHead>
            <TableBody>
              {report.nextSteps.map((line, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ width: 48, fontWeight: 700 }}>{i + 1}</TableCell>
                  <TableCell>{line}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}

      {report.limitations.length > 0 && (
        <Section number={next()} title="Limitations & Review Notes">
          <Table size="small">
            <TableHead><TableRow><TableCell>#</TableCell><TableCell>What must be verified</TableCell></TableRow></TableHead>
            <TableBody>
              {report.limitations.map((line, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ width: 48 }}>{i + 1}</TableCell>
                  <TableCell>{line}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
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
