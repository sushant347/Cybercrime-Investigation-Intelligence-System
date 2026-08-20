import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Tooltip,
  Typography,
  alpha,
  useTheme,
} from "@mui/material";
import dayjs from "dayjs";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { BRAND, lightModeEquivalent } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

import { eventTitle } from "./eventText";
import { UNSTAGED, primaryStage, stageMeta } from "./stages";
import { humanSpan } from "./timeScale";

/** Number of moments shown before the investigator asks to expand the story. */
const INITIAL_MOMENTS = 8;

/** Intake timestamps are provenance records, not incident chronology. */
export const isAcquisitionFallback = (event: TimelineEvent) =>
  (event.time_source ?? "").toLowerCase().replaceAll(" ", "_") === "upload_time_fallback";

interface Moment {
  timestamp: string;
  at: number;
  events: TimelineEvent[];
}

const validTime = (event: TimelineEvent) => {
  const value = new Date(event.timestamp).getTime();
  return Number.isNaN(value) ? null : value;
};

const timeBasis = (event: TimelineEvent) => {
  if (isAcquisitionFallback(event)) return "Acquisition";
  return event.timestamp_inferred ? "Inferred" : "Recorded";
};

const sourceLabel = (event: TimelineEvent) =>
  (event.time_source || "unresolved").replaceAll("_", " ");

/**
 * Investigator-first chronology.
 *
 * The former Gantt/swimlane view made a small case look dense because one
 * multi-stage exhibit was repeated across several rows. This view draws each
 * event once, in chronological order. Attack stages remain visible as chips,
 * while timestamp provenance is shown beside the finding it qualifies.
 * Equal vertical spacing represents sequence only; the exact elapsed time is
 * stated in the header rather than encoded as a misleading empty canvas.
 */
export function TimelineChart({
  events,
  milestoneKeys,
  selected,
  onSelect,
  renderDetails,
}: {
  events: TimelineEvent[];
  milestoneKeys: Set<string>;
  selected: TimelineEvent | null;
  onSelect: (event: TimelineEvent) => void;
  renderDetails?: (event: TimelineEvent) => ReactNode;
}) {
  const theme = useTheme();
  const [includeAcquisition, setIncludeAcquisition] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const model = useMemo(() => {
    const acquisitionOnly = events.filter(isAcquisitionFallback);
    const visible = includeAcquisition
      ? events
      : events.filter((event) => !isAcquisitionFallback(event));
    const dated = visible
      .map((event) => ({ event, at: validTime(event) }))
      .filter((item): item is { event: TimelineEvent; at: number } => item.at !== null)
      .sort((a, b) => a.at - b.at || a.event.evidence_id.localeCompare(b.event.evidence_id));
    const undated = visible.length - dated.length;
    const moments: Moment[] = [];
    for (const item of dated) {
      const timestamp = new Date(item.at).toISOString();
      const previous = moments.at(-1);
      if (previous?.timestamp === timestamp) {
        previous.events.push(item.event);
      } else {
        moments.push({ timestamp, at: item.at, events: [item.event] });
      }
    }
    return { acquisitionOnly, dated, undated, moments };
  }, [events, includeAcquisition]);

  const { acquisitionOnly, dated, undated, moments } = model;
  const visibleMoments = expanded ? moments : moments.slice(0, INITIAL_MOMENTS);
  const hiddenMoments = moments.length - visibleMoments.length;
  const inferred = dated.filter(({ event }) =>
    event.timestamp_inferred && !isAcquisitionFallback(event)).length;
  const recorded = dated.filter(({ event }) =>
    !event.timestamp_inferred && !isAcquisitionFallback(event)).length;
  const critical = dated.filter(({ event }) => event.critical).length;
  const first = dated[0]?.at;
  const last = dated.at(-1)?.at;

  if (!dated.length) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: "center", borderRadius: 3 }}>
        <Typography variant="subtitle1" fontWeight={700}>
          No evidence-derived event times
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {undated > 0
            ? `${undated} event(s) have no usable timestamp and remain in the evidence list.`
            : "No event can currently be placed in the incident sequence."}
        </Typography>
        {acquisitionOnly.length > 0 && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            {acquisitionOnly.length} acquisition-only record
            {acquisitionOnly.length === 1 ? " is" : "s are"} excluded from incident chronology.
          </Typography>
        )}
      </Paper>
    );
  }

  return (
    <Box sx={{ px: { xs: 1, sm: 2 }, pt: 1.5, pb: 1 }}>
      <Paper
        variant="outlined"
        sx={{
          p: { xs: 1.5, md: 2 },
          mb: 1.5,
          borderRadius: 3,
          borderColor: alpha(BRAND.primary, 0.2),
          background: `linear-gradient(135deg, ${alpha(BRAND.primary, 0.08)}, ${alpha(BRAND.primary, 0.015)} 58%, transparent)`,
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="subtitle1" fontWeight={800}>
                {dated.length}{" "}
                {includeAcquisition
                  ? `chronology record${dated.length === 1 ? "" : "s"}`
                  : `incident event${dated.length === 1 ? "" : "s"}`}
              </Typography>
              {critical > 0 && (
                <Chip
                  size="small"
                  label={`${critical} priority`}
                  sx={{ color: BRAND.critical, bgcolor: alpha(BRAND.critical, 0.09) }}
                />
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.45 }}>
              {dayjs(first).format("MMM D, YYYY HH:mm")} - {dayjs(last).format("MMM D, YYYY HH:mm")}
              {first !== undefined && last !== undefined ? ` · ${humanSpan(last - first)}` : ""}
            </Typography>
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
              <BasisPill color={lightModeEquivalent(BRAND.primary, theme) as string} label={`${recorded} recorded`} />
              <BasisPill color={lightModeEquivalent(BRAND.high, theme) as string} label={`${inferred} inferred`} />
              {includeAcquisition && (
                <BasisPill color={theme.palette.text.secondary} label={`${acquisitionOnly.length} acquisition`} />
              )}
              {undated > 0 && <BasisPill color={theme.palette.text.disabled} label={`${undated} unresolved`} />}
            </Stack>
          </Box>

          {acquisitionOnly.length > 0 && (
            <Tooltip title="Upload time records when CIIS received an exhibit. It is not proof of when the incident occurred.">
              <FormControlLabel
                sx={{ m: 0, alignSelf: { xs: "flex-start", md: "center" } }}
                control={
                  <Switch
                    size="small"
                    checked={includeAcquisition}
                    onChange={(event) => {
                      setIncludeAcquisition(event.target.checked);
                      setExpanded(false);
                    }}
                    inputProps={{ "aria-label": "Include acquisition timestamps" }}
                  />
                }
                label={
                  <Typography variant="caption" color="text.secondary">
                    Show {acquisitionOnly.length} acquisition record
                    {acquisitionOnly.length === 1 ? "" : "s"}
                  </Typography>
                }
              />
            </Tooltip>
          )}
        </Stack>
      </Paper>

      {acquisitionOnly.length > 0 && (
        <Alert
          severity={includeAcquisition ? "warning" : "info"}
          variant="outlined"
          sx={{ mb: 1.5, borderRadius: 2.5, py: 0 }}
        >
          {includeAcquisition
            ? "Acquisition records are included for provenance; they are not incident events."
            : `${acquisitionOnly.length} upload timestamp${acquisitionOnly.length === 1 ? " is" : "s are"} kept out of the incident story.`}
        </Alert>
      )}

      <Box
        aria-label={`Chronological sequence of ${dated.length} events`}
        sx={{
          position: "relative",
          "&::before": {
            content: '""',
            position: "absolute",
            top: 18,
            bottom: 18,
            left: { xs: 15, sm: 137 },
            width: 2,
            borderRadius: 2,
            background: `linear-gradient(${alpha(BRAND.primary, 0.15)}, ${alpha(BRAND.primary, 0.55)}, ${alpha(BRAND.primary, 0.15)})`,
          },
        }}
      >
        <Stack spacing={1.25}>
          {visibleMoments.map((moment, index) => (
            <MomentRow
              key={moment.timestamp}
              moment={moment}
              number={index + 1}
              milestoneKeys={milestoneKeys}
              selected={selected}
              onSelect={onSelect}
              renderDetails={renderDetails}
            />
          ))}
        </Stack>
      </Box>

      {hiddenMoments > 0 && (
        <Box sx={{ pl: { xs: 5, sm: 20 }, pt: 1.25 }}>
          <Button size="small" variant="outlined" onClick={() => setExpanded(true)}>
            Show {hiddenMoments} more moment{hiddenMoments === 1 ? "" : "s"}
          </Button>
        </Box>
      )}
      {expanded && moments.length > INITIAL_MOMENTS && (
        <Box sx={{ pl: { xs: 5, sm: 20 }, pt: 1.25 }}>
          <Button size="small" onClick={() => setExpanded(false)}>
            Show concise story
          </Button>
        </Box>
      )}

      <Typography variant="caption" color="text.disabled" display="block" sx={{ mt: 1.5, pl: { sm: 20 } }}>
        Cards are equally spaced to keep the sequence readable; timestamps show the actual elapsed time. Select a finding for full evidence details.
      </Typography>
    </Box>
  );
}

function MomentRow({
  moment,
  number,
  milestoneKeys,
  selected,
  onSelect,
  renderDetails,
}: {
  moment: Moment;
  number: number;
  milestoneKeys: Set<string>;
  selected: TimelineEvent | null;
  onSelect: (event: TimelineEvent) => void;
  renderDetails?: (event: TimelineEvent) => ReactNode;
}) {
  const theme = useTheme();
  const representative = moment.events[0];
  const primary = primaryStage(representative.stages);
  const meta = stageMeta(primary, number - 1);
  const isCritical = moment.events.some((event) => event.critical);
  const isMilestone = moment.events.some((event) =>
    milestoneKeys.has(`${event.timestamp}|${event.description}`));
  const markerColor = lightModeEquivalent(
    isCritical ? BRAND.critical : isMilestone ? BRAND.high : meta.color,
    theme,
  ) as string;

  return (
    <Box
      data-testid="timeline-moment"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "32px minmax(0, 1fr)", sm: "120px 34px minmax(0, 1fr)" },
        columnGap: { xs: 0.75, sm: 0 },
        alignItems: "start",
        position: "relative",
      }}
    >
      <Box sx={{ display: { xs: "none", sm: "block" }, pr: 2, pt: 1.1, textAlign: "right" }}>
        <Typography variant="caption" fontWeight={800} display="block">
          {dayjs(moment.at).format("MMM D, YYYY")}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {dayjs(moment.at).format("HH:mm:ss")}
        </Typography>
      </Box>

      <Box sx={{ position: "relative", minHeight: 44, display: "flex", justifyContent: "center", pt: 1.2 }}>
        <Box
          aria-label={isCritical ? "Critical moment" : isMilestone ? "Milestone" : "Event moment"}
          sx={{
            position: "relative",
            zIndex: 1,
            width: isCritical ? 20 : 16,
            height: isCritical ? 20 : 16,
            borderRadius: isMilestone && !isCritical ? 0.75 : "50%",
            transform: isMilestone && !isCritical ? "rotate(45deg)" : "none",
            bgcolor: theme.palette.background.paper,
            border: `${isCritical ? 4 : 3}px solid ${markerColor}`,
            boxShadow: `0 0 0 5px ${alpha(markerColor, 0.12)}`,
          }}
        />
      </Box>

      <Paper
        variant="outlined"
        sx={{
          overflow: "hidden",
          borderRadius: 3,
          borderColor: moment.events.some((event) => event === selected)
            ? BRAND.primary
            : "divider",
          boxShadow: moment.events.some((event) => event === selected)
            ? `0 0 0 2px ${alpha(BRAND.primary, 0.12)}, 0 8px 24px ${alpha(theme.palette.common.black, 0.08)}`
            : `0 3px 14px ${alpha(theme.palette.common.black, 0.045)}`,
          transition: "border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease",
          "&:hover": {
            borderColor: alpha(BRAND.primary, 0.45),
            boxShadow: `0 8px 24px ${alpha(theme.palette.common.black, 0.09)}`,
            transform: "translateY(-1px)",
          },
        }}
      >
        <Box sx={{ p: { xs: 1.1, sm: 1.25 }, borderLeft: `4px solid ${alpha(markerColor, 0.8)}` }}>
          <Stack direction="row" alignItems="center" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mb: 0.75 }}>
            <Typography variant="caption" fontWeight={800} color="text.secondary">
              {String(number).padStart(2, "0")}
            </Typography>
            <Typography variant="caption" fontWeight={800} sx={{ display: { xs: "block", sm: "none" } }}>
              {dayjs(moment.at).format("MMM D, YYYY · HH:mm:ss")}
            </Typography>
            {moment.events.length > 1 && (
              <Chip size="small" label={`${moment.events.length} events at this moment`} />
            )}
            {isCritical && (
              <Chip size="small" label="Priority review" sx={{ color: BRAND.critical, bgcolor: alpha(BRAND.critical, 0.08) }} />
            )}
            {isMilestone && !isCritical && (
              <Chip size="small" label="Milestone" sx={{ color: BRAND.high, bgcolor: alpha(BRAND.high, 0.09) }} />
            )}
          </Stack>

          <Stack spacing={moment.events.length > 1 ? 0.75 : 0}>
            {moment.events.map((event) => (
              <EventFinding
                key={`${event.evidence_id}|${event.description}`}
                event={event}
                selected={event === selected}
                onSelect={onSelect}
                renderDetails={renderDetails}
              />
            ))}
          </Stack>
        </Box>
      </Paper>
    </Box>
  );
}

function EventFinding({
  event,
  selected,
  onSelect,
  renderDetails,
}: {
  event: TimelineEvent;
  selected: boolean;
  onSelect: (event: TimelineEvent) => void;
  renderDetails?: (event: TimelineEvent) => ReactNode;
}) {
  const theme = useTheme();
  const stages = event.stages.length ? event.stages : [UNSTAGED];
  const basis = timeBasis(event);
  const basisColor = lightModeEquivalent(
    basis === "Recorded"
      ? BRAND.primary
      : basis === "Inferred"
        ? BRAND.high
        : theme.palette.text.secondary,
    theme,
  ) as string;

  return (
    <Box>
      <Box
        component="button"
        type="button"
        data-testid="timeline-event"
        aria-expanded={selected}
        onClick={() => onSelect(event)}
        sx={{
          display: "block",
          width: "100%",
          p: 0.75,
          border: 0,
          borderRadius: 2,
          bgcolor: selected ? alpha(BRAND.primary, 0.075) : "transparent",
          color: "inherit",
          textAlign: "left",
          font: "inherit",
          cursor: "pointer",
          "&:hover": { bgcolor: alpha(BRAND.primary, 0.055) },
          "&:focus-visible": { outline: `2px solid ${BRAND.primary}`, outlineOffset: 2 },
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={0.75} alignItems={{ md: "flex-start" }}>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="body2" fontWeight={750} sx={{ overflowWrap: "anywhere" }}>
              {eventTitle(event)}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
              {event.evidence_id}{event.file_name ? ` · ${event.file_name}` : ""}
            </Typography>
          </Box>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
            <Tooltip title={`Timestamp source: ${sourceLabel(event)}; confidence: ${event.confidence || "unknown"}`}>
              <Chip
                size="small"
                variant="outlined"
                label={`${basis} · ${event.confidence || "unknown"}`}
                sx={{ color: basisColor, borderColor: alpha(basisColor, 0.45) }}
              />
            </Tooltip>
            {renderDetails && (
              <ExpandMoreIcon
                fontSize="small"
                sx={{
                  color: "text.secondary",
                  transition: "transform 180ms ease",
                  transform: selected ? "rotate(180deg)" : "none",
                }}
              />
            )}
          </Stack>
        </Stack>

        <Stack direction="row" spacing={0.6} flexWrap="wrap" useFlexGap sx={{ mt: 0.65 }}>
          {stages.map((stage, index) => {
            const meta = stageMeta(stage, index);
            return (
              <Chip
                key={stage}
                size="small"
                label={meta.label}
                sx={{
                  height: 22,
                  color: lightModeEquivalent(meta.color, theme),
                  bgcolor: alpha(meta.color, 0.08),
                  "& .MuiChip-label": { px: 0.9, fontSize: "0.68rem", fontWeight: 700 },
                }}
              />
            );
          })}
        </Stack>
      </Box>

      {renderDetails && (
        <Collapse in={selected} unmountOnExit>
          {renderDetails(event)}
        </Collapse>
      )}
    </Box>
  );
}

function BasisPill({ color, label }: { color: string; label: string }) {
  return (
    <Stack direction="row" spacing={0.55} alignItems="center">
      <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: color }} />
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}
