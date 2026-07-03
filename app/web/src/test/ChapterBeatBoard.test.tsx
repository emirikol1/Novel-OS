import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import ChapterBeatBoard from "../components/ChapterBeatBoard";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

const SAMPLE_BEATS = [
  {
    id: "beat_3_001",
    title: "Alarm fails",
    summary: "",
    sort_order: 0,
    status: "planned" as const,
    linked_node_ids: [],
  },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue([]);
});

test("loads empty beat board", async () => {
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  expect(await screen.findByTestId("chapter-beat-board")).toBeInTheDocument();
  expect(screen.getByText(/No beats yet/i)).toBeInTheDocument();
});

test("add beat calls createChapterBeat", async () => {
  const create = vi.spyOn(client.api, "createChapterBeat").mockResolvedValue({
    id: "beat_3_002",
    title: "New beat",
    summary: "",
    sort_order: 0,
    status: "planned",
    linked_node_ids: [],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  await screen.findByText(/No beats yet/i);
  await user.click(screen.getByRole("button", { name: /\+ Add beat/i }));
  await waitFor(() => expect(create).toHaveBeenCalledWith("sample-p", 3, expect.objectContaining({
    title: "New beat",
    status: "planned",
  })));
});

test("inline edit debounces PATCH", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue(SAMPLE_BEATS);
  const update = vi.spyOn(client.api, "updateChapterBeat").mockResolvedValue({
    ...SAMPLE_BEATS[0],
    title: "Updated alarm",
  });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  const titleInput = await screen.findByLabelText(/Beat title/i);
  await user.clear(titleInput);
  await user.type(titleInput, "Updated alarm");
  await vi.advanceTimersByTimeAsync(750);
  await waitFor(() => expect(update).toHaveBeenCalledWith(
    "sample-p",
    3,
    "beat_3_001",
    expect.objectContaining({ title: "Updated alarm" }),
  ));
  vi.useRealTimers();
});

test("toggle status PATCHes immediately", async () => {
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue(SAMPLE_BEATS);
  const update = vi.spyOn(client.api, "updateChapterBeat").mockResolvedValue({
    ...SAMPLE_BEATS[0],
    status: "landed",
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  await screen.findByLabelText(/Beat title/i);
  await user.click(screen.getByRole("button", { name: "landed" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith(
    "sample-p",
    3,
    "beat_3_001",
    expect.objectContaining({ status: "landed" }),
  ));
});

test("delete beat calls deleteChapterBeat", async () => {
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue(SAMPLE_BEATS);
  const del = vi.spyOn(client.api, "deleteChapterBeat").mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  await screen.findByLabelText(/Beat title/i);
  const card = screen.getByTestId("beat-card-beat_3_001");
  await user.click(within(card).getByRole("button", { name: /Delete beat/i }));
  await waitFor(() => expect(del).toHaveBeenCalledWith("sample-p", 3, "beat_3_001"));
});

test("drag reorder calls reorderChapterBeats", async () => {
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue([
    SAMPLE_BEATS[0],
    {
      id: "beat_3_002",
      title: "Second beat",
      summary: "",
      sort_order: 1,
      status: "planned",
      linked_node_ids: [],
    },
  ]);
  const reorder = vi.spyOn(client.api, "reorderChapterBeats").mockResolvedValue([
    {
      id: "beat_3_002",
      title: "Second beat",
      summary: "",
      sort_order: 0,
      status: "planned",
      linked_node_ids: [],
    },
    SAMPLE_BEATS[0],
  ]);
  render(
    <TestProviders>
      <ChapterBeatBoard projectId="sample-p" chapterNumber={3} />
    </TestProviders>,
  );
  await screen.findByTestId("beat-card-beat_3_001");
  const handle = screen.getAllByLabelText(/Drag to reorder beat/i)[0];
  const target = screen.getByTestId("beat-card-beat_3_002");
  fireEvent.dragStart(handle);
  fireEvent.dragOver(target);
  fireEvent.drop(target);
  await waitFor(() => expect(reorder).toHaveBeenCalledWith(
    "sample-p",
    3,
    ["beat_3_002", "beat_3_001"],
  ));
});
