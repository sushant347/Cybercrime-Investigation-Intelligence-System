/**
 * Time scale for the attack timeline.
 *
 * A straight linear axis is the wrong instrument for this data. A real case
 * looks like: one document dated January, one dated June, then seven events
 * inside the same minute in August. On a linear axis 99% of the width is
 * empty months and the seven events that *are* the attack land on top of each
 * other in less than a pixel. The chart is then technically correct and
 * completely unreadable — which is exactly the complaint.
 *
 * So the axis is piecewise linear: stretches of time containing no events at
 * all are collapsed to a fixed narrow band, marked with a break and labelled
 * with the duration skipped, and the remaining width is given to the periods
 * where something actually happened. Time still runs strictly left to right
 * and nothing is hidden — only the empty space is rationed.
 *
 * `compress: false` returns a plain linear scale, for when true proportion
 * matters more than legibility (printing into a case file, say).
 */

/** Pixels given to one collapsed gap. */
const GAP_PX = 44;
/** Collapsed gaps may never eat more than this share of the plot. */
const MAX_GAP_SHARE = 0.4;
/** A gap must be at least this fraction of the total span to be collapsed. */
const MIN_GAP_SHARE = 0.08;
/** …and this many times the typical spacing, so evenly spread events survive. */
const GAP_VS_TYPICAL = 4;
/** Room reserved per extra distinct moment inside an active stretch. */
const PX_PER_MOMENT = 26;
const MAX_MOMENT_RESERVE = 140;

export interface Segment {
  kind: "active" | "gap";
  /** Time range covered. */
  t0: number;
  t1: number;
  /** Pixel range covered. */
  x0: number;
  x1: number;
}

export interface TimeScale {
  /** Map a timestamp to an x pixel. Clamped to the domain. */
  x: (t: number) => number;
  segments: Segment[];
  /** Just the collapsed stretches, for drawing break marks. */
  gaps: Segment[];
  /** True when at least one stretch was collapsed. */
  compressed: boolean;
  min: number;
  max: number;
}

/** Human duration ("4m", "3h 20m", "2d"). */
export function humanSpan(ms: number): string {
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
  const days = hours / 24;
  if (days < 31) {
    const d = Math.floor(days);
    const h = Math.round(hours - d * 24);
    return h ? `${d}d ${h}h` : `${d}d`;
  }
  const months = days / 30.44;
  if (months < 12) {
    const mo = Math.round(months);
    return `${mo} month${mo === 1 ? "" : "s"}`;
  }
  const years = days / 365.25;
  return `${years.toFixed(years < 10 ? 1 : 0)} years`;
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * @param times  every event timestamp in ms (unsorted, duplicates fine)
 * @param x0     left edge of the plot area in pixels
 * @param width  width of the plot area in pixels
 */
export function buildTimeScale(
  times: number[],
  x0: number,
  width: number,
  { compress = true }: { compress?: boolean } = {},
): TimeScale {
  const unique = [...new Set(times)].sort((a, b) => a - b);

  // A single instant still deserves a readable axis: give it a minute either
  // side rather than dividing by a zero span.
  if (unique.length === 0) {
    const now = Date.now();
    return linear(now - 30_000, now + 30_000, x0, width);
  }
  if (unique.length === 1) {
    return linear(unique[0] - 30_000, unique[0] + 30_000, x0, width);
  }

  const min = unique[0];
  const max = unique[unique.length - 1];
  if (!compress) return linear(min, max, x0, width);

  const deltas: number[] = [];
  for (let i = 1; i < unique.length; i += 1) deltas.push(unique[i] - unique[i - 1]);
  const span = max - min;
  const typical = median(deltas.filter((d) => d > 0)) || 0;

  // A gap is worth collapsing only if it is both a big slice of the whole
  // span *and* far larger than the usual spacing. Requiring both stops an
  // evenly-paced timeline being chopped up for no reason.
  const isDead = (d: number) =>
    d / span >= MIN_GAP_SHARE && (typical === 0 || d >= typical * GAP_VS_TYPICAL);

  interface Raw {
    kind: "active" | "gap";
    t0: number;
    t1: number;
    moments: number;
  }
  const raw: Raw[] = [];
  let current: Raw = { kind: "active", t0: unique[0], t1: unique[0], moments: 1 };
  for (let i = 1; i < unique.length; i += 1) {
    const delta = unique[i] - unique[i - 1];
    if (isDead(delta)) {
      raw.push(current);
      raw.push({ kind: "gap", t0: unique[i - 1], t1: unique[i], moments: 0 });
      current = { kind: "active", t0: unique[i], t1: unique[i], moments: 1 };
    } else {
      current.t1 = unique[i];
      current.moments += 1;
    }
  }
  raw.push(current);

  const gapCount = raw.filter((s) => s.kind === "gap").length;
  if (gapCount === 0) return linear(min, max, x0, width);

  const gapPx = Math.min(GAP_PX, (width * MAX_GAP_SHARE) / gapCount);
  const actives = raw.filter((s) => s.kind === "active");
  let activeBudget = width - gapPx * gapCount;

  // Each active stretch first reserves room for the moments inside it, so a
  // five-second burst of ten events is not crushed by a neighbouring stretch
  // that happens to span three days.
  const reserve = actives.map((s) =>
    Math.min(MAX_MOMENT_RESERVE, Math.max(0, s.moments - 1) * PX_PER_MOMENT),
  );
  const reserveTotal = reserve.reduce((a, b) => a + b, 0);
  let scale = 1;
  if (reserveTotal > activeBudget * 0.75) scale = (activeBudget * 0.75) / reserveTotal;
  const reserved = reserve.map((r) => r * scale);
  activeBudget -= reserved.reduce((a, b) => a + b, 0);

  const durationTotal = actives.reduce((sum, s) => sum + (s.t1 - s.t0), 0);

  const segments: Segment[] = [];
  let cursor = x0;
  let activeIndex = 0;
  for (const seg of raw) {
    let px: number;
    if (seg.kind === "gap") {
      px = gapPx;
    } else {
      const share =
        durationTotal > 0
          ? (activeBudget * (seg.t1 - seg.t0)) / durationTotal
          : activeBudget / actives.length;
      px = reserved[activeIndex] + share;
      activeIndex += 1;
    }
    segments.push({ kind: seg.kind, t0: seg.t0, t1: seg.t1, x0: cursor, x1: cursor + px });
    cursor += px;
  }
  // Absorb rounding drift so the last segment lands exactly on the right edge.
  if (segments.length) segments[segments.length - 1].x1 = x0 + width;

  return {
    x: makeLookup(segments, min, max, x0, width),
    segments,
    gaps: segments.filter((s) => s.kind === "gap"),
    compressed: true,
    min,
    max,
  };
}

function linear(min: number, max: number, x0: number, width: number): TimeScale {
  const span = Math.max(1, max - min);
  const segments: Segment[] = [
    { kind: "active", t0: min, t1: max, x0, x1: x0 + width },
  ];
  return {
    x: (t: number) => x0 + ((Math.min(max, Math.max(min, t)) - min) / span) * width,
    segments,
    gaps: [],
    compressed: false,
    min,
    max,
  };
}

/** Binary-search the segment holding `t`, then interpolate inside it. */
function makeLookup(
  segments: Segment[],
  min: number,
  max: number,
  x0: number,
  width: number,
): (t: number) => number {
  return (input: number) => {
    const t = Math.min(max, Math.max(min, input));
    let lo = 0;
    let hi = segments.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (t > segments[mid].t1) lo = mid + 1;
      else hi = mid;
    }
    const seg = segments[lo];
    if (!seg) return x0 + width;
    const span = seg.t1 - seg.t0;
    if (span <= 0) return seg.x0;
    return seg.x0 + ((t - seg.t0) / span) * (seg.x1 - seg.x0);
  };
}

const SEC = 1000;
const MIN = 60 * SEC;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;
const TICK_STEPS = [
  SEC, 5 * SEC, 15 * SEC, 30 * SEC,
  MIN, 5 * MIN, 15 * MIN, 30 * MIN,
  HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
  DAY, 2 * DAY, 7 * DAY, 14 * DAY, 30 * DAY, 90 * DAY, 365 * DAY,
];

export interface Tick {
  t: number;
  x: number;
  fmt: string;
}

/**
 * Axis ticks, generated per active segment.
 *
 * Ticks are placed on round times inside each stretch and then thinned so no
 * two labels collide — a compressed axis has segments of wildly different
 * pixel-per-second scales, so a single global step cannot work.
 */
export function buildTicks(scale: TimeScale, minLabelGap = 92): Tick[] {
  const out: Tick[] = [];

  for (const seg of scale.segments) {
    if (seg.kind !== "active") continue;
    const px = seg.x1 - seg.x0;
    const span = seg.t1 - seg.t0;

    if (span <= 0 || px < 40) {
      // A single moment (or a sliver): label it once, at its own position.
      out.push({ t: seg.t0, x: seg.x0, fmt: pickFormat(scale.max - scale.min) });
      continue;
    }
    const target = Math.max(1, Math.floor(px / minLabelGap));
    const step = TICK_STEPS.find((s) => s >= span / target) ?? TICK_STEPS[TICK_STEPS.length - 1];
    const fmt = pickFormat(span);
    for (let t = Math.ceil(seg.t0 / step) * step; t <= seg.t1; t += step) {
      out.push({ t, x: scale.x(t), fmt });
    }
    // A stretch wide enough to matter but with no round tick inside it still
    // needs an anchor, or a whole burst of activity goes unlabelled.
    if (!out.some((tick) => tick.x >= seg.x0 && tick.x <= seg.x1)) {
      out.push({ t: seg.t0, x: seg.x0, fmt });
    }
  }

  // Thin collisions, keeping the leftmost of any overlapping pair.
  out.sort((a, b) => a.x - b.x);
  const kept: Tick[] = [];
  for (const tick of out) {
    if (!kept.length || tick.x - kept[kept.length - 1].x >= minLabelGap * 0.62) {
      kept.push(tick);
    }
  }
  return kept;
}

function pickFormat(span: number): string {
  if (span < MIN) return "HH:mm:ss";
  if (span < DAY) return "MMM D, HH:mm";
  return "MMM D, YYYY";
}
