import { Box, Typography, useTheme } from "@mui/material";
import dayjs from "dayjs";
import { useMemo, useRef, useState } from "react";

import { BRAND } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

interface TooltipState {
  x: number;
  y: number;
  event: TimelineEvent;
}

/**
 * Horizontal time-axis view of the engine's reconstructed events.
 * Every dot is one engine event positioned by its resolved timestamp;
 * hovering shows the description, evidence and correlated entities. Events
 * with unresolved timestamps are counted separately rather than guessed.
 */
export function TimelineAxis({
  events,
  milestoneKeys,
  selected,
  onSelect,
}: {
  events: TimelineEvent[];
  /** `${timestamp}|${description}` keys marking milestone events. */
  milestoneKeys: Set<string>;
  selected: TimelineEvent | null;
  onSelect: (event: TimelineEvent) => void;
}) {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const { dated, undatedCount, min, max } = useMemo(() => {
    const withDates = events.filter(
      (e) => e.timestamp && !Number.isNaN(new Date(e.timestamp).getTime()),
    );
    const times = withDates.map((e) => new Date(e.timestamp).getTime());
    return {
      dated: withDates,
      undatedCount: events.length - withDates.length,
      min: times.length ? Math.min(...times) : 0,
      max: times.length ? Math.max(...times) : 1,
    };
  }, [events]);

  if (dated.length === 0) {
    return (
      <Box sx={{ px: 2, py: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          No events with resolved timestamps to plot
          {undatedCount > 0 ? ` (${undatedCount} unresolved)` : ""}.
        </Typography>
      </Box>
    );
  }

  const width = 960; // viewBox units; scales to container width
  const height = 92;
  const padX = 36;
  const axisY = 56;
  const span = Math.max(1, max - min);
  const xFor = (t: number) => padX + ((t - min) / span) * (width - padX * 2);

  // Distribute overlapping dots vertically so simultaneous events stay visible.
  const slots = new Map<number, number>();
  const positioned = dated.map((event) => {
    const x = Math.round(xFor(new Date(event.timestamp).getTime()));
    const bucket = Math.round(x / 14);
    const lane = slots.get(bucket) ?? 0;
    slots.set(bucket, lane + 1);
    return { event, x, y: axisY - 10 - lane * 13 };
  });

  const fmtTick = (t: number) => dayjs(t).format(span > 86400000 ? "MMM D" : "HH:mm");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => min + f * span);

  const colorFor = (event: TimelineEvent) => {
    if (event.critical) return BRAND.critical;
    if (milestoneKeys.has(`${event.timestamp}|${event.description}`)) return BRAND.high;
    return BRAND.primary;
  };

  const handleHover = (
    e: React.MouseEvent<SVGCircleElement>,
    event: TimelineEvent,
  ) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, event });
  };

  return (
    <Box ref={containerRef} sx={{ position: "relative", px: 2, pt: 1.5 }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        role="img"
        aria-label="Event timeline axis"
      >
        {/* Axis */}
        <line
          x1={padX}
          y1={axisY}
          x2={width - padX}
          y2={axisY}
          stroke={theme.palette.divider}
          strokeWidth={1.5}
        />
        {ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={xFor(t)}
              y1={axisY - 4}
              x2={xFor(t)}
              y2={axisY + 4}
              stroke={theme.palette.divider}
              strokeWidth={1.5}
            />
            <text
              x={xFor(t)}
              y={axisY + 20}
              textAnchor="middle"
              fontSize={11}
              fill={theme.palette.text.secondary}
            >
              {fmtTick(t)}
            </text>
          </g>
        ))}
        {/* Events */}
        {positioned.map(({ event, x, y }, i) => {
          const isSelected = selected === event;
          return (
            <g key={`${event.timestamp}-${i}`}>
              <line
                x1={x}
                y1={y + 5}
                x2={x}
                y2={axisY}
                stroke={colorFor(event)}
                strokeWidth={1}
                opacity={0.45}
              />
              <circle
                cx={x}
                cy={y}
                r={isSelected ? 7 : 5.5}
                fill={colorFor(event)}
                stroke={theme.palette.background.paper}
                strokeWidth={1.5}
                style={{ cursor: "pointer" }}
                onMouseEnter={(e) => handleHover(e, event)}
                onMouseLeave={() => setTooltip(null)}
                onClick={() => onSelect(event)}
              />
            </g>
          );
        })}
      </svg>

      <Typography variant="caption" color="text.disabled" sx={{ display: "block", pb: 1 }}>
        {dated.length} event(s) plotted
        {undatedCount > 0 ? ` · ${undatedCount} with unresolved timestamps (listed below)` : ""}
        {" · "}
        <Box component="span" sx={{ color: BRAND.critical }}>
          ●
        </Box>{" "}
        critical{" "}
        <Box component="span" sx={{ color: BRAND.high }}>
          ●
        </Box>{" "}
        milestone{" "}
        <Box component="span" sx={{ color: BRAND.primary }}>
          ●
        </Box>{" "}
        event · hover for details, click to inspect
      </Typography>

      {tooltip && (
        <Box
          sx={{
            position: "absolute",
            left: Math.min(tooltip.x + 12, (containerRef.current?.clientWidth ?? 400) - 290),
            top: tooltip.y + 12,
            zIndex: 10,
            width: 280,
            p: 1.25,
            borderRadius: 2,
            pointerEvents: "none",
            bgcolor: theme.palette.mode === "dark" ? "rgba(18,26,46,0.97)" : "rgba(255,255,255,0.98)",
            border: 1,
            borderColor: "divider",
            boxShadow: 6,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
            {dayjs(tooltip.event.timestamp).format("YYYY-MM-DD HH:mm")}
            {tooltip.event.timestamp_inferred ? " (inferred)" : ""} ·{" "}
            {tooltip.event.evidence_id}
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, my: 0.25 }}>
            {tooltip.event.description}
          </Typography>
          {tooltip.event.critical && tooltip.event.critical_reasons.length > 0 && (
            <Typography variant="caption" sx={{ color: BRAND.critical, display: "block" }}>
              Critical: {tooltip.event.critical_reasons.join("; ")}
            </Typography>
          )}
          {(tooltip.event.correlated_with?.length ?? 0) > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              Correlates with{" "}
              {tooltip.event.correlated_with
                ?.slice(0, 3)
                .map(
                  (c) =>
                    `${c.linked_to}${
                      c.shared_entities.length
                        ? ` (${c.shared_entities.slice(0, 3).join(", ")})`
                        : ""
                    }`,
                )
                .join("; ")}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}
