import { describe, expect, it } from "vitest";
import { previewPendingStages } from "./syncChapterPreviewPending";

describe("previewPendingStages", () => {
  it("marks outline and source stages for active previews", () => {
    expect(
      previewPendingStages(
        { source: "final", text: "x", original_word_count: 1, preview_word_count: 2, generated_at: null, instructions: "" },
        { source: "notes", text: "y", original_word_count: 0, preview_word_count: 1, generated_at: null, instructions: "" },
        null,
        null,
      ),
    ).toEqual(["outline", "final"]);
  });

  it("marks draft when regenerate targets draft on advanced chapters", () => {
    expect(
      previewPendingStages(
        { source: "draft", text: "x", original_word_count: 1, preview_word_count: 2, generated_at: null, instructions: "" },
        null,
        null,
        null,
      ),
    ).toEqual(["draft"]);
  });

  it("marks draft when redraft preview is active", () => {
    expect(
      previewPendingStages(
        null,
        null,
        null,
        null,
        { source: "final", mode: "align", text: "x", original_word_count: 10, preview_word_count: 12, generated_at: null, instructions: "" },
      ),
    ).toEqual(["draft"]);
  });

  it("marks stage for paragraph-format preview", () => {
    expect(
      previewPendingStages(
        null,
        null,
        null,
        { source: "revised", text: "x", original_word_count: 10, preview_word_count: 10, generated_at: null, instructions: "" },
      ),
    ).toEqual(["revised"]);
  });

  it("marks stage for dialogue quote preview", () => {
    expect(
      previewPendingStages(
        null,
        null,
        null,
        null,
        null,
        null,
        { source: "draft", text: "x", original_word_count: 10, preview_word_count: 10, generated_at: null, instructions: "" },
      ),
    ).toEqual(["draft"]);
  });

  it("marks source and revised stages for boundary-alignment preview", () => {
    expect(
      previewPendingStages(
        null,
        null,
        null,
        null,
        null,
        {
          chapter_a: 1,
          chapter_b: 2,
          source: "final",
          adjusted: true,
          direction: "a_to_b",
          move_text: "bridge",
          text_a: "x",
          text_b: "y",
          original_word_count_a: 10,
          original_word_count_b: 12,
          preview_word_count_a: 11,
          preview_word_count_b: 13,
          generated_at: null,
        },
      ),
    ).toEqual(["final", "revised"]);
  });
});
