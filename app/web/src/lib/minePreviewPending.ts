/** Pending chapter mine previews awaiting accept/discard. */

import { api } from "../api/client";

const KEY = "novel-os:mine-preview-pending";

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
  window.dispatchEvent(new CustomEvent("novel-os:mine-preview-pending"));
}

export function minePreviewKey(kind: string, chapter: number): string {
  return `${kind}:${chapter}`;
}

export function setMinePreviewPending(
  projectId: string,
  kind: string,
  chapter: number,
  pending: boolean,
) {
  const store = readStore();
  if (!store[projectId]) store[projectId] = {};
  const key = minePreviewKey(kind, chapter);
  if (pending) store[projectId][key] = true;
  else delete store[projectId][key];
  writeStore(store);
}

export function hasMinePreviewPending(
  projectId: string,
  kind: string,
  chapter: number,
): boolean {
  return Boolean(readStore()[projectId]?.[minePreviewKey(kind, chapter)]);
}

export function projectMinePreviewsPending(projectId: string, kind?: string): Array<{ kind: string; chapter: number }> {
  const rows = readStore()[projectId] ?? {};
  const out: Array<{ kind: string; chapter: number }> = [];
  for (const [key, pending] of Object.entries(rows)) {
    if (!pending) continue;
    const [k, ch] = key.split(":");
    if (kind && k !== kind) continue;
    const chapter = Number(ch);
    if (!k || !Number.isFinite(chapter)) continue;
    out.push({ kind: k, chapter });
  }
  return out.sort((a, b) => a.chapter - b.chapter);
}

export async function syncMinePreviewPendingFromApi(projectId: string) {
  const previews = await api.listChapterMinePreviews(projectId);
  const store = readStore();
  store[projectId] = {};
  for (const row of previews) {
    store[projectId][minePreviewKey(row.kind, row.chapter_number)] = true;
  }
  writeStore(store);
}
