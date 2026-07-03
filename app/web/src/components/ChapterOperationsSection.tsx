import ToolTip from "./ToolTip";

export default function ChapterOperationsSection({
  busy,
  onInsertBefore,
  onInsertAfter,
  onDuplicate,
  onMergeNext,
  onRenumber,
  onDelete,
}: {
  busy: boolean;
  onInsertBefore: () => void;
  onInsertAfter: () => void;
  onDuplicate: () => void;
  onMergeNext: () => void;
  onRenumber: () => void;
  onDelete: () => void;
}) {
  const disabled = busy;

  return (
    <div className="rounded-lg border border-paper-line bg-paper/60 px-3 py-3">
      <div className="mb-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Chapter operations</p>
        <p className="text-[12px] text-ink-muted">Insert, duplicate, renumber, merge, or delete this chapter.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ToolTip id="chapter.insertBefore">
          <button
            type="button"
            onClick={onInsertBefore}
            disabled={disabled}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
          >
            Insert Before
          </button>
        </ToolTip>
        <ToolTip id="chapter.insertAfter">
          <button
            type="button"
            onClick={() => onInsertAfter()}
            disabled={disabled}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
          >
            Insert After
          </button>
        </ToolTip>
        <ToolTip id="chapter.duplicateChapter">
          <button
            type="button"
            onClick={onDuplicate}
            disabled={disabled}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
          >
            Duplicate
          </button>
        </ToolTip>
        <ToolTip id="chapter.mergeNextChapter">
          <button
            type="button"
            onClick={onMergeNext}
            disabled={disabled}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-[12px] font-semibold text-red-600 transition-colors hover:bg-red-50 disabled:opacity-40"
          >
            Merge Next
          </button>
        </ToolTip>
        <ToolTip id="chapter.renumberChapter">
          <button
            type="button"
            onClick={onRenumber}
            disabled={disabled}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
          >
            # Renumber
          </button>
        </ToolTip>
        <ToolTip id="chapter.deleteChapter">
          <button
            type="button"
            onClick={onDelete}
            disabled={disabled}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-[12px] font-semibold text-red-600 transition-colors hover:bg-red-50 disabled:opacity-40"
          >
            Delete
          </button>
        </ToolTip>
      </div>
    </div>
  );
}
