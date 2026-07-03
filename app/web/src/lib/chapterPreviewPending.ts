/** Local flags when a chapter has AI preview results awaiting review. */

const KEY = "novel-os:chapter-preview-pending";

type Store = Record<string, Record<string, boolean>>;

function readStore(): Store {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  localStorage.setItem(KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent("novel-os:preview-pending"));
}

export function setChapterPreviewPending(projectId: string, chapter: number, pending: boolean) {
  const store = readStore();
  if (!store[projectId]) store[projectId] = {};
  if (pending) store[projectId][String(chapter)] = true;
  else delete store[projectId][String(chapter)];
  writeStore(store);
}

export function reassignChapterPreviewPending(
  projectId: string,
  fromChapter: number,
  toChapter: number,
  swap = false,
) {
  if (fromChapter === toChapter) return;
  const store = readStore();
  const project = store[projectId];
  if (!project) return;
  const fromPending = Boolean(project[String(fromChapter)]);
  const toPending = Boolean(project[String(toChapter)]);
  if (!fromPending && !(swap && toPending)) return;
  delete project[String(fromChapter)];
  delete project[String(toChapter)];
  if (fromPending) project[String(toChapter)] = true;
  if (swap && toPending) project[String(fromChapter)] = true;
  writeStore(store);
}

export function remapChapterPreviewPending(
  projectId: string,
  mapping: Array<{ from_number: number; to_number: number }>,
) {
  if (mapping.length === 0) return;
  const store = readStore();
  const project = store[projectId];
  if (!project) return;
  const moved: Record<string, boolean> = {};
  for (const row of mapping) {
    const fromKey = String(row.from_number);
    if (project[fromKey]) moved[String(row.to_number)] = true;
    delete project[fromKey];
  }
  Object.assign(project, moved);
  writeStore(store);
}

export function hasChapterPreviewPending(projectId: string, chapter: number): boolean {
  return Boolean(readStore()[projectId]?.[String(chapter)]);
}

export function projectChaptersWithPendingPreviews(projectId: string): Set<number> {
  const rows = readStore()[projectId] ?? {};
  return new Set(Object.keys(rows).filter((k) => rows[k]).map(Number));
}
