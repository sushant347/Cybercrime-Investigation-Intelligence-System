import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/testUtils";
import type { TimelineAnalysis, TimelineEvent } from "@/types";

import { TimelineTab } from "../TimelineTab";

const timeline = vi.hoisted(() => vi.fn());
vi.mock("@/api", () => ({ investigationApi: { timeline } }));

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  // jsdom implements neither of these; the tab calls both while rendering.
  Element.prototype.scrollIntoView = vi.fn();
});

const event = (over: Partial<TimelineEvent>): TimelineEvent => ({
  timestamp: "2026-01-01T10:00:00Z",
  event_type: "evidence_acquired",
  evidence_id: "EVID_00001",
  description: "Phishing SMS received",
  stages: ["initial_contact"],
  critical: false,
  critical_reasons: [],
  ...over,
});

const report = (events: TimelineEvent[]): TimelineAnalysis => ({
  case_id: "CASE_1",
  events,
  attack_stages: [],
  stage_progression: [],
  progression_consistent: true,
  milestones: [],
  critical_events: [],
  summary: "",
  statistics: {},
  analysis_time_ms: 1,
});

describe("TimelineTab event details", () => {
  it("opens the detail underneath the event, not beside it", async () => {
    timeline.mockResolvedValue({
      report: report([
        event({
          evidence_id: "EVID_00042",
          description: "Victim asked for an OTP",
          critical: true,
          critical_reasons: ["Credential request detected"],
        }),
      ]),
    });

    const user = userEvent.setup();
    renderWithProviders(<TimelineTab caseId="CASE_1" />);

    const row = await screen.findByRole("button", { expanded: false });
    // Nothing is shown until the investigator asks for it.
    expect(screen.queryByText("Why this is critical")).not.toBeInTheDocument();
    expect(screen.getAllByText("Victim asked for an OTP")).toHaveLength(1);

    await user.click(row);

    await waitFor(() =>
      expect(screen.getByText("Why this is critical")).toBeInTheDocument(),
    );
    expect(row).toHaveAttribute("aria-expanded", "true");

    // The detail must be a *sibling below* the summary row, sharing its
    // container — that is what makes it read downward rather than off to
    // the side.
    const detail = screen.getByText("Credential request detected");
    expect(row.parentElement?.contains(detail)).toBe(true);
    expect(row.contains(detail)).toBe(false);
    expect(
      row.compareDocumentPosition(detail) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("collapses again when the same event is clicked twice", async () => {
    timeline.mockResolvedValue({ report: report([event({})]) });

    const user = userEvent.setup();
    renderWithProviders(<TimelineTab caseId="CASE_1" />);

    const row = await screen.findByRole("button", { expanded: false });
    await user.click(row);
    await waitFor(() => expect(row).toHaveAttribute("aria-expanded", "true"));

    await user.click(row);
    await waitFor(() => expect(row).toHaveAttribute("aria-expanded", "false"));
  });

  it("explains in plain words what the attack stage means", async () => {
    timeline.mockResolvedValue({
      report: report([event({ stages: ["financial_transaction"] })]),
    });

    const user = userEvent.setup();
    renderWithProviders(<TimelineTab caseId="CASE_1" />);

    await user.click(await screen.findByRole("button", { expanded: false }));

    await waitFor(() =>
      expect(
        screen.getByText(/A payment, transfer or wallet transaction took place/),
      ).toBeInTheDocument(),
    );
  });

  it("keeps detailed stage evidence collapsed until requested", async () => {
    const stagedReport = report([event({})]);
    stagedReport.attack_stages = [{
      stage: "initial_contact",
      evidence_ids: ["EVID_00001"],
      first_seen: "2026-01-01T10:00:00Z",
      last_seen: "2026-01-01T10:00:00Z",
      matched_keywords: ["offer"],
      explanation: "Initial contact was evidenced by the stored message.",
    }];
    timeline.mockResolvedValue({ report: stagedReport });

    const user = userEvent.setup();
    renderWithProviders(<TimelineTab caseId="CASE_1" />);

    const toggle = await screen.findByRole("button", { name: /review analysis/i });
    expect(screen.queryByText("Initial contact was evidenced by the stored message.")).not.toBeInTheDocument();

    await user.click(toggle);
    expect(await screen.findByText("Initial contact was evidenced by the stored message.")).toBeInTheDocument();
  });
});
