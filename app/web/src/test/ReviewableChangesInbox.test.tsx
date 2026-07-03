import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import ReviewableChangesInbox from "../components/ReviewableChangesInbox";
import * as client from "../api/client";

const PENDING_CHANGE: client.ReviewableChange = {
  id: "change-1",
  kind: "story_graph",
  title: "Link arc to chapter beat",
  summary: "Connects an existing arc to a chapter beat.",
  reason: null,
  source: "graph_suggestions",
  status: "pending",
  confidence: 0.86,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  target: { type: "node", id: "node-1" },
  before: { description: "old", status: "planned" },
  after: { description: "new", status: "active" },
  conflicts: null,
  revert_available: false,
};

const APPLIED_CHANGE: client.ReviewableChange = {
  ...PENDING_CHANGE,
  id: "change-2",
  title: "Applied graph suggestion",
  status: "applied_needs_review",
  revert_available: true,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

test("renders pending changes with structured before and after fields and applies a change", async () => {
  const user = userEvent.setup();
  vi.spyOn(client.api, "reviewableChanges").mockResolvedValue([PENDING_CHANGE, APPLIED_CHANGE]);
  const apply = vi.spyOn(client.api, "applyReviewableChange").mockResolvedValue({
    ...PENDING_CHANGE,
    status: "applied_needs_review",
    revert_available: true,
  });

  render(<ReviewableChangesInbox projectId="p" />);

  expect(await screen.findByText("Link arc to chapter beat")).toBeInTheDocument();
  expect(screen.getByText("description")).toBeInTheDocument();
  expect(screen.getByText("old")).toBeInTheDocument();
  expect(screen.getByText("new")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Apply" }));

  expect(apply).toHaveBeenCalledWith("p", "change-1");
  expect(await screen.findByText("No pending reviewable changes.")).toBeInTheDocument();
});

test("supports applied filter mark-reviewed action and graph suggestion generation", async () => {
  const user = userEvent.setup();
  vi.spyOn(client.api, "reviewableChanges").mockResolvedValue([APPLIED_CHANGE]);
  const markReviewed = vi.spyOn(client.api, "markReviewableChangeReviewed").mockResolvedValue({
    ...APPLIED_CHANGE,
    status: "reviewed",
  });
  const generated = vi.spyOn(client.api, "generateGraphSuggestions").mockResolvedValue([PENDING_CHANGE]);

  render(<ReviewableChangesInbox projectId="p" />);

  await screen.findByText("Reviewable Changes");
  await user.click(screen.getByRole("button", { name: /Applied/i }));
  await user.click(screen.getByRole("button", { name: "Mark reviewed" }));

  expect(markReviewed).toHaveBeenCalledWith("p", "change-2");

  await user.click(screen.getByLabelText("Auto-apply graph suggestions"));
  await user.click(screen.getByRole("button", { name: "Generate graph suggestions" }));

  await waitFor(() => {
    expect(generated).toHaveBeenCalledWith("p", { auto_apply: true });
  });
});
