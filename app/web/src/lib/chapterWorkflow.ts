/** Track last-accessed chapter (binder) and last function per chapter (buttons). */

export type ChapterFunction =
  | "write"
  | "edit"
  | "validate"
  | "approve"
  | "regenerate"
  | "redraft-from-brief"
  | "expand"
  | "format-paragraphs"
  | "check-dialogue-quotes"
  | "align-boundary"
  | "outline-notes"
  | "outline-text"
  | "mine-plots"
  | "mine-characters"
  | "mine-bible"
  | "extract";

const STORAGE_KEY = "novel-os:chapter-workflow-v2";

type ProjectWorkflow = {
  /** Single chapter — blue dot in binder / board */
  lastAccessedChapter: number | null;
  /** Per-chapter last pipeline action — blue dot on buttons in that chapter only */
  lastFunctionByChapter: Record<string, ChapterFunction>;
};

type Store = Record<string, ProjectWorkflow>;

function emptyProject(): ProjectWorkflow {
  return { lastAccessedChapter: null, lastFunctionByChapter: {} };
}

function readStore(): Store {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent("novel-os:workflow"));
}

function projectStore(store: Store, projectId: string): ProjectWorkflow {
  if (!store[projectId]) store[projectId] = emptyProject();
  return store[projectId];
}

/** Opening a chapter — binder blue dot follows this (one chapter per project). */
export function recordChapterVisit(projectId: string, chapter: number) {
  const store = readStore();
  const p = projectStore(store, projectId);
  p.lastAccessedChapter = chapter;
  writeStore(store);
}

/** Running a pipeline action — updates button marker for this chapter + last accessed. */
export function recordChapterFunction(
  projectId: string,
  chapter: number,
  fn: ChapterFunction,
) {
  const store = readStore();
  const p = projectStore(store, projectId);
  p.lastAccessedChapter = chapter;
  p.lastFunctionByChapter[String(chapter)] = fn;
  writeStore(store);
}

export function getLastAccessedChapter(projectId: string): number | null {
  const ch = readStore()[projectId]?.lastAccessedChapter;
  return ch != null ? ch : null;
}

export function getChapterFunction(
  projectId: string,
  chapter: number,
): ChapterFunction | null {
  return readStore()[projectId]?.lastFunctionByChapter[String(chapter)] ?? null;
}

export function reassignChapterWorkflowMarker(
  projectId: string,
  fromChapter: number,
  toChapter: number,
  swap = false,
) {
  if (fromChapter === toChapter) return;
  const store = readStore();
  const p = store[projectId];
  if (!p) return;
  if (p.lastAccessedChapter === fromChapter) {
    p.lastAccessedChapter = toChapter;
  } else if (swap && p.lastAccessedChapter === toChapter) {
    p.lastAccessedChapter = fromChapter;
  }
  const fromFn = p.lastFunctionByChapter[String(fromChapter)];
  const toFn = p.lastFunctionByChapter[String(toChapter)];
  delete p.lastFunctionByChapter[String(fromChapter)];
  delete p.lastFunctionByChapter[String(toChapter)];
  if (fromFn) p.lastFunctionByChapter[String(toChapter)] = fromFn;
  if (swap && toFn) p.lastFunctionByChapter[String(fromChapter)] = toFn;
  writeStore(store);
}

export function remapChapterWorkflowMarkers(
  projectId: string,
  mapping: Array<{ from_number: number; to_number: number }>,
) {
  if (mapping.length === 0) return;
  const store = readStore();
  const p = store[projectId];
  if (!p) return;
  const lastMove = mapping.find((row) => row.from_number === p.lastAccessedChapter);
  if (lastMove) p.lastAccessedChapter = lastMove.to_number;
  const moved: Record<string, ChapterFunction> = {};
  for (const row of mapping) {
    const fromKey = String(row.from_number);
    const fn = p.lastFunctionByChapter[fromKey];
    if (fn) moved[String(row.to_number)] = fn;
    delete p.lastFunctionByChapter[fromKey];
  }
  Object.assign(p.lastFunctionByChapter, moved);
  writeStore(store);
}

export const CHAPTER_FUNCTION_LABELS: Record<ChapterFunction, string> = {
  write: "Generate Draft",
  edit: "Revise",
  validate: "Validate",
  approve: "Approve",
  regenerate: "Regenerate",
  "redraft-from-brief": "Redraft from brief",
  expand: "Expand placeholders",
  "format-paragraphs": "AI Paragraphs",
  "check-dialogue-quotes": "Check dialogue quotes",
  "align-boundary": "Fix chapter alignment",
  "outline-notes": "Outline from notes",
  "outline-text": "Outline from text",
  "mine-plots": "Mine plots",
  "mine-characters": "Mine characters",
  "mine-bible": "Mine story bible",
  extract: "Extract",
};
