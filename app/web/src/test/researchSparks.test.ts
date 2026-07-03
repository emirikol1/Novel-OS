import { describe, expect, it } from "vitest";
import {
  collectAllTags,
  filterResearchSparks,
  parseTagsInput,
} from "../lib/researchSparks";
import type { ResearchSparkSummary } from "../api/client";

function spark(overrides: Partial<ResearchSparkSummary> = {}): ResearchSparkSummary {
  return {
    id: "s1",
    title: "Title",
    body: "Body text",
    source_url: "",
    tags: [],
    kind: "note",
    attachment_ref: "",
    link_character_id: null,
    link_chapter: null,
    link_plot_thread_id: null,
    link_bible_section: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("researchSparks utils", () => {
  it("parses comma-separated tags", () => {
    expect(parseTagsInput("a, b; c")).toEqual(["a", "b", "c"]);
  });

  it("filters by text, tag, and kind", () => {
    const sparks = [
      spark({ id: "1", title: "Castle", tags: ["history"], kind: "note" }),
      spark({ id: "2", title: "Harbor", body: "ships", tags: ["mood"], kind: "link" }),
    ];
    expect(filterResearchSparks(sparks, { q: "ships" }).map((s) => s.id)).toEqual(["2"]);
    expect(filterResearchSparks(sparks, { tag: "history" }).map((s) => s.id)).toEqual(["1"]);
    expect(filterResearchSparks(sparks, { kind: "link" }).map((s) => s.id)).toEqual(["2"]);
  });

  it("collects unique tags case-insensitively", () => {
    const sparks = [
      spark({ tags: ["History", "mood"] }),
      spark({ tags: ["history", "tone"] }),
    ];
    expect(collectAllTags(sparks)).toEqual(["History", "mood", "tone"]);
  });
});
