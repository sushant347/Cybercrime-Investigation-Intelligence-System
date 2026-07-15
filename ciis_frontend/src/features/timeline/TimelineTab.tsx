import TimelineIcon from "@mui/icons-material/Timeline";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
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
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
                <Typography variant="caption" color="text.secondary">
                  Stage progression{timeline.progression_consistent ? " (consistent)" : " (inconsistent)"}:
                </Typography>
                {timeline.stage_progression.map((stage, i) => (
                  <Stack key={`${stage}-${i}`} direction="row" spacing={1} alignItems="center">
                    {i > 0 && <Typography variant="caption">→</Typography>}
                    <Chip size="small" label={titleCase(stage)} color="primary" variant="outlined" />
                  </Stack>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      )}

      {timeline.attack_stages.length > 0 && (
        <Card>
          <CardHeader title="Attack Stages" subheader="Detected by the timeline engine" />
          <Divider />
          <CardContent>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
              {timeline.attack_stages.map((stage) => (
                <Card key={stage.stage} variant="outlined" sx={{ flex: "1 1 240px" }}>
                  <CardContent>
                    <Typography variant="subtitle2" sx={{ textTransform: "capitalize" }}>
                      {titleCase(stage.stage)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {formatDateTime(stage.first_seen)} → {formatDateTime(stage.last_seen)}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {stage.explanation}
                    </Typography>
                    <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                      {stage.evidence_ids.map((id) => (
                        <Chip key={id} size="small" label={id} variant="outlined" />
                      ))}
                      {stage.matched_keywords.slice(0, 6).map((kw) => (
                        <Chip key={kw} size="small" label={kw} sx={{ bgcolor: `${BRAND.high}22` }} />
                      ))}
                    </Stack>
                  </CardContent>
                </Card>
              ))}
            </Stack>
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

        <Stack direction={{ xs: "column", lg: "row" }}>
          <Box sx={{ flex: 1, p: 2, maxHeight: 600, overflow: "auto" }}>
            {filtered.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                No events match the current filters.
              </Typography>
            ) : (
              filtered.map((event, i) => {
                const isMilestone = timeline.milestones.some(
                  (m) => m.timestamp === event.timestamp && m.description === event.description,
                );
                return (
                  <Stack
                    key={`${event.timestamp}-${i}`}
                    direction="row"
                    spacing={2}
                    onClick={() => setSelected(event)}
                    sx={{
                      cursor: "pointer",
                      py: 1.25,
                      px: 1,
                      borderRadius: 2,
                      "&:hover": { bgcolor: "action.hover" },
                      bgcolor: selected === event ? "action.selected" : undefined,
                    }}
                  >
                    <Stack alignItems="center" sx={{ minWidth: 14 }}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: "50%",
                          mt: 0.75,
                          bgcolor: event.critical
                            ? BRAND.critical
                            : isMilestone
                              ? BRAND.high
                              : BRAND.primary,
                          boxShadow: event.critical ? `0 0 8px ${BRAND.critical}` : undefined,
                        }}
                      />
                      {i < filtered.length - 1 && (
                        <Box sx={{ flex: 1, width: "2px", bgcolor: "divider", mt: 0.5 }} />
                      )}
                    </Stack>
                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        {formatDateTime(event.timestamp)} · {titleCase(event.event_type)}
                        {event.evidence_id ? ` · ${event.evidence_id}` : ""}
                      </Typography>
                      <Typography variant="body2">{event.description}</Typography>
                      <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                        {event.critical && (
                          <Tooltip title={event.critical_reasons.join("; ")}>
                            <Chip size="small" label="CRITICAL" sx={{ bgcolor: `${BRAND.critical}22`, color: BRAND.critical, fontWeight: 700 }} />
                          </Tooltip>
                        )}
                        {isMilestone && <Chip size="small" label="Milestone" variant="outlined" />}
                        {event.stages.map((stage) => (
                          <Chip key={stage} size="small" label={titleCase(stage)} variant="outlined" />
                        ))}
                      </Stack>
                    </Box>
                  </Stack>
                );
              })
            )}
          </Box>

          <Box
            sx={{
              width: { xs: "100%", lg: 320 },
              borderLeft: { lg: 1 },
              borderTop: { xs: 1, lg: 0 },
              borderColor: { xs: "divider", lg: "divider" },
              p: 2,
            }}
          >
            {!selected ? (
              <Typography variant="body2" color="text.secondary">
                Select an event to see its full engine-provided details.
              </Typography>
            ) : (
              <Stack spacing={1}>
                <Typography variant="subtitle2">{titleCase(selected.event_type)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatDateTime(selected.timestamp)}
                </Typography>
                <Typography variant="body2">{selected.description}</Typography>
                {selected.evidence_id && (
                  <Typography variant="body2" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    {selected.evidence_id}
                  </Typography>
                )}
                {selected.critical_reasons.length > 0 && (
                  <>
                    <Typography variant="subtitle2" color="error">
                      Critical because:
                    </Typography>
                    {selected.critical_reasons.map((reason, i) => (
                      <Typography key={i} variant="body2">
                        • {reason}
                      </Typography>
                    ))}
                  </>
                )}
              </Stack>
            )}
          </Box>
        </Stack>
      </Card>
    </Stack>
  );
}
