import { useCallback, useEffect, useRef, useState } from "react";
import { api, type StoryGraphNodeSummary } from "../api/client";
import DeleteButton from "./DeleteButton";
import EditorSaveBar, { formatSavedAt } from "./EditorSaveBar";
import ToolTip from "./ToolTip";
import { fieldClass } from "./Modal";
import { useToast } from "./Toaster";
import {
  beatCounts,
  beatDisplayText,
  beatsFromSummaries,
  sortBeats,
  type ChapterBeatDraft,
  type BeatStatus,
} from "../lib/chapterBeats";

type BeatFieldDraft = {
  title: string;
  summary: string;
};

export default function ChapterBeatBoard({
  projectId,
  chapterNumber,
  graphNodes: _graphNodes,
  disabled = false,
  refreshToken = 0,
  onChange,
}: {
  projectId: string;
  chapterNumber: number;
  graphNodes?: StoryGraphNodeSummary[];
  disabled?: boolean;
  refreshToken?: number;
  onChange?: () => void;
}) {
  const toast = useToast();
  const [beats, setBeats] = useState<ChapterBeatDraft[]>([]);
  const [drafts, setDrafts] = useState<Record<string, BeatFieldDraft>>({});
  const [loading, setLoading] = useState(true);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [boardDirty, setBoardDirty] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const beatsRef = useRef(beats);
  beatsRef.current = beats;

  const loadBeats = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listChapterBeats(projectId, chapterNumber);
      const next = beatsFromSummaries(list);
      setBeats(next);
      setDrafts((prev) => {
        const mapped: Record<string, BeatFieldDraft> = {};
        for (const b of next) {
          mapped[b.id] = prev[b.id] ?? { title: b.title, summary: b.summary };
        }
        return mapped;
      });
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      setBeats([]);
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterNumber, toast]);

  useEffect(() => {
    void loadBeats();
  }, [loadBeats, refreshToken]);

  const flashSaved = useCallback(() => {
    setSaveState("saved");
    setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 1500);
  }, []);

  const persistReorder = useCallback(async (orderedIds: string[]) => {
    setSaveState("saving");
    try {
      const updated = await api.reorderChapterBeats(projectId, chapterNumber, orderedIds);
      setBeats(beatsFromSummaries(updated));
      setLastSaved(formatSavedAt());
      onChange?.();
      flashSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      void loadBeats();
    } finally {
      setSaveState("idle");
    }
  }, [projectId, chapterNumber, onChange, toast, flashSaved, loadBeats]);

  const persistBeat = useCallback(async (beatId: string, draft: BeatFieldDraft, status?: BeatStatus) => {
    const title = draft.title.trim();
    if (!title) return;
    setSaveState("saving");
    try {
      const updated = await api.updateChapterBeat(projectId, chapterNumber, beatId, {
        title,
        summary: draft.summary.trim(),
        ...(status ? { status } : {}),
      });
      setBeats((list) => list.map((b) => (b.id === beatId ? beatsFromSummaries([updated])[0] : b)));
      setDrafts((d) => ({ ...d, [beatId]: { title: updated.title, summary: updated.summary ?? "" } }));
      setBoardDirty(false);
      setLastSaved(formatSavedAt());
      onChange?.();
      flashSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setSaveState("idle");
    }
  }, [projectId, chapterNumber, onChange, toast, flashSaved]);

  function queueSave(beatId: string, draft: BeatFieldDraft) {
    clearTimeout(timers.current[beatId]);
    timers.current[beatId] = setTimeout(() => {
      const orig = beatsRef.current.find((b) => b.id === beatId);
      if (!orig || beatId.startsWith("temp_")) return;
      const changed =
        draft.title.trim() !== orig.title.trim()
        || draft.summary.trim() !== (orig.summary ?? "").trim();
      if (changed && draft.title.trim()) void persistBeat(beatId, draft);
    }, 700);
  }

  function patchDraft(beatId: string, patch: Partial<BeatFieldDraft>) {
    setBoardDirty(true);
    setDrafts((d) => {
      const next = { ...d[beatId], ...patch };
      queueSave(beatId, next);
      return { ...d, [beatId]: next };
    });
  }

  async function toggleStatus(beatId: string, nextStatus: BeatStatus) {
    const beat = beatsRef.current.find((b) => b.id === beatId);
    if (!beat || beat.status === nextStatus || beatId.startsWith("temp_")) return;
    const draft = drafts[beatId] ?? { title: beat.title, summary: beat.summary };
    await persistBeat(beatId, draft, nextStatus);
  }

  async function addBeat() {
    if (disabled) return;
    setSaveState("saving");
    try {
      const sortOrder = beats.length;
      const created = await api.createChapterBeat(projectId, chapterNumber, {
        title: "New beat",
        summary: "",
        status: "planned",
        sort_order: sortOrder,
      });
      const row = beatsFromSummaries([created])[0];
      setBeats((list) => sortBeats([...list, row]));
      setDrafts((d) => ({ ...d, [row.id]: { title: row.title, summary: row.summary } }));
      setLastSaved(formatSavedAt());
      onChange?.();
      flashSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setSaveState("idle");
    }
  }

  async function deleteBeat(beat: ChapterBeatDraft) {
    try {
      await api.deleteChapterBeat(projectId, chapterNumber, beat.id);
      setBeats((list) => list.filter((b) => b.id !== beat.id));
      toast("Beat removed", "success");
      onChange?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  function clearDrag() {
    setDragId(null);
    setOverId(null);
  }

  function onDragOverRow(e: React.DragEvent, id: string) {
    e.preventDefault();
    if (!dragId || dragId === id) return;
    setOverId(id);
  }

  async function onDropRow(targetId: string) {
    if (!dragId || dragId === targetId) {
      clearDrag();
      return;
    }
    const ids = beats.map((b) => b.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) {
      clearDrag();
      return;
    }
    ids.splice(from, 1);
    ids.splice(to, 0, dragId);
    setBeats(ids.map((id) => beats.find((b) => b.id === id)!));
    clearDrag();
    void persistReorder(ids);
  }

  const counts = beatCounts(beats);

  if (loading) {
    return (
      <p className="text-[12.5px] text-ink-muted">Loading chapter beats…</p>
    );
  }

  return (
    <div data-testid="chapter-beat-board">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Chapter beats
            {beats.length > 0 && (
              <span className="ml-2 font-normal normal-case text-ink-muted">
                ({counts.planned} planned · {counts.landed} landed)
              </span>
            )}
          </p>
          <p className="mt-0.5 text-[12px] text-ink-muted">
            Chapter-local events for planning and prompts. Durable world facts still belong in Story Bible.
          </p>
        </div>
        <ToolTip id="chapter.beatAdd">
          <button
            type="button"
            onClick={() => void addBeat()}
            disabled={disabled || saveState === "saving"}
            className="text-[12px] font-medium text-ink-text hover:underline disabled:opacity-40"
          >
            + Add beat
          </button>
        </ToolTip>
      </div>

      <EditorSaveBar
        dirty={boardDirty}
        saving={saveState === "saving"}
        lastSaved={lastSaved}
        autosaveOnly
        hint={
          <>
            <span className="font-medium text-ink-text">≡</span> drag to reorder
          </>
        }
        autosaveNote
      />

      {beats.length === 0 ? (
        <p className="text-[12px] text-ink-muted">
          No beats yet — add what must happen in this chapter, or extract landed beats from manuscript.
        </p>
      ) : (
        <ol className="flex flex-col gap-1.5">
          {beats.map((beat) => {
            const d = drafts[beat.id] ?? { title: beat.title, summary: beat.summary };
            const isOver = overId === beat.id && dragId !== beat.id;
            return (
              <li
                key={beat.id}
                data-testid={`beat-card-${beat.id}`}
                onDragOver={(e) => onDragOverRow(e, beat.id)}
                onDrop={() => void onDropRow(beat.id)}
                className={`group rounded-lg border bg-paper-card transition-colors ${
                  isOver ? "border-ink/30 bg-ink/[0.03]" : "border-paper-line"
                } ${dragId === beat.id ? "opacity-40" : ""}`}
              >
                <div className="flex items-start gap-1.5 px-2 py-2">
                  <ToolTip id="chapter.beatReorder">
                    <button
                      type="button"
                      draggable={!disabled}
                      onDragStart={() => setDragId(beat.id)}
                      onDragEnd={clearDrag}
                      aria-label="Drag to reorder beat"
                      disabled={disabled}
                      className="mt-1 shrink-0 cursor-grab touch-none rounded p-0.5 text-ink-muted hover:bg-ink/5 hover:text-ink-text active:cursor-grabbing disabled:opacity-40"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" />
                        <circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
                        <circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" />
                      </svg>
                    </button>
                  </ToolTip>

                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div
                        role="group"
                        aria-label="Beat status"
                        className="inline-flex rounded-lg border border-paper-line p-0.5"
                      >
                        {(["planned", "landed"] as const).map((status) => (
                          <ToolTip key={status} id="chapter.beatStatusToggle">
                            <button
                              type="button"
                              disabled={disabled}
                              aria-pressed={beat.status === status}
                              onClick={() => void toggleStatus(beat.id, status)}
                              className={`rounded-md px-2 py-0.5 text-[11px] font-semibold capitalize transition-colors disabled:opacity-40 ${
                                beat.status === status
                                  ? status === "landed"
                                    ? "bg-st-approved/15 text-st-approved"
                                    : "bg-ink/10 text-ink-text"
                                  : "text-ink-muted hover:bg-ink/5"
                              }`}
                            >
                              {status}
                            </button>
                          </ToolTip>
                        ))}
                      </div>
                      <span className="truncate text-[11px] text-ink-muted" title={beatDisplayText(beat)}>
                        {beatDisplayText(beat)}
                      </span>
                    </div>

                    <input
                      className={`${fieldClass} text-[13px]`}
                      value={d.title}
                      disabled={disabled}
                      onChange={(e) => patchDraft(beat.id, { title: e.target.value })}
                      placeholder="Beat name"
                      aria-label="Beat title"
                    />
                    <textarea
                      className={`${fieldClass} min-h-[40px] py-1.5 text-[12px] leading-snug`}
                      value={d.summary}
                      disabled={disabled}
                      onChange={(e) => patchDraft(beat.id, { summary: e.target.value })}
                      placeholder="Optional summary for prompts"
                      rows={2}
                      aria-label="Beat summary"
                    />
                  </div>

                  <ToolTip id="chapter.beatDelete">
                    <DeleteButton
                      label={`Delete beat ${beatDisplayText(beat)}`}
                      title="Delete"
                      message={`Remove "${beatDisplayText(beat)}"?`}
                      onConfirm={() => void deleteBeat(beat)}
                      className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                    />
                  </ToolTip>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
