import { useRef, useState, type ReactNode } from "react";
import { type EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { openSearchPanel } from "@codemirror/search";
import MarkdownEditor, { type EditorSelectionInfo } from "./MarkdownEditor";
import AnnotatedPreview from "./AnnotatedPreview";
import type { AddCommentPayload, CommentItem } from "../api/client";
import type { MentionTarget } from "../lib/mentions";
import ManuscriptControls, {
  EditorToggleChip,
  FormatToolbar,
  MEASURES,
  ToolbarBtn,
  useManuscriptPrefs,
  type ManuscriptStage,
} from "./ManuscriptControls";
import { surround, prefixLine, insertBlock } from "./editorCommands";
import ToolTip from "./ToolTip";

function MentionTips() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <ToolTip id="chapter.mentionTips">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex h-8 items-center rounded-md border border-paper-line bg-paper-card px-2.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-ink/5 hover:text-ink-text"
        >
          Mention tips
        </button>
      </ToolTip>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-80 rounded-lg border border-paper-line bg-paper-card p-3 text-[12px] leading-relaxed text-ink-text shadow-[var(--shadow-lift)]">
          <div className="mb-2 flex items-start justify-between gap-3">
            <p className="font-semibold text-ink-text">Inline mentions</p>
            <ToolTip id="chapter.contextPreviewClose">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded px-1 text-ink-muted hover:bg-ink/5 hover:text-ink-text"
                aria-label="Close mention tips"
              >
                x
              </button>
            </ToolTip>
          </div>
          <ul className="space-y-1.5 text-ink-muted">
            <li>
              Character: <code className="rounded bg-ink/5 px-1">[[char:Full Name]]</code>
            </li>
            <li>
              Location or lore: <code className="rounded bg-ink/5 px-1">[[lore:Label]]</code>
            </li>
            <li>
              Specific bible section:{" "}
              <code className="rounded bg-ink/5 px-1">[[lore:world_rules:Label]]</code>
            </li>
            <li>Type <code className="rounded bg-ink/5 px-1">[[</code> or <code className="rounded bg-ink/5 px-1">@</code> for autocomplete.</li>
            <li>Mentions add prompt context and warnings, but memory changes still require Review mentions approval.</li>
          </ul>
        </div>
      )}
    </div>
  );
}

function EditorToolbarTrailing({
  focus,
  onToggleFocus,
  typewriter,
  onTypewriterChange,
  vanishing,
  onVanishingChange,
  showWritingModes,
}: {
  focus: boolean;
  onToggleFocus: () => void;
  typewriter: boolean;
  onTypewriterChange: (v: boolean) => void;
  vanishing: boolean;
  onVanishingChange: (v: boolean) => void;
  showWritingModes: boolean;
}) {
  return (
    <>
      {showWritingModes && (
        <>
          <EditorToggleChip
            active={typewriter}
            onClick={() => onTypewriterChange(!typewriter)}
            label="Typewriter"
            tipId="chapter.typewriter"
          />
          <EditorToggleChip
            active={vanishing}
            onClick={() => onVanishingChange(!vanishing)}
            label="Vanishing"
            tipId="chapter.vanishing"
          />
        </>
      )}
      <ToolTip id="chapter.focusMode">
        <button
          type="button"
          onClick={onToggleFocus}
          className={`flex h-8 items-center rounded-md px-2.5 text-[12px] font-medium transition-colors ${
            focus
              ? "bg-ink text-on-ink hover:bg-ink-800"
              : "border border-paper-line bg-paper-card text-ink-text hover:bg-ink/5"
          }`}
        >
          {focus ? "Exit focus" : "Focus"}
        </button>
      </ToolTip>
      {showWritingModes && <MentionTips />}
    </>
  );
}

export default function ManuscriptEditor({
  stage,
  text,
  onChange,
  placeholder,
  dirty,
  saving,
  lastSaved,
  focus,
  onToggleFocus,
  headerExtra,
  trailing,
  articleClassName = "rounded-md bg-paper-card px-8 py-10 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[50vh]",
  mentionTargets,
  projectId,
  onCharacterMentionAction,
  annotations = [],
  onCreateAnnotation,
  focusAnnotationId,
  fluidLayout,
  showSaveStatus,
}: {
  stage: ManuscriptStage;
  text: string;
  onChange: (v: string) => void;
  placeholder?: string;
  dirty: boolean;
  saving: boolean;
  lastSaved: string | null;
  focus: boolean;
  onToggleFocus: () => void;
  /** Shown below controls when not in focus mode (e.g. copy revised hint). */
  headerExtra?: ReactNode;
  /** Extra controls on the right of the control strip (e.g. Reopen). */
  trailing?: ReactNode;
  articleClassName?: string;
  mentionTargets?: MentionTarget[];
  projectId?: string;
  onCharacterMentionAction?: (
    parsed: Pick<import("../lib/mentions").ParsedMention, "kind" | "label" | "section">,
    resolved: MentionTarget,
  ) => void;
  annotations?: CommentItem[];
  onCreateAnnotation?: (payload: AddCommentPayload) => Promise<void>;
  focusAnnotationId?: string | null;
  /** Scales type size and column width with the studio center pane. */
  fluidLayout?: { columnMaxPx: number; fontRem: number };
  showSaveStatus?: boolean;
}) {
  const cm = useRef<ReactCodeMirrorRef>(null);
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [selection, setSelection] = useState<EditorSelectionInfo | null>(null);
  const [annotateOpen, setAnnotateOpen] = useState(false);
  const [annotateBody, setAnnotateBody] = useState("");
  const [annotateBusy, setAnnotateBusy] = useState(false);
  const prefs = useManuscriptPrefs();

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const editorFontRem = fluidLayout
    ? fluidLayout.fontRem * (prefs.size / 1.075)
    : prefs.size;
  const columnMaxWidth = fluidLayout
    ? `${fluidLayout.columnMaxPx}px`
    : MEASURES[prefs.measure];

  function cmd(fn: (v: EditorView) => void) {
    const view = cm.current?.view;
    if (view) fn(view);
  }

  async function submitAnnotation() {
    if (!selection?.text.trim() || !annotateBody.trim() || !onCreateAnnotation) return;
    setAnnotateBusy(true);
    try {
      await onCreateAnnotation({
        body: annotateBody.trim(),
        quote: selection.text,
        stage,
        start_offset: selection.from,
        end_offset: selection.to,
      });
      setAnnotateBody("");
      setAnnotateOpen(false);
      setSelection(null);
    } finally {
      setAnnotateBusy(false);
    }
  }

  const selectionSnippet = selection?.text
    ? selection.text.length > 72
      ? `${selection.text.slice(0, 72)}…`
      : selection.text
    : "";

  const toolbarTrailing = (
    <EditorToolbarTrailing
      focus={focus}
      onToggleFocus={onToggleFocus}
      typewriter={prefs.typewriter}
      onTypewriterChange={prefs.setTypewriter}
      vanishing={prefs.vanishing}
      onVanishingChange={prefs.setVanishing}
      showWritingModes={mode === "write"}
    />
  );

  return (
    <div
      className={focus ? "flex min-h-0 flex-1 flex-col" : undefined}
      style={{ ["--editor-size" as string]: `${editorFontRem}rem` }}
    >
      <ManuscriptControls
        stage={stage}
        mode={mode}
        onModeChange={setMode}
        words={words}
        dirty={dirty}
        saving={saving}
        lastSaved={lastSaved}
        focus={focus}
        measure={prefs.measure}
        onMeasureChange={prefs.setMeasure}
        bionicPreview={prefs.bionicPreview}
        onBionicPreviewChange={prefs.setBionicPreview}
        trailing={trailing}
        showSaveStatus={showSaveStatus}
      />

      {!focus && headerExtra ? <div className="mb-3">{headerExtra}</div> : null}

      <FormatToolbar measure={prefs.measure} trailing={toolbarTrailing}>
        {mode === "write" && (
          <>
            <ToolbarBtn onClick={() => cmd((v) => surround(v, "**"))} label="Bold" tipId="chapter.formatBold">
              <b>B</b>
            </ToolbarBtn>
            <ToolbarBtn onClick={() => cmd((v) => surround(v, "*"))} label="Italic" tipId="chapter.formatItalic">
              <i>I</i>
            </ToolbarBtn>
            <ToolbarBtn onClick={() => cmd((v) => prefixLine(v, "## "))} label="Heading" tipId="chapter.formatHeading">
              H
            </ToolbarBtn>
            <ToolbarBtn onClick={() => cmd((v) => prefixLine(v, "> "))} label="Quote" tipId="chapter.formatQuote">
              ”
            </ToolbarBtn>
            <ToolbarBtn onClick={() => cmd((v) => insertBlock(v, "\n\n---\n\n"))} label="Scene break" tipId="chapter.formatSceneBreak">
              ✦
            </ToolbarBtn>
            <div className="mx-1 h-5 w-px bg-paper-line" />
            <ToolbarBtn onClick={() => cmd((v) => surround(v, "[[char:", "]]"))} label="Insert character mention: [[char:Full Name]]" tipId="chapter.formatCharMention">
              Char
            </ToolbarBtn>
            <ToolbarBtn onClick={() => cmd((v) => surround(v, "[[lore:", "]]"))} label="Insert location/lore mention: [[lore:Label]]" tipId="chapter.formatLoreMention">
              Lore
            </ToolbarBtn>
            <div className="mx-1 h-5 w-px bg-paper-line" />
            <ToolbarBtn onClick={() => cmd((v) => openSearchPanel(v))} label="Find & replace" tipId="chapter.formatFindReplace">
              ⌕
            </ToolbarBtn>
            {onCreateAnnotation && selection?.text.trim() ? (
              <ToolbarBtn
                onClick={() => setAnnotateOpen((v) => !v)}
                label="Annotate selected text"
                tipId="chapter.formatAnnotate"
              >
                ✎
              </ToolbarBtn>
            ) : null}
          </>
        )}
      </FormatToolbar>

      {annotateOpen && selection?.text.trim() && onCreateAnnotation ? (
        <div className="mb-3 rounded-lg border border-amber/35 bg-amber/5 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-deep">
            Annotate · {stage}
          </p>
          <blockquote className="mt-1.5 border-l-2 border-amber/50 pl-2 text-[12px] italic text-ink-muted">
            “{selectionSnippet}”
          </blockquote>
          <textarea
            value={annotateBody}
            onChange={(e) => setAnnotateBody(e.target.value)}
            placeholder="Your note about this passage…"
            rows={2}
            className="mt-2 w-full resize-y rounded-md border border-paper-line bg-paper px-2.5 py-1.5 text-[13px] text-ink-text placeholder:text-paper-muted"
          />
          <div className="mt-2 flex justify-end gap-2">
            <ToolTip id="modal.cancel">
              <button
                type="button"
                onClick={() => {
                  setAnnotateOpen(false);
                  setAnnotateBody("");
                }}
                className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-medium text-ink-muted hover:bg-ink/5"
              >
                Cancel
              </button>
            </ToolTip>
            <ToolTip id="chapter.commentAdd">
              <button
                type="button"
                onClick={() => void submitAnnotation()}
                disabled={!annotateBody.trim() || annotateBusy}
                className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
              >
                {annotateBusy ? "Saving…" : "Add annotation"}
              </button>
            </ToolTip>
          </div>
        </div>
      ) : null}

      <article
        className={
          focus
            ? "flex min-h-0 flex-1 flex-col rounded-md bg-paper-card px-8 py-8 shadow-[var(--shadow-paper)] ring-1 ring-paper-line"
            : articleClassName
        }
        style={{
          width: columnMaxWidth,
          maxWidth: columnMaxWidth,
          minWidth: columnMaxWidth,
          marginInline: "auto",
        }}
      >
        {mode === "write" ? (
          <div className={`prose-manuscript ${focus ? "min-h-0 flex-1" : ""}`}>
            <MarkdownEditor
              ref={cm}
              value={text}
              onChange={onChange}
              placeholder={placeholder}
              typewriter={prefs.typewriter}
              vanishing={prefs.vanishing}
              className={prefs.typewriter ? "cm-typewriter" : undefined}
              mentionTargets={mentionTargets}
              onSelectionChange={setSelection}
              annotations={annotations}
              annotationStage={stage}
              focusAnnotationId={focusAnnotationId}
            />
          </div>
        ) : (
          <AnnotatedPreview
            source={text}
            annotations={annotations}
            stage={stage}
            style={{ fontSize: `${prefs.size}rem` }}
            bionic={prefs.bionicPreview}
            mentionTargets={mentionTargets}
            projectId={projectId}
            onCharacterMentionAction={onCharacterMentionAction}
            focusAnnotationId={focusAnnotationId}
          />
        )}
      </article>
    </div>
  );
}
