import { describe, expect, it } from "vitest";

import { buildTicks, buildTimeScale, humanSpan } from "../timeScale";

const X0 = 200;
const W = 800;

const at = (iso: string) => new Date(iso).getTime();

describe("buildTimeScale", () => {
  it("spreads evenly paced events linearly, with nothing collapsed", () => {
    const times = [
      at("2026-01-01T10:00:00Z"),
      at("2026-01-01T11:00:00Z"),
      at("2026-01-01T12:00:00Z"),
      at("2026-01-01T13:00:00Z"),
    ];
    const scale = buildTimeScale(times, X0, W);

    expect(scale.compressed).toBe(false);
    expect(scale.gaps).toHaveLength(0);
    expect(scale.x(times[0])).toBeCloseTo(X0, 5);
    expect(scale.x(times[3])).toBeCloseTo(X0 + W, 5);
    // Equal spacing in time must stay equal spacing in pixels.
    const step = scale.x(times[1]) - scale.x(times[0]);
    expect(scale.x(times[2]) - scale.x(times[1])).toBeCloseTo(step, 5);
  });

  it("collapses a dead stretch so the busy period gets the width", () => {
    // The shape of a real case: one stray dated document months before the
    // burst of events that is the actual attack.
    const burst = [
      at("2026-08-03T14:00:00Z"),
      at("2026-08-03T14:01:00Z"),
      at("2026-08-03T14:02:00Z"),
      at("2026-08-03T14:03:00Z"),
    ];
    const times = [at("2026-01-04T00:00:00Z"), ...burst];

    const linear = buildTimeScale(times, X0, W, { compress: false });
    const scale = buildTimeScale(times, X0, W);

    expect(scale.compressed).toBe(true);
    expect(scale.gaps).toHaveLength(1);

    // Linearly the whole four-minute burst is sub-pixel; compressed it is
    // most of the plot — which is the entire point of the exercise.
    const linearBurst = linear.x(burst[3]) - linear.x(burst[0]);
    const scaledBurst = scale.x(burst[3]) - scale.x(burst[0]);
    expect(linearBurst).toBeLessThan(1);
    expect(scaledBurst).toBeGreaterThan(W * 0.5);
  });

  it("keeps time strictly left to right across a collapsed gap", () => {
    const times = [
      at("2026-01-01T00:00:00Z"),
      at("2026-01-01T00:01:00Z"),
      at("2026-06-01T00:00:00Z"),
      at("2026-06-01T00:01:00Z"),
    ];
    const scale = buildTimeScale(times, X0, W);
    const xs = times.map(scale.x);
    for (let i = 1; i < xs.length; i += 1) expect(xs[i]).toBeGreaterThan(xs[i - 1]);
    expect(xs[0]).toBeCloseTo(X0, 5);
    expect(xs[xs.length - 1]).toBeCloseTo(X0 + W, 5);
  });

  it("never lets collapsed gaps eat the plot, however many there are", () => {
    const times: number[] = [];
    for (let month = 0; month < 10; month += 1) {
      times.push(at(`2026-0${(month % 9) + 1}-01T00:00:00Z`) + month * 86400_000 * 31);
    }
    const scale = buildTimeScale(times, X0, W);
    const gapPx = scale.gaps.reduce((sum, g) => sum + (g.x1 - g.x0), 0);
    expect(gapPx).toBeLessThanOrEqual(W * 0.4 + 0.001);
  });

  it("gives a single instant a readable axis instead of dividing by zero", () => {
    const t = at("2026-01-01T10:00:00Z");
    const scale = buildTimeScale([t, t, t], X0, W);
    expect(Number.isFinite(scale.x(t))).toBe(true);
    expect(scale.x(t)).toBeCloseTo(X0 + W / 2, 0);
  });

  it("clamps anything outside the domain to the plot edges", () => {
    const times = [at("2026-01-01T10:00:00Z"), at("2026-01-01T12:00:00Z")];
    const scale = buildTimeScale(times, X0, W);
    expect(scale.x(at("2020-01-01T00:00:00Z"))).toBeCloseTo(X0, 5);
    expect(scale.x(at("2030-01-01T00:00:00Z"))).toBeCloseTo(X0 + W, 5);
  });

  it("leaves the axis honest when compression is turned off", () => {
    const times = [
      at("2026-01-04T00:00:00Z"),
      at("2026-08-03T14:00:00Z"),
      at("2026-08-03T14:01:00Z"),
    ];
    const scale = buildTimeScale(times, X0, W, { compress: false });
    expect(scale.compressed).toBe(false);
    expect(scale.gaps).toHaveLength(0);
  });
});

describe("buildTicks", () => {
  it("labels each active stretch and never collides two labels", () => {
    const times = [
      at("2026-01-01T00:00:00Z"),
      at("2026-01-01T00:05:00Z"),
      at("2026-06-01T00:00:00Z"),
      at("2026-06-01T00:05:00Z"),
    ];
    const scale = buildTimeScale(times, X0, W);
    const ticks = buildTicks(scale);

    expect(ticks.length).toBeGreaterThan(1);
    for (let i = 1; i < ticks.length; i += 1) {
      expect(ticks[i].x).toBeGreaterThan(ticks[i - 1].x);
    }
    // Both sides of the collapsed gap must carry at least one label,
    // otherwise half the chart has no readable time at all.
    const gap = scale.gaps[0];
    expect(ticks.some((t) => t.x <= gap.x0)).toBe(true);
    expect(ticks.some((t) => t.x >= gap.x1)).toBe(true);
  });

  it("picks a format matching the range it is labelling", () => {
    const dayScale = buildTimeScale(
      [at("2026-01-01T00:00:00Z"), at("2026-03-01T00:00:00Z")],
      X0,
      W,
    );
    expect(buildTicks(dayScale)[0].fmt).toBe("MMM D, YYYY");

    const minuteScale = buildTimeScale(
      [at("2026-01-01T00:00:00Z"), at("2026-01-01T00:00:30Z")],
      X0,
      W,
    );
    expect(buildTicks(minuteScale)[0].fmt).toBe("HH:mm:ss");
  });
});

describe("humanSpan", () => {
  it.each([
    [500, "instant"],
    [45_000, "45s"],
    [90_000, "2m"],
    [2 * 3600_000, "2h"],
    [2.5 * 3600_000, "2h 30m"],
    [3 * 86400_000, "3d"],
    [90 * 86400_000, "3 months"],
    [800 * 86400_000, "2.2 years"],
  ])("renders %ims as %s", (ms, expected) => {
    expect(humanSpan(ms)).toBe(expected);
  });
});
