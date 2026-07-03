import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import ProjectsList from "../routes/ProjectsList";
import StashPanel from "../components/StashPanel";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

test("renders project cards from the API", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([
    { id: "the-last-signal", title: "The Last Signal", genre: "Sci-Fi", chapter_count: 3, status: "in_progress" },
  ]);
  render(
    <TestProviders>
      <MemoryRouter><ProjectsList /></MemoryRouter>
    </TestProviders>,
  );
  expect(await screen.findByText("The Last Signal")).toBeInTheDocument();
  expect(screen.getByText(/3 chapters/i)).toBeInTheDocument();
});

test("stash panel lists filename date and size", async () => {
  vi.spyOn(client.api, "stashed").mockResolvedValue([
    {
      id: "old-draft",
      title: "Old Draft",
      genre: "",
      chapter_count: 0,
      stashed_at: "2026-01-15T12:00:00Z",
      filename: "old-draft.novel-os.zip",
      size_bytes: 2048,
    },
  ]);
  render(
    <TestProviders>
      <MemoryRouter>
        <StashPanel />
      </MemoryRouter>
    </TestProviders>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Stash/i }));
  expect(await screen.findByText("old-draft.novel-os.zip")).toBeInTheDocument();
  expect(screen.getByText(/2\.0 KB/i)).toBeInTheDocument();
  expect(screen.queryByText("Old Draft")).not.toBeInTheDocument();
});
