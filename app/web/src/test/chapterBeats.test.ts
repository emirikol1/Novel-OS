import { describe, expect, it } from "vitest";
import {
  beatDisplayText,
  beatsFromSummaries,
  beatCounts,
  newLocalBeat,
  sortBeats,
  type ChapterBeatDraft,
} from "../lib/chapterBeats";

describe("chapterBeats utils", () => {
  it("sorts by sort_order then id", () => {
    const beats: ChapterBeatDraft[] = [
      { id: "b2", title: "Second", summary: "", sort_order: 1, status: "planned", linked_node_ids: [] },
      { id: "b1", title: "First", summary: "", sort_order: 0, status: "planned", linked_node_ids: [] },
    ];
    expect(sortBeats(beats).map((b) => b.id)).toEqual(["b1", "b2"]);
  });

  it("maps API summaries to drafts", () => {
    const drafts = beatsFromSummaries([
      {
        id: "beat_1",
        title: "Alarm fails",
        summary: "The code does not work",
        sort_order: 0,
        status: "planned",
        linked_node_ids: ["sg_main"],
      },
    ]);
    expect(drafts[0]?.title).toBe("Alarm fails");
    expect(drafts[0]?.linked_node_ids).toEqual(["sg_main"]);
  });

  it("formats display text from title and summary", () => {
    expect(
      beatDisplayText({
        id: "x",
        title: "Vault opens",
        summary: "The door slides aside",
        sort_order: 0,
        status: "landed",
        linked_node_ids: [],
      }),
    ).toBe("Vault opens — The door slides aside");
    expect(
      beatDisplayText({
        id: "x",
        title: "",
        summary: "Summary only",
        sort_order: 0,
        status: "planned",
        linked_node_ids: [],
      }),
    ).toBe("Summary only");
  });

  it("creates a local beat placeholder", () => {
    const beat = newLocalBeat(3, 2);
    expect(beat.sort_order).toBe(2);
    expect(beat.status).toBe("planned");
    expect(beat.id.startsWith("temp_")).toBe(true);
  });

  it("counts planned and landed beats", () => {
    expect(
      beatCounts([
        { id: "a", title: "A", summary: "", sort_order: 0, status: "planned", linked_node_ids: [] },
        { id: "b", title: "B", summary: "", sort_order: 1, status: "landed", linked_node_ids: [] },
      ]),
    ).toEqual({ planned: 1, landed: 1 });
  });
});
