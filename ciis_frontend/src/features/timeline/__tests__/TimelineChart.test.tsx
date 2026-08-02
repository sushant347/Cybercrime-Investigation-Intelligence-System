import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/testUtils";
import type { TimelineEvent } from "@/types";

import { TimelineChart } from "../TimelineChart";

/**
 * jsdom has no layout engine, so the chart would measure a 0px-wide container
 * and draw nothing. Stub the measurement (and ResizeObserver) per test —
 * `restoreMocks` in vite.config clears spies between tests, so this cannot be
 * hoisted to `beforeAll`.
 */
beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 900, height: 120, top: 40, left: 20, right: 920, bottom: 160, x: 20, y: 40,
    toJSON: () => ({}),
  });
});

const event = (over: Partial<TimelineEvent>): TimelineEvent => ({
  timestamp: "2026-01-01T10:00:00Z",
  event_type: "evidence_captured",
  evidence_id: "EVID_00001",
  description: "Phishing SMS received",
  stages: [],
  critical: false,
  critical_reasons: [],
  ...over,
});

const draw = (events: TimelineEvent[], milestones = new Set<string>()) =>
  renderWithProviders(
    <TimelineChart
      events={events}
      milestoneKeys={milestones}
      selected={null}
      onSelect={() => {}}
    />,
  );

/** Lane names are the bold 12.5px labels in the left column of each row. */
const laneLabels = (container: HTMLElement) =>
  [...container.querySelectorAll('svg text[font-weight="700"][font-size="12.5"]')].map(
    (n) => n.textContent,
  );

/** Marker groups carry the invisible r=15 hit area; lane rows do not. */
const markers = (container: HTMLElement) =>
  [...container.querySelectorAll("svg g")].filter((g) => g.querySelector('circle[r="15"]'));

describe("TimelineChart", () => {
  it("draws one lane per attack stage, in first-occurrence order", () => {
    const { container } = draw([
      event({ timestamp: "2026-01-01T12:00:00Z", stages: ["credential_theft"] }),
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"] }),
    ]);
    // Initial contact happened first, so it is the top lane regardless of input order.
    expect(laneLabels(container)).toEqual(["Initial Contact", "Credential Theft"]);
  });

  it("puts events the engine could not attribute in an 'Unattributed' lane", () => {
    const { container } = draw([event({ stages: [] })]);
    expect(laneLabels(container)).toEqual(["Unattributed"]);
  });

  it("keeps the unattributed lane at the bottom, below the real stages", () => {
    const { container } = draw([
      event({ timestamp: "2026-01-01T09:00:00Z", stages: [] }),
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"] }),
    ]);
    expect(laneLabels(container)).toEqual(["Initial Contact", "Unattributed"]);
  });

  it("labels each lane with its event count and duration", () => {
    const { container } = draw([
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"] }),
      event({ timestamp: "2026-01-01T12:30:00Z", stages: ["initial_contact"] }),
    ]);
    expect(container.textContent).toContain("2 events · 2h 30m");
  });

  it("merges simultaneous events into one marker carrying a count", () => {
    const { container } = draw([
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"], description: "A" }),
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"], description: "B" }),
      event({ timestamp: "2026-01-01T18:00:00Z", stages: ["initial_contact"], description: "C" }),
    ]);
    const drawn = markers(container);
    expect(drawn).toHaveLength(2); // three events, two distinct moments
    expect(drawn[0].querySelector("text")?.textContent).toBe("2");
  });

  it("shows a viewport-anchored tooltip on hover", () => {
    const { container } = draw([
      event({
        stages: ["credential_theft"],
        description: "Victim clicked the credential-harvesting link",
        critical: true,
        critical_reasons: ["Credential entry detected"],
      }),
    ]);

    fireEvent.mouseEnter(markers(container)[0]);

    expect(
      screen.getByText("Victim clicked the credential-harvesting link"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Credential entry detected/)).toBeInTheDocument();

    // `position: fixed` is what lets it clamp to the viewport rather than be
    // clipped by the scrolling card the chart sits in.
    const tip = [...container.querySelectorAll("div")].find(
      (node) => getComputedStyle(node).position === "fixed",
    );
    expect(tip).toBeDefined();
    expect(tip!.textContent).toContain("Victim clicked the credential-harvesting link");
  });

  it("reports unresolved timestamps instead of guessing a position", () => {
    draw([event({ timestamp: "" }), event({ timestamp: "not-a-date" })]);
    expect(screen.getByText(/No events with a resolved timestamp to plot/)).toBeInTheDocument();
    expect(screen.getByText(/2 event\(s\) have no usable time/)).toBeInTheDocument();
  });

  it("counts undated events alongside the plotted ones", () => {
    draw([event({ stages: ["initial_contact"] }), event({ timestamp: "" })]);
    expect(screen.getByText(/1 without a usable time/)).toBeInTheDocument();
  });

  it("distinguishes severity by shape, not colour alone", () => {
    const { container } = draw([
      event({ timestamp: "2026-01-01T10:00:00Z", stages: ["initial_contact"], critical: true }),
      event({ timestamp: "2026-01-01T20:00:00Z", stages: ["initial_contact"] }),
    ]);
    const drawn = markers(container);
    // Critical draws a thick ring; a plain event does not.
    expect(drawn[0].querySelector('circle[stroke-width="3.5"]')).toBeTruthy();
    expect(drawn[1].querySelector('circle[stroke-width="3.5"]')).toBeNull();
  });

  it("draws a milestone as a rotated square so it reads without colour", () => {
    const stamp = "2026-01-01T10:00:00Z";
    const { container } = draw(
      [event({ timestamp: stamp, stages: ["initial_contact"], description: "Money sent" })],
      new Set([`${stamp}|Money sent`]),
    );
    expect(markers(container)[0].querySelector("rect[transform^='rotate(45']")).toBeTruthy();
  });
});
