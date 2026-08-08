import { Box, FormControlLabel, Stack, Switch, Tooltip, Typography, useTheme } from "@mui/material";
import dayjs from "dayjs";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { MetricLabel } from "@/components/common/MetricLabel";
import { BRAND } from "@/theme/theme";
import type { TimelineEvent } from "@/types";

import { eventTitle } from "./eventText";
import { UNSTAGED, primaryStage, stageMeta } from "./stages";
import { buildTicks, buildTimeScale, humanSpan, type TimeScale } from "./timeScale";

/**
 * Gantt-style swimlane chart of the engine's reconstructed timeline.
 *
 * One lane per attack stage, ordered as the attack unfolded, with a bar
 * spanning each stage's first to last event — so both the *sequence* and the
 * *duration* of the attack are readable at a glance. Lane colour escalates
 * along the canonical stage order (see `stages.ts`), which means the severity
 * story is visible before any label is read.
 *
 * Two things make it read as a chart rather than a smear on real data:
 *
 *  - **The axis rations empty time** (see `timeScale.ts`). Cases routinely
 *    span months while every event that matters happens inside one minute.
 *  - **Each event is drawn once**, in the stage it enters the story at. An
 *    event evidencing four stages used to appear four times, so eleven
 *    events drew twenty-three markers and every lane count was wrong. The
 *    other stages it evidences get a hollow echo, which keeps the stage bar
 *    honest without double counting.
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
/** Keeps a marker sitting on the first or last instant off the plot edge. */
const EDGE_PAD = 18;
const BAR_H = 20;
/** Hovering off a marker waits this long, so the pointer can reach the card. */
const HOVER_GRACE_MS = 220;
/** Marks the tooltip so the page-scroll listener can tell its own scroll apart. */
const TOOLTIP_MARKER = "data-timeline-tooltip";
/** Below this width a collapsed-gap band cannot hold its own duration label. */
const GAP_LABEL_MIN_PX = 46;

interface Cluster {
  x: number;
  lane: number;
  events: TimelineEvent[];
  kind: "critical" | "milestone" | "event";
  /** Echoes mark a stage the event evidences but is not primarily drawn in. */
  echo: boolean;
}

interface Hover {
  cx: number;
  cy: number;
  cluster: Cluster;
}

const at = (event: TimelineEvent) => new Date(event.timestamp).getTime();

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
  const [compress, setCompress] = useState(true);
  const [everyStage, setEveryStage] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // The tooltip is viewport-anchored, so scrolling the page would leave it
  // stranded next to nothing — hence dropping it on scroll. But the tooltip
  // scrolls internally when a cluster has more events than fit, and this
  // listener is on the capture phase, so it used to see that inner scroll and
  // close the very list the reader was scrolling. Scrolls that originate
  // inside the tooltip are therefore ignored.
  useEffect(() => {
    if (!hover) return;
    const drop = (event: Event) => {
      const target = event.target;
      if (target instanceof Element && target.closest(`[${TOOLTIP_MARKER}]`)) return;
      setHover(null);
    };
    window.addEventListener("scroll", drop, true);
    return () => window.removeEventListener("scroll", drop, true);
  }, [hover]);

  useEffect(() => () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);

  /** Leaving a marker starts a countdown the tooltip itself can cancel. */
  const scheduleClose = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setHover(null), HOVER_GRACE_MS);
  }, []);
  const cancelClose = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = null;
  }, []);

  const model = useMemo(() => {
    const dated = events.filter(
      (e) => e.timestamp && !Number.isNaN(new Date(e.timestamp).getTime()),
    );
    const undated = events.length - dated.length;
    if (dated.length === 0) {
      return { dated, undated, lanes: [] as string[] };
    }

    // Lane order follows first occurrence, so lanes read in attack order.
    // Every stage any event *evidences* earns a lane, even if no event is
    // drawn there — losing "Credential Theft" from the picture because its
    // one event entered at an earlier stage would hide the worst finding.
    const firstSeen = new Map<string, number>();
    for (const event of dated) {
      const t = at(event);
      for (const stage of event.stages.length ? event.stages : [UNSTAGED]) {
        if (!firstSeen.has(stage) || t < firstSeen.get(stage)!) firstSeen.set(stage, t);
      }
    }
    const lanes = [...firstSeen.entries()]
      .sort((a, b) => a[1] - b[1])
      .map(([stage]) => stage)
      // Unattributed events always sit at the bottom, out of the attack story.
      .sort((a, b) => Number(a === UNSTAGED) - Number(b === UNSTAGED));

    return { dated, undated, lanes };
  }, [events]);

  const { dated, undated, lanes } = model;

  const plotW = Math.max(140, width - LABEL_W - RIGHT_PAD);
  const height = TOP_PAD + lanes.length * LANE_H + AXIS_H;
  const laneY = (lane: number) => TOP_PAD + lane * LANE_H + LANE_H / 2;
  const axisY = TOP_PAD + lanes.length * LANE_H;

  /** The (possibly gap-compressed) time axis. */
  const scale: TimeScale = useMemo(
    () =>
      buildTimeScale(
        dated.map(at),
        LABEL_W + EDGE_PAD,
        Math.max(1, plotW - EDGE_PAD * 2),
        { compress },
      ),
    [dated, plotW, compress],
  );

  const layout = useMemo(() => {
    const empty = {
      clusters: [] as Cluster[],
      bars: [] as {
        lane: number;
        x1: number;
        x2: number;
        from: number;
        to: number;
        count: number;
        echoes: number;
      }[],
    };
    if (!dated.length || !lanes.length || plotW <= 0) return empty;

    const kindOf = (e: TimelineEvent): Cluster["kind"] =>
      e.critical
        ? "critical"
        : milestoneKeys.has(`${e.timestamp}|${e.description}`)
          ? "milestone"
          : "event";
    const rank = { event: 0, milestone: 1, critical: 2 } as const;

    const clusters: Cluster[] = [];
    const bars: typeof empty.bars = [];

    /** Merge a time-sorted run of events into markers no closer than CLUSTER_PX. */
    const clusterRun = (run: TimelineEvent[], lane: number, echo: boolean) => {
      let current: Cluster | null = null;
      for (const event of run) {
        const x = scale.x(at(event));
        if (current && x - current.x < CLUSTER_PX) {
          current.events.push(event);
          if (rank[kindOf(event)] > rank[current.kind]) current.kind = kindOf(event);
          continue;
        }
        current = { x, lane, events: [event], kind: kindOf(event), echo };
        clusters.push(current);
      }
    };

    lanes.forEach((stage, lane) => {
      const evidencing = dated
        .filter((e) => (stage === UNSTAGED ? e.stages.length === 0 : e.stages.includes(stage)))
        .sort((a, b) => at(a) - at(b));
      if (!evidencing.length) return;

      // With `everyStage` on, the chart reverts to a marker per stage per
      // event — the data-faithful reading, at the cost of double counting.
      const primary = everyStage
        ? evidencing
        : evidencing.filter((e) => primaryStage(e.stages) === stage);
      const echoes = everyStage
        ? []
        : evidencing.filter((e) => primaryStage(e.stages) !== stage);

      const from = at(evidencing[0]);
      const to = at(evidencing[evidencing.length - 1]);
      bars.push({
        lane,
        x1: scale.x(from),
        x2: scale.x(to),
        from,
        to,
        count: primary.length,
        echoes: echoes.length,
      });

      clusterRun(primary, lane, false);
      clusterRun(echoes, lane, true);
    });

    return { clusters, bars };
  }, [dated, lanes, plotW, scale, milestoneKeys, everyStage]);

  const ticks = useMemo(() => buildTicks(scale), [scale]);

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

  const hasEchoes = layout.bars.some((b) => b.echoes > 0);

  return (
    <Box sx={{ px: 2, pt: 2, pb: 1 }}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={1}
        alignItems={{ md: "baseline" }}
        sx={{ mb: 1.5 }}
      >
        <Typography variant="subtitle2">Attack timeline</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
          {dayjs(scale.min).format("MMM D, YYYY HH:mm")} →{" "}
          {dayjs(scale.max).format("MMM D, YYYY HH:mm")}
          {"  ·  "}
          spans {humanSpan(scale.max - scale.min)}
          {"  ·  "}
          {dated.length} event{dated.length === 1 ? "" : "s"}
          {undated > 0 ? ` · ${undated} without a usable time` : ""}
        </Typography>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Legend shape="ring" color={BRAND.critical} label="Critical" />
          <Legend shape="diamond" color={BRAND.high} label="Milestone" />
          <Legend shape="dot" color={BRAND.primary} label="Event" />
          {hasEchoes && !everyStage && (
            <Legend shape="hollow" color={theme.palette.text.secondary} label="Also evidences" term="also_evidences" />
          )}
        </Stack>
      </Stack>

      {/* Axis and lane behaviour, kept next to the chart they change. */}
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 0.5 }}>
        <Tooltip title="Cases often span months while everything that matters happens in one minute. Collapsing the empty stretches gives that minute room to be read. Turn this off for a true-to-scale axis.">
          <FormControlLabel
            sx={{ mr: 0 }}
            control={
              <Switch
                size="small"
                checked={compress}
                onChange={(e) => setCompress(e.target.checked)}
                inputProps={{ "aria-label": "Compress quiet periods" }}
              />
            }
            label={
              <Typography variant="caption" color="text.secondary">
                Compress quiet periods
              </Typography>
            }
          />
        </Tooltip>
        <Tooltip title="An event can evidence several stages at once. By default it is drawn once, in the stage it enters the story at, with a hollow echo in the others. Turn this on to draw a full marker in every stage it evidences.">
          <FormControlLabel
            sx={{ mr: 0 }}
            control={
              <Switch
                size="small"
                checked={everyStage}
                onChange={(e) => setEveryStage(e.target.checked)}
                inputProps={{ "aria-label": "Draw in every stage" }}
              />
            }
            label={
              <Typography variant="caption" color="text.secondary">
                Draw in every stage
              </Typography>
            }
          />
        </Tooltip>
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
              scheduleClose();
              setHotLane(null);
            }}
          >
            {/* Stage names and captions are free text of unknown length. The
                plot begins at LABEL_W, so without a clip a long stage name ran
                under the gridlines and markers. This bounds the label column
                absolutely, whatever the wording or font. */}
            <defs>
              <clipPath id="timeline-label-column">
                <rect x={0} y={0} width={LABEL_W - 10} height={height} />
              </clipPath>
            </defs>

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
                  <g clipPath="url(#timeline-label-column)">
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
                      {laneCaption(bar)}
                    </text>
                  </g>
                  {/* Separates the label column from the plot, so the eye reads
                      them as two panes instead of one crowded strip. */}
                  <line
                    x1={LABEL_W - 10}
                    x2={LABEL_W - 10}
                    y1={TOP_PAD + lane * LANE_H + 6}
                    y2={TOP_PAD + (lane + 1) * LANE_H - 6}
                    stroke={theme.palette.divider}
                    strokeWidth={1}
                  />
                </g>
              );
            })}

            {/* Collapsed stretches of dead time, drawn before the data. */}
            {scale.gaps.map((gap) => (
              <g key={`gap-${gap.t0}`} aria-hidden>
                <rect
                  x={gap.x0}
                  y={TOP_PAD}
                  width={Math.max(0, gap.x1 - gap.x0)}
                  height={axisY - TOP_PAD}
                  fill={theme.palette.text.primary}
                  opacity={0.05}
                />
                {[gap.x0, gap.x1].map((x) => (
                  <line
                    key={x}
                    x1={x}
                    x2={x}
                    y1={TOP_PAD}
                    y2={axisY}
                    stroke={theme.palette.divider}
                    strokeWidth={1.5}
                  />
                ))}
                {/* A narrow gap has no room for its own duration; the label
                    would spill over the markers on either side of it. */}
                {gap.x1 - gap.x0 >= GAP_LABEL_MIN_PX && (
                  <text
                    x={(gap.x0 + gap.x1) / 2}
                    y={axisY - 6}
                    textAnchor="middle"
                    fontSize={9.5}
                    fill={theme.palette.text.secondary}
                  >
                    {humanSpan(gap.t1 - gap.t0)}
                  </text>
                )}
              </g>
            ))}

            {/* Time gridlines behind the data. */}
            {ticks.map((tick) => (
              <line
                key={`grid-${tick.t}-${tick.x}`}
                x1={tick.x}
                x2={tick.x}
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
            {ticks.map((tick) => (
              <g key={`tick-${tick.t}-${tick.x}`}>
                <line
                  x1={tick.x}
                  x2={tick.x}
                  y1={axisY}
                  y2={axisY + 5}
                  stroke={theme.palette.divider}
                  strokeWidth={1.5}
                />
                <text
                  x={tick.x}
                  y={axisY + 20}
                  textAnchor="middle"
                  fontSize={11}
                  fill={theme.palette.text.secondary}
                >
                  {dayjs(tick.t).format(tick.fmt)}
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
                  key={`${cluster.lane}-${cluster.echo ? "e" : "p"}-${i}`}
                  data-marker={cluster.echo ? "echo" : "primary"}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={(e) => {
                    cancelClose();
                    setHotLane(cluster.lane);
                    const box = (e.currentTarget as SVGGElement).getBoundingClientRect();
                    setHover({
                      cx: box.left + box.width / 2,
                      cy: box.top + box.height / 2,
                      cluster,
                    });
                  }}
                  // Moving off a marker into empty canvas used to leave the
                  // card stranded until the pointer left the whole chart.
                  onMouseLeave={scheduleClose}
                  onClick={() => onSelect(cluster.events[0])}
                >
                  {/* Generous invisible hit area — a 6px dot is hard to hover. */}
                  <circle
                    cx={cluster.x}
                    cy={cy}
                    r={cluster.echo ? 11 : 15}
                    fill="transparent"
                  />
                  {cluster.echo ? (
                    <EchoMarker x={cluster.x} y={cy} grow={grow} color={color} />
                  ) : (
                    <Marker
                      kind={cluster.kind}
                      x={cluster.x}
                      y={cy}
                      grow={grow}
                      color={color}
                      ring={theme.palette.background.paper}
                      emphasised={isSelected}
                    />
                  )}
                  {cluster.events.length > 1 && !cluster.echo && (
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
        happened at that moment. Hover to read them all, click to open the event below.
        {scale.compressed
          ? " Shaded bands are stretches with no events at all, collapsed so the busy periods have room; the label gives the time skipped."
          : ""}
      </Typography>

      {hover && (
        <ClusterTooltip
          hover={hover}
          milestoneKeys={milestoneKeys}
          onSelect={onSelect}
          onEnter={cancelClose}
          onLeave={scheduleClose}
        />
      )}
    </Box>
  );
}

/** Lane sub-caption: what is drawn here, and over how long. */
/**
 * One short line under each stage name.
 *
 * Says the same three things as before — how many events start here, how many
 * merely evidence the stage, and how long it ran — but tersely. The long form
 * ("no events start here · 1 also evidence this · 2 days") ran past the label
 * column on most screens and buried the numbers a reader scans for. "echo"
 * matches the hollow echo markers, which the "draw in every stage" toggle
 * explains.
 */
function laneCaption(
  bar: { count: number; echoes: number; from: number; to: number } | undefined,
): string {
  if (!bar) return "no events";
  const echo = bar.echoes > 0 ? ` · ${bar.echoes} echo` : "";
  if (bar.count === 0) return `none start${echo}`;
  const span = bar.to > bar.from ? humanSpan(bar.to - bar.from) : "one moment";
  return `${bar.count} event${bar.count === 1 ? "" : "s"}${echo} · ${span}`;
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

/**
 * The same event, seen from a stage it evidences but is not counted in.
 * Deliberately quiet: a short tick, no fill, no count — it is a cross
 * reference, not a second occurrence.
 */
function EchoMarker({
  x, y, grow, color,
}: {
  x: number;
  y: number;
  grow: number;
  color: string;
}) {
  const r = 4 + grow;
  return (
    <circle
      cx={x}
      cy={y}
      r={r}
      fill="none"
      stroke={color}
      strokeWidth={1.5}
      strokeDasharray="2 2"
      opacity={0.85}
    />
  );
}

/**
 * One legend key. The label carries the glossary definition on hover — the
 * legend says *which glyph* means critical, but not what the engine counts as
 * critical, and that is the part a reader new to the case actually needs.
 */
function Legend({
  shape,
  color,
  label,
  term,
}: {
  shape: string;
  color: string;
  label: string;
  term?: string;
}) {
  const glyph =
    shape === "ring"
      ? { border: `2.5px solid ${color}`, borderRadius: "50%" }
      : shape === "hollow"
        ? { border: `1.5px dashed ${color}`, borderRadius: "50%" }
        : shape === "diamond"
          ? { bgcolor: color, transform: "rotate(45deg)" }
          : { bgcolor: color, borderRadius: "50%" };
  return (
    <Stack direction="row" spacing={0.6} alignItems="center">
      <Box sx={{ width: 10, height: 10, flexShrink: 0, ...glyph }} />
      <MetricLabel name={term ?? label} label={label} variant="caption" />
    </Stack>
  );
}

/**
 * Viewport-anchored tooltip listing *every* event under the marker.
 *
 * It used to show the first four and say "+7 more", which is the worst of
 * both: the reader is told there is more and given no way to see it without
 * clicking through. It now takes pointer events, so the pointer can travel
 * into it (a grace period covers the gap), scrolls when the list is long, and
 * each row is clickable — hover to read, click to open.
 *
 * It measures itself and then clamps to the visible viewport, flipping above
 * the marker when there is no room below. Anchoring to the *viewport* rather
 * than to the chart is what stops it being clipped by the scrolling card the
 * chart lives in — an absolutely-positioned box could only guess, and got cut
 * off near the right and bottom edges.
 */
function ClusterTooltip({
  hover,
  milestoneKeys,
  onSelect,
  onEnter,
  onLeave,
}: {
  hover: Hover;
  milestoneKeys: Set<string>;
  onSelect: (event: TimelineEvent) => void;
  onEnter: () => void;
  onLeave: () => void;
}) {
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

  const { events, echo } = hover.cluster;

  return (
    <Box
      ref={ref}
      {...{ [TOOLTIP_MARKER]: "" }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      sx={{
        position: "fixed",
        left: pos?.left ?? -9999,
        top: pos?.top ?? -9999,
        // Hidden until measured, so it never flashes in the wrong place.
        visibility: pos ? "visible" : "hidden",
        zIndex: theme.zIndex.tooltip,
        width: "min(380px, calc(100vw - 16px))",
        // Long clusters scroll inside the card instead of being truncated.
        maxHeight: "min(340px, 60vh)",
        overflowY: "auto",
        overscrollBehavior: "contain",
        p: 1.5,
        borderRadius: 2,
        border: 1,
        borderColor: "divider",
        boxShadow: 8,
        bgcolor: theme.palette.mode === "dark" ? "rgba(18,26,46,0.98)" : "rgba(255,255,255,0.99)",
      }}
    >
      {(events.length > 1 || echo) && (
        <Typography
          variant="caption"
          sx={{ fontWeight: 700, display: "block", mb: 0.75 }}
        >
          {events.length > 1 ? `${events.length} events at this moment` : "Also evidences this stage"}
          {events.length > 1 && echo ? " · also evidence this stage" : ""}
        </Typography>
      )}
      <Stack spacing={1.25}>
        {events.map((event, i) => {
          const kind = event.critical
            ? "critical"
            : milestoneKeys.has(`${event.timestamp}|${event.description}`)
              ? "milestone"
              : "event";
          const color =
            kind === "critical" ? BRAND.critical : kind === "milestone" ? BRAND.high : BRAND.primary;
          return (
            <Box
              key={`${event.timestamp}-${i}`}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(event)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(event);
                }
              }}
              sx={{
                cursor: "pointer",
                borderRadius: 1,
                px: 0.75,
                py: 0.5,
                mx: -0.75,
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.25 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: color, flexShrink: 0 }} />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {dayjs(event.timestamp).format("MMM D, YYYY HH:mm")}
                  {event.timestamp_inferred ? " (inferred)" : ""}
                </Typography>
              </Stack>
              <Typography
                variant="body2"
                sx={{ fontWeight: 600, overflowWrap: "anywhere" }}
              >
                {eventTitle(event)}
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
                  sx={{ color: BRAND.critical, display: "block", overflowWrap: "anywhere" }}
                >
                  Critical: {event.critical_reasons.join("; ")}
                </Typography>
              )}
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}
