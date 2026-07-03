import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api, type SnapshotMeta, type SnapshotText, type CommentItem,
  type AddCommentPayload, type AnnotationStage,
} from "../api/client";
import {
  ANNOTATION_STAGES, STAGE_LABELS, commentStage, isManuscriptAnnotation, isManuscriptStage,
} from "../lib/annotations";
import { useToast } from "./Toaster";
import { useConfirm } from "./Confirm";
import DiffView from "./DiffView";
import ToolTip from "./ToolTip";
import InspectorCastPanel from "./InspectorCastPanel";
import type { CharacterSummary } from "../api/client";
import { INSPECTOR_WIDTH_DEFAULT } from "../lib/chapterStudioLayout";
import type { ToolTipId } from "../lib/toolRegistry";

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

type StageFilter = AnnotationStage | "all";

type InspectorTab = "versions" | "cast" | "comments";

const INSPECTOR_TAB_TIPS: Record<InspectorTab, ToolTipId> = {
  versions: "chapter.inspectorSnapshotsTab",
  cast: "chapter.inspectorCastTab",
  comments: "chapter.inspectorNotesTab",
};

const INSPECTOR_TAB_LABELS: Record<InspectorTab, string> = {
  versions: "Snapshots",
  cast: "Cast",
  comments: "Notes",
};

const INSPECTOR_TABS: InspectorTab[] = ["versions", "cast", "comments"];

export default function Inspector({
  id, num, currentText, flush, onRestored,
  selectedStage, comments, onCommentsChange, focusAnnotationId, onFocusAnnotation,
  commentPrefill, onClearCommentPrefill, initialTab, refreshToken,
  characters = [],
  width,
}: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText: string) => void;
  selectedStage?: "outline" | "draft" | "revised" | "final";
  comments?: CommentItem[];
  onCommentsChange?: () => void;
  focusAnnotationId?: string | null;
  onFocusAnnotation?: (id: string | null) => void;
  commentPrefill?: AddCommentPayload | null;
  onClearCommentPrefill?: () => void;
  initialTab?: InspectorTab;
  refreshToken?: number;
  characters?: CharacterSummary[];
  width?: number;
}) {
  const [tab, setTab] = useState<InspectorTab>(initialTab ?? "versions");

  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (commentPrefill) setTab("comments");
  }, [commentPrefill]);

  return (
    <aside
      className="flex min-h-0 shrink-0 flex-col overflow-y-auto border-l border-paper-line bg-paper-card/40"
      style={{ width: width ?? INSPECTOR_WIDTH_DEFAULT }}
    >
      <div className="flex gap-0 border-b border-paper-line px-2">
        {INSPECTOR_TABS.map((t) => (
          <ToolTip key={t} id={INSPECTOR_TAB_TIPS[t]} className="flex shrink-0">
            <button
              type="button"
              onClick={() => setTab(t)}
              className={`px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.06em] transition-colors ${
                tab === t ? "text-ink-text" : "text-paper-muted hover:text-ink-muted"
              }`}
            >
              {INSPECTOR_TAB_LABELS[t]}
              {tab === t && <span className="mt-1 block h-0.5 rounded-full bg-amber-deep" />}
            </button>
          </ToolTip>
        ))}
      </div>
      {tab === "versions" ? (
        <Snapshots id={id} num={num} currentText={currentText} flush={flush} onRestored={onRestored} refreshToken={refreshToken} />
      ) : tab === "cast" ? (
        <InspectorCastPanel
          projectId={id}
          chapterNumber={num}
          characters={characters}
          refreshToken={refreshToken}
        />
      ) : (
          <Comments
            id={id}
            num={num}
            selectedStage={selectedStage}
            comments={comments}
            onCommentsChange={onCommentsChange}
            focusAnnotationId={focusAnnotationId}
            onFocusAnnotation={onFocusAnnotation}
            commentPrefill={commentPrefill}
            onClearCommentPrefill={onClearCommentPrefill}
          />
        )}
    </aside>
  );
}

function Snapshots({ id, num, currentText, flush, onRestored, refreshToken }: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText: string) => void;
  refreshToken?: number;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [list, setList] = useState<SnapshotMeta[]>([]);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState<SnapshotText | null>(null);

  const reload = useCallback(() => {
    api.snapshots(id, num).then(setList).catch(() => setList([]));
  }, [id, num]);
  useEffect(() => {
    reload();
    setViewing(null);
  }, [reload, refreshToken]);

  async function saveVersion() {
    setBusy(true);
    try {
      await flush();
      await api.createSnapshot(id, num, label.trim() || "Version");
      setLabel("");
      toast("Version saved", "success");
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function view(sid: string) {
    if (viewing?.id === sid) { setViewing(null); return; }
    try { setViewing(await api.getSnapshot(id, num, sid)); }
    catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  async function restore(sid: string) {
    try {
      const r = await api.restoreSnapshot(id, num, sid);
      toast("Restored — previous Final saved as a snapshot", "success");
      setViewing(null);
      onRestored(r.final);
      reload();
    } catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  async function remove(sid: string) {
    const ok = await confirm({
      title: "Delete version",
      message: "This permanently deletes this snapshot. It can't be undone.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    try { await api.deleteSnapshot(id, num, sid); reload(); if (viewing?.id === sid) setViewing(null); }
    catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="flex gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (optional)…"
          className="min-w-0 flex-1 rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-[13px] text-ink-text placeholder:text-paper-muted"
        />
        <ToolTip id="chapter.snapshotSave">
          <button onClick={saveVersion} disabled={busy}
                  className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
            {busy ? "Saving…" : "Save version"}
          </button>
        </ToolTip>
      </div>

      {list.length === 0 && <p className="py-6 text-center text-[13px] text-ink-muted">No versions yet.</p>}

      {list.map((s) => (
        <div key={s.id} className="rounded-lg border border-paper-line bg-paper-card p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-[13.5px] font-semibold text-ink-text">{s.label}</p>
              <p className="nums text-[11.5px] text-ink-muted">{when(s.created_at)} · {s.word_count.toLocaleString()} words</p>
            </div>
          </div>
          <div className="mt-2 flex gap-3 text-[12px] font-medium">
            <ToolTip id="chapter.snapshotDiff">
              <button onClick={() => view(s.id)} className="text-st-drafted hover:underline">
                {viewing?.id === s.id ? "Hide diff" : "Diff"}
              </button>
            </ToolTip>
            <ToolTip id="chapter.snapshotRestore">
              <button onClick={() => restore(s.id)} className="text-amber-deep hover:underline">Restore</button>
            </ToolTip>
            <ToolTip id="chapter.snapshotDelete">
              <button onClick={() => remove(s.id)} className="text-ink-muted hover:text-red-600">Delete</button>
            </ToolTip>
          </div>
          {viewing?.id === s.id && (
            <div className="mt-3 max-h-72 overflow-y-auto rounded-md border border-paper-line bg-paper p-3">
              <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wider text-paper-muted">
                Snapshot → current
              </p>
              <DiffView oldText={viewing.text} newText={currentText} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function StageBadge({ stage }: { stage: AnnotationStage }) {
  const manuscript = isManuscriptStage(stage);
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        manuscript
          ? "bg-amber/15 text-amber-deep"
          : "bg-ink/5 text-ink-muted"
      }`}
    >
      {STAGE_LABELS[stage]}
    </span>
  );
}

function Comments({
  id, num, selectedStage, comments: externalComments, onCommentsChange,
  focusAnnotationId, onFocusAnnotation, commentPrefill, onClearCommentPrefill,
}: {
  id: string; num: number;
  selectedStage?: "outline" | "draft" | "revised" | "final";
  comments?: CommentItem[];
  onCommentsChange?: () => void;
  focusAnnotationId?: string | null;
  onFocusAnnotation?: (id: string | null) => void;
  commentPrefill?: AddCommentPayload | null;
  onClearCommentPrefill?: () => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [list, setList] = useState<CommentItem[]>([]);
  const [body, setBody] = useState("");
  const [quote, setQuote] = useState("");
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");

  const reload = useCallback(() => {
    if (externalComments) {
      setList(externalComments);
      return;
    }
    api.comments(id, num).then(setList).catch(() => setList([]));
  }, [id, num, externalComments]);

  useEffect(reload, [reload]);

  useEffect(() => {
    if (selectedStage && selectedStage !== "outline") {
      setStageFilter(selectedStage);
    }
  }, [selectedStage]);

  useEffect(() => {
    if (!commentPrefill) return;
    setBody(commentPrefill.body ?? "");
    setQuote(commentPrefill.quote ?? "");
    if (commentPrefill.stage && commentPrefill.stage !== "comment") {
      setStageFilter(commentPrefill.stage);
    }
  }, [commentPrefill]);

  const filtered = useMemo(() => {
    if (stageFilter === "all") return list;
    return list.filter((c) => commentStage(c) === stageFilter);
  }, [list, stageFilter]);

  async function removeComment(cid: string) {
    const ok = await confirm({
      title: "Delete note", message: "Delete this note?", confirmLabel: "Delete", danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteComment(id, num, cid);
      reload();
      onCommentsChange?.();
      if (focusAnnotationId === cid) onFocusAnnotation?.(null);
    } catch { /* ignore */ }
  }

  async function add() {
    if (!body.trim()) return;
    try {
      const payload: AddCommentPayload = {
        body: body.trim(),
        quote: quote.trim(),
        stage: commentPrefill?.stage ?? (selectedStage && selectedStage !== "outline" ? selectedStage : "comment"),
        start_offset: commentPrefill?.start_offset,
        end_offset: commentPrefill?.end_offset,
        paragraph_hash: commentPrefill?.paragraph_hash,
      };
      await api.addComment(id, num, payload);
      setBody("");
      setQuote("");
      onClearCommentPrefill?.();
      reload();
      onCommentsChange?.();
      toast(isManuscriptStage(payload.stage ?? "comment") ? "Annotation added" : "Note added", "success");
    } catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  const filterOptions: StageFilter[] = ["all", ...ANNOTATION_STAGES];

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="flex flex-wrap gap-1.5">
        {filterOptions.map((f) => (
          <ToolTip key={f} id="chapter.commentStageFilter">
            <button
              type="button"
              onClick={() => setStageFilter(f)}
              className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
                stageFilter === f
                  ? "bg-amber/20 text-amber-deep"
                  : "bg-ink/5 text-ink-muted hover:bg-ink/10 hover:text-ink-text"
              }`}
            >
              {f === "all" ? "All" : STAGE_LABELS[f]}
            </button>
          </ToolTip>
        ))}
      </div>

      <div className="rounded-lg border border-paper-line bg-paper-card p-3">
        <input value={quote} onChange={(e) => setQuote(e.target.value)}
               placeholder="Quote (optional)…"
               className="mb-2 w-full rounded-md border border-paper-line bg-paper px-2.5 py-1.5 text-[12.5px] text-ink-text placeholder:text-paper-muted" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)}
                  placeholder="Add a note or annotation…" rows={2}
                  className="w-full resize-y rounded-md border border-paper-line bg-paper px-2.5 py-1.5 text-[13px] text-ink-text placeholder:text-paper-muted" />
        <div className="mt-2 flex justify-end">
          <ToolTip id="chapter.commentAdd">
            <button onClick={add} disabled={!body.trim()}
                    className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
              Add note
            </button>
          </ToolTip>
        </div>
      </div>

      {filtered.length === 0 && (
        <p className="py-6 text-center text-[13px] text-ink-muted">
          {list.length === 0 ? "No notes yet." : "No notes for this stage."}
        </p>
      )}

      {filtered.map((c) => {
        const stage = commentStage(c);
        const focused = focusAnnotationId === c.id;
        return (
          <div
            key={c.id}
            className={`rounded-lg border p-3 transition-colors ${
              focused
                ? "border-amber-deep bg-amber/10"
                : c.resolved
                  ? "border-paper-line bg-paper-card/50 opacity-70"
                  : "border-paper-line bg-paper-card"
            }`}
          >
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <StageBadge stage={stage} />
              {isManuscriptAnnotation(c) && c.start_offset != null && c.end_offset != null ? (
                <span className="nums text-[10.5px] text-paper-muted">
                  {c.start_offset}–{c.end_offset}
                </span>
              ) : null}
            </div>
            {c.quote && (
              <ToolTip id="chapter.commentFocusQuote">
                <button
                  type="button"
                  onClick={() => onFocusAnnotation?.(focused ? null : c.id)}
                  className="mb-1.5 w-full text-left"
                >
                  <blockquote className="border-l-2 border-amber pl-2 text-[12px] italic text-ink-muted hover:text-ink-text">
                    “{c.quote.length > 120 ? `${c.quote.slice(0, 120)}…` : c.quote}”
                  </blockquote>
                </button>
              </ToolTip>
            )}
            <p className={`text-[13.5px] text-ink-text ${c.resolved ? "line-through" : ""}`}>{c.body}</p>
            <div className="mt-2 flex items-center gap-3 text-[11.5px]">
              <span className="nums text-paper-muted">{when(c.created_at)}</span>
              <ToolTip id="chapter.commentResolve">
                <button onClick={() => api.updateComment(id, num, c.id, !c.resolved).then(() => { reload(); onCommentsChange?.(); })}
                        className="font-medium text-st-approved hover:underline">
                  {c.resolved ? "Reopen" : "Resolve"}
                </button>
              </ToolTip>
              <ToolTip id="chapter.commentDelete">
                <button onClick={() => removeComment(c.id)}
                        className="font-medium text-ink-muted hover:text-red-600">Delete</button>
              </ToolTip>
            </div>
          </div>
        );
      })}
    </div>
  );
}
