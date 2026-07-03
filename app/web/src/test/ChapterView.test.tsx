import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { beforeEach, vi } from "vitest";

// CodeMirror doesn't render meaningfully in jsdom — swap it for a plain textarea.
vi.mock("../components/MarkdownEditor", () => ({
  default: (props: { value: string; onChange: (v: string) => void }) => (
    <textarea value={props.value} onChange={(e) => props.onChange(e.target.value)} />
  ),
}));

import ChapterView from "../routes/ChapterView";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

function renderAt(path = "/projects/p/chapters/1") {
  render(
    <TestProviders>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
        </Routes>
      </MemoryRouter>
    </TestProviders>,
  );
}

const META = {
  number: 1, title: "Opening", status: "drafted", word_count: 5, pov: "Lena",
  outline: null, draft: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
  vi.spyOn(client.api, "getRegeneratePreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getOutlinePreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getExpandPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getParagraphsPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getAlignmentPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getRedraftPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(null);
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue([]);
  vi.spyOn(client.api, "getChapterBeatCandidatesPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue([]);
});

test("shows the pipeline flow and renders the selected stage", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue(META);
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "storyBible").mockResolvedValue({ data: {} });
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1, status: "drafted",
    outline: "# Beats", draft: null, revised: null, final: null, continuity: null,
  });
  vi.spyOn(client.api, "comments").mockResolvedValue([]);

  renderAt();
  // flow ribbon shows every stage
  expect(await screen.findByText("Outline")).toBeInTheDocument();
  expect(screen.getByText("Final")).toBeInTheDocument();
  // outline is the only present stage, so it renders by default
  await waitFor(() => expect(document.body).toHaveTextContent("Beats"));
});

test("clicking an intra-chapter stage stays on that stage", async () => {
  const user = userEvent.setup();

  vi.spyOn(client.api, "chapter").mockResolvedValue({
    ...META,
    status: "complete",
    word_count: 1200,
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "storyBible").mockResolvedValue({ data: {} });
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1,
    status: "complete",
    outline: "# Beats one",
    draft: "Draft one",
    revised: "Revised one",
    final: "Final one",
    continuity: null,
  });
  vi.spyOn(client.api, "comments").mockResolvedValue([]);

  renderAt();

  // Default lands on the highest prose stage (Final).
  await screen.findByRole("button", { name: /Step 4, Final stage/ });
  await waitFor(() => expect(document.body).toHaveTextContent("Final one"));

  // Click Outline — must switch and stay there, never bounce back to Final.
  const outlineButton = screen.getByRole("button", { name: /Step 1, Outline stage/ });
  await user.click(outlineButton);
  await waitFor(() => expect(document.body).toHaveTextContent("Beats one"));

  // Give any spurious effects a chance to fire and stomp the selection.
  await new Promise((r) => setTimeout(r, 50));
  expect(document.body).toHaveTextContent("Beats one");
  expect(document.body).not.toHaveTextContent("Final one");

  // Draft click also holds.
  const draftButton = screen.getByRole("button", { name: /Step 2, Draft stage/ });
  await user.click(draftButton);
  await waitFor(() => expect(document.body).toHaveTextContent("Draft one"));
  await new Promise((r) => setTimeout(r, 50));
  expect(document.body).toHaveTextContent("Draft one");
});

test("deep-link ?stage=outline is honored on first load", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue({
    ...META,
    status: "complete",
    word_count: 1200,
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "storyBible").mockResolvedValue({ data: {} });
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1,
    status: "complete",
    outline: "# Beats two",
    draft: "Draft two",
    revised: "Revised two",
    final: "Final two",
    continuity: null,
  });
  vi.spyOn(client.api, "comments").mockResolvedValue([]);

  renderAt("/projects/p/chapters/1?stage=outline");

  // Even though final prose exists, the deep-link wins.
  await waitFor(() => expect(document.body).toHaveTextContent("Beats two"));
  await new Promise((r) => setTimeout(r, 50));
  expect(document.body).not.toHaveTextContent("Final two");
});
