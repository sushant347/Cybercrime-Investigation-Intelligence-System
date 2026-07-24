import ScienceIcon from "@mui/icons-material/Science";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useQuery } from "@tanstack/react-query";

import { investigationApi } from "@/api";
import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";

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
            <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
              {Object.entries(corr.strength_distribution).map(([strength, count]) => (
                <Chip
                  key={strength}
                  size="small"
                  label={`${strength}: ${count}`}
                  variant="outlined"
                  sx={{ textTransform: "capitalize" }}
                />
              ))}
            </Stack>
            {corr.pairs.map((pair) => (
              <Accordion key={`${pair.evidence_a}-${pair.evidence_b}`} disableGutters>
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
                      {pair.evidence_a} ↔ {pair.evidence_b}
                    </Typography>
                    <StatusChip value={pair.relationship_strength} />
                    <ConfidenceBar
                      value={pair.correlation_confidence}
                      scale="fraction"
                      label="Correlation confidence"
                    />
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
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
                            <TableCell>Contribution</TableCell>
                            <TableCell>Reason</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {pair.factors.map((factor) => (
                            <TableRow key={factor.factor}>
                              <TableCell sx={{ textTransform: "capitalize" }}>
                                {factor.factor.replace(/_/g, " ")}
                              </TableCell>
                              <TableCell>{factor.matches}</TableCell>
                              <TableCell>{factor.weight}</TableCell>
                              <TableCell>{factor.contribution.toFixed(2)}</TableCell>
                              <TableCell>{factor.reason}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            ))}
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
                            <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                              {match.value}
                            </TableCell>
                            <TableCell>{match.this_evidence_ids.join(", ")}</TableCell>
                            <TableCell>{match.other_evidence_ids.join(", ")}</TableCell>
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
                  Methodology (engine): {susp.methodology}
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
                      <Typography
                        variant="body2"
                        sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 700 }}
                        noWrap
                      >
                        {suspect.identity_value}
                      </Typography>
                      <Chip size="small" label={suspect.identity_type} variant="outlined" />
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
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Score component</TableCell>
                              <TableCell>Score</TableCell>
                              <TableCell>Weight</TableCell>
                              <TableCell>Explanation</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {suspect.components.map((component) => (
                              <TableRow key={component.name}>
                                <TableCell sx={{ textTransform: "capitalize" }}>
                                  {component.name.replace(/_/g, " ")}
                                </TableCell>
                                <TableCell>{component.score.toFixed(1)}</TableCell>
                                <TableCell>{component.weight.toFixed(2)}</TableCell>
                                <TableCell>
                                  <Tooltip title={component.explanation}>
                                    <Typography variant="body2" noWrap sx={{ maxWidth: 360 }}>
                                      {component.explanation}
                                    </Typography>
                                  </Tooltip>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      )}
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
