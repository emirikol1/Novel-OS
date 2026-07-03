import { Link, useParams } from "react-router-dom";
import type { ChapterSummary } from "../api/client";
import ChapterPipelineStatus from "./ChapterPipelineStatus";
import DeleteButton from "./DeleteButton";
import PendingAiStar from "./PendingAiStar";
import ToolTip from "./ToolTip";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import { useWorkflowMarkers } from "../hooks/useWorkflowMarkers";
import { hasChapterPreviewPending } from "../lib/chapterPreviewPending";

export default function ChapterBoard({
  chapters,
  onDelete,
  onRenumber,
}: {
  chapters: ChapterSummary[];
  onDelete?: (c: ChapterSummary) => void;
  onRenumber?: (c: ChapterSummary) => void;
}) {
  const { id = "" } = useParams();
  const { lastAccessedChapter } = useWorkflowMarkers(id);
  const { isProjectJobRunning } = useBackgroundJob();

  if (chapters.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-12 text-center">
        <p className="font-display text-[18px] text-ink-text">No chapters planned yet</p>
        <p className="mt-2 text-[13.5px] text-ink-muted">
          Plan one with <code className="font-mono text-[12px]">plan chapter --number 1</code>
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {chapters.map((c) => {
        const isLastAccessed = lastAccessedChapter === c.number;
        return (
        <div
          key={c.number}
          className="group relative flex flex-col rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
        >
          {onRenumber && (
            <ToolTip id="chapter.renumberChapter">
              <button type="button"
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); onRenumber(c); }}
                      aria-label={`Renumber chapter ${c.number}`}
                      className="absolute right-10 top-2 z-10 rounded-md p-1.5 text-[11px] font-bold text-ink-muted opacity-0 transition-opacity hover:bg-ink/5 hover:text-ink-text group-hover:opacity-100">
                #
              </button>
            </ToolTip>
          )}
          {onDelete && (
            <DeleteButton
              label={`Delete chapter ${c.number}`}
              message={`Delete chapter ${c.number}${c.title ? `: "${c.title}"` : ""}? All outline, draft, and manuscript files for this chapter will be removed.`}
              confirmLabel="Delete chapter"
              onConfirm={() => onDelete(c)}
              tipId="chapter.deleteChapter"
              className="absolute right-2 top-2 z-10 opacity-0 transition-opacity group-hover:opacity-100"
            />
          )}
          <Link
            to={`/projects/${id}/chapters/${c.number}`}
            className="flex flex-1 flex-col p-5"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-display text-[13px] font-semibold uppercase tracking-[0.12em] text-amber-deep">
                Ch {c.number}
                {isProjectJobRunning("landed-beats", id, String(c.number)) && (
                  <span
                    className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-amber-deep align-middle"
                    title="Landed beats extraction running"
                    aria-label="Landed beats extraction running"
                  />
                )}
                {hasChapterPreviewPending(id, c.number) && (
                  <ToolTip id="chapter.aiPreviewPending">
                    <PendingAiStar />
                  </ToolTip>
                )}
              </span>
              <span className="inline-flex items-center gap-1">
                <ChapterPipelineStatus chapter={c} />
              </span>
            </div>
            {isLastAccessed ? (
              <ToolTip id="chapter.resumeWorkflow">
                <span
                  className="mt-3 font-display text-[19px] font-medium leading-snug text-amber-deep transition-colors group-hover:text-amber-deep"
                >
                  {c.title || "Untitled"}
                </span>
              </ToolTip>
            ) : (
              <span
                className="mt-3 font-display text-[19px] font-medium leading-snug text-ink-text transition-colors group-hover:text-amber-deep"
              >
                {c.title || "Untitled"}
              </span>
            )}
            <div className="mt-5 flex items-center gap-3 text-[12.5px] text-ink-muted">
              <span className="nums">{c.word_count.toLocaleString()} words</span>
              {c.pov && (
                <>
                  <span className="text-paper-muted">·</span>
                  <span className="truncate">POV {c.pov}</span>
                </>
              )}
            </div>
          </Link>
        </div>
      );})}
    </div>
  );
}
