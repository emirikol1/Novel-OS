import { useEffect, useState } from "react";
import { api, type ChapterMinePreview, type MineKind } from "../api/client";
import Modal from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import { setMinePreviewPending } from "../lib/minePreviewPending";
import { fallbackMinePreviewUi } from "../lib/minePreviewSummary";

const KIND_LABEL: Record<MineKind, string> = {
  plots: "Plot threads",
  characters: "Characters",
  bible: "Story bible",
};

const KIND_INTRO: Record<MineKind, string> = {
  plots:
    "The AI read this chapter and suggested plot updates. Nothing changes until you click Apply — this is a review step, not automatic editing.",
  characters:
    "The AI read this chapter and suggested cast profile updates. Nothing changes until you click Apply.",
  bible:
    "The AI read this chapter and suggested durable story bible notes. Nothing changes until you click Apply.",
};

function uiFromPreview(preview: ChapterMinePreview) {
  return preview.ui_summary ?? fallbackMinePreviewUi(preview.kind, preview.changes);
}

export default function ChapterMinePreviewModal({
  open,
  onClose,
  projectId,
  chapterNumber,
  kind,
  onApplied,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapterNumber: number;
  kind: MineKind;
  onApplied: () => void;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState<ChapterMinePreview | null>(null);

  useEffect(() => {
    if (!open) return;
    void loadPreview();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when modal opens
  }, [open, projectId, chapterNumber, kind]);

  async function loadPreview() {
    setLoading(true);
    try {
      const row = await api.getChapterMinePreview(projectId, chapterNumber, kind);
      setPreview(row);
      setMinePreviewPending(projectId, kind, chapterNumber, Boolean(row));
      if (row) {
        const ui = uiFromPreview(row);
        if (!ui.can_apply) {
          toast("Mining finished — nothing could be applied. Read the summary below.", "info");
        }
      }
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setLoading(false);
    }
  }

  async function closeAndDiscard() {
    if (!preview) {
      onClose();
      return;
    }
    try {
      await api.discardChapterMinePreview(projectId, chapterNumber, kind);
      setMinePreviewPending(projectId, kind, chapterNumber, false);
      setPreview(null);
      onClose();
    } catch (e) {
      toast(String(e), "error");
    }
  }

  async function applyPreview() {
    if (!preview) return;
    const ui = uiFromPreview(preview);
    if (!ui.can_apply) return;
    setApplying(true);
    try {
      const result = await api.applyChapterMinePreview(projectId, chapterNumber, kind);
      setMinePreviewPending(projectId, kind, chapterNumber, false);
      setPreview(null);
      toast(
        `Applied ${result.changes.length} ${KIND_LABEL[kind].toLowerCase()} update(s) from chapter ${chapterNumber}`,
        "success",
      );
      onApplied();
      onClose();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setApplying(false);
    }
  }

  const ui = preview ? uiFromPreview(preview) : null;

  return (
    <Modal
      open={open}
      onClose={() => void closeAndDiscard()}
      title={`Review ${KIND_LABEL[kind]} — Chapter ${chapterNumber}`}
      size="wide"
    >
      <p className="mb-3 text-[13px] leading-relaxed text-ink-text">
        {KIND_INTRO[kind]}
      </p>

      {loading && <p className="text-[13px] text-ink-muted">Loading preview…</p>}

      {!loading && preview && ui && (
        <div className="space-y-4">
          <div className="rounded-lg border border-paper-line bg-paper/50 px-4 py-3 text-[13px] leading-relaxed text-ink-text">
            {ui.advice}
          </div>

          {ui.proposed.length > 0 && (
            <section>
              <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                What the AI extracted
              </h3>
              <ul className="space-y-1 rounded-lg border border-paper-line bg-paper/30 p-3 text-[13px] text-ink-text">
                {ui.proposed.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          )}

          {ui.will_apply.length > 0 && (
            <section>
              <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-st-approved">
                Will apply ({ui.will_apply.length})
              </h3>
              <ul className="space-y-1 rounded-lg border border-st-approved/30 bg-st-approved/5 p-3 text-[13px] text-ink-text">
                {ui.will_apply.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          )}

          {ui.skipped.length > 0 && (
            <section>
              <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                Skipped ({ui.skipped.length})
              </h3>
              <ul className="space-y-1 rounded-lg border border-paper-line bg-paper/20 p-3 text-[13px] text-ink-muted">
                {ui.skipped.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          )}

          {ui.will_apply.length === 0 && ui.skipped.length === 0 && (
            <p className="text-[13px] text-ink-muted">No registry changes proposed.</p>
          )}

          {preview.report_path && (
            <p className="text-[12px] text-ink-muted">
              Full agent report is saved in project feedback (chapter {chapterNumber} mine {kind}).
            </p>
          )}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12px] text-ink-muted">
          {ui?.can_apply
            ? "Apply writes the green items to your project."
            : "Nothing to apply — use Discard to close."}
        </p>
        <div className="flex flex-wrap gap-2">
          <ToolTip id="modal.minePreviewReview">
            <button
              type="button"
              disabled={applying}
              onClick={() => void closeAndDiscard()}
              className="rounded-lg border border-paper-line bg-paper px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
            >
              Discard
            </button>
          </ToolTip>
          <ToolTip id="modal.minePreviewReview">
            <button
              type="button"
              disabled={applying || loading || !preview || !ui?.can_apply}
              onClick={() => void applyPreview()}
              className="rounded-lg bg-amber-deep px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-amber-deep/90 disabled:cursor-not-allowed disabled:opacity-40"
              title={ui?.can_apply ? undefined : "No successful updates to apply"}
            >
              {applying ? "Applying…" : "Apply to project"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}
