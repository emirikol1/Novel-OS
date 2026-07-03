import type { ChapterBeatSummary } from "../api/client";

export type BeatStatus = "planned" | "landed";

export type ChapterBeatDraft = {
  id: string;
  title: string;
  summary: string;
  sort_order: number;
  status: BeatStatus;
  linked_node_ids: string[];
};

export function sortBeats(beats: ChapterBeatDraft[]): ChapterBeatDraft[] {
  return [...beats].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
}

export function beatsFromSummaries(list: ChapterBeatSummary[]): ChapterBeatDraft[] {
  return sortBeats(
    list.map((b) => ({
      id: b.id,
      title: b.title ?? "",
      summary: b.summary ?? "",
      sort_order: b.sort_order ?? 0,
      status: b.status ?? "planned",
      linked_node_ids: [...(b.linked_node_ids ?? [])],
    })),
  );
}

export function beatDisplayText(b: ChapterBeatDraft): string {
  const title = b.title.trim();
  const summary = b.summary.trim();
  if (title && summary && summary.toLowerCase() !== title.toLowerCase()) {
    return `${title} — ${summary}`;
  }
  return title || summary || "Untitled beat";
}

export function newLocalBeat(_chapterNumber: number, sortOrder: number): ChapterBeatDraft {
  return {
    id: `temp_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    title: "",
    summary: "",
    sort_order: sortOrder,
    status: "planned",
    linked_node_ids: [],
  };
}

export function beatCounts(beats: ChapterBeatDraft[]): { planned: number; landed: number } {
  let planned = 0;
  let landed = 0;
  for (const b of beats) {
    if (b.status === "landed") landed += 1;
    else planned += 1;
  }
  return { planned, landed };
}
