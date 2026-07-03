import ManuscriptEditor from "./ManuscriptEditor";
import ToolTip from "./ToolTip";
import type { AddCommentPayload, CommentItem } from "../api/client";
import type { MentionTarget } from "../lib/mentions";

export default function FinalEditor(props: {
  hasFinal: boolean;
  canPromote: boolean;
  promoteFrom: string;
  text: string;
  onChange: (v: string) => void;
  onPromote: () => void;
  onReopen?: () => void;
  canReopen?: boolean;
  dirty: boolean;
  busy: null | "saving" | "promoting" | "reopening";
  lastSaved: string | null;
  focus: boolean;
  onToggleFocus: () => void;
  mentionTargets?: MentionTarget[];
  projectId?: string;
  onCharacterMentionAction?: (
    parsed: Pick<import("../lib/mentions").ParsedMention, "kind" | "label" | "section">,
    resolved: MentionTarget,
  ) => void;
  annotations?: CommentItem[];
  onCreateAnnotation?: (payload: AddCommentPayload) => Promise<void>;
  focusAnnotationId?: string | null;
  fluidLayout?: { columnMaxPx: number; fontRem: number };
  showSaveStatus?: boolean;
  paragraphFormat?: string;
}) {
  const {
    hasFinal, canPromote, promoteFrom, text, onChange, onPromote,
    onReopen, canReopen, dirty, busy, lastSaved, focus, onToggleFocus,
    mentionTargets, projectId, onCharacterMentionAction,
    annotations, onCreateAnnotation, focusAnnotationId, fluidLayout,
    showSaveStatus, paragraphFormat,
  } = props;

  if (!hasFinal) {
    return (
      <div
        className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line"
        style={fluidLayout ? { maxWidth: fluidLayout.columnMaxPx, width: fluidLayout.columnMaxPx, minWidth: fluidLayout.columnMaxPx, marginInline: "auto" } : { maxWidth: "42rem", marginInline: "auto" }}
      >
        <p className="font-display text-[20px] text-ink-text">No Final yet</p>
        <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-ink-muted">
          The Final is the human-reviewed, canonical chapter. Promote the latest AI stage to
          start reviewing — your drafts stay untouched as provenance.
        </p>
        <ToolTip id="chapter.promoteToFinal">
          <button
            type="button"
            onClick={onPromote}
            disabled={!canPromote || busy != null}
            className="mt-6 inline-flex items-center rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          >
            {busy === "promoting" ? "Promoting…" : canPromote ? `Promote ${promoteFrom} → Final` : "Nothing to Promote Yet"}
          </button>
        </ToolTip>
      </div>
    );
  }

  return (
    <ManuscriptEditor
      stage="final"
      text={text}
      onChange={onChange}
      placeholder="Write the chapter…"
      dirty={dirty}
      saving={busy === "saving"}
      lastSaved={lastSaved}
      focus={focus}
      onToggleFocus={onToggleFocus}
      mentionTargets={mentionTargets}
      projectId={projectId}
      onCharacterMentionAction={onCharacterMentionAction}
      annotations={annotations}
      onCreateAnnotation={onCreateAnnotation}
      focusAnnotationId={focusAnnotationId}
      fluidLayout={fluidLayout}
      showSaveStatus={showSaveStatus}
      paragraphFormat={paragraphFormat}
      articleClassName="rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line"
      trailing={
        canReopen && onReopen ? (
          <ToolTip id="chapter.reopen">
            <button
              type="button"
              onClick={onReopen}
              disabled={busy != null}
              className="rounded-lg border border-paper-line px-4 py-1.5 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
            >
              {busy === "reopening" ? "Reopening…" : "Reopen for revision"}
            </button>
          </ToolTip>
        ) : undefined
      }
    />
  );
}
