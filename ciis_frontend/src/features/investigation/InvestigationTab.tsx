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
import { EntityChip, entityTypeLabel } from "@/components/common/EntityChip";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";
import type { SuspectProfile } from "@/types";
import { CorrelationTable } from "./CorrelationTable";
import { BRAND } from "@/theme/theme";

/**
 * Every suspect anchor in the case, grouped by identifier family.
 *
 * The assessment below is one accordion per suspect, so the question an
 * investigator actually opens this card to answer — *what kinds of identity is
 * this case built on?* — required expanding every row to find out. This strip
 * answers it before anything is expanded, and flags the threat-intelligence
 * hits in the same glance.
 */
function CapturedIdentities({ suspects }: { suspects: SuspectProfile[] }) {
  const byType = new Map<string, SuspectProfile[]>();
  for (const suspect of suspects) {
    const bucket = byType.get(suspect.identity_type) ?? [];
    bucket.push(suspect);
    byType.set(suspect.identity_type, bucket);
  }
  const flaggedCount = suspects.filter((s) => s.threat_flagged).length;

  return (
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
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1.5 }}
      >
        <Typography variant="overline" color="text.secondary">
          Identities captured
        </Typography>
        <Chip
          size="small"
          label={`${suspects.length} total`}
          sx={{ height: 20, fontWeight: 700 }}
        />
        {flaggedCount > 0 && (
          <StatusChip value="critical" label={`${flaggedCount} threat-flagged`} />
        )}
      </Stack>

      <Stack spacing={1.25}>
        {[...byType.entries()].map(([type, group]) => (
          <Stack
            key={type}
            direction={{ xs: "column", sm: "row" }}
            spacing={1}
            alignItems={{ xs: "flex-start", sm: "center" }}
          >
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ minWidth: 120, fontWeight: 600 }}
            >
              {entityTypeLabel(type)} ({group.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ minWidth: 0 }}>
              {group.map((suspect) => (
                <EntityChip
                  key={suspect.suspect_id}
                  entityType={suspect.identity_type}
                  value={suspect.identity_value}
                  size="small"
                  flagged={suspect.threat_flagged}
                  title={
                    `${entityTypeLabel(suspect.identity_type)}: ${suspect.identity_value}` +
                    ` — ${suspect.confidence_score.toFixed(0)}% confidence` +
                    ` across ${suspect.evidence_count} evidence item(s)` +
                    (suspect.threat_flagged ? " · flagged by threat intelligence" : "")
                  }
                />
              ))}
            </Stack>
          </Stack>
        ))}
      </Stack>
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
              <CapturedIdentities suspects={susp.suspects} />
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
