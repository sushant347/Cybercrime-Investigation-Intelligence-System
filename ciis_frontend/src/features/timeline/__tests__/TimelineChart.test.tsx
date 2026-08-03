import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const draw = (
  events: TimelineEvent[],
  milestones = new Set<string>(),
  onSelect: (event: TimelineEvent) => void = () => {},
) =>
  renderWithProviders(
    <TimelineChart
      events={events}
      milestoneKeys={milestones}
      selected={null}
      onSelect={onSelect}
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

/** Echoes carry a smaller hit area; `markers()` therefore counts only solids. */
const echoes = (container: HTMLElement) =>
  [...container.querySelectorAll('svg g[data-marker="echo"]')];

describe("TimelineChart multi-stage events", () => {
  it("draws one solid marker per event, whatever it evidences", () => {
    const { container } = draw([
      event({
        stages: ["initial_contact", "social_engineering", "financial_transaction"],
        description: "One document evidencing three stages",
      }),
    ]);

    // Three lanes, because all three stages are evidenced...
    expect(laneLabels(container)).toEqual([
      "Initial Contact",
      "Social Engineering",
      "Money Movement",
    ]);
    // ...but one event is one marker. It used to be drawn three times, which
    // made every lane count and the total both wrong.
    expect(markers(container)).toHaveLength(1);
    expect(echoes(container)).toHaveLength(2);
  });

  it("puts the marker in the stage the event enters the story at", () => {
    const { container } = draw([
      event({ stages: ["financial_transaction", "initial_contact"] }),
    ]);
    // Lane 0 is Initial Contact; the solid marker belongs to it.
    const solid = markers(container)[0];
    const lanes = [...container.querySelectorAll("svg g")];
    expect(lanes.indexOf(solid)).toBeGreaterThan(-1);
    expect(solid.getAttribute("data-marker")).toBe("primary");
    expect(echoes(container)).toHaveLength(1);
  });

  it("says how many events merely evidence a stage, without counting them twice", () => {
    const { container } = draw([
      event({ stages: ["initial_contact", "credential_theft"] }),
      event({ timestamp: "2026-01-01T11:00:00Z", stages: ["initial_contact"] }),
    ]);
    expect(container.textContent).toContain("2 events");
    expect(container.textContent).toContain("no events start here · 1 also evidence this");
  });

  it("draws a full marker in every stage when asked to", async () => {
    const user = userEvent.setup();
    const { container } = draw([
      event({ stages: ["initial_contact", "social_engineering", "financial_transaction"] }),
    ]);

    await user.click(screen.getByRole("checkbox", { name: /draw in every stage/i }));

    expect(markers(container)).toHaveLength(3);
    expect(echoes(container)).toHaveLength(0);
  });
});

describe("TimelineChart time axis", () => {
  /** A stray dated document months before the burst that is the real attack. */
  const skewed = [
    event({ timestamp: "2026-01-01T00:00:00Z", stages: ["initial_contact"] }),
    event({ timestamp: "2026-06-01T00:00:00Z", stages: ["initial_contact"] }),
    event({ timestamp: "2026-06-01T00:01:00Z", stages: ["initial_contact"] }),
    event({ timestamp: "2026-06-01T00:02:00Z", stages: ["initial_contact"] }),
  ];

  it("collapses dead stretches and labels the time skipped", () => {
    const { container } = draw(skewed);
    expect(container.textContent).toContain("5 months");
    expect(container.textContent).toMatch(/Shaded bands are stretches with no events/);
  });

  it("separates a burst that a linear axis would stack in one pixel", () => {
    const { container } = draw(skewed);
    const xs = markers(container)
      .map((g) => Number(g.querySelector("circle")?.getAttribute("cx") ?? 0))
      .sort((a, b) => a - b);
    expect(xs).toHaveLength(4);
    // The three events a minute apart must be visibly apart, not merged.
    expect(xs[3] - xs[1]).toBeGreaterThan(40);
  });

  it("goes back to a true-to-scale axis on request", async () => {
    const user = userEvent.setup();
    const { container } = draw(skewed);

    expect(markers(container)).toHaveLength(4);

    await user.click(screen.getByRole("checkbox", { name: /compress quiet periods/i }));

    expect(container.textContent).not.toMatch(/Shaded bands are stretches with no events/);
    // Un-compressed, the one-minute burst collapses into a single marker —
    // which is exactly the picture the compressed axis exists to avoid.
    expect(markers(container).length).toBeLessThan(4);
  });
});

describe("TimelineChart hover card", () => {
  const cluster = Array.from({ length: 7 }, (_, i) =>
    event({ stages: ["initial_contact"], description: `Event number ${i + 1}` }),
  );

  it("shows every event under the marker, not the first few", () => {
    const { container } = draw(cluster);
    fireEvent.mouseEnter(markers(container)[0]);

    expect(screen.getByText("7 events at this moment")).toBeInTheDocument();
    for (let i = 1; i <= 7; i += 1) {
      expect(screen.getByText(`Event number ${i}`)).toBeInTheDocument();
    }
    // The old card stopped at four and offered "+3 more" with no way to see them.
    expect(screen.queryByText(/more — click the marker/)).not.toBeInTheDocument();
  });

  it("stays open while the pointer travels into it", () => {
    const { container } = draw(cluster);
    const marker = markers(container)[0];

    fireEvent.mouseEnter(marker);
    fireEvent.mouseLeave(marker);
    // A grace period keeps it alive across the gap between marker and card.
    const card = screen.getByText("7 events at this moment");
    fireEvent.mouseEnter(card.parentElement!);
    expect(screen.getByText("Event number 5")).toBeInTheDocument();
  });

  it("opens the event that was clicked, not the first in the cluster", () => {
    const onSelect = vi.fn();
    const { container } = draw(cluster, new Set(), onSelect);

    fireEvent.mouseEnter(markers(container)[0]);
    fireEvent.click(screen.getByText("Event number 5"));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ description: "Event number 5" }),
    );
  });

  it("reads the engine's boilerplate description as the file it came from", () => {
    const { container } = draw([
      event({
        stages: ["initial_contact"],
        evidence_id: "EVID_00023",
        description: "Evidence EVID_00023 (bank_transactions.csv); stages: financial_transaction",
      }),
    ]);
    fireEvent.mouseEnter(markers(container)[0]);
    expect(screen.getByText("bank_transactions.csv")).toBeInTheDocument();
  });
});
