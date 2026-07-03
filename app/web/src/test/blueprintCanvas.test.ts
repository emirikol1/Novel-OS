import { describe, expect, it } from "vitest";
import {
  actSplitIndices,
  applyBriefsToBlueprintCanvas,
  buildBlueprintCanvas,
  buildChapterBriefDisplay,
  chapterMatchesGraphNode,
  graphNodesOnCanvas,
  groupChaptersIntoActs,
  matchPlotThreadsInText,
  outlineSnippet,
  requiredBeatsSummary,
  textMentionsLabel,
  threadSearchLabels,
} from "../lib/blueprintCanvas";
import type { ChapterSummary, PlotThreadSummary } from "../api/client";
import { SAMPLE_BRIEF_CHARACTERS, SAMPLE_CHAPTER_BRIEF } from "../lib/chapterBrief";
import { SAMPLE_GRAPH_NODES } from "../lib/storyGraph";

function chapter(n: number, title = ""): ChapterSummary {
  return {
    number: n,
    title,
    status: "planned",
    word_count: 0,
    pov: "",
    pipeline_step: "none",
  };
}

function thread(
  id: string,
  name: string,
  subplots: string[] = [],
): PlotThreadSummary {
  return {
    id,
    name,
    description: "",
    thread_type: "main",
    status: "active",
    priority: 1,
    sort_order: 0,
    subplots,
  };
}

describe("blueprintCanvas", () => {
  it("splits chapters into three act buckets", () => {
    expect(actSplitIndices(0)).toEqual([0, 0, 0]);
    expect(actSplitIndices(1)).toEqual([1, 0, 0]);
    expect(actSplitIndices(2)).toEqual([1, 1, 0]);
    expect(actSplitIndices(6)).toEqual([2, 2, 2]);
    expect(actSplitIndices(7)).toEqual([3, 2, 2]);
  });

  it("groups chapters into act lanes in chapter order", () => {
    const lanes = groupChaptersIntoActs([
      chapter(3, "Three"),
      chapter(1, "One"),
      chapter(2, "Two"),
    ]);
    expect(lanes).toHaveLength(3);
    expect(lanes[0].chapters.map((c) => c.chapter.number)).toEqual([1]);
    expect(lanes[1].chapters.map((c) => c.chapter.number)).toEqual([2]);
    expect(lanes[2].chapters.map((c) => c.chapter.number)).toEqual([3]);
  });

  it("detects label mentions with word boundaries for short names", () => {
    expect(textMentionsLabel("The uprising begins", "up")).toBe(false);
    expect(textMentionsLabel("The uprising begins", "uprising")).toBe(true);
    expect(textMentionsLabel("UPRISING at dawn", "uprising")).toBe(true);
  });

  it("collects thread and subplot labels without duplicates", () => {
    const labels = threadSearchLabels(thread("t1", "Main Plot", ["Main Plot", "Side beat"]));
    expect(labels).toEqual(["Main Plot", "Side beat"]);
  });

  it("matches plot threads mentioned in outline text", () => {
    const threads = [
      thread("a", "The Uprising"),
      thread("b", "Love Story", ["first kiss"]),
    ];
    const matches = matchPlotThreadsInText(
      "Chapter focuses on the uprising and hints at first kiss.",
      threads,
    );
    expect(matches).toHaveLength(2);
    expect(matches.map((m) => m.id).sort()).toEqual(["a", "b"]);
  });

  it("builds canvas cards with snippets and thread badges", () => {
    const chapters = [chapter(1, "Opening")];
    const outlines = new Map<number, string | null>([
      [1, "# Beat\n\nThe Uprising escalates with a long paragraph that should be trimmed for display purposes on the blueprint board."],
    ]);
    const lanes = buildBlueprintCanvas(chapters, outlines, [thread("p1", "The Uprising")], 40);
    const card = lanes[0].chapters[0];
    expect(card.outlineSnippet).toMatch(/…$/);
    expect(card.plotThreads[0]?.name).toBe("The Uprising");
  });

  it("truncates outline snippets", () => {
    expect(outlineSnippet("  hello   world  ", 8)).toBe("hello w…");
    expect(outlineSnippet(null)).toBeNull();
  });

  it("summarizes required beats for card display", () => {
    expect(requiredBeatsSummary([])).toBeNull();
    expect(requiredBeatsSummary(["One beat"])).toBe("One beat");
    const long = requiredBeatsSummary(
      ["First beat", "Second beat", "Third beat"],
      2,
      120,
    );
    expect(long).toBe("First beat · Second beat (+1 more)");
  });

  it("builds chapter brief display from sample fixtures", () => {
    const display = buildChapterBriefDisplay(
      { ...SAMPLE_CHAPTER_BRIEF, chapter_number: 1 },
      SAMPLE_BRIEF_CHARACTERS,
      SAMPLE_GRAPH_NODES,
    );
    expect(display?.povName).toBe("Alice");
    expect(display?.activeNodes.map((n) => n.title)).toEqual([
      "Inside man betrayal",
      "The Heist",
    ]);
    expect(display?.activeCharacterNames).toEqual(["Alice", "Bob"]);
    expect(display?.requiredBeatsSummary).toMatch(/Alice discovers/);
  });

  it("enriches blueprint lanes with brief assignments", () => {
    const chapters = [chapter(3, "Vault")];
    const outlines = new Map<number, string | null>([[3, null]]);
    const lanes = buildBlueprintCanvas(chapters, outlines, []);
    const briefs = new Map([[3, { ...SAMPLE_CHAPTER_BRIEF, chapter_number: 3 }]]);
    const enriched = applyBriefsToBlueprintCanvas(
      lanes,
      briefs,
      SAMPLE_BRIEF_CHARACTERS,
      SAMPLE_GRAPH_NODES,
    );
    const card = enriched[0].chapters[0];
    expect(card.brief?.povName).toBe("Alice");
    expect(graphNodesOnCanvas(enriched).map((n) => n.id).sort()).toEqual([
      "sg_main",
      "sg_sub2",
    ]);
    expect(chapterMatchesGraphNode(card, "sg_main")).toBe(true);
    expect(chapterMatchesGraphNode(card, "sg_sub1")).toBe(false);
  });
});
