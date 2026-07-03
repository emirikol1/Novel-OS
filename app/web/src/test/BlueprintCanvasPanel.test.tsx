import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import BlueprintCanvasPanel from "../components/BlueprintCanvasPanel";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";
import { SAMPLE_BRIEF_CHARACTERS, SAMPLE_CHAPTER_BRIEF } from "../lib/chapterBrief";
import { SAMPLE_GRAPH_NODES } from "../lib/storyGraph";

const CHAPTERS: client.ChapterSummary[] = [
  { number: 1, title: "Setup", status: "planned", word_count: 0, pov: "", pipeline_step: "none" },
  { number: 3, title: "Vault", status: "planned", word_count: 1200, pov: "Alice", pipeline_step: "drafted" },
];

function renderPanel() {
  return render(
    <TestProviders>
      <MemoryRouter>
        <BlueprintCanvasPanel
          projectId="sample-p"
          chapters={CHAPTERS}
          characters={SAMPLE_BRIEF_CHARACTERS}
          plotThreads={[]}
          onSelectPlotThread={vi.fn()}
        />
      </MemoryRouter>
    </TestProviders>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1,
    status: "planned",
    outline: null,
    draft: null,
    revised: null,
    final: null,
    continuity: null,
  });
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue(SAMPLE_GRAPH_NODES);
  vi.spyOn(client.api, "getChapterBrief").mockImplementation(async (_id, n) => {
    if (n === 3) return { ...SAMPLE_CHAPTER_BRIEF, chapter_number: 3 };
    return null;
  });
});

test("shows story graph assignments from mocked chapter briefs", async () => {
  renderPanel();
  expect(await screen.findByText("Vault")).toBeInTheDocument();
  expect(screen.getByText(/POV/)).toBeInTheDocument();
  expect(screen.getAllByText("Alice").length).toBeGreaterThan(0);
  expect(screen.getAllByText("The Heist").length).toBeGreaterThanOrEqual(1);
  expect(screen.getAllByText(/Inside man betrayal/).length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText(/Beats:/)).toBeInTheDocument();
  expect(screen.getAllByText(/Edit brief/).length).toBe(2);
});

test("filters chapters by selected graph node", async () => {
  const user = userEvent.setup();
  renderPanel();
  const heist = await screen.findByRole("button", { name: "The Heist" });
  await user.click(heist);
  await waitFor(() => {
    const cards = screen.getAllByRole("article");
    const dimmed = cards.filter((el) => el.className.includes("opacity-40"));
    expect(dimmed).toHaveLength(1);
  });
  await user.click(screen.getByRole("button", { name: "Clear filter" }));
  await waitFor(() => {
    const cards = screen.getAllByRole("article");
    expect(cards.every((el) => !el.className.includes("opacity-40"))).toBe(true);
  });
});
