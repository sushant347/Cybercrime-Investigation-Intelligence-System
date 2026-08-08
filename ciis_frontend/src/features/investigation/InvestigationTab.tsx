import ScienceIcon from "@mui/icons-material/Science";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
  type Theme,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";

import { investigationApi } from "@/api";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { EmptyState } from "@/components/common/EmptyState";
import { EntityValue } from "@/components/common/EntityValue";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { MetricLabel } from "@/components/common/MetricLabel";
import { ScoreComponents } from "@/components/common/ScoreComponents";
import { StatusChip } from "@/components/common/StatusChip";
import { TablePanel, type FilterOption } from "@/components/common/TablePanel";
import { formatDateTime } from "@/lib/format";
import { BRAND, severityColor } from "@/theme/theme";

/** Strength buckets, ordered strongest-first for the filter row. */
const STRENGTH_ORDER = ["very_strong", "strong", "medium", "weak"];

const strengthRank = (value: string | undefined) => {
  const i = STRENGTH_ORDER.indexOf((value ?? "").toLowerCase());
  return i === -1 ? STRENGTH_ORDER.length : i;
};

/** Build clickable filter chips from an engine-supplied distribution map. */
function strengthFilters(
  distribution: Record<string, number>,
  theme: Theme,
): FilterOption[] {
  return Object.entries(distribution)
    .sort((a, b) => strengthRank(a[0]) - strengthRank(b[0]))
    .map(([strength, count]) => ({
      label: strength.replace(/_/g, " "),
      value: strength.toLowerCase(),
      count,
      color: severityColor(strength.replace(/_/g, " ").split(" ").pop(), theme),
    }));
}

/** Specificity reads as a colour-graded figure everywhere it appears. */
function Specificity({ value, reason }: { value: number | null; reason?: string }) {
  if (value === null) return <>—</>;
  return (
    <Tooltip title={reason ?? ""}>
      <Box
        component="span"
        sx={{
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          color:
            value >= 0.7 ? BRAND.low : value >= 0.4 ? BRAND.high : BRAND.critical,
        }}
      >
        {value.toFixed(2)}
      </Box>
    </Tooltip>
  );
}

/**
 * Module 5 - Investigation View.
 *
 * Correlations, campaigns, and suspects exactly as the Phase-2 engine stored
 * them. Every explanation string is engine output, never rewritten — this
 * component only decides how it is laid out.
 *
 * Presentation is table-first rather than a stack of accordions: on a case
 * with 36 pairs and 13 suspects the accordion version ran to roughly fifty
 * full-width cards, which could not be compared and could not be searched.
 * See `TablePanel` for the reasoning.
 */
export function InvestigationTab({ caseId }: { caseId: string }) {
  const theme = useTheme();

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
        <CardContent>
          {!corr ? (
            <Typography variant="body2" color="text.secondary">
              Correlation analysis has not been generated.
            </Typography>
          ) : (
            <TablePanel
              rows={corr.pairs}
              getKey={(p) => `${p.evidence_a}-${p.evidence_b}`}
              emptyMessage="The engine found no correlated evidence pairs in this case."
              searchOf={(p) => `${p.evidence_a} ${p.evidence_b} ${p.explanation}`}
              searchPlaceholder="Find an evidence id…"
              filters={{
                options: strengthFilters(corr.strength_distribution, theme),
                bucketOf: (p) => (p.relationship_strength ?? "").toLowerCase(),
              }}
              initialSort={{ id: "confidence", dir: "desc" }}
              columns={[
                {
                  id: "pair",
                  label: "Evidence pair",
                  width: "34%",
                  sortValue: (p) => p.evidence_a,
                  render: (p) => (
                    <Stack direction="row" spacing={0.75} alignItems="center">
                      <EntityValue value={p.evidence_a} />
                      <Typography component="span" color="text.disabled">
                        ↔
                      </Typography>
                      <EntityValue value={p.evidence_b} />
                    </Stack>
                  ),
                },
                {
                  id: "strength",
                  label: <MetricLabel name="relationship_strength" label="Strength" />,
                  width: "18%",
                  sortValue: (p) => -strengthRank(p.relationship_strength),
                  render: (p) => <StatusChip value={p.relationship_strength} />,
                },
                {
                  id: "confidence",
                  label: <MetricLabel name="correlation_confidence" label="Confidence" />,
                  width: "22%",
                  sortValue: (p) => p.correlation_confidence,
                  render: (p) => (
                    <ConfidenceBar
                      value={p.correlation_confidence}
                      scale="fraction"
                      label="Correlation confidence"
                    />
                  ),
                },
                {
                  id: "why",
                  label: "Why they are linked",
                  width: "26%",
                  render: (p) => (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {p.correlation_reasons[0] ?? p.explanation}
                    </Typography>
                  ),
                },
              ]}
              renderDetail={(pair) => (
                <Stack spacing={1.5}>
                  <Typography variant="body2">{pair.explanation}</Typography>
                  {pair.correlation_reasons.length > 0 && (
                    <Stack spacing={0.5}>
                      {pair.correlation_reasons.map((reason, i) => (
                        <Typography key={i} variant="body2" color="text.secondary">
                          • {reason}
                        </Typography>
                      ))}
                    </Stack>
                  )}
                  {pair.factors.length > 0 && (
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Factor</TableCell>
                          <TableCell>Matches</TableCell>
                          <TableCell>Weight</TableCell>
                          <TableCell>
                            <MetricLabel name="specificity" label="Specificity" />
                          </TableCell>
                          <TableCell>
                            <MetricLabel name="contribution" label="Contribution" />
                          </TableCell>
                          <TableCell>Reason</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {pair.factors.map((factor) => {
                          const details = factor.value_details ?? [];
                          // Mean specificity of the values actually counted;
                          // non-entity factors (hash, proximity) have none.
                          const specificity = details.length
                            ? details.reduce((sum, d) => sum + d.specificity, 0) /
                              details.length
                            : null;
                          return (
                            <TableRow key={factor.factor}>
                              <TableCell sx={{ textTransform: "capitalize" }}>
                                {factor.factor.replace(/_/g, " ")}
                              </TableCell>
                              <TableCell>{factor.matches}</TableCell>
                              <TableCell>{factor.weight}</TableCell>
                              <TableCell>
                                <Specificity
                                  value={specificity}
                                  reason={details.map((d) => d.reason).join(" · ")}
                                />
                              </TableCell>
                              <TableCell>{factor.contribution.toFixed(2)}</TableCell>
                              <TableCell>{factor.reason}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </Stack>
              )}
            />
          )}
        </CardContent>
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
          ) : (
            <TablePanel
              rows={cross.links}
              getKey={(l) => l.other_case_id}
              emptyMessage="This case shares no entities with any other case in the engine."
              searchOf={(l) => `${l.other_case_id} ${l.match_reason}`}
              searchPlaceholder="Find a case…"
              initialSort={{ id: "confidence", dir: "desc" }}
              columns={[
                {
                  id: "case",
                  label: "Case",
                  width: "28%",
                  sortValue: (l) => l.other_case_id,
                  render: (l) => <EntityValue value={l.other_case_id} type="case" />,
                },
                {
                  id: "strength",
                  label: <MetricLabel name="relationship_strength" label="Strength" />,
                  width: "18%",
                  sortValue: (l) => -strengthRank(l.relationship_strength),
                  render: (l) => <StatusChip value={l.relationship_strength} />,
                },
                {
                  id: "shared",
                  label: "Shared",
                  width: "20%",
                  sortValue: (l) => l.matched_entities.length,
                  render: (l) => (
                    <Chip size="small" label={`${l.matched_entities.length} entity(ies)`} />
                  ),
                },
                {
                  id: "confidence",
                  label: "Match confidence",
                  width: "22%",
                  sortValue: (l) => l.match_confidence,
                  render: (l) => (
                    <ConfidenceBar
                      value={l.match_confidence}
                      scale="fraction"
                      label="Match confidence"
                    />
                  ),
                },
              ]}
              renderDetail={(link) => (
                <Stack spacing={1.5}>
                  <Typography variant="body2">{link.match_reason}</Typography>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Entity</TableCell>
                        <TableCell>Shared value</TableCell>
                        <TableCell>
                          <MetricLabel name="specificity" label="Specificity" />
                        </TableCell>
                        <TableCell>This case</TableCell>
                        <TableCell>{link.other_case_id}</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {link.matched_entities.map((match) => (
                        <TableRow key={`${match.entity_type}-${match.value}`}>
                          <TableCell sx={{ textTransform: "capitalize" }}>
                            {match.entity_type.replace(/_/g, " ")}
                          </TableCell>
                          <TableCell>
                            <EntityValue value={match.value} type={match.entity_type} />
                          </TableCell>
                          <TableCell>
                            <Specificity
                              value={match.specificity ?? 1}
                              reason={match.specificity_reason ?? ""}
                            />
                          </TableCell>
                          <TableCell>{match.this_evidence_ids.join(", ")}</TableCell>
                          <TableCell>{match.other_evidence_ids.join(", ")}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Stack>
              )}
            />
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
          ) : (
            <TablePanel
              rows={camp.campaigns}
              getKey={(c) => c.campaign_id}
              emptyMessage="The engine did not cluster any evidence into campaigns for this case."
              searchOf={(c) => `${c.campaign_id} ${c.summary} ${c.signature.join(" ")}`}
              searchPlaceholder="Find a campaign…"
              initialSort={{ id: "members", dir: "desc" }}
              columns={[
                {
                  id: "campaign",
                  label: "Campaign",
                  width: "30%",
                  sortValue: (c) => c.campaign_id,
                  render: (c) => <EntityValue value={c.campaign_id} />,
                },
                {
                  id: "members",
                  label: "Members",
                  width: "16%",
                  sortValue: (c) => c.members.length,
                  render: (c) => <Chip size="small" label={`${c.members.length} item(s)`} />,
                },
                {
                  id: "signature",
                  label: "Signature",
                  width: "32%",
                  render: (c) => (
                    <Stack direction="row" spacing={0.5} sx={{ overflow: "hidden" }}>
                      {c.signature.slice(0, 2).map((sig) => (
                        <Chip
                          key={sig}
                          size="small"
                          label={sig}
                          color="primary"
                          variant="outlined"
                        />
                      ))}
                      {c.signature.length > 2 && (
                        <Chip size="small" label={`+${c.signature.length - 2}`} variant="outlined" />
                      )}
                    </Stack>
                  ),
                },
                {
                  id: "confidence",
                  label: "Confidence",
                  width: "22%",
                  sortValue: (c) => c.campaign_confidence,
                  render: (c) => (
                    <ConfidenceBar
                      value={c.campaign_confidence}
                      scale="fraction"
                      label="Campaign confidence"
                    />
                  ),
                },
              ]}
              renderDetail={(campaign) => (
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
                          <TableCell>
                            <EntityValue value={member.evidence_id} />
                          </TableCell>
                          <TableCell>
                            {member.membership_explanation || member.link_reasons.join("; ")}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Stack>
              )}
            />
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
          ) : (
            <>
              {susp.methodology && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: "block", mb: 2 }}
                >
                  Methodology (engine): {susp.methodology}
                </Typography>
              )}
              <TablePanel
                rows={susp.suspects}
                getKey={(s) => s.suspect_id}
                emptyMessage="The engine did not identify suspect identities in this case."
                searchOf={(s) => `${s.identity_value} ${s.identity_type} ${s.explanation}`}
                searchPlaceholder="Find an identifier…"
                initialSort={{ id: "confidence", dir: "desc" }}
                filters={{
                  options: [
                    { label: "threat-flagged", value: "flagged", color: BRAND.critical },
                    { label: "not flagged", value: "clean" },
                  ],
                  bucketOf: (s) => (s.threat_flagged ? "flagged" : "clean"),
                }}
                columns={[
                  {
                    id: "identity",
                    label: "Identifier",
                    width: "34%",
                    sortValue: (s) => s.identity_value,
                    render: (s) => (
                      <EntityValue value={s.identity_value} type={s.identity_type} />
                    ),
                  },
                  {
                    id: "type",
                    label: "Type",
                    width: "16%",
                    sortValue: (s) => s.identity_type,
                    render: (s) => (
                      <Chip
                        size="small"
                        label={s.identity_type.replace(/_/g, " ")}
                        variant="outlined"
                        sx={{ textTransform: "capitalize" }}
                      />
                    ),
                  },
                  {
                    id: "risk",
                    label: "Risk",
                    width: "22%",
                    sortValue: (s) => (s.threat_flagged ? 1 : 0),
                    render: (s) => (
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        {s.threat_flagged && (
                          <MetricLabel name="threat_flagged">
                            <StatusChip value="critical" label="threat intel" />
                          </MetricLabel>
                        )}
                        <StatusChip value={s.risk_level || s.confidence_level} />
                      </Stack>
                    ),
                  },
                  {
                    id: "confidence",
                    label: <MetricLabel name="suspect_confidence" label="Confidence" />,
                    width: "22%",
                    sortValue: (s) => s.confidence_score,
                    render: (s) => (
                      <ConfidenceBar
                        value={s.confidence_score}
                        scale="percent"
                        label="Suspect confidence"
                      />
                    ),
                  },
                ]}
                renderDetail={(suspect) => (
                  <Stack spacing={1.5}>
                    <Typography variant="body2">{suspect.explanation}</Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Chip
                        size="small"
                        label={`Relationship: ${suspect.relationship_strength || "—"}`}
                        variant="outlined"
                      />
                      <Chip
                        size="small"
                        label={`Evidence: ${suspect.evidence_count}`}
                        variant="outlined"
                      />
                      {suspect.aliases.map((alias) => (
                        <Chip key={alias} size="small" label={`alias: ${alias}`} />
                      ))}
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      First seen {formatDateTime(suspect.first_seen)} · last seen{" "}
                      {formatDateTime(suspect.last_seen)} · appears in:{" "}
                      {suspect.evidence_ids.join(", ")}
                    </Typography>
                    {suspect.components.length > 0 && (
                      <Box sx={{ maxWidth: 560 }}>
                        <ScoreComponents
                          components={suspect.components}
                          total={suspect.confidence_score}
                        />
                      </Box>
                    )}
                  </Stack>
                )}
              />
            </>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
