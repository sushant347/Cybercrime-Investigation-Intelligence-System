import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Fragment, useState } from "react";
import type { ReactNode } from "react";

import { EntityChip, entityTypeLabel } from "@/components/common/EntityChip";
import { KeyFindings } from "./KeyFindings";
import type { ReportLegalBasisSection } from "@/types";
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

/**
 * One methodology line, split into the parts it is actually written in.
 *
 * The engine stores each stage as `"Phase 1 - Acquisition & OCR: <what it
 * did>; <where the output is stored>"`. Printed whole it is a dense sentence
 * whose phase label, stage name and individual steps all run together, so each
 * is pulled out and laid out in its own place. The text itself is untouched.
 */
function splitMethod(line: string): {
  phase: string;
  stage: string;
  steps: string[];
} {
  const divider = line.indexOf(":");
  const head = divider < 0 ? "Analysis" : line.slice(0, divider);
  const body = (divider < 0 ? line : line.slice(divider + 1)).trim();
  const phased = head.match(/^Phase\s+(\d+)\s*-\s*(.*)$/i);
  return {
    phase: phased ? `Phase ${phased[1]}` : "",
    stage: (phased ? phased[2] : head).trim(),
    // The engine writes each stage as one sentence, so the half after the
    // colon starts lowercase. Standing alone in its own column that reads as
    // a fragment, so only the first letter is lifted — acronyms such as
    // "metadata/EXIF" and the wording itself are left alone.
    steps: body
      .split(";")
      .map((step) => step.trim())
      .filter(Boolean)
      .map((step) =>
        /^[a-z]/.test(step) ? step[0].toUpperCase() + step.slice(1) : step,
      ),
  };
}

/** A labelled block of engine prose — the unit both provisions and guidance use. */
function Field({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2">{value}</Typography>
    </Box>
  );
}

/** Evidence ids as chips, under a label. */
function EvidenceChips({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <Box sx={{ mt: 1.75 }}>
      <Typography variant="overline" color="text.secondary">
        Evidence behind it
      </Typography>
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
        {ids.map((id) => (
          <Chip key={id} label={id} size="small" variant="outlined" />
        ))}
      </Stack>
    </Box>
  );
}

/**
 * Statutory basis: a shortlist that stays a list until asked to open.
 *
 * Six provisions and two follow-up actions, each carrying four blocks of
 * statutory prose, ran to several screens — so the section's own shape (how
 * many provisions, which ones, how much evidence behind each) was only
 * visible by scrolling past all of it. Every provision is now a row that
 * states what it is and how much evidence sits behind it, opening to the full
 * text unchanged. Nothing is dropped or shortened; it is folded.
 *
 * The caveat is the exception and is never folded: it is what stops the list
 * being read as a charging decision, so it stays beside the count it
 * qualifies.
 */
function StatutoryBasis({
  basis,
  accent,
}: {
  basis: ReportLegalBasisSection;
  accent: string;
}) {
  const provisions = basis.provisions;
  const guidance = basis.investigative_guidance ?? [];
  const manual = basis.manual_review_provisions ?? [];
  const sources = basis.sources ?? [];

  const keys = [
    ...provisions.map((p) => `p:${p.section}`),
    ...guidance.map((_, i) => `g:${i}`),
    ...(manual.length > 0 ? ["manual"] : []),
  ];
  // The first provision opens by default: a column of closed bars gives a
  // reader no sense of what one contains, and the engine orders provisions by
  // relevance, so the first is the one worth showing.
  const [open, setOpen] = useState<Record<string, boolean>>(() =>
    provisions[0] ? { [`p:${provisions[0].section}`]: true } : {},
  );

  const allOpen = keys.length > 0 && keys.every((k) => open[k]);
  const toggleAll = () =>
    setOpen(allOpen ? {} : Object.fromEntries(keys.map((k) => [k, true])));
  const toggle = (key: string) =>
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  const panelSx = {
    border: 1,
    borderColor: "divider",
    borderLeft: 3,
    borderLeftColor: accent,
    borderRadius: 1,
    "&:before": { display: "none" },
  } as const;

  return (
    <>
      <Box
        sx={{
          p: 2,
          mb: 2,
          borderRadius: 1,
          border: 1,
          borderColor: "divider",
          bgcolor: "action.hover",
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
          What this section is
        </Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          Offences whose description matches what the evidence shows — a
          shortlist for legal review.
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.6 }}>
          {basis.caveat}
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", mt: 1.5, fontWeight: 700 }}
        >
          {basis.statute} · {basis.jurisdiction}
        </Typography>
        {basis.language_note && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mt: 0.5 }}
          >
            {basis.language_note}
          </Typography>
        )}
      </Box>

      <Stack
        direction="row"
        alignItems="baseline"
        justifyContent="space-between"
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="body2">{basis.summary}</Typography>
        {keys.length > 0 && (
          <Typography
            component="button"
            type="button"
            variant="caption"
            onClick={toggleAll}
            sx={{
              background: "none",
              border: 0,
              p: 0,
              cursor: "pointer",
              color: "text.secondary",
              textDecoration: "underline",
              font: "inherit",
              whiteSpace: "nowrap",
            }}
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </Typography>
        )}
      </Stack>

      <Stack spacing={1}>
        {provisions.map((provision) => {
          const key = `p:${provision.section}`;
          return (
            <Accordion
              key={provision.section}
              disableGutters
              elevation={0}
              expanded={!!open[key]}
              onChange={() => toggle(key)}
              sx={panelSx}
            >
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Stack
                  direction="row"
                  spacing={1.5}
                  alignItems="center"
                  sx={{ flex: 1, minWidth: 0, pr: 1 }}
                >
                  <Chip
                    size="small"
                    label={`s.${provision.section}`}
                    sx={{ fontWeight: 700, height: 22 }}
                  />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, minWidth: 0 }}>
                    {provision.title}
                  </Typography>
                  <Box sx={{ flex: 1 }} />
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ whiteSpace: "nowrap" }}
                  >
                    {provision.evidence_ids.length} item
                    {provision.evidence_ids.length === 1 ? "" : "s"}
                  </Typography>
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: "block", mb: 1.5 }}
                >
                  {provision.citation}
                </Typography>
                <Stack spacing={1.5}>
                  <Field label="What the law covers" value={provision.conduct} />
                  {/* The question an investigator actually opens this for, so
                      it is the one that carries the accent. */}
                  <Box sx={{ borderLeft: 2, borderColor: accent, pl: 1.5 }}>
                    <Field
                      label="What in this case pointed here"
                      value={provision.basis}
                    />
                  </Box>
                  <Field
                    label="Maximum penalty on conviction"
                    value={provision.penalty}
                  />
                </Stack>
                <EvidenceChips ids={provision.evidence_ids} />
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Stack>

      {guidance.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Evidentiary and regulatory follow-up
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Records to preserve and parties to approach while they still hold
            the data — not findings that any institution broke a rule.
          </Typography>

          <Stack spacing={1} sx={{ mt: 1.5 }}>
            {guidance.map((item, index) => {
              const key = `g:${index}`;
              return (
                <Accordion
                  key={`${item.source_id}-${item.control_ids.join("-")}`}
                  disableGutters
                  elevation={0}
                  expanded={!!open[key]}
                  onChange={() => toggle(key)}
                  sx={{
                    border: 1,
                    borderColor: "divider",
                    borderRadius: 1,
                    "&:before": { display: "none" },
                  }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Stack
                      direction="row"
                      spacing={1.5}
                      alignItems="center"
                      sx={{ flex: 1, minWidth: 0, pr: 1 }}
                    >
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, minWidth: 0 }}>
                        {item.title}
                      </Typography>
                      <Box sx={{ flex: 1 }} />
                      <Chip
                        size="small"
                        label={item.status.replaceAll("_", " ")}
                        variant="outlined"
                        sx={{ height: 22 }}
                      />
                    </Stack>
                  </AccordionSummary>
                  <AccordionDetails sx={{ pt: 0 }}>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block", mb: 1.5 }}
                    >
                      {item.citation}
                    </Typography>
                    <Stack spacing={1.25}>
                      {[
                        ["What the rule expects", item.expectation],
                        ["Why it applies here", item.basis],
                        ["What to do about it", item.recommended_action],
                        ["Who it binds", item.applicability],
                      ]
                        .filter(([, value]) => value)
                        .map(([label, value]) => (
                          <Field key={label} label={label} value={value} />
                        ))}
                    </Stack>
                    <EvidenceChips ids={item.evidence_ids} />
                  </AccordionDetails>
                </Accordion>
              );
            })}
          </Stack>
        </Box>
      )}

      {manual.length > 0 && (
        <Accordion
          disableGutters
          elevation={0}
          expanded={!!open.manual}
          onChange={() => toggle("manual")}
          sx={{
            mt: 3,
            border: 1,
            borderColor: "divider",
            borderRadius: 1,
            "&:before": { display: "none" },
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              {manual.length} provision{manual.length === 1 ? "" : "s"} requiring
              manual review
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Typography variant="caption" color="text.secondary">
              The current evidence model does not automatically assess these
              sections.
            </Typography>
            <Stack spacing={0.75} sx={{ mt: 1 }}>
              {manual.map((item) => (
                <Typography key={item.section} variant="body2">
                  <strong>
                    Section {item.section} — {item.title}.
                  </strong>{" "}
                  {item.reason}
                </Typography>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {sources.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Primary sources
          </Typography>
          <Stack spacing={0.75} sx={{ mt: 0.75 }}>
            {sources.map((source) => (
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
    </>
  );
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
  const theme = useTheme();
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

          {/* The engine states every reason for a pair in one paragraph ending
              each clause with an unlabelled "[weight 0.66]". Read as a table
              cell that is a wall of text, and the bracketed number explains
              nothing on its own. The same reasons arrive structured, so they
              are laid out as rows and the arithmetic is stated once here. */}
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 1.5 }}>
            Each reason below is worth <strong>points</strong> — how identifying
            that kind of match is, multiplied by how rare the shared values are
            across all evidence held. The points add up to the pair&rsquo;s{" "}
            <strong>weight</strong>, and the confidence is that weight on a
            saturating scale: several independent reasons push confidence up,
            while no single one reaches certainty on its own.
          </Typography>

          <Table size="small" sx={{ mt: 1.5 }}>
            <TableHead>
              <TableRow>
                <TableCell>Items</TableCell>
                <TableCell>Strength</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Why They Are Linked</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report.connections.map((row) => (
                <TableRow key={row.pair}>
                  <TableCell sx={{ fontFamily: MONO, whiteSpace: "nowrap", verticalAlign: "top" }}>
                    {row.pair}
                  </TableCell>
                  <TableCell sx={{ verticalAlign: "top" }}>
                    <Chip size="small" label={row.strength} variant="outlined" />
                  </TableCell>
                  <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {row.confidence}
                    </Typography>
                    {row.weight !== null && (
                      <Typography variant="caption" color="text.secondary">
                        from weight {row.weight.toFixed(2)}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ verticalAlign: "top" }}>
                    <Typography variant="body2" sx={{ mb: row.factors.length ? 1 : 0 }}>
                      {row.meaning}
                    </Typography>
                    {row.factors.length > 0 ? (
                      <Stack spacing={0.75}>
                        {/* Strongest first: the factor that actually carried
                            the pair should not be buried behind the weakest. */}
                        {[...row.factors]
                          .sort((a, b) => b.contribution - a.contribution)
                          .map((factor) => (
                            <Stack
                              key={factor.factor}
                              direction="row"
                              spacing={1}
                              alignItems="baseline"
                            >
                              <Typography
                                variant="caption"
                                sx={{
                                  width: 108,
                                  flexShrink: 0,
                                  fontWeight: 700,
                                  textTransform: "capitalize",
                                }}
                              >
                                {factor.label}
                              </Typography>
                              <Typography
                                variant="caption"
                                sx={{
                                  width: 42,
                                  flexShrink: 0,
                                  fontFamily: MONO,
                                  fontWeight: 700,
                                  color: accent,
                                }}
                              >
                                +{factor.contribution.toFixed(2)}
                              </Typography>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ minWidth: 0, wordBreak: "break-word" }}
                              >
                                {factor.detail}
                              </Typography>
                            </Stack>
                          ))}
                      </Stack>
                    ) : (
                      /* Reports stored before the factors were carried through. */
                      <Typography variant="caption" color="text.secondary">
                        {row.basis}
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
                      ? {
                          bgcolor: accent,
                          // The accent is a light green on dark and a dark
                          // green on light, so the text on it has to invert
                          // with it — a fixed near-black read as 1.3:1 once
                          // the accent went dark.
                          color: theme.palette.mode === "dark" ? "#08130c" : "#ffffff",
                          fontWeight: 700,
                        }
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

      {(report.methodology.length > 0 ||
        report.methodologyScope.objective !== "") && (
        <Section number={next()} title="Methodology">
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            How this report was produced. Every figure in the sections above is
            read back out of the stored outputs named below — none of it is
            written by hand and none of it is free-text generated, so the same
            evidence re-analysed yields the same report.
          </Typography>

          {/* Objective, coverage and reproducibility are stored beside the
              stage list and printed in the PDF; on screen the stages used to
              appear without them, which left the scope of the run unstated. */}
          {report.methodologyScope.objective !== "" && (
            <Table size="small" sx={{ mb: 3 }}>
              <TableBody>
                {[
                  ["What this run set out to do", report.methodologyScope.objective],
                  ["What it covered", report.methodologyScope.evidenceScope],
                  ["Repeatability", report.methodologyScope.reproducibility],
                ]
                  .filter(([, value]) => value !== "")
                  .map(([label, value]) => (
                    <TableRow key={label}>
                      <TableCell
                        sx={{ width: 190, fontWeight: 700, verticalAlign: "top" }}
                      >
                        {label}
                      </TableCell>
                      <TableCell>{value}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          )}

          {report.methodology.length > 0 && (
            <>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                Processing stages, in the order they ran
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Each stage reads the previous stage&rsquo;s stored output, so a
                failure anywhere upstream is visible rather than silently
                filled in.
              </Typography>
              <Table size="small" sx={{ mt: 1.5 }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 40 }}>#</TableCell>
                    <TableCell sx={{ width: "26%" }}>Stage</TableCell>
                    <TableCell>What it did, and where the output is stored</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.methodology.map((line, i) => {
                    const row = splitMethod(line);
                    return (
                      <TableRow key={i}>
                        <TableCell
                          sx={{ fontWeight: 700, color: "text.secondary", verticalAlign: "top" }}
                        >
                          {i + 1}
                        </TableCell>
                        <TableCell sx={{ verticalAlign: "top" }}>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>
                            {row.stage}
                          </Typography>
                          {row.phase !== "" && (
                            <Typography variant="caption" color="text.secondary">
                              {row.phase}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell sx={{ verticalAlign: "top" }}>
                          <Stack spacing={0.5}>
                            {row.steps.map((step, index) => (
                              <Typography key={index} variant="body2">
                                {step}
                              </Typography>
                            ))}
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </Section>
      )}

      {report.legalBasis && (
        <Section number={next()} title="Statutory Basis">
          <StatutoryBasis basis={report.legalBasis} accent={accent} />
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
