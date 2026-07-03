import { api, type RedraftPreview, type RegeneratePreview } from "../api/client";
import type { StageKey } from "../components/PipelineFlow";
import { setChapterPreviewPending } from "./chapterPreviewPending";

const STAGE_KEYS: StageKey[] = ["outline", "draft", "revised", "final"];

function stageFromSource(source: string | undefined): StageKey | null {
  if (source && STAGE_KEYS.includes(source as StageKey)) return source as StageKey;
  return null;
}

/** Map active preview payloads to pipeline stages that need review. */
export function previewPendingStages(
  regenerate: RegeneratePreview | null | undefined,
  outline: RegeneratePreview | null | undefined,
  expand: RegeneratePreview | null | undefined,
  paragraphs: RegeneratePreview | null | undefined,
  redraft?: RedraftPreview | null | undefined,
): StageKey[] {
  const out: StageKey[] = [];
  if (outline) out.push("outline");
  for (const preview of [regenerate, expand, paragraphs]) {
    const stage = stageFromSource(preview?.source);
    if (stage && !out.includes(stage)) out.push(stage);
  }
  if (redraft && !out.includes("draft")) out.push("draft");
  return out;
}

/** Read server-side preview files and sync the chapter-list star flag. */
export async function syncChapterPreviewPendingFromApi(
  projectId: string,
  chapter: number,
): Promise<boolean> {
  const [regenerate, outline, expand, paragraphs, redraft, beats] = await Promise.all([
    api.getRegeneratePreview(projectId, chapter),
    api.getOutlinePreview(projectId, chapter),
    api.getExpandPreview(projectId, chapter),
    api.getParagraphsPreview(projectId, chapter),
    api.getRedraftPreview(projectId, chapter),
    api.getChapterBeatCandidatesPreview(projectId, chapter),
  ]);
  const pending = Boolean(regenerate || outline || expand || paragraphs || redraft || beats);
  setChapterPreviewPending(projectId, chapter, pending);
  return pending;
}

/** Refresh preview stars for every chapter on the project dashboard. */
export async function syncProjectPreviewPendingFromApi(
  projectId: string,
  chapters: number[],
): Promise<void> {
  await Promise.all(chapters.map((n) => syncChapterPreviewPendingFromApi(projectId, n)));
}
