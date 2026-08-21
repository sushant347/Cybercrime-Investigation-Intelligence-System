import ScienceIcon from "@mui/icons-material/Science";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Collapse,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { investigationApi } from "@/api";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { EntityChip } from "@/components/common/EntityChip";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";
import { CorrelationTable } from "./CorrelationTable";
import { BRAND } from "@/theme/theme";

/**
 * The engine's own paragraph for a suspect, folded away by default.
 *
 * It restates the whole component table in prose, so it is redundant with what
 * is on screen — but it is the engine's verbatim output and the record of what
 * the assessment said, so it is kept one click away rather than dropped.
 */
function SuspectSentence({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <Box>
      <Typography
        component="button"
        type="button"
        variant="caption"
        onClick={() => setOpen((v) => !v)}
        sx={{
          background: "none",
          border: 0,
          p: 0,
          cursor: "pointer",
          color: "text.secondary",
          textDecoration: "underline",
          font: "inherit",
        }}
      >
        {open ? "Hide" : "Show"} the engine&rsquo;s full sentence
      </Typography>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {text}
        </Typography>
      </Collapse>
    </Box>
  );
}

/**
 * Module 5 - Investigation View.
 * Correlations, campaigns, and suspects exactly as the Phase-2 engine
 * stored them. Every explanation string is engine output, never rewritten.
 */
export function InvestigationTab({ caseId }: { caseId: string }) {
  const correlation = useQuery({
    queryKey: ["artifact", caseId, "correlation"],
    queryFn: () => investigationApi.correlation(caseId),
    retry: false,
  });
  const crossCase = useQuery({
    queryKey: ["artifact", caseId, "cross_case"],
    queryFn: () => investigationApi.crossCase(caseId),
    retry: false,
  });
  const campaigns = useQuery({
    queryKey: ["artifact", caseId, "campaigns"],
    queryFn: () => investigationApi.campaigns(caseId),
    retry: false,
  });
  const suspects = useQuery({
    queryKey: ["artifact", caseId, "suspects"],
    queryFn: () => investigationApi.suspects(caseId),
    retry: false,
  });

  if (
    correlation.isPending ||
    crossCase.isPending ||
    campaigns.isPending ||
    suspects.isPending
  ) {
    return <DetailSkeleton />;
  }

  const nothing = !correlation.data && !campaigns.data && !suspects.data;
  if (nothing) {
    return (
      <EmptyState
        icon={<ScienceIcon />}
        title="No investigation artifacts yet"
        description='Phase-2 analysis has not been run for this case. Use "Run Analysis" above — correlation, campaigns, suspects, timeline, analytics, priority, and the report are generated in one pass.'
      />
    );
  }

  const corr = correlation.data?.report;
  const cross = crossCase.data?.report;
  const camp = campaigns.data?.report;
  const susp = suspects.data?.report;

  return (
    <Stack spacing={2}>
      {/* ------------------------------------------------ Correlation */}
      <Card>
        <CardHeader
          title="Evidence Correlation"
          subheader={
            corr
              ? `${corr.related_pair_count} related pair(s) of ${corr.pair_count} examined · strongest: ${corr.strongest_pair || "—"} · generated ${formatDateTime(correlation.data?.generated_at)}`
              : "Not generated"
          }
        />
        <Divider />
        {!corr ? (
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              Correlation analysis has not been generated.
            </Typography>
          </CardContent>
        ) : corr.pairs.length === 0 ? (
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              The engine found no correlated evidence pairs in this case.
            </Typography>
          </CardContent>
        ) : (
          <CardContent>
            <CorrelationTable
              pairs={corr.pairs}
              strengthDistribution={corr.strength_distribution}
            />
          </CardContent>
        )}
      </Card>

      {/* ------------------------------------------------ Cross-case */}
      <Card>
        <CardHeader
          title="Cross-Case Correlation"
          subheader={
            cross
              ? `${cross.link_count} linked case(s)${cross.related_case_ids.length ? ` · ${cross.related_case_ids.join(", ")}` : ""} · generated ${formatDateTime(crossCase.data?.generated_at)}`
              : "Not generated"
          }
        />
        <Divider />
        <CardContent>
          {!cross ? (
            <Typography variant="body2" color="text.secondary">
              Cross-case correlation has not been generated.
            </Typography>
          ) : cross.links.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              This case shares no entities with any other case in the engine.
            </Typography>
          ) : (
            cross.links.map((link) => (
              <Accordion key={link.other_case_id} disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Stack
                    direction="row"
                    spacing={2}
                    alignItems="center"
                    sx={{ flex: 1, minWidth: 0 }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 700 }}
                    >
                      {link.other_case_id}
                    </Typography>
                    <StatusChip value={link.relationship_strength} />
                    <Chip size="small" label={`${link.matched_entities.length} shared entity(ies)`} />
                    <ConfidenceBar
                      value={link.match_confidence}
                      scale="fraction"
                      label="Match confidence"
                    />
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1.5}>
                    <Typography variant="body2">{link.match_reason}</Typography>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Entity</TableCell>
                          <TableCell>Shared value</TableCell>
                          <Tooltip title="How identifying this value is across every case. A low figure means it is common everywhere, so it barely supports the link.">
                            <TableCell>Specificity</TableCell>
                          </Tooltip>
                          <TableCell>This case</TableCell>
                          <TableCell>{link.other_case_id}</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {link.matched_entities.map((match) => {
                          const specificity = match.specificity ?? 1;
                          return (
                            <TableRow key={`${match.entity_type}-${match.value}`}>
                              <TableCell sx={{ textTransform: "capitalize" }}>
                                {match.entity_type.replace(/_/g, " ")}
                              </TableCell>
                              <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                                {match.value}
                              </TableCell>
                              <TableCell>
                                <Tooltip title={match.specificity_reason ?? ""}>
                                  <Box
                                    component="span"
                                    sx={{
                                      fontWeight: 700,
                                      color:
                                        specificity >= 0.7
                                          ? BRAND.low
                                          : specificity >= 0.4
                                            ? BRAND.high
                                            : BRAND.critical,
                                    }}
                                  >
                                    {specificity.toFixed(2)}
                                  </Box>
                                </Tooltip>
                              </TableCell>
                              <TableCell>{match.this_evidence_ids.join(", ")}</TableCell>
                              <TableCell>{match.other_evidence_ids.join(", ")}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Stack>
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </CardContent>
      </Card>

      {/* -------------------------------------------------- Campaigns */}
      <Card>
        <CardHeader
          title="Scam Campaign Detection"
          subheader={
            camp
              ? `${camp.campaign_count} campaign(s) detected · ${camp.unclustered_evidence.length} unclustered item(s)`
              : "Not generated"
          }
        />
        <Divider />
        <CardContent>
          {!camp ? (
            <Typography variant="body2" color="text.secondary">
              Campaign analysis has not been generated.
            </Typography>
          ) : camp.campaigns.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              The engine did not cluster any evidence into campaigns for this case.
            </Typography>
          ) : (
            camp.campaigns.map((campaign) => (
              <Accordion key={campaign.campaign_id} disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Stack direction="row" spacing={2} alignItems="center" sx={{ flex: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {campaign.campaign_id}
                    </Typography>
                    <Chip size="small" label={`${campaign.members.length} member(s)`} />
                    <ConfidenceBar
                      value={campaign.campaign_confidence}
                      scale="fraction"
                      label="Campaign confidence"
                    />
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1.5}>
                    {campaign.summary && <Typography variant="body2">{campaign.summary}</Typography>}
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      {campaign.signature.map((sig) => (
                        <Chip key={sig} size="small" label={sig} color="primary" variant="outlined" />
                      ))}
                      {campaign.shared_brands.map((brand) => (
                        <Chip key={brand} size="small" label={`brand: ${brand}`} variant="outlined" />
                      ))}
                      {campaign.shared_domains.map((domain) => (
                        <Chip key={domain} size="small" label={`domain: ${domain}`} variant="outlined" />
                      ))}
                    </Stack>
                    {(campaign.timeline_start || campaign.timeline_end) && (
                      <Typography variant="caption" color="text.secondary">
                        Active {formatDateTime(campaign.timeline_start)} —{" "}
                        {formatDateTime(campaign.timeline_end)}
                      </Typography>
                    )}
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Evidence</TableCell>
                          <TableCell>Membership explanation</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {campaign.memberships.map((member) => (
                          <TableRow key={member.evidence_id}>
                            <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                              {member.evidence_id}
                            </TableCell>
                            <TableCell>
                              {member.membership_explanation || member.link_reasons.join("; ")}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Stack>
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </CardContent>
      </Card>

      {/* --------------------------------------------------- Suspects */}
      <Card>
        <CardHeader
          title="Suspect Confidence Assessment"
          subheader={
            susp
              ? `${susp.suspect_count} suspect identity(ies) · top: ${susp.top_suspect || "—"}`
              : "Not generated"
          }
        />
        <Divider />
        <CardContent>
          {!susp ? (
            <Typography variant="body2" color="text.secondary">
              Suspect assessment has not been generated.
            </Typography>
          ) : susp.suspects.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              The engine did not identify suspect identities in this case.
            </Typography>
          ) : (
            <>
              {susp.methodology && (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 2 }}>
                  How these are scored: {susp.methodology}
                </Typography>
              )}
              {susp.suspects.map((suspect) => (
                <Accordion key={suspect.suspect_id} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Stack
                      direction="row"
                      spacing={2}
                      alignItems="center"
                      sx={{ flex: 1, minWidth: 0 }}
                    >
                      <EntityChip
                        entityType={suspect.identity_type}
                        value={suspect.identity_value}
                        flagged={suspect.threat_flagged}
                      />
                      {suspect.threat_flagged && <StatusChip value="critical" label="threat intel" />}
                      <StatusChip value={suspect.risk_level || suspect.confidence_level} />
                      <ConfidenceBar
                        value={suspect.confidence_score}
                        scale="percent"
                        label="Suspect confidence"
                      />
                    </Stack>
                  </AccordionSummary>
                  <AccordionDetails>
                    {/* The engine's `explanation` is a paragraph that restates
                        every component — name, score, weight and reasoning —
                        which the table below already lays out in columns, and
                        the Explanation column was `noWrap`-truncated so the
                        one readable copy was the one behind a tooltip. The
                        table now carries the reasoning in full and closes on
                        the arithmetic; the paragraph is kept verbatim behind a
                        disclosure. */}
                    <Stack spacing={2}>
                      <Stack
                        direction="row"
                        spacing={1}
                        flexWrap="wrap"
                        useFlexGap
                        alignItems="center"
                      >
                        <Chip
                          size="small"
                          label={`Seen in ${suspect.evidence_count} item(s): ${suspect.evidence_ids.join(", ")}`}
                          variant="outlined"
                        />
                        <Chip
                          size="small"
                          label={`Links to its other evidence: ${(suspect.relationship_strength || "—").replace(/_/g, " ")}`}
                          variant="outlined"
                        />
                      </Stack>

                      <Typography variant="caption" color="text.secondary">
                        First seen {formatDateTime(suspect.first_seen)} · last seen{" "}
                        {formatDateTime(suspect.last_seen)}
                      </Typography>

                      {suspect.aliases.length > 0 && (
                        <Box>
                          <Typography variant="overline" color="text.secondary">
                            Appears alongside
                          </Typography>
                          <Stack
                            direction="row"
                            spacing={0.5}
                            flexWrap="wrap"
                            useFlexGap
                            sx={{ mt: 0.5 }}
                          >
                            {suspect.aliases.map((alias) => {
                              const [type = "", ...rest] = alias.split(":");
                              const value = rest.join(":");
                              return value ? (
                                <EntityChip
                                  key={alias}
                                  entityType={type}
                                  value={value}
                                  size="small"
                                />
                              ) : (
                                <Chip key={alias} size="small" label={alias} />
                              );
                            })}
                          </Stack>
                        </Box>
                      )}

                      {suspect.components.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Each component is scored 0&ndash;100 and multiplied by
                            its weight; the results add up to the{" "}
                            {suspect.confidence_score.toFixed(1)} confidence above.
                          </Typography>
                        <Table size="small" sx={{ mt: 1 }}>
                          <TableHead>
                            <TableRow>
                              <TableCell>Component</TableCell>
                              <TableCell>What the engine found</TableCell>
                              <TableCell align="right">Score</TableCell>
                              <TableCell align="right">Weight</TableCell>
                              <TableCell align="right">Adds</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {[...suspect.components]
                              .sort(
                                (a, b) =>
                                  b.score * b.weight - a.score * a.weight,
                              )
                              .map((component) => (
                              <TableRow key={component.name}>
                                <TableCell
                                  sx={{
                                    textTransform: "capitalize",
                                    fontWeight: 700,
                                    verticalAlign: "top",
                                  }}
                                >
                                  {component.name.replace(/_/g, " ")}
                                </TableCell>
                                <TableCell sx={{ verticalAlign: "top", wordBreak: "break-word" }}>
                                  {component.explanation}
                                </TableCell>
                                <TableCell align="right" sx={{ verticalAlign: "top" }}>
                                  {component.score.toFixed(1)}
                                </TableCell>
                                <TableCell align="right" sx={{ verticalAlign: "top" }}>
                                  {component.weight.toFixed(2)}
                                </TableCell>
                                <TableCell
                                  align="right"
                                  sx={{
                                    verticalAlign: "top",
                                    fontWeight: 700,
                                    fontFamily: '"JetBrains Mono", monospace',
                                  }}
                                >
                                  {(component.score * component.weight).toFixed(1)}
                                </TableCell>
                              </TableRow>
                            ))}
                            <TableRow>
                              <TableCell
                                colSpan={4}
                                align="right"
                                sx={{ fontWeight: 700, borderBottom: 0 }}
                              >
                                Confidence score
                              </TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  fontWeight: 700,
                                  borderBottom: 0,
                                  fontFamily: '"JetBrains Mono", monospace',
                                }}
                              >
                                {suspect.confidence_score.toFixed(1)}
                              </TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                        </Box>
                      )}

                      <SuspectSentence text={suspect.explanation} />
                    </Stack>
                  </AccordionDetails>
                </Accordion>
              ))}
            </>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
