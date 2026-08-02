import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import TimelineIcon from "@mui/icons-material/Timeline";
import {
  Box,
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
import { useEffect, useMemo, useRef, useState } from "react";

import { investigationApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { SearchField } from "@/components/common/SearchField";
import { formatDateTime, titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

import { TimelineChart } from "./TimelineChart";
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
  const listRef = useRef<HTMLDivElement>(null);

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

  // Selecting a marker in the chart opens that event's row further down the
  // page, which is off-screen on a long case — bring it into view.
  useEffect(() => {
    if (!selected) return;
    const index = filtered.indexOf(selected);
    if (index < 0) return;
    listRef.current
      ?.querySelector(`[data-event-index="${index}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selected, filtered]);

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
      {timeline.summary && (
        <Card>
          <CardContent>
            <Typography variant="body1">{timeline.summary}</Typography>
            {timeline.stage_progression.length > 0 && (
              <Box sx={{ mt: 2 }}>
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
            title="Attack Stages"
            subheader="Each stage the engine detected, when it ran, and what it was based on"
          />
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
                      {formatDateTime(stage.first_seen)} → {formatDateTime(stage.last_seen)}
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
        </Card>
      )}

      <Card>
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

        {/* Swimlane chart of the filtered events */}
        <TimelineChart
          events={filtered}
          milestoneKeys={milestoneKeys}
          selected={selected}
          onSelect={setSelected}
        />
        <Divider />

        <Box ref={listRef} sx={{ p: 2 }}>
          {filtered.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
              No events match the current filters.
            </Typography>
          ) : (
            filtered.map((event, i) => {
              const isMilestone = milestoneKeys.has(`${event.timestamp}|${event.description}`);
              const isOpen = selected === event;
              const dotColor = event.critical
                ? BRAND.critical
                : isMilestone
                  ? BRAND.high
                  : BRAND.primary;
              return (
                <Stack
                  key={`${event.timestamp}-${i}`}
                  direction="row"
                  spacing={2}
                  data-event-index={i}
                >
                  {/* Continuous rail: the line stretches through the expanded
                      detail too, so the thread of the timeline is never cut. */}
                  <Stack alignItems="center" sx={{ minWidth: 14 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        mt: 1.5,
                        flexShrink: 0,
                        bgcolor: dotColor,
                        boxShadow: event.critical ? `0 0 8px ${BRAND.critical}` : undefined,
                      }}
                    />
                    {i < filtered.length - 1 && (
                      <Box sx={{ flex: 1, width: "2px", bgcolor: "divider", mt: 0.5 }} />
                    )}
                  </Stack>

                  <Box sx={{ minWidth: 0, flex: 1, pb: 1 }}>
                    <Stack
                      direction="row"
                      spacing={1}
                      alignItems="flex-start"
                      onClick={() => setSelected(isOpen ? null : event)}
                      role="button"
                      tabIndex={0}
                      aria-expanded={isOpen}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelected(isOpen ? null : event);
                        }
                      }}
                      sx={{
                        cursor: "pointer",
                        py: 1.25,
                        px: 1,
                        borderRadius: 2,
                        "&:hover": { bgcolor: "action.hover" },
                        bgcolor: isOpen ? "action.selected" : undefined,
                      }}
                    >
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          {event.timestamp ? formatDateTime(event.timestamp) : "Timestamp unresolved"} · {titleCase(event.event_type)}
                          {event.evidence_id ? ` · ${event.evidence_id}` : ""}
                        </Typography>
                        <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>
                          {event.description}
                        </Typography>
                        <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                          {event.critical && (
                            <Tooltip title={event.critical_reasons.join("; ")}>
                              <Chip size="small" label="CRITICAL" sx={{ bgcolor: `${BRAND.critical}22`, color: BRAND.critical, fontWeight: 700 }} />
                            </Tooltip>
                          )}
                          <Chip
                            size="small"
                            label={`${titleCase(event.time_source ?? "legacy upload time")} · ${event.confidence ?? "unknown"}`}
                            color={event.timestamp_inferred ? "warning" : "default"}
                            variant="outlined"
                          />
                          {isMilestone && <Chip size="small" label="Milestone" variant="outlined" />}
                          {event.stages.map((stage, n) => (
                            <Chip
                              key={stage}
                              size="small"
                              label={stageMeta(stage, n).label}
                              variant="outlined"
                              sx={{ borderColor: `${stageMeta(stage, n).color}80` }}
                            />
                          ))}
                        </Stack>
                      </Box>
                      <ExpandMoreIcon
                        fontSize="small"
                        sx={{
                          mt: 0.5,
                          flexShrink: 0,
                          color: "text.secondary",
                          transition: "transform 180ms ease",
                          transform: isOpen ? "rotate(180deg)" : "none",
                        }}
                      />
                    </Stack>

                    {/* Details open downward, underneath the event they belong
                        to, rather than in a side panel the reader has to look
                        across to and mentally pair up. */}
                    <Collapse in={isOpen} unmountOnExit>
                      <EventDetail event={event} />
                    </Collapse>
                  </Box>
                </Stack>
              );
            })
          )}
        </Box>
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
