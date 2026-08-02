import { Box, Stack, Typography, useTheme } from "@mui/material";
import dayjs from "dayjs";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { BRAND } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

import { UNSTAGED, stageMeta } from "./stages";

/**
 * Gantt-style swimlane chart of the engine's reconstructed timeline.
 *
 * One lane per attack stage, ordered as the attack unfolded, with a bar
 * spanning each stage's first to last event — so both the *sequence* and the
 * *duration* of the attack are readable at a glance. Lane colour escalates
 * along the canonical stage order (see `stages.ts`), which means the severity
 * story is visible before any label is read.
 *
 * Marker shape, not just colour, carries severity: critical events are a
 * haloed ring and milestones a diamond, so the chart survives greyscale
 * printing and colour-blind readers — both of which matter for something a
 * supervisor may print into a case file.
 */

/** Events closer together than this merge into one cluster marker. */
const CLUSTER_PX = 16;

const LANE_H = 54;
const AXIS_H = 36;
const TOP_PAD = 10;
const LABEL_W = 210;
const RIGHT_PAD = 28;
const BAR_H = 20;

interface Cluster {
  x: number;
  lane: number;
  events: TimelineEvent[];
  kind: "critical" | "milestone" | "event";
}

interface Hover {
  cx: number;
  cy: number;
  cluster: Cluster;
}

const at = (event: TimelineEvent) => new Date(event.timestamp).getTime();

/** Human duration for a stage bar ("4m", "3h 20m", "2d"). */
function humanSpan(ms: number): string {
  if (ms < 1000) return "instant";
  const mins = ms / 60000;
  if (mins < 1) return `${Math.round(ms / 1000)}s`;
  if (mins < 60) return `${Math.round(mins)}m`;
  const hours = mins / 60;
  if (hours < 24) {
    const h = Math.floor(hours);
    const m = Math.round(mins - h * 60);
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  const days = Math.floor(hours / 24);
  const h = Math.round(hours - days * 24);
  return h ? `${days}d ${h}h` : `${days}d`;
}

/** Axis ticks on a human-friendly step (seconds → months) for the span. */
function buildTicks(min: number, max: number, targetCount: number) {
  const SEC = 1000;
  const MIN = 60 * SEC;
  const HOUR = 60 * MIN;
  const DAY = 24 * HOUR;
  const steps = [
    SEC, 5 * SEC, 15 * SEC, 30 * SEC,
    MIN, 5 * MIN, 15 * MIN, 30 * MIN,
    HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
    DAY, 2 * DAY, 7 * DAY, 14 * DAY, 30 * DAY, 90 * DAY, 365 * DAY,
  ];
  const span = Math.max(1, max - min);
  const step = steps.find((s) => s >= span / Math.max(1, targetCount))
    ?? steps[steps.length - 1];

  const ticks: number[] = [];
  // Align to the step so labels land on round times, not on the first event.
  for (let t = Math.ceil(min / step) * step; t <= max; t += step) ticks.push(t);
  if (ticks.length === 0) ticks.push(min, max);

  return {
    ticks,
    fmt: step < MIN ? "HH:mm:ss" : step < DAY ? "MMM D, HH:mm" : "MMM D, YYYY",
  };
}

export function TimelineChart({
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
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<Hover | null>(null);
  const [hotLane, setHotLane] = useState<number | null>(null);

  // Render at real pixel width so labels stay at their intended size — a
  // scaled viewBox stretched the type differently on every screen.
  useLayoutEffect(() => {
    const node = wrapRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(node);
    setWidth(node.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  // The tooltip is viewport-anchored, so a scroll would leave it stranded.
  useEffect(() => {
    if (!hover) return;
    const drop = () => setHover(null);
    window.addEventListener("scroll", drop, true);
    return () => window.removeEventListener("scroll", drop, true);
  }, [hover]);

  const model = useMemo(() => {
    const dated = events.filter(
      (e) => e.timestamp && !Number.isNaN(new Date(e.timestamp).getTime()),
    );
    const undated = events.length - dated.length;
    if (dated.length === 0) {
      return { dated, undated, lanes: [] as string[], min: 0, max: 0 };
    }

    const times = dated.map(at);
    let min = Math.min(...times);
    let max = Math.max(...times);
    if (max === min) {
      // A single instant still deserves a readable axis: show a minute around it.
      min -= 30_000;
      max += 30_000;
    }

    // Lane order follows first occurrence, so lanes read in attack order.
    const firstSeen = new Map<string, number>();
    for (const event of dated) {
      for (const stage of event.stages.length ? event.stages : [UNSTAGED]) {
        const t = at(event);
        if (!firstSeen.has(stage) || t < firstSeen.get(stage)!) firstSeen.set(stage, t);
      }
    }
    const lanes = [...firstSeen.entries()]
      .sort((a, b) => a[1] - b[1])
      .map(([stage]) => stage)
      // Unattributed events always sit at the bottom, out of the attack story.
      .sort((a, b) => Number(a === UNSTAGED) - Number(b === UNSTAGED));

    return { dated, undated, lanes, min, max };
  }, [events]);

  const { dated, undated, lanes, min, max } = model;

  const plotW = Math.max(140, width - LABEL_W - RIGHT_PAD);
  const height = TOP_PAD + lanes.length * LANE_H + AXIS_H;
  const span = Math.max(1, max - min);
  const xFor = (t: number) => LABEL_W + ((t - min) / span) * plotW;
  const laneY = (lane: number) => TOP_PAD + lane * LANE_H + LANE_H / 2;
  const axisY = TOP_PAD + lanes.length * LANE_H;

  const layout = useMemo(() => {
    const empty = {
      clusters: [] as Cluster[],
      bars: [] as { lane: number; x1: number; x2: number; from: number; to: number; count: number }[],
    };
    if (!dated.length || !lanes.length || plotW <= 0) return empty;

    const scale = (t: number) => LABEL_W + ((t - min) / Math.max(1, max - min)) * plotW;
    const kindOf = (e: TimelineEvent): Cluster["kind"] =>
      e.critical
        ? "critical"
        : milestoneKeys.has(`${e.timestamp}|${e.description}`)
          ? "milestone"
          : "event";
    const rank = { event: 0, milestone: 1, critical: 2 } as const;

    const clusters: Cluster[] = [];
    const bars: typeof empty.bars = [];

    lanes.forEach((stage, lane) => {
      const inLane = dated
        .filter((e) => (stage === UNSTAGED ? e.stages.length === 0 : e.stages.includes(stage)))
        .sort((a, b) => at(a) - at(b));
      if (!inLane.length) return;

      const from = at(inLane[0]);
      const to = at(inLane[inLane.length - 1]);
      bars.push({ lane, x1: scale(from), x2: scale(to), from, to, count: inLane.length });

      let current: Cluster | null = null;
      for (const event of inLane) {
        const x = scale(at(event));
        if (current && x - current.x < CLUSTER_PX) {
          current.events.push(event);
          if (rank[kindOf(event)] > rank[current.kind]) current.kind = kindOf(event);
          continue;
        }
        current = { x, lane, events: [event], kind: kindOf(event) };
        clusters.push(current);
      }
    });

    return { clusters, bars };
  }, [dated, lanes, plotW, min, max, milestoneKeys]);

  const { ticks, fmt } = useMemo(
    () => buildTicks(min, max, Math.max(2, Math.floor(plotW / 140))),
    [min, max, plotW],
  );

  if (!dated.length) {
    return (
      <Box sx={{ px: 2, py: 3, textAlign: "center" }}>
        <Typography variant="body2" color="text.secondary">
          No events with a resolved timestamp to plot
          {undated > 0 ? ` — ${undated} event(s) have no usable time and are listed below` : ""}.
        </Typography>
      </Box>
    );
  }

  const severityColor = (kind: Cluster["kind"]) =>
    kind === "critical" ? BRAND.critical : kind === "milestone" ? BRAND.high : BRAND.primary;

  return (
    <Box sx={{ px: 2, pt: 2, pb: 1 }}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        alignItems={{ sm: "baseline" }}
        sx={{ mb: 1.5 }}
      >
        <Typography variant="subtitle2">Attack timeline</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
          {dayjs(min).format("MMM D, YYYY HH:mm")} → {dayjs(max).format("MMM D, YYYY HH:mm")}
          {"  ·  "}
          spans {humanSpan(max - min)}
          {"  ·  "}
          {dated.length} event{dated.length === 1 ? "" : "s"}
          {undated > 0 ? ` · ${undated} without a usable time` : ""}
        </Typography>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Legend shape="ring" color={BRAND.critical} label="Critical" />
          <Legend shape="diamond" color={BRAND.high} label="Milestone" />
          <Legend shape="dot" color={BRAND.primary} label="Event" />
        </Stack>
      </Stack>

      <Box ref={wrapRef} sx={{ width: "100%" }}>
        {width > 0 && (
          <svg
            width={width}
            height={height}
            role="img"
            aria-label={`Timeline of ${dated.length} events across ${lanes.length} attack stages`}
            style={{ display: "block", overflow: "visible" }}
            onMouseLeave={() => {
              setHover(null);
              setHotLane(null);
            }}
          >
            {/* Lane rows: label column on the left, plot area on the right. */}
            {lanes.map((stage, lane) => {
              const meta = stageMeta(stage, lane);
              const bar = layout.bars.find((b) => b.lane === lane);
              const hot = hotLane === lane;
              return (
                <g key={stage} onMouseEnter={() => setHotLane(lane)}>
                  <rect
                    x={0}
                    y={TOP_PAD + lane * LANE_H}
                    width={Math.max(width, 0)}
                    height={LANE_H}
                    rx={8}
                    fill={hot ? meta.color : theme.palette.text.primary}
                    opacity={hot ? 0.07 : lane % 2 === 1 ? 0.025 : 0}
                  />
                  {/* Colour key + stage name + what it actually means. */}
                  <circle cx={12} cy={laneY(lane) - 5} r={5} fill={meta.color} />
                  <text
                    x={26}
                    y={laneY(lane) - 1}
                    fontSize={12.5}
                    fontWeight={700}
                    fill={theme.palette.text.primary}
                  >
                    {meta.label}
                  </text>
                  <text
                    x={26}
                    y={laneY(lane) + 14}
                    fontSize={10.5}
                    fill={theme.palette.text.secondary}
                  >
                    {bar
                      ? `${bar.count} event${bar.count === 1 ? "" : "s"} · ${
                          bar.to > bar.from ? humanSpan(bar.to - bar.from) : "single moment"
                        }`
                      : "no events"}
                  </text>
                </g>
              );
            })}

            {/* Time gridlines behind the data. */}
            {ticks.map((t) => (
              <line
                key={`grid-${t}`}
                x1={xFor(t)}
                x2={xFor(t)}
                y1={TOP_PAD}
                y2={axisY}
                stroke={theme.palette.divider}
                strokeDasharray="2 5"
              />
            ))}

            {/* Stage bars: first → last event, in the stage's own colour. */}
            {layout.bars.map(({ lane, x1, x2 }) => {
              const meta = stageMeta(lanes[lane], lane);
              return (
                <g key={`bar-${lane}`}>
                  <rect
                    x={x1 - BAR_H / 2}
                    y={laneY(lane) - BAR_H / 2}
                    width={Math.max(x2 - x1 + BAR_H, BAR_H)}
                    height={BAR_H}
                    rx={BAR_H / 2}
                    fill={meta.color}
                    opacity={0.16}
                  />
                  <rect
                    x={x1 - BAR_H / 2}
                    y={laneY(lane) - BAR_H / 2}
                    width={Math.max(x2 - x1 + BAR_H, BAR_H)}
                    height={BAR_H}
                    rx={BAR_H / 2}
                    fill="none"
                    stroke={meta.color}
                    strokeOpacity={0.4}
                  />
                </g>
              );
            })}

            {/* Axis */}
            <line
              x1={LABEL_W}
              x2={LABEL_W + plotW}
              y1={axisY}
              y2={axisY}
              stroke={theme.palette.divider}
              strokeWidth={1.5}
            />
            {ticks.map((t) => (
              <g key={`tick-${t}`}>
                <line
                  x1={xFor(t)}
                  x2={xFor(t)}
                  y1={axisY}
                  y2={axisY + 5}
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
                  {dayjs(t).format(fmt)}
                </text>
              </g>
            ))}

            {/* Event markers */}
            {layout.clusters.map((cluster, i) => {
              const color = severityColor(cluster.kind);
              const isSelected = !!selected && cluster.events.includes(selected);
              const isHovered = hover?.cluster === cluster;
              const grow = isSelected ? 2.5 : isHovered ? 1.5 : 0;
              const cy = laneY(cluster.lane);
              return (
                <g
                  key={`${cluster.lane}-${i}`}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={(e) => {
                    setHotLane(cluster.lane);
                    const box = (e.currentTarget as SVGGElement).getBoundingClientRect();
                    setHover({
                      cx: box.left + box.width / 2,
                      cy: box.top + box.height / 2,
                      cluster,
                    });
                  }}
                  onClick={() => onSelect(cluster.events[0])}
                >
                  {/* Generous invisible hit area — a 6px dot is hard to hover. */}
                  <circle cx={cluster.x} cy={cy} r={15} fill="transparent" />
                  <Marker
                    kind={cluster.kind}
                    x={cluster.x}
                    y={cy}
                    grow={grow}
                    color={color}
                    ring={theme.palette.background.paper}
                    emphasised={isSelected}
                  />
                  {cluster.events.length > 1 && (
                    <text
                      x={cluster.x}
                      y={cy - 13 - grow}
                      textAnchor="middle"
                      fontSize={10}
                      fontWeight={700}
                      fill={color}
                    >
                      {cluster.events.length}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </Box>

      <Typography variant="caption" color="text.disabled" sx={{ display: "block", mt: 1 }}>
        Each row is one stage of the attack, coloured by how serious it is; the bar runs from
        that stage's first event to its last. A number above a marker means several events
        happened at that moment. Hover for details, click to open the event below.
      </Typography>

      {hover && <ClusterTooltip hover={hover} milestoneKeys={milestoneKeys} />}
    </Box>
  );
}

/** Marker shapes double up the severity signal so colour is never the only cue. */
function Marker({
  kind, x, y, grow, color, ring, emphasised,
}: {
  kind: Cluster["kind"];
  x: number;
  y: number;
  grow: number;
  color: string;
  ring: string;
  emphasised: boolean;
}) {
  if (kind === "critical") {
    const r = 6 + grow;
    return (
      <>
        <circle cx={x} cy={y} r={r + 5} fill={color} opacity={0.2} />
        <circle cx={x} cy={y} r={r} fill={ring} stroke={color} strokeWidth={3.5} />
      </>
    );
  }
  if (kind === "milestone") {
    const s = 6.5 + grow;
    return (
      <>
        {emphasised && <circle cx={x} cy={y} r={s + 5} fill={color} opacity={0.2} />}
        <rect
          x={x - s} y={y - s} width={s * 2} height={s * 2}
          transform={`rotate(45 ${x} ${y})`}
          fill={color} stroke={ring} strokeWidth={2} rx={1.5}
        />
      </>
    );
  }
  const r = 5.5 + grow;
  return (
    <>
      {emphasised && <circle cx={x} cy={y} r={r + 5} fill={color} opacity={0.2} />}
      <circle cx={x} cy={y} r={r} fill={color} stroke={ring} strokeWidth={2} />
    </>
  );
}

function Legend({ shape, color, label }: { shape: string; color: string; label: string }) {
  const glyph =
    shape === "ring"
      ? { border: `2.5px solid ${color}`, borderRadius: "50%" }
      : shape === "diamond"
        ? { bgcolor: color, transform: "rotate(45deg)" }
        : { bgcolor: color, borderRadius: "50%" };
  return (
    <Stack direction="row" spacing={0.6} alignItems="center">
      <Box sx={{ width: 10, height: 10, flexShrink: 0, ...glyph }} />
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

/**
 * Viewport-anchored tooltip.
 *
 * It measures itself and then clamps to the visible viewport, flipping above
 * the marker when there is no room below. Anchoring to the *viewport* rather
 * than to the chart is what stops it being clipped by the scrolling card the
 * chart lives in — an absolutely-positioned box could only guess, and got cut
 * off near the right and bottom edges.
 */
function ClusterTooltip({ hover, milestoneKeys }: { hover: Hover; milestoneKeys: Set<string> }) {
  const theme = useTheme();
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const { width, height } = node.getBoundingClientRect();
    const margin = 8;
    const gap = 18;

    let left = hover.cx - width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

    // Prefer below the marker; flip above when that would overflow.
    let top = hover.cy + gap;
    if (top + height > window.innerHeight - margin) top = hover.cy - gap - height;
    top = Math.max(margin, Math.min(top, window.innerHeight - height - margin));

    setPos({ left, top });
  }, [hover]);

  const shown = hover.cluster.events.slice(0, 4);
  const more = hover.cluster.events.length - shown.length;

  return (
    <Box
      ref={ref}
      sx={{
        position: "fixed",
        left: pos?.left ?? -9999,
        top: pos?.top ?? -9999,
        // Hidden until measured, so it never flashes in the wrong place.
        visibility: pos ? "visible" : "hidden",
        zIndex: theme.zIndex.tooltip,
        pointerEvents: "none",
        width: "min(360px, calc(100vw - 16px))",
        p: 1.5,
        borderRadius: 2,
        border: 1,
        borderColor: "divider",
        boxShadow: 8,
        bgcolor: theme.palette.mode === "dark" ? "rgba(18,26,46,0.98)" : "rgba(255,255,255,0.99)",
      }}
    >
      {hover.cluster.events.length > 1 && (
        <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 0.75 }}>
          {hover.cluster.events.length} events at this moment
        </Typography>
      )}
      <Stack spacing={1.25}>
        {shown.map((event, i) => {
          const kind = event.critical
            ? "critical"
            : milestoneKeys.has(`${event.timestamp}|${event.description}`)
              ? "milestone"
              : "event";
          const color =
            kind === "critical" ? BRAND.critical : kind === "milestone" ? BRAND.high : BRAND.primary;
          return (
            <Box key={`${event.timestamp}-${i}`}>
              <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.25 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: color, flexShrink: 0 }} />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {dayjs(event.timestamp).format("MMM D, YYYY HH:mm")}
                  {event.timestamp_inferred ? " (inferred)" : ""}
                </Typography>
              </Stack>
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  // Long OCR-derived descriptions must wrap, never overflow.
                  overflowWrap: "anywhere",
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {event.description}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
                {event.evidence_id}
                {event.stages.length
                  ? ` · ${event.stages.map((s, n) => stageMeta(s, n).label).join(", ")}`
                  : ""}
              </Typography>
              {event.critical && event.critical_reasons.length > 0 && (
                <Typography
                  variant="caption"
                  sx={{
                    color: BRAND.critical,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    overflowWrap: "anywhere",
                  }}
                >
                  Critical: {event.critical_reasons.join("; ")}
                </Typography>
              )}
            </Box>
          );
        })}
      </Stack>
      {more > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
          +{more} more — click the marker to open them below.
        </Typography>
      )}
    </Box>
  );
}
