import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/testUtils";
import type { AppNotification } from "@/types";

// Mock the whole API module so the bell never hits a real backend.
const list = vi.fn();
const markRead = vi.fn();
vi.mock("@/api", () => ({
  notificationsApi: {
    list: (...args: unknown[]) => list(...args),
    markRead: (...args: unknown[]) => markRead(...args),
  },
}));

import { NotificationBell } from "@/features/notifications/NotificationBell";

const NOTIFS: AppNotification[] = [
  {
    id: 1,
    type: "processing_complete",
    title: "Evidence EVID_00001 processed",
    message: "screenshot.png processed for CASE_0001.",
    case_id: "CASE_0001",
    evidence_id: "EVID_00001",
    read: false,
    created_at: "2026-07-24T10:00:00Z",
  },
  {
    id: 2,
    type: "high_priority",
    title: "CASE_0001 flagged HIGH priority",
    message: "Engine priority score: 82.",
    case_id: "CASE_0001",
    evidence_id: "",
    read: false,
    created_at: "2026-07-24T10:05:00Z",
  },
];

beforeEach(() => {
  list.mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: NOTIFS,
    unread_count: 2,
  });
  markRead.mockResolvedValue({ marked_read: 2 });
});

describe("NotificationBell", () => {
  it("shows the unread badge count", async () => {
    renderWithProviders(<NotificationBell />);
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("lists notifications when opened", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationBell />);
    await screen.findByText("2");
    await user.click(screen.getByLabelText(/Notifications/i));
    expect(
      await screen.findByText("Evidence EVID_00001 processed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("CASE_0001 flagged HIGH priority"),
    ).toBeInTheDocument();
  });

  it("marks all read via the API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationBell />);
    await screen.findByText("2");
    await user.click(screen.getByLabelText(/Notifications/i));
    await user.click(await screen.findByRole("button", { name: /mark all read/i }));
    await waitFor(() => expect(markRead).toHaveBeenCalledWith(undefined));
  });

  it("shows an empty state with no notifications", async () => {
    list.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
      unread_count: 0,
    });
    const user = userEvent.setup();
    renderWithProviders(<NotificationBell />);
    await user.click(screen.getByLabelText(/Notifications/i));
    expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
  });
});
