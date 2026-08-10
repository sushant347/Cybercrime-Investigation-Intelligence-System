import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TimelineEvent } from "@/types";

import { TimelineChart } from "../TimelineChart";

const event = (overrides: Partial<TimelineEvent> = {}): TimelineEvent => ({
  timestamp: "2026-06-11T10:42:00Z",
  event_type: "evidence_event",
  evidence_id: "EVID_001",
  file_name: "message.png",
  description: "Victim received a payment request",
  time_source: "content_labeled_date_time",
  confidence: "high",
  timestamp_inferred: false,
  stages: ["initial_contact"],
  critical: false,
  critical_reasons: [],
  ...overrides,
});

function draw(
  events: TimelineEvent[],
  milestoneKeys = new Set<string>(),
  onSelect = vi.fn(),
  selected: TimelineEvent | null = null,
) {
  return {
    ...render(
      <TimelineChart
        events={events}
        milestoneKeys={milestoneKeys}
        selected={selected}
        onSelect={onSelect}
      />,
    ),
    onSelect,
  };
}

const eventCards = () => screen.queryAllByTestId("timeline-event");

describe("TimelineChart incident story", () => {
  it("renders each event once in chronological order", () => {
    draw([
      event({ timestamp: "2026-06-15T05:45:00Z", evidence_id: "EVID_LATE", description: "Complaint filed" }),
      event({ timestamp: "2026-06-11T10:42:00Z", evidence_id: "EVID_EARLY", description: "Payment requested" }),
    ]);

    expect(eventCards().map((card) => card.textContent)).toEqual([
      expect.stringContaining("Payment requested"),
      expect.stringContaining("Complaint filed"),
    ]);
    expect(screen.getByText(/Cards are equally spaced/)).toBeInTheDocument();
  });

  it("shows all stages as readable chips without duplicating an event", () => {
    draw([event({ stages: ["initial_contact", "social_engineering", "financial_transaction"] })]);

    expect(eventCards()).toHaveLength(1);
    expect(screen.getByText("Initial Contact")).toBeInTheDocument();
    expect(screen.getByText("Social Engineering")).toBeInTheDocument();
    expect(screen.getByText("Money Movement")).toBeInTheDocument();
  });

  it("groups simultaneous events into one moment while keeping both selectable", () => {
    draw([
      event({ evidence_id: "EVID_001", description: "First finding" }),
      event({ evidence_id: "EVID_002", description: "Second finding" }),
    ]);

    expect(screen.getAllByTestId("timeline-moment")).toHaveLength(1);
    expect(screen.getByText("2 events at this moment")).toBeInTheDocument();
    expect(eventCards()).toHaveLength(2);
  });

  it("opens the exact finding selected by the investigator", () => {
    const second = event({ evidence_id: "EVID_002", description: "Second finding" });
    const { onSelect } = draw([event(), second]);

    fireEvent.click(screen.getByRole("button", { name: /Second finding/ }));
    expect(onSelect).toHaveBeenCalledWith(second);
  });

  it("distinguishes critical and milestone moments by accessible labels", () => {
    const stampA = "2026-06-11T10:42:00Z";
    const stampB = "2026-06-12T10:42:00Z";
    draw(
      [
        event({ timestamp: stampA, critical: true, description: "Critical transfer" }),
        event({ timestamp: stampB, evidence_id: "EVID_002", description: "Complaint milestone" }),
      ],
      new Set([`${stampB}|Complaint milestone`]),
    );

    expect(screen.getByLabelText("Critical moment")).toBeInTheDocument();
    expect(screen.getByLabelText("Milestone")).toBeInTheDocument();
    expect(screen.getByText("Priority review")).toBeInTheDocument();
  });

  it("shows timestamp basis and confidence on the finding", () => {
    draw([event({ timestamp_inferred: true, confidence: "medium", time_source: "content_date_only" })]);
    expect(screen.getByText("Inferred · medium")).toBeInTheDocument();
    expect(screen.getByText("0 recorded")).toBeInTheDocument();
    expect(screen.getByText("1 inferred")).toBeInTheDocument();
  });

  it("reports unresolved timestamps without inventing a position", () => {
    draw([event({ timestamp: "" }), event({ timestamp: "not-a-date", evidence_id: "EVID_002" })]);
    expect(screen.getByText("No evidence-derived event times")).toBeInTheDocument();
    expect(screen.getByText(/2 event\(s\) have no usable timestamp/)).toBeInTheDocument();
  });

  it("progressively discloses large timelines", async () => {
    const user = userEvent.setup();
    draw(Array.from({ length: 10 }, (_, index) => event({
      evidence_id: `EVID_${index}`,
      timestamp: `2026-06-${String(index + 1).padStart(2, "0")}T10:42:00Z`,
      description: `Finding ${index}`,
    })));

    expect(eventCards()).toHaveLength(8);
    await user.click(screen.getByRole("button", { name: "Show 2 more moments" }));
    expect(eventCards()).toHaveLength(10);
    expect(screen.getByRole("button", { name: "Show concise story" })).toBeInTheDocument();
  });

  it("uses the readable file title when the engine description is boilerplate", () => {
    draw([event({
      file_name: "bank_transactions.csv",
      description: "Evidence EVID_001 (bank_transactions.csv); stages: financial_transaction",
    })]);
    const card = eventCards()[0];
    expect(within(card).getAllByText("bank_transactions.csv").length).toBeGreaterThan(0);
  });
});

describe("TimelineChart acquisition provenance", () => {
  const incident = event({
    evidence_id: "EVID_EVENT",
    stages: ["financial_transaction"],
  });
  const acquisition = event({
    timestamp: "2026-08-07T05:20:00Z",
    evidence_id: "EVID_ACQUIRED",
    description: "Uploaded message",
    time_source: "upload_time_fallback",
    timestamp_inferred: true,
    confidence: "low",
  });

  it("keeps acquisition records out of the incident story by default", () => {
    draw([incident, acquisition]);
    expect(screen.getByText("1 incident event")).toBeInTheDocument();
    expect(eventCards()).toHaveLength(1);
    expect(screen.getByText(/1 upload timestamp is kept out/)).toBeInTheDocument();
  });

  it("adds acquisition records only when explicitly requested", async () => {
    const user = userEvent.setup();
    draw([incident, acquisition]);

    await user.click(screen.getByRole("checkbox", { name: /include acquisition timestamps/i }));

    expect(screen.getByText("2 chronology records")).toBeInTheDocument();
    expect(eventCards()).toHaveLength(2);
    expect(screen.getByText("Acquisition · low")).toBeInTheDocument();
    expect(screen.getByText(/not incident events/)).toBeInTheDocument();
  });
});
