import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import InspectorCastPanel from "../components/InspectorCastPanel";
import * as client from "../api/client";

const CAST: client.CharacterSummary[] = [
  { id: "c1", full_name: "Alice Hart", role: "protagonist", aliases: ["Ali"] },
  { id: "c2", full_name: "Bruno Vale", role: "antagonist" },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(client.api, "getChapterBrief").mockResolvedValue({
    pov_character_id: "c1",
    pov_mode: "third_limited",
    tone: "",
    tense: "",
    prose_style: "",
    vocabulary_level: "",
    style_notes: "",
    target_word_count: 2500,
    mentioned_character_ids: ["c2"],
    active_character_ids: ["c1"],
    active_node_ids: [],
    continuity_notes: "",
    ending_hook: "",
  });
  vi.spyOn(client.api, "character").mockImplementation(async (_id, charId) => ({
    id: charId,
    full_name: charId === "c1" ? "Alice Hart" : "Bruno Vale",
    role: charId === "c1" ? "protagonist" : "antagonist",
    aliases: charId === "c1" ? ["Ali"] : [],
    age: null,
    physical_description: "Tall and watchful",
    internal_desire: "",
    external_goal: "",
    fear: "",
    weakness: "",
    strength: "",
    secret: "",
    arc_stage: "",
    arc_progress: 0,
    current_location: "",
    emotional_state: "",
    notes: "",
    last_appearance_chapter: 1,
    relationships: {},
  }));
});

test("lists chapter cast first and opens character detail", async () => {
  const user = userEvent.setup();
  render(
    <InspectorCastPanel projectId="sample-p" chapterNumber={3} characters={CAST} />,
  );

  expect(await screen.findByText("In this chapter")).toBeInTheDocument();
  expect(screen.getByText("Alice Hart")).toBeInTheDocument();
  expect(screen.getByText("active")).toBeInTheDocument();
  expect(screen.getByText("mentioned")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Alice Hart/i }));
  await waitFor(() => {
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Tall and watchful")).toBeInTheDocument();
  });
});

test("filters cast by search", async () => {
  const user = userEvent.setup();
  render(
    <InspectorCastPanel projectId="sample-p" chapterNumber={3} characters={CAST} />,
  );

  await screen.findByText("Alice Hart");
  await user.type(screen.getByRole("searchbox", { name: "Search cast" }), "bruno");

  expect(screen.queryByText("Alice Hart")).not.toBeInTheDocument();
  expect(screen.getByText("Bruno Vale")).toBeInTheDocument();
});
