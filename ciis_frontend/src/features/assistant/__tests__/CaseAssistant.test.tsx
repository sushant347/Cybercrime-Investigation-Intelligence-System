import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/testUtils";

const { status, ask } = vi.hoisted(() => ({
  status: vi.fn(),
  ask: vi.fn(),
}));

vi.mock("@/api", () => ({
  ragApi: { status, ask },
}));

import { CaseAssistant } from "../CaseAssistant";

beforeEach(() => {
  status.mockReset();
  ask.mockReset();
  status.mockResolvedValue({
    case_id: "CASE_1",
    available: true,
    status: "fresh",
    detail: "ready",
  });
  ask.mockResolvedValue({
    answer: "The first event is the phishing message. [TIMELINE_EVID_00001]",
    insufficient_evidence: false,
    cited_sources: [{
      evidence_id: "TIMELINE_EVID_00001",
      file_name: "timeline_analysis.json",
      chunk_ids: ["CASE_1:artifact:TIMELINE_EVID_00001:000"],
      source_kind: "timeline_event",
      title: "Timeline event for EVID_00001",
      url: "",
      supporting_evidence_ids: ["EVID_00001"],
    }],
    retrieved_sources: [],
    evidence_breakdown: [],
    shared_entity_links: [],
    warnings: [],
  });
});

describe("CaseAssistant", () => {
  it("stays case-scoped and shows grounded citations", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CaseAssistant caseId="CASE_1" />);

    await user.click(screen.getByRole("button", { name: /open case assistant/i }));
    await screen.findByText("Useful starting questions");
    await user.click(screen.getByRole("button", { name: /what happened first/i }));

    await waitFor(() => expect(ask).toHaveBeenCalledWith(
      "CASE_1",
      "What happened first in the reconstructed timeline?",
    ));
    expect(await screen.findByText(/The first event is the phishing message/)).toBeInTheDocument();
    expect(screen.getByText("TIMELINE_EVID_00001")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "EVID_00001" })).toHaveAttribute(
      "href",
      "/cases/CASE_1/evidence/EVID_00001",
    );
  });

  it("explains when the separate RAG environment is unavailable", async () => {
    status.mockResolvedValue({
      case_id: "CASE_1",
      available: false,
      status: "unavailable",
      detail: "Configure CIIS_RAG_PYTHON with the separate RAG environment.",
    });
    const user = userEvent.setup();
    renderWithProviders(<CaseAssistant caseId="CASE_1" />);

    await user.click(screen.getByRole("button", { name: /open case assistant/i }));

    expect(await screen.findByText(/Configure CIIS_RAG_PYTHON/)).toBeInTheDocument();
    expect(screen.getByLabelText("Ask about this case")).toBeDisabled();
  });
});
