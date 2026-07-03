import type { ChapterSummary } from "../api/client";
import type { PipelineStep } from "./chapterPipeline";

const PIPELINE_BUCKETS: PipelineStep[] = [
  "none", "drafted", "revised", "validated", "approved", "final",
];

export interface PipelineCounts {
  none: number;
  drafted: number;
  revised: number;
  validated: number;
  approved: number;
  final: number;
}

export interface WritingStats {
  totalWords: number;
  chapterCount: number;
  pipeline: PipelineCounts;
  completionPct: number;
  nextAction: string;
  nextChapter?: number;
  zeroWordChapters: number[];
  missingFinalChapters: number[];
}

export function countPipeline(chapters: ChapterSummary[]): PipelineCounts {
  const counts: PipelineCounts = {
    none: 0, drafted: 0, revised: 0, validated: 0, approved: 0, final: 0,
  };
  for (const c of chapters) {
    const step = (c.pipeline_step || "none").toLowerCase() as PipelineStep;
    if (step in counts) counts[step]++;
    else counts.none++;
  }
  return counts;
}

export function computeNextAction(
  chapters: ChapterSummary[],
  nextChapterNumber: number,
): { label: string; chapter?: number } {
  const sorted = [...chapters].sort((a, b) => a.number - b.number);

  const firstNone = sorted.find(
    (c) => c.pipeline_step === "none" || c.status === "planned",
  );
  if (firstNone) {
    return { label: `Draft chapter ${firstNone.number}`, chapter: firstNone.number };
  }

  const firstDrafted = sorted.find((c) => c.pipeline_step === "drafted");
  if (firstDrafted) {
    return { label: `Revise chapter ${firstDrafted.number}`, chapter: firstDrafted.number };
  }

  const firstRevised = sorted.find((c) => c.pipeline_step === "revised");
  if (firstRevised) {
    return { label: `Validate chapter ${firstRevised.number}`, chapter: firstRevised.number };
  }

  const firstPromote = sorted.find(
    (c) => c.pipeline_step === "validated" || c.pipeline_step === "approved",
  );
  if (firstPromote) {
    return {
      label: `Promote or final review chapter ${firstPromote.number}`,
      chapter: firstPromote.number,
    };
  }

  if (chapters.length === 0) {
    return { label: `Plan chapter ${nextChapterNumber}` };
  }

  const allFinal = chapters.every((c) => c.pipeline_step === "final");
  if (allFinal) {
    return { label: "Export manuscript or plan next chapter" };
  }

  return { label: `Plan chapter ${nextChapterNumber}` };
}

export function buildWritingStats(
  chapters: ChapterSummary[],
  nextChapterNumber: number,
): WritingStats {
  const totalWords = chapters.reduce((s, c) => s + c.word_count, 0);
  const pipeline = countPipeline(chapters);
  const chapterCount = chapters.length;
  const completionPct = chapterCount
    ? Math.round((pipeline.final / chapterCount) * 100)
    : 0;
  const next = computeNextAction(chapters, nextChapterNumber);
  const zeroWordChapters = chapters.filter((c) => c.word_count === 0).map((c) => c.number);
  const missingFinalChapters = chapters
    .filter((c) => c.pipeline_step !== "final")
    .map((c) => c.number);

  return {
    totalWords,
    chapterCount,
    pipeline,
    completionPct,
    nextAction: next.label,
    nextChapter: next.chapter,
    zeroWordChapters,
    missingFinalChapters,
  };
}

export { PIPELINE_BUCKETS };
