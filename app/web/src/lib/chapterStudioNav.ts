import type { ChapterStages } from "../api/client";
import type { StageKey } from "../components/PipelineFlow";

/** Where the author is working in Chapter Studio — preserved across chapter switches. */
export type ChapterStudioPlace = "brief" | "outline" | "prose";

const STORAGE_KEY = "novel-os:chapter-studio-place-v1";

type Store = Record<string, ChapterStudioPlace>;

function readStore(): Store {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function readStudioPlace(projectId: string): ChapterStudioPlace | null {
  return readStore()[projectId] ?? null;
}

export function writeStudioPlace(projectId: string, place: ChapterStudioPlace) {
  const store = readStore();
  store[projectId] = place;
  writeStore(store);
}

export function studioPlaceFromSelection(
  briefExpanded: boolean,
  selected: StageKey,
): ChapterStudioPlace {
  if (briefExpanded) return "brief";
  if (selected === "outline") return "outline";
  return "prose";
}

/** Highest prose stage available — where the author would continue work. */
export function bestProseStage(stages: ChapterStages): StageKey {
  if (stages.final != null) return "final";
  if (stages.revised != null) return "revised";
  if (stages.draft != null) return "draft";
  return "outline";
}

export function stageForStudioPlace(
  place: ChapterStudioPlace,
  stages: ChapterStages,
): StageKey {
  if (place === "outline") return "outline";
  return bestProseStage(stages);
}
