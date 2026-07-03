import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import ChapterBriefPanel from "../components/ChapterBriefPanel";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";
import { SAMPLE_CHAPTER_BRIEF } from "../lib/chapterBrief";
import { ELIGIBILITY_GRAPH_NODES, SAMPLE_GRAPH_EDGES, SAMPLE_GRAPH_NODES } from "../lib/storyGraph";
import { setChapterPreviewPending } from "../lib/chapterPreviewPending";
import { watchBackgroundJob } from "../hooks/useBackgroundJob";

const CHARS = [
  { id: "char_a", full_name: "Alice", role: "protagonist" },
  { id: "char_b", full_name: "Bob", role: "antagonist" },
];

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(null);
  vi.spyOn(client.api, "listChapterBeats").mockResolvedValue([]);
  vi.spyOn(client.api, "storyGraphNodes").mockResolvedValue(SAMPLE_GRAPH_NODES);
  vi.spyOn(client.api, "storyGraphEdges").mockResolvedValue(SAMPLE_GRAPH_EDGES);
});

test("explains prompt effect and loads empty brief", async () => {
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} />
    </TestProviders>,
  );
  expect(await screen.findByRole("button", { name: /Chapter Brief/i })).toBeInTheDocument();
  expect(screen.queryByLabelText(/POV character/i)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  expect(await screen.findByText(/single source of truth/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/POV character/i)).toBeInTheDocument();
});

test("notifies parent only when the user actually toggles the panel", async () => {
  const onCollapsedChange = vi.fn();
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel
        projectId="sample-p"
        chapterNumber={3}
        characters={CHARS}
        onCollapsedChange={onCollapsedChange}
      />
    </TestProviders>,
  );
  await screen.findByRole("button", { name: /Chapter Brief/i });
  // The panel starts collapsed by default; the parent already knows this and
  // should NOT be notified on mount, otherwise a spurious "collapse" callback
  // will stomp state the parent set for other reasons (e.g. pipeline stage
  // selection). See ChapterView bug 0.51.
  expect(onCollapsedChange).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  expect(onCollapsedChange).toHaveBeenCalledWith(false);
  onCollapsedChange.mockClear();
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  expect(onCollapsedChange).toHaveBeenCalledWith(true);
});

test("saves chapter brief with mocked API", async () => {
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.selectOptions(screen.getByLabelText(/POV character/i), "char_a");
  await user.selectOptions(screen.getByLabelText(/Narrative perspective/i), "first_person");
  await user.click(screen.getByRole("button", { name: /Save brief/i }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.pov_character_id).toBe("char_a");
  expect(save.mock.calls[0]?.[2]?.pov_mode).toBe("first_person");
});

test("loads existing brief from mocked API", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await userEvent.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await waitFor(() => {
    expect(screen.getByDisplayValue(/vault door opens/i)).toBeInTheDocument();
  });
  expect(screen.getByLabelText(/Narrative perspective/i)).toHaveValue("third_limited");
  const toggle = screen.getByRole("button", { name: /Chapter Brief/i });
  expect(within(toggle).getByText(/saved/i)).toBeInTheDocument();
});

test("starts chapter brief generation as a background job", async () => {
  const projectId = "sample-p-brief-start";
  const start = vi.spyOn(client.api, "generateChapterBriefAsync").mockResolvedValue({
    job_id: "brief-job-1",
    kind: "chapter_brief",
    status: "running",
    error: null,
  });
  const interval = vi.spyOn(window, "setInterval").mockImplementation(() => 1);
  const user = userEvent.setup();
  try {
    render(
      <TestProviders>
        <ChapterBriefPanel projectId={projectId} chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
      </TestProviders>,
    );
    await screen.findByText(/Chapter Brief/i);
    await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
    await user.click(screen.getByRole("button", { name: /Generate brief/i }));

    await waitFor(() => expect(start).toHaveBeenCalledWith(projectId, 3, {
      source: "best",
    }));
  } finally {
    interval.mockRestore();
  }
});

test("sends current style fields when generating a chapter brief", async () => {
  const projectId = "sample-p-brief-current-fields";
  const start = vi.spyOn(client.api, "generateChapterBriefAsync").mockResolvedValue({
    job_id: "brief-job-current-fields",
    kind: "chapter_brief",
    status: "running",
    error: null,
  });
  const interval = vi.spyOn(window, "setInterval").mockImplementation(() => 1);
  const user = userEvent.setup();
  try {
    render(
      <TestProviders>
        <ChapterBriefPanel projectId={projectId} chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
      </TestProviders>,
    );
    await screen.findByText(/Chapter Brief/i);
    await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
    await user.selectOptions(screen.getByLabelText(/Tense/i), "present");
    await user.type(screen.getByLabelText(/Style notes/i), "Keep sentences clipped.");
    await user.click(screen.getByRole("button", { name: /Generate brief/i }));

    await waitFor(() => expect(start).toHaveBeenCalled());
    expect(start.mock.calls[0]?.[2]?.current_brief).toEqual(expect.objectContaining({
      tense: "present",
      style_notes: "Keep sentences clipped.",
      target_word_count: 0,
    }));
  } finally {
    interval.mockRestore();
  }
});

test("graph focus picker filters nodes and keeps hidden in-effect selections visible", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));

  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));
  expect(await screen.findByTestId("graph-focus-picker")).toBeInTheDocument();
  expect(screen.getByTestId("graph-focus-counts")).toHaveTextContent("2 in effect · 1 eligible");

  await user.type(screen.getByLabelText(/Search story-graph nodes/i), "betrayal");

  const picker = screen.getByTestId("graph-focus-picker");
  expect(screen.getByTestId("graph-focus-counts")).toHaveTextContent("2 in effect · 1 eligible");
  expect(within(picker).getByText(/In effect \(hidden by filters\)/i)).toBeInTheDocument();
  expect(within(picker).getByText(/The Heist/i)).toBeInTheDocument();
  expect(within(picker).queryByText(/Vault alarm subplot/i)).not.toBeInTheDocument();
});

test("graph focus select all eligible updates active_node_ids on save", async () => {
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue({
    ...SAMPLE_CHAPTER_BRIEF,
    active_node_ids: ["sg_main", "sg_sub1", "sg_sub2"],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));

  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));
  await user.click(screen.getByRole("button", { name: /Select all eligible/i }));
  await user.click(screen.getByRole("button", { name: /Save brief/i }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.active_node_ids).toEqual(
    expect.arrayContaining(["sg_main", "sg_sub1", "sg_sub2"]),
  );
  expect(save.mock.calls[0]?.[2]?.active_node_ids).toHaveLength(3);
});

test("compact graph focus shows selected chips only until modal opens", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));

  const section = await screen.findByTestId("chapter-graph-focus-section");
  expect(within(section).getByText(/The Heist/i)).toBeInTheDocument();
  expect(within(section).getByText(/Inside man betrayal/i)).toBeInTheDocument();
  expect(within(section).queryByText(/Vault alarm subplot/i)).not.toBeInTheDocument();
  expect(screen.queryByTestId("graph-focus-picker")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));
  expect(await screen.findByTestId("graph-focus-picker")).toBeInTheDocument();
  expect(screen.getByText(/Vault alarm subplot/i)).toBeInTheDocument();
});

test("removing graph focus chip updates active_node_ids on save", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue({
    ...SAMPLE_CHAPTER_BRIEF,
    active_node_ids: ["sg_main"],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));

  await user.click(screen.getByRole("button", { name: /Remove Inside man betrayal from chapter/i }));
  await user.click(screen.getByRole("button", { name: /Save brief/i }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.active_node_ids).toEqual(["sg_main"]);
});

test("generate brief refreshes the beat board", async () => {
  const projectId = "sample-p-brief-refresh";
  let generated = false;
  vi.spyOn(client.api, "getChapterBrief").mockImplementation(async () => (
    generated ? SAMPLE_CHAPTER_BRIEF : null
  ));
  const generatedBeats = [
    {
      id: "beat_3_001",
      title: "Hero finds the hidden map",
      summary: "",
      sort_order: 0,
      status: "planned" as const,
      linked_node_ids: [],
    },
  ];
  const listBeats = vi.spyOn(client.api, "listChapterBeats").mockImplementation(async () => (
    generated ? generatedBeats : []
  ));
  vi.spyOn(client.api, "generateChapterBriefAsync").mockResolvedValue({
    job_id: "brief-job-2",
    kind: "chapter_brief",
    status: "running",
    error: null,
  });
  vi.spyOn(client.api, "getJob").mockImplementation(async () => {
    generated = true;
    return {
      job_id: "brief-job-2",
      kind: "chapter_brief",
      status: "done",
      error: null,
    };
  });
  let pollJob: (() => Promise<void>) | null = null;
  const interval = vi.spyOn(window, "setInterval").mockImplementation((callback) => {
    pollJob = callback as () => Promise<void>;
    return 1;
  });
  vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);
  const user = userEvent.setup();
  try {
    render(
      <TestProviders>
        <ChapterBriefPanel projectId={projectId} chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
      </TestProviders>,
    );
    await screen.findByText(/Chapter Brief/i);
    await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
    await user.click(screen.getByRole("button", { name: /Generate brief/i }));
    expect(pollJob).toBeTruthy();
    await pollJob?.();

    await waitFor(() => {
      expect(screen.getByDisplayValue(/vault door opens/i)).toBeInTheDocument();
    });
    await waitFor(() => expect(listBeats.mock.calls.length).toBeGreaterThan(1));
    expect(screen.getByDisplayValue("Hero finds the hidden map")).toBeInTheDocument();
  } finally {
    interval.mockRestore();
  }
});

const MOCK_BEAT_CANDIDATES = {
  chapter_number: 3,
  source_used: "draft",
  candidates: [
    {
      rank: 1,
      beat: "Hero finds the hidden map",
      significance: "turning_point",
      involved_characters: ["Alice"],
      story_relevance: "Sets up the vault sequence",
      category: "discovery",
    },
    {
      rank: 2,
      beat: "Guard confronts the intruder",
      significance: "conflict",
      involved_characters: ["Bob"],
      story_relevance: "Raises stakes before the vault",
      category: "confrontation",
    },
  ],
};

test("extracts landed beats via candidate review and apply", async () => {
  setChapterPreviewPending("sample-p", 3, true);
  vi.spyOn(client.api, "getChapterBeatCandidatesPreview").mockResolvedValue(MOCK_BEAT_CANDIDATES);
  vi.spyOn(client.api, "discardChapterBeatCandidatesPreview").mockResolvedValue(undefined);
  const appliedBeats = [
    {
      id: "beat_3_001",
      title: "Hero finds the hidden map",
      summary: "",
      sort_order: 0,
      status: "landed" as const,
      linked_node_ids: [],
    },
    {
      id: "beat_3_002",
      title: "Vault alarm triggered",
      summary: "",
      sort_order: 1,
      status: "landed" as const,
      linked_node_ids: [],
    },
  ];
  let reloadAfterApply = false;
  const listBeats = vi.spyOn(client.api, "listChapterBeats").mockImplementation(async () => (
    reloadAfterApply ? appliedBeats : []
  ));
  const apply = vi.spyOn(client.api, "applyChapterBeatCandidates").mockImplementation(async () => {
    reloadAfterApply = true;
    return SAMPLE_CHAPTER_BRIEF;
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /Review landed beats/i }));

  await waitFor(() => {
    expect(screen.getByText(/Review landed beat candidates/i)).toBeInTheDocument();
  });
  expect(screen.getByText(/Source used:/i)).toHaveTextContent("draft");
  expect(screen.getByText(/Hero finds the hidden map/i)).toBeInTheDocument();
  expect(screen.getByText(/Sets up the vault sequence/i)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Apply selected/i }));

  await waitFor(() => expect(apply).toHaveBeenCalledWith("sample-p", 3, {
    selected_beats: ["Hero finds the hidden map", "Guard confronts the intruder"],
    mode: "append",
  }));
  await waitFor(() => expect(listBeats.mock.calls.length).toBeGreaterThan(1));
  await waitFor(() => {
    expect(screen.getByDisplayValue("Hero finds the hidden map")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Vault alarm triggered")).toBeInTheDocument();
  });
});

test("allows applying landed beats when preview is ready but async job still appears running", async () => {
  const projectId = "stale-running-p";
  setChapterPreviewPending(projectId, 3, true);
  vi.spyOn(client.api, "getChapterBeatCandidatesPreview").mockResolvedValue(MOCK_BEAT_CANDIDATES);
  const apply = vi.spyOn(client.api, "applyChapterBeatCandidates").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const interval = vi.spyOn(window, "setInterval").mockImplementation(() => 1);
  watchBackgroundJob("stale-job", {
    label: "Landed beats extraction",
    kind: "landed-beats",
    projectId,
    scope: "3",
  });
  const user = userEvent.setup();
  try {
    render(
      <TestProviders>
        <ChapterBriefPanel projectId={projectId} chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
      </TestProviders>,
    );
    await screen.findByText(/Chapter Brief/i);
    await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
    await user.click(screen.getByRole("button", { name: /Extracting landed beats/i }));

    const applyButton = await screen.findByRole("button", { name: /Apply selected \(2\)/i });
    expect(applyButton).toBeEnabled();
    await user.click(applyButton);

    await waitFor(() => expect(apply).toHaveBeenCalledWith(projectId, 3, {
      selected_beats: ["Hero finds the hidden map", "Guard confronts the intruder"],
      mode: "append",
    }));
  } finally {
    interval.mockRestore();
  }
});

test("starts landed beats extraction as a background job", async () => {
  const start = vi.spyOn(client.api, "generateChapterBeatCandidatesAsync").mockResolvedValue({
    job_id: "job-1",
    kind: "landed_beats",
    status: "running",
    error: null,
  });
  vi.spyOn(client.api, "getChapterBeatCandidatesPreview").mockResolvedValue(null);
  vi.spyOn(client.api, "getJob").mockResolvedValue({
    job_id: "job-1",
    kind: "landed_beats",
    status: "done",
    error: null,
  });
  const interval = vi.spyOn(window, "setInterval").mockImplementation(() => {
    return 1;
  });
  vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);
  const user = userEvent.setup();
  try {
    render(
      <TestProviders>
        <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
      </TestProviders>,
    );
    await screen.findByText(/Chapter Brief/i);
    await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
    await user.click(screen.getByRole("button", { name: /Extract landed beats/i }));

    await waitFor(() => expect(start).toHaveBeenCalledWith("sample-p", 3, {
      source: "best",
      count: 10,
    }));
    expect(await screen.findByText(/Archivist is extracting landed beats/i)).toBeInTheDocument();
  } finally {
    interval.mockRestore();
  }
});

test("opens context preview and shows included items, reasons, and omissions", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  vi.spyOn(client.api, "getChapterContextPreview").mockResolvedValue({
    chapter_number: 3,
    mode: "draft",
    bible: {
      items: [
        {
          key: "bible:logline",
          label: "Logline",
          body: "A thief races the clock in a flooded vault city.",
          reason: "text_match",
          score: 112,
        },
      ],
      omitted_count: 2,
      omitted_labels: ["Themes", "World rules"],
      omitted_reason: "budget cap",
    },
    graph: {
      items: [
        {
          key: "graph:sg_main",
          label: "The Heist",
          body: "(main, active, priority 5) — Steal the vault key",
          reason: "explicit_selection",
          score: 245,
        },
      ],
      omitted_count: 1,
      omitted_labels: ["Vault alarm subplot"],
      omitted_reason: "budget cap",
    },
    active_characters: [
      { id: "char_a", name: "Alice" },
      { id: "char_b", name: "Bob" },
    ],
    beats: [
      {
        id: "beat_3_001",
        title: "Hero finds the hidden map",
        status: "planned",
        summary: "Sets up the vault sequence",
      },
    ],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /Context preview/i }));

  const dialog = await screen.findByRole("dialog", { name: /Context preview/i });
  expect(within(dialog).getByText(/Logline/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Matched chapter outline\/text/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/The Heist/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Selected in chapter brief/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Omitted 2/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Themes/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Not included:.*Vault alarm subplot/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Alice, Bob/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Chapter beats/i)).toBeInTheDocument();
  expect(within(dialog).getByText(/Hero finds the hidden map/i)).toBeInTheDocument();
});

test("character triple toggle cycles silver then gold and saves exclusive cast state", async () => {
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue({
    ...SAMPLE_CHAPTER_BRIEF,
    mentioned_character_ids: [],
    active_character_ids: ["char_b"],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));

  const bobToggle = screen.getByTestId("brief-character-toggle-char_b");
  expect(bobToggle).toHaveAttribute("aria-label", "Bob: not in chapter");

  await user.click(bobToggle);
  expect(bobToggle).toHaveAttribute("aria-label", "Bob: mentioned");
  expect(bobToggle.className).toMatch(/border-ink/);

  await user.click(bobToggle);
  expect(bobToggle).toHaveAttribute("aria-label", "Bob: active");
  expect(bobToggle.className).toMatch(/border-amber-deep/);

  await user.click(screen.getByRole("button", { name: /Save brief/i }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.mentioned_character_ids).toEqual([]);
  expect(save.mock.calls[0]?.[2]?.active_character_ids).toEqual(["char_b"]);
});

test("plot picker shows in-effect and eligible sections", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));

  expect(await screen.findByTestId("graph-focus-in-effect")).toBeInTheDocument();
  expect(screen.getByTestId("graph-focus-eligible")).toBeInTheDocument();
  expect(screen.getByText(/Vault alarm subplot/i)).toBeInTheDocument();
});

test("checking eligible plot adds to active_node_ids on save", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue({
    ...SAMPLE_CHAPTER_BRIEF,
    active_node_ids: ["sg_main", "sg_sub1", "sg_sub2"],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));

  const eligibleSection = await screen.findByTestId("graph-focus-eligible");
  const vaultRow = within(eligibleSection).getByText(/Vault alarm subplot/i).closest("label");
  expect(vaultRow).toBeTruthy();
  await user.click(within(vaultRow as HTMLElement).getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: /Save brief/i }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.active_node_ids).toEqual(
    expect.arrayContaining(["sg_main", "sg_sub1", "sg_sub2"]),
  );
});

test("out-of-range plot is not listed as eligible at chapter 3", async () => {
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue(SAMPLE_CHAPTER_BRIEF);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel
        projectId="sample-p"
        chapterNumber={3}
        characters={CHARS}
        graphNodes={ELIGIBILITY_GRAPH_NODES}
      />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /\+ Add plot\/subplot/i }));

  const eligibleSection = screen.getByTestId("graph-focus-eligible");
  expect(within(eligibleSection).queryByText(/Epilogue arc/i)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Show 2 out-of-range plots/i }));
  expect(await screen.findByTestId("graph-focus-out-of-range")).toBeInTheDocument();
  expect(screen.getByText(/Epilogue arc/i)).toBeInTheDocument();
});

test("create plot from brief calls createStoryGraphNode with lifespan defaults", async () => {
  const created = {
    id: "sg_new",
    kind: "subplot",
    title: "New subplot from brief",
    description: "",
    status: "active",
    priority: 0,
    linked_character_ids: [],
    legacy_plot_thread_id: "",
    created_from: "manual",
    sort_order: 0,
    start_chapter: 3,
    resolution_chapter: null,
  };
  const create = vi.spyOn(client.api, "createStoryGraphNode").mockResolvedValue(created);
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /\+ New plot\/subplot/i }));

  const modal = await screen.findByTestId("create-plot-from-brief-modal");
  await user.type(within(modal).getByPlaceholderText(/Plot or subplot title/i), "New subplot from brief");
  await user.click(within(modal).getByRole("button", { name: /Create plot/i }));

  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(create.mock.calls[0]?.[1]).toMatchObject({
    title: "New subplot from brief",
    start_chapter: 3,
    chapter_number: 3,
    assign_to_brief: true,
  });
});

test("create plot with assign adds new id to active_node_ids", async () => {
  const created = {
    id: "sg_new",
    kind: "subplot",
    title: "New subplot from brief",
    description: "",
    status: "active",
    priority: 0,
    linked_character_ids: [],
    legacy_plot_thread_id: "",
    created_from: "manual",
    sort_order: 0,
    start_chapter: 3,
    resolution_chapter: null,
  };
  vi.spyOn(client.api, "createStoryGraphNode").mockResolvedValue(created);
  const save = vi.spyOn(client.api, "saveChapterBrief").mockResolvedValue({
    ...SAMPLE_CHAPTER_BRIEF,
    active_node_ids: ["sg_main", "sg_sub2", "sg_new"],
  });
  const user = userEvent.setup();
  render(
    <TestProviders>
      <ChapterBriefPanel projectId="sample-p" chapterNumber={3} characters={CHARS} graphNodes={SAMPLE_GRAPH_NODES} />
    </TestProviders>,
  );
  await screen.findByText(/Chapter Brief/i);
  await user.click(screen.getByRole("button", { name: /Chapter Brief/i }));
  await user.click(screen.getByRole("button", { name: /\+ New plot\/subplot/i }));

  const modal = await screen.findByTestId("create-plot-from-brief-modal");
  await user.type(within(modal).getByPlaceholderText(/Plot or subplot title/i), "New subplot from brief");
  await user.click(within(modal).getByRole("button", { name: /Create plot/i }));

  await waitFor(() => {
    expect(screen.getByText(/New subplot from brief/i)).toBeInTheDocument();
  });

  await user.click(screen.getByRole("button", { name: /Save brief/i }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0]?.[2]?.active_node_ids).toEqual(
    expect.arrayContaining(["sg_new"]),
  );
});
