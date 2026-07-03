import type {
  ChapterBriefSummary,
  ChapterSummary,
  CharacterSummary,
  PlotThreadSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { characterNameById } from "./chapterBrief";

export type BlueprintViewMode = "compact" | "detailed";

export const BLUEPRINT_VIEW_KEY = "novel-os:blueprint-view-mode";

export interface PlotThreadRef {
  id: string;
  name: string;
  thread_type: string;
  matchedLabel: string;
}

export interface StoryGraphNodeRef {
  id: string;
  title: string;
  kind: string;
}

export interface ChapterBriefDisplay {
  hasBrief: boolean;
  povName: string | null;
  activeNodes: StoryGraphNodeRef[];
  activeCharacterNames: string[];
  requiredBeatsSummary: string | null;
}

export interface BlueprintChapterCard {
  chapter: ChapterSummary;
  outlineSnippet: string | null;
  plotThreads: PlotThreadRef[];
  brief: ChapterBriefDisplay | null;
}

export interface BlueprintActLane {
  act: 1 | 2 | 3;
  label: string;
  chapters: BlueprintChapterCard[];
}

const ACT_LABELS: Record<1 | 2 | 3, string> = {
  1: "Act I — Setup",
  2: "Act II — Confrontation",
  3: "Act III — Resolution",
};

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Case-insensitive mention check; short labels require word boundaries. */
export function textMentionsLabel(text: string, label: string): boolean {
  const needle = label.trim();
  if (!needle || needle.length < 2) return false;
  if (needle.length < 4) {
    return new RegExp(`\\b${escapeRegex(needle)}\\b`, "i").test(text);
  }
  return text.toLowerCase().includes(needle.toLowerCase());
}

export function outlineSnippet(text: string | null | undefined, maxLen = 120): string | null {
  if (!text?.trim()) return null;
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= maxLen) return flat;
  return `${flat.slice(0, maxLen - 1)}…`;
}

export function threadSearchLabels(thread: PlotThreadSummary): string[] {
  const labels = [thread.name, ...thread.subplots];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of labels) {
    const label = raw.trim();
    const key = label.toLowerCase();
    if (!label || seen.has(key)) continue;
    seen.add(key);
    out.push(label);
  }
  return out;
}

export function matchPlotThreadsInText(
  text: string,
  threads: PlotThreadSummary[],
): PlotThreadRef[] {
  if (!text.trim()) return [];
  const matched: PlotThreadRef[] = [];
  const seenIds = new Set<string>();

  for (const thread of threads) {
    for (const label of threadSearchLabels(thread)) {
      if (!textMentionsLabel(text, label)) continue;
      if (seenIds.has(thread.id)) break;
      seenIds.add(thread.id);
      matched.push({
        id: thread.id,
        name: thread.name,
        thread_type: thread.thread_type,
        matchedLabel: label,
      });
      break;
    }
  }

  return matched.sort((a, b) => a.name.localeCompare(b.name));
}

export function actSplitIndices(chapterCount: number): [number, number, number] {
  if (chapterCount <= 0) return [0, 0, 0];
  if (chapterCount === 1) return [1, 0, 0];
  if (chapterCount === 2) return [1, 1, 0];
  const act1End = Math.ceil(chapterCount / 3);
  const act2End = Math.ceil((2 * chapterCount) / 3);
  return [act1End, act2End - act1End, chapterCount - act2End];
}

export function groupChaptersIntoActs(chapters: ChapterSummary[]): BlueprintActLane[] {
  const sorted = [...chapters].sort((a, b) => a.number - b.number);
  const [a1, a2, a3] = actSplitIndices(sorted.length);
  const slices = [
    sorted.slice(0, a1),
    sorted.slice(a1, a1 + a2),
    sorted.slice(a1 + a2, a1 + a2 + a3),
  ];

  return ([1, 2, 3] as const).map((act, i) => ({
    act,
    label: ACT_LABELS[act],
    chapters: slices[i].map((chapter) => ({
      chapter,
      outlineSnippet: null,
      plotThreads: [],
      brief: null,
    })),
  }));
}

export function buildBlueprintCanvas(
  chapters: ChapterSummary[],
  outlinesByChapter: Map<number, string | null>,
  threads: PlotThreadSummary[],
  snippetLen = 120,
): BlueprintActLane[] {
  const lanes = groupChaptersIntoActs(chapters);

  return lanes.map((lane) => ({
    ...lane,
    chapters: lane.chapters.map((card) => {
      const outline = outlinesByChapter.get(card.chapter.number) ?? null;
      const searchText = [outline, card.chapter.title].filter(Boolean).join("\n");
      return {
        chapter: card.chapter,
        outlineSnippet: outlineSnippet(outline, snippetLen),
        plotThreads: matchPlotThreadsInText(searchText, threads),
        brief: card.brief,
      };
    }),
  }));
}

export function requiredBeatsSummary(
  beats: string[],
  maxBeats = 2,
  maxLen = 96,
): string | null {
  const trimmed = beats.map((b) => b.trim()).filter(Boolean);
  if (trimmed.length === 0) return null;
  const shown = trimmed.slice(0, maxBeats);
  let text = shown.join(" · ");
  if (trimmed.length > maxBeats) {
    text += ` (+${trimmed.length - maxBeats} more)`;
  }
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1)}…`;
}

export function buildChapterBriefDisplay(
  brief: ChapterBriefSummary | null | undefined,
  characters: CharacterSummary[],
  nodes: StoryGraphNodeSummary[],
): ChapterBriefDisplay | null {
  if (!brief) return null;
  const charNames = characterNameById(characters);
  const nodeByNodeId = new Map(nodes.map((n) => [n.id, n]));

  const povName = brief.pov_character_id
    ? charNames.get(brief.pov_character_id) ?? null
    : null;
  const activeNodes = (brief.active_node_ids ?? [])
    .map((id) => {
      const node = nodeByNodeId.get(id);
      if (!node) return null;
      return { id: node.id, title: node.title, kind: node.kind };
    })
    .filter((n): n is StoryGraphNodeRef => n !== null)
    .sort((a, b) => a.title.localeCompare(b.title));

  const activeCharacterNames = (brief.active_character_ids ?? [])
    .map((id) => charNames.get(id))
    .filter((name): name is string => Boolean(name));

  const beatsSummary = requiredBeatsSummary(brief.required_beats ?? []);

  const hasBrief = Boolean(
    povName
    || activeNodes.length
    || activeCharacterNames.length
    || beatsSummary
    || brief.continuity_notes?.trim()
    || brief.ending_hook?.trim(),
  );

  if (!hasBrief) return null;

  return {
    hasBrief: true,
    povName,
    activeNodes,
    activeCharacterNames,
    requiredBeatsSummary: beatsSummary,
  };
}

export function applyBriefsToBlueprintCanvas(
  lanes: BlueprintActLane[],
  briefsByChapter: Map<number, ChapterBriefSummary | null>,
  characters: CharacterSummary[],
  nodes: StoryGraphNodeSummary[],
): BlueprintActLane[] {
  return lanes.map((lane) => ({
    ...lane,
    chapters: lane.chapters.map((card) => ({
      ...card,
      brief: buildChapterBriefDisplay(
        briefsByChapter.get(card.chapter.number) ?? null,
        characters,
        nodes,
      ),
    })),
  }));
}

export function graphNodesOnCanvas(lanes: BlueprintActLane[]): StoryGraphNodeRef[] {
  const byId = new Map<string, StoryGraphNodeRef>();
  for (const lane of lanes) {
    for (const card of lane.chapters) {
      for (const node of card.brief?.activeNodes ?? []) {
        if (!byId.has(node.id)) byId.set(node.id, node);
      }
    }
  }
  return [...byId.values()].sort((a, b) => a.title.localeCompare(b.title));
}

export function chapterMatchesGraphNode(
  card: BlueprintChapterCard,
  nodeId: string | null,
): boolean {
  if (!nodeId) return true;
  return (card.brief?.activeNodes ?? []).some((n) => n.id === nodeId);
}

export function readBlueprintViewMode(): BlueprintViewMode {
  try {
    const v = localStorage.getItem(BLUEPRINT_VIEW_KEY);
    if (v === "compact" || v === "detailed") return v;
  } catch {
    /* ignore */
  }
  return "detailed";
}

export function writeBlueprintViewMode(mode: BlueprintViewMode): void {
  try {
    localStorage.setItem(BLUEPRINT_VIEW_KEY, mode);
  } catch {
    /* ignore */
  }
}
