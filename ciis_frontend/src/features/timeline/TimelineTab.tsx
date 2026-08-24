import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import TimelineIcon from "@mui/icons-material/Timeline";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Collapse,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { useMemo, useState } from "react";

import { investigationApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { SearchField } from "@/components/common/SearchField";
import { formatDateTime, titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

import { TimelineChart } from "./TimelineChart";
import { isGeneratedDescription } from "./eventText";
import { stageMeta } from "./stages";

/**
 * Module 7 - Interactive investigation timeline.
 * All events, stages, milestones and critical flags come from the engine's
 * timeline_analysis artifact; the UI only filters and displays.
 */
export function TimelineTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);
  const [showStageAnalysis, setShowStageAnalysis] = useState(false);

  const { data, isPending } = useQuery({
    queryKey: ["artifact", caseId, "timeline"],
    queryFn: () => investigationApi.timeline(caseId),
    retry: false,
  });

  const timeline = data?.report;

  const filtered = useMemo(() => {
    if (!timeline) return [];
    const q = search.trim().toLowerCase();
    return timeline.events.filter((event) => {
      if (criticalOnly && !event.critical) return false;
      if (dateFrom && dayjs(event.timestamp).isBefore(dayjs(dateFrom))) return false;
      if (dateTo && dayjs(event.timestamp).isAfter(dayjs(dateTo).endOf("day"))) return false;
      if (
        q &&
        !event.description.toLowerCase().includes(q) &&
        !event.evidence_id.toLowerCase().includes(q) &&
        !event.stages.some((s) => s.toLowerCase().includes(q))
      ) {
        return false;
      }
      return true;
    });
  }, [timeline, search, dateFrom, dateTo, criticalOnly]);

  const milestoneKeys = useMemo(
    () =>
      new Set(
        (timeline?.milestones ?? []).map((m) => `${m.timestamp}|${m.description}`),
      ),
    [timeline],
  );

  if (isPending) return <DetailSkeleton />;
  if (!timeline) {
    return (
      <EmptyState
        icon={<TimelineIcon />}
        title="Timeline not generated"
        description="Run the investigation analysis to reconstruct the attack timeline, stages, and milestones for this case."
      />
    );
  }

  return (
    <Stack spacing={2}>
      {(timeline.summary || timeline.stage_progression.length > 0) && (
        <Card>
          <CardHeader
            title="Investigation overview"
            subheader="What the engine reconstructed before reviewing individual findings"
          />
          <Divider />
          <CardContent>
            {timeline.summary && (
              <Typography variant="body2" color="text.secondary">
                {timeline.summary}
              </Typography>
            )}
            {timeline.stage_progression.length > 0 && (
              <Box sx={{ mt: timeline.summary ? 2 : 0 }}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    How the attack progressed
                  </Typography>
                  <Chip
                    size="small"
                    label={timeline.progression_consistent ? "Consistent order" : "Out of order"}
                    sx={{
                      height: 20,
                      fontSize: "0.68rem",
                      bgcolor: timeline.progression_consistent ? `${BRAND.low}22` : `${BRAND.high}22`,
                      color: timeline.progression_consistent ? BRAND.low : BRAND.high,
                    }}
                  />
                </Stack>
                {/* Numbered flow: the order the engine reconstructed, read left to right. */}
                <Stack direction="row" alignItems="center" flexWrap="wrap" useFlexGap sx={{ gap: 1 }}>
                  {timeline.stage_progression.map((stage, i) => {
                    const meta = stageMeta(stage, i);
                    return (
                      <Stack key={`${stage}-${i}`} direction="row" spacing={1} alignItems="center">
                        {i > 0 && (
                          <Typography variant="body2" color="text.disabled" aria-hidden>
                            →
                          </Typography>
                        )}
                        <Tooltip title={meta.meaning}>
                          <Chip
                            size="small"
                            label={`${i + 1}. ${meta.label}`}
                            sx={{
                              bgcolor: `${meta.color}1f`,
                              color: meta.color,
                              border: `1px solid ${meta.color}55`,
                            }}
                          />
                        </Tooltip>
                      </Stack>
                    );
                  })}
                </Stack>
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {timeline.attack_stages.length > 0 && (
        <Card>
          <CardHeader
            title="Attack-stage analysis"
            subheader={`${timeline.attack_stages.length} detected stage${timeline.attack_stages.length === 1 ? "" : "s"} · expand for evidence and keyword basis`}
            action={
              <Button
                size="small"
                onClick={() => setShowStageAnalysis((open) => !open)}
                aria-expanded={showStageAnalysis}
                endIcon={
                  <ExpandMoreIcon
                    sx={{
                      transition: "transform 180ms ease",
                      transform: showStageAnalysis ? "rotate(180deg)" : "none",
                    }}
                  />
                }
              >
                {showStageAnalysis ? "Hide analysis" : "Review analysis"}
              </Button>
            }
          />
          <Collapse in={showStageAnalysis} unmountOnExit>
            <Divider />
            <CardContent>
            <Box
              sx={{
                display: "grid",
                gap: 2,
                gridTemplateColumns: {
                  xs: "1fr",
                  sm: "repeat(2, minmax(0, 1fr))",
                  lg: "repeat(3, minmax(0, 1fr))",
                  xl: "repeat(4, minmax(0, 1fr))",
                },
              }}
            >
              {timeline.attack_stages.map((stage, i) => {
                const meta = stageMeta(stage.stage, i);
                return (
                <Card
                  key={stage.stage}
                  variant="outlined"
                  sx={{ display: "flex", flexDirection: "column", minWidth: 0 }}
                >
                  <Box sx={{ height: 4, bgcolor: meta.color }} />
                  <CardContent sx={{ minWidth: 0 }}>
                    <Stack direction="row" spacing={1} alignItems="baseline" sx={{ mb: 0.5 }}>
                      <Typography variant="caption" color="text.disabled" sx={{ fontWeight: 700 }}>
                        {i + 1}
                      </Typography>
                      <Typography variant="subtitle2" noWrap sx={{ flex: 1 }}>
                        {meta.label}
                      </Typography>
                      <Chip
                        size="small"
                        label={`${stage.evidence_ids.length} item${stage.evidence_ids.length === 1 ? "" : "s"}`}
                        variant="outlined"
                        sx={{ height: 20, fontSize: "0.68rem" }}
                      />
                    </Stack>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {meta.meaning}
                    </Typography>
                    <Typography variant="caption" color="text.disabled" display="block" sx={{ mt: 0.5 }}>
                      {stage.first_seen && stage.last_seen ? (
                        <>
                          {formatDateTime(stage.first_seen)} - {formatDateTime(stage.last_seen)}
                        </>
                      ) : (
                        "No evidence-derived event time for this stage"
                      )}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, overflowWrap: "anywhere" }}>
                      {stage.explanation}
                    </Typography>
                    <Stack direction="row" spacing={0.5} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
                      {stage.evidence_ids.map((id) => (
                        <Chip
                          key={id}
                          size="small"
                          label={id}
                          variant="outlined"
                          sx={{ height: 22, fontSize: "0.68rem" }}
                        />
                      ))}
                      {stage.matched_keywords.slice(0, 6).map((kw) => (
                        <Chip
                          key={kw}
                          size="small"
                          label={kw}
                          sx={{ height: 22, fontSize: "0.68rem", bgcolor: `${BRAND.high}22` }}
                        />
                      ))}
                    </Stack>
                  </CardContent>
                </Card>
                );
              })}
            </Box>
            </CardContent>
          </Collapse>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Incident chronology"
          subheader="Evidence-derived events in time order; select a finding to inspect its basis and relationships"
        />
        <Divider />
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          sx={{ p: 2 }}
          alignItems={{ md: "center" }}
        >
          <SearchField
            value={search}
            onSearch={setSearch}
            placeholder="Search events, evidence, stages…"
            sx={{ flex: 1, minWidth: 200 }}
          />
          <TextField
            size="small"
            type="date"
            label="From"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormControlLabel
            control={
              <Switch checked={criticalOnly} onChange={(e) => setCriticalOnly(e.target.checked)} />
            }
            label="Critical only"
          />
        </Stack>
        <Divider />

        {filtered.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 3, textAlign: "center" }}>
            No events match the current filters.
          </Typography>
        ) : (
          <TimelineChart
            events={filtered}
            milestoneKeys={milestoneKeys}
            selected={selected}
            onSelect={(event) =>
              setSelected((current) => current === event ? null : event)
            }
            renderDetails={(event) => <EventDetail event={event} />}
          />
        )}
      </Card>
    </Stack>
  );
}

/** Everything the engine recorded about one event, shown beneath its row. */
function EventDetail({ event }: { event: TimelineEvent }) {
  return (
    <Box
      sx={{
        mt: 0.5,
        mb: 1.5,
        ml: 1,
        p: 2,
        borderRadius: 2,
        border: 1,
        borderColor: "divider",
        bgcolor: "action.hover",
      }}
    >
      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" },
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline" color="text.secondary">
            When
          </Typography>
          <Typography variant="body2">
            {event.timestamp ? formatDateTime(event.timestamp) : "Timestamp unresolved"}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Source: {titleCase(event.time_source ?? "legacy upload time")} ·{" "}
            {event.confidence ?? "unknown"} confidence
            {event.timestamp_inferred ? " · inferred by the engine" : ""}
          </Typography>
        </Box>

        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline" color="text.secondary">
            Evidence
          </Typography>
          <Typography
            variant="body2"
            sx={{ fontFamily: '"JetBrains Mono", monospace', overflowWrap: "anywhere" }}
          >
            {event.evidence_id || "—"}
          </Typography>
          {event.file_name && (
            <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
              {event.file_name}
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ mt: 2 }}>
        <Typography variant="overline" color="text.secondary">
          What happened
        </Typography>
        <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>
          {event.description}
        </Typography>
        {/* The engine writes this line from the evidence id, file name and
            stage list when it has no narrative to give. Saying so is more
            use than letting the reader wonder what they are missing. */}
        {isGeneratedDescription(event) && (
          <Typography variant="caption" color="text.disabled">
            The engine recorded no narrative for this event — the line above is
            assembled from the fields shown here.
          </Typography>
        )}
      </Box>

      {event.stages.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="overline" color="text.secondary">
            Attack stage
          </Typography>
          <Stack spacing={0.75} sx={{ mt: 0.5 }}>
            {event.stages.map((stage, n) => {
              const meta = stageMeta(stage, n);
              return (
                <Stack key={stage} direction="row" spacing={1} alignItems="flex-start">
                  <Box
                    sx={{
                      width: 10, height: 10, borderRadius: "50%", mt: 0.6,
                      bgcolor: meta.color, flexShrink: 0,
                    }}
                  />
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {meta.label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {meta.meaning}
                    </Typography>
                  </Box>
                </Stack>
              );
            })}
          </Stack>
        </Box>
      )}

      {event.critical_reasons.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="overline" sx={{ color: BRAND.critical }}>
            Why this is critical
          </Typography>
          <Stack component="ul" sx={{ m: 0, pl: 2.5 }} spacing={0.25}>
            {event.critical_reasons.map((reason, i) => (
              <Typography key={i} component="li" variant="body2" sx={{ overflowWrap: "anywhere" }}>
                {reason}
              </Typography>
            ))}
          </Stack>
        </Box>
      )}

      {(event.correlated_with?.length ?? 0) > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="overline" color="text.secondary">
            Linked to other evidence
          </Typography>
          <Stack spacing={1} sx={{ mt: 0.5 }}>
            {event.correlated_with?.map((item, i) => (
              <Box key={`${item.linked_to}-${i}`} sx={{ minWidth: 0 }}>
                <Typography
                  variant="body2"
                  sx={{ fontFamily: '"JetBrains Mono", monospace', overflowWrap: "anywhere" }}
                >
                  {item.linked_to}
                  <Typography component="span" variant="caption" color="text.secondary">
                    {" "}· {titleCase(item.type)} · {Math.round((item.confidence ?? 0) * 100)}% confidence
                  </Typography>
                </Typography>
                {item.shared_entities.length > 0 && (
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                    {item.shared_entities.map((entity) => (
                      <Chip
                        key={entity}
                        size="small"
                        label={entity}
                        sx={{ bgcolor: `${BRAND.accent}22`, color: BRAND.accent }}
                      />
                    ))}
                  </Stack>
                )}
              </Box>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
