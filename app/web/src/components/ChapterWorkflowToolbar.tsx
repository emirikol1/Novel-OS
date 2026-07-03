import type { ChapterStages } from "../api/client";
import type { StageKey } from "./PipelineFlow";
import { useState } from "react";
import ResumeWorkflowDot from "./ResumeWorkflowDot";
import ToolTip from "./ToolTip";
import { CHAPTER_FUNCTION_LABELS, type ChapterFunction } from "../lib/chapterWorkflow";
import type { ToolTipId } from "../lib/toolRegistry";

export type MineKind = "plots" | "characters" | "bible";

export type ChapterWorkflowToolbarProps = {
  num: number;
  stages: ChapterStages;
  selected: StageKey;
  canReopen: boolean;
  reviseUses: string | null;
  hasRegenerateSource: boolean;
  mineSourceStage: string;
  expandMarkerCount: number;
  longChapterText: boolean;
  hasSavedBrief: boolean;
  hasOutlineNotes: boolean;
  isRunning: boolean;
  runningStage: string | null;
  lastFn: ChapterFunction | null;
  regenerating: boolean;
  expanding: boolean;
  formattingParagraphs: boolean;
  redrafting: boolean;
  outlineGenerating: boolean;
  splittingChapter: boolean;
  aligningBoundary: boolean;
  hasNextChapter: boolean;
  busy: string | null;
  hasActivePreview: boolean;
  regenInstructions: string;
  setRegenInstructions: (value: string) => void;
  applyNotesToOutline: boolean;
  setApplyNotesToOutline: (value: boolean) => void;
  outlineInstructions: string;
  setOutlineInstructions: (value: string) => void;
  redraftMode: "align" | "preserve";
  setRedraftMode: (value: "align" | "preserve") => void;
  isMining: (kind: MineKind) => boolean;
  onGenerateDraft: () => void;
  onRevise: () => void;
  onValidate: () => void;
  onApprove: () => void;
  onReviewMentions: () => void;
  onReopen: () => void;
  onRegenerate: () => void;
  onRedraftFromBrief: () => void;
  onExpandPlaceholders: () => void;
  onFormatParagraphs: () => void;
  onAlignBoundary: () => void;
  onRegenerateOutline: (mode: "notes" | "text") => void;
  onSplitChapter: () => void;
  onMine: (kind: MineKind) => void;
  /** Tighter spacing when rendered in sticky chapter chrome. */
  embedded?: boolean;
};

function WorkflowSection({
  hint,
  children,
}: {
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      {hint && (
        <p className="mb-1 text-[11px] leading-snug text-ink-muted">{hint}</p>
      )}
      <div className="rounded-md border border-paper-line/60 bg-paper/40 px-3 py-2">
        {children}
      </div>
    </div>
  );
}

function RunButton({
  label, onClick, running, disabled, resume, resumeLabel, tipId,
}: {
  label: string; onClick: () => void; running: boolean; disabled?: boolean;
  resume?: boolean; resumeLabel?: string; tipId?: ToolTipId;
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 rounded-md border border-paper-line bg-paper-card px-3 py-1 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
    >
      {resume && (
        <ResumeWorkflowDot title={resumeLabel ?? "Last function used on this chapter"} />
      )}
      {running ? "Running…" : label}
    </button>
  );
  return tipId ? <ToolTip id={tipId}>{button}</ToolTip> : button;
}

function MineButton({
  label, running, onClick, disabled, resume, resumeLabel, tipId,
}: {
  label: string;
  running: boolean;
  onClick: () => void;
  disabled?: boolean;
  resume?: boolean;
  resumeLabel?: string;
  tipId?: ToolTipId;
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 rounded-md border border-amber/30 bg-amber/5 px-3 py-1 text-[12px] font-semibold text-ink-text transition-colors hover:bg-amber/10 disabled:opacity-40"
    >
      {resume && (
        <ResumeWorkflowDot title={resumeLabel ?? "Last function used on this chapter"} />
      )}
      {running ? "Mining…" : label}
    </button>
  );
  return tipId ? <ToolTip id={tipId}>{button}</ToolTip> : button;
}

export function CodexSyncSection({
  hasRegenerateSource,
  mineSourceStage,
  isRunning,
  isMining,
  lastFn,
  onMine,
}: {
  hasRegenerateSource: boolean;
  mineSourceStage: string;
  isRunning: boolean;
  isMining: (kind: MineKind) => boolean;
  lastFn: ChapterFunction | null;
  onMine: (kind: MineKind) => void;
}) {
  if (!hasRegenerateSource) return null;

  return (
    <div className="border-t border-paper-line/70 pt-2.5">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
        Codex sync
      </p>
      <div className="rounded-md border border-paper-line/60 bg-paper/40 px-3 py-2">
        <div className="flex flex-wrap items-center gap-1.5">
        <MineButton
          label="Plots & subplots"
          running={isMining("plots")}
          disabled={isRunning || isMining("plots")}
          resume={lastFn === "mine-plots"}
          resumeLabel={CHAPTER_FUNCTION_LABELS["mine-plots"]}
          tipId="chapter.minePlots"
          onClick={() => onMine("plots")}
        />
        <MineButton
          label="Characters"
          running={isMining("characters")}
          disabled={isRunning || isMining("characters")}
          resume={lastFn === "mine-characters"}
          resumeLabel={CHAPTER_FUNCTION_LABELS["mine-characters"]}
          tipId="chapter.mineCharacters"
          onClick={() => onMine("characters")}
        />
        <MineButton
          label="Story bible"
          running={isMining("bible")}
          disabled={isRunning || isMining("bible")}
          resume={lastFn === "mine-bible"}
          resumeLabel={CHAPTER_FUNCTION_LABELS["mine-bible"]}
          tipId="chapter.mineBible"
          onClick={() => onMine("bible")}
        />
        <span className="text-[11px] text-ink-muted">
          Uses {mineSourceStage} stage · LM Studio · preview before apply · run any or all in parallel
        </span>
      </div>
      </div>
    </div>
  );
}

export default function ChapterWorkflowToolbar(props: ChapterWorkflowToolbarProps) {
  const {
    stages,
    selected,
    canReopen,
    reviseUses,
    hasRegenerateSource,
    expandMarkerCount,
    longChapterText,
    hasSavedBrief,
    hasOutlineNotes,
    isRunning,
    runningStage,
    lastFn,
    regenerating,
    expanding,
    formattingParagraphs,
    redrafting,
    outlineGenerating,
    splittingChapter,
    aligningBoundary,
    hasNextChapter,
    busy,
    hasActivePreview,
    regenInstructions,
    setRegenInstructions,
    applyNotesToOutline,
    setApplyNotesToOutline,
    outlineInstructions,
    setOutlineInstructions,
    redraftMode,
    setRedraftMode,
    onGenerateDraft,
    onRevise,
    onValidate,
    onApprove,
    onReviewMentions,
    onReopen,
    onRegenerate,
    onRedraftFromBrief,
    onExpandPlaceholders,
    onFormatParagraphs,
    onAlignBoundary,
    onRegenerateOutline,
    onSplitChapter,
    embedded = false,
  } = props;

  const [outlineSource, setOutlineSource] = useState<"notes" | "text">("notes");

  const showPlan = selected === "outline";
  const showDraft = selected === "draft";
  const showRevise = selected === "revised";
  const showFinalize = selected === "final";
  const showNotesInputs = !hasActivePreview;

  return (
    <div className={`flex flex-col gap-2 ${embedded ? "mt-1" : "mt-2.5"}`}>
      {showPlan && (
        <WorkflowSection hint="Optional — beats and direction before drafting.">
          <div className="flex flex-col gap-1.5">
            {showNotesInputs && (
              <>
                <ToolTip id="chapter.outlineNotes" className="block max-w-xl">
                  <textarea
                    className="w-full rounded-md border border-paper-line bg-paper-card px-2.5 py-1.5 text-[12.5px] leading-relaxed text-ink-text placeholder:text-ink-muted"
                    rows={3}
                    value={outlineInstructions}
                    onChange={(e) => setOutlineInstructions(e.target.value)}
                    placeholder="Outline notes & direction — beats, what must happen, pacing, ending hook. POV and style live on the chapter brief."
                    disabled={outlineGenerating || isRunning}
                  />
                </ToolTip>
                <ToolTip id="chapter.applyNotesToOutline">
                  <label className="flex max-w-xl cursor-pointer items-center gap-2 text-[11px] text-ink-muted">
                    <input
                      type="checkbox"
                      checked={applyNotesToOutline}
                      onChange={(e) => setApplyNotesToOutline(e.target.checked)}
                      disabled={regenerating || isRunning || outlineGenerating}
                      className="rounded border-paper-line"
                    />
                    Also apply revision notes to outline (Revise, Outline from notes/text)
                  </label>
                </ToolTip>
              </>
            )}
            <div className="rounded-md border border-paper-line/80 bg-paper-card/80 px-3 py-2">
              <div className="flex flex-wrap items-center gap-3">
                <RunButton
                  label={outlineGenerating ? "Outlining…" : "Regenerate outline"}
                  running={outlineGenerating}
                  disabled={
                    isRunning
                    || outlineGenerating
                    || (outlineSource === "notes" ? !hasOutlineNotes : !hasRegenerateSource)
                  }
                  resume={lastFn === (outlineSource === "notes" ? "outline-notes" : "outline-text")}
                  resumeLabel={CHAPTER_FUNCTION_LABELS[outlineSource === "notes" ? "outline-notes" : "outline-text"]}
                  tipId={outlineSource === "notes" ? "chapter.outlineFromNotes" : "chapter.outlineFromText"}
                  onClick={() => onRegenerateOutline(outlineSource)}
                />
                <div className="flex flex-wrap items-center gap-4 text-[12px] text-ink-text">
                  <ToolTip id="chapter.outlineFromNotes">
                    <label className="inline-flex cursor-pointer items-center gap-2">
                      <input
                        type="radio"
                        name="outline-regenerate-source"
                        checked={outlineSource === "notes"}
                        onChange={() => setOutlineSource("notes")}
                        disabled={outlineGenerating || isRunning}
                        className="border-paper-line text-amber-deep"
                      />
                      From notes
                    </label>
                  </ToolTip>
                  <ToolTip id="chapter.outlineFromText">
                    <label className="inline-flex cursor-pointer items-center gap-2">
                      <input
                        type="radio"
                        name="outline-regenerate-source"
                        checked={outlineSource === "text"}
                        onChange={() => setOutlineSource("text")}
                        disabled={outlineGenerating || isRunning}
                        className="border-paper-line text-amber-deep"
                      />
                      From text
                    </label>
                  </ToolTip>
                </div>
              </div>
            </div>
          </div>
        </WorkflowSection>
      )}

      {showDraft && (
        <WorkflowSection>
          <div className="flex flex-wrap items-center gap-1.5">
            <RunButton
              label="Generate Draft"
              running={runningStage === "write"}
              disabled={isRunning}
              resume={lastFn === "write"}
              resumeLabel={CHAPTER_FUNCTION_LABELS.write}
              tipId="chapter.generateDraft"
              onClick={onGenerateDraft}
            />
            <RunButton
              label={formattingParagraphs ? "Formatting…" : "AI Paragraphs"}
              running={formattingParagraphs}
              disabled={
                isRunning
                || formattingParagraphs
                || expanding
                || regenerating
                || redrafting
                || !hasRegenerateSource
                || hasActivePreview
              }
              resume={lastFn === "format-paragraphs"}
              resumeLabel={CHAPTER_FUNCTION_LABELS["format-paragraphs"]}
              tipId="chapter.formatParagraphs"
              onClick={onFormatParagraphs}
            />
            {hasNextChapter && (
              <RunButton
                label={aligningBoundary ? "Aligning…" : "Fix chapter alignment"}
                running={aligningBoundary}
                disabled={
                  isRunning
                  || aligningBoundary
                  || formattingParagraphs
                  || expanding
                  || regenerating
                  || redrafting
                  || !hasRegenerateSource
                  || hasActivePreview
                }
                resume={lastFn === "align-boundary"}
                resumeLabel={CHAPTER_FUNCTION_LABELS["align-boundary"]}
                tipId="chapter.alignBoundary"
                onClick={onAlignBoundary}
              />
            )}
          </div>
        </WorkflowSection>
      )}

      {(showRevise || showFinalize) && (
        <WorkflowSection hint="Adds paragraph breaks and scene breaks (... on its own line) only — never changes wording.">
          <div className="flex flex-wrap items-center gap-1.5">
          <RunButton
            label={formattingParagraphs ? "Formatting…" : "AI Paragraphs"}
            running={formattingParagraphs}
            disabled={
              isRunning
              || formattingParagraphs
              || expanding
              || regenerating
              || redrafting
              || !hasRegenerateSource
              || hasActivePreview
            }
            resume={lastFn === "format-paragraphs"}
            resumeLabel={CHAPTER_FUNCTION_LABELS["format-paragraphs"]}
            tipId="chapter.formatParagraphs"
            onClick={onFormatParagraphs}
          />
          {hasNextChapter && (
            <RunButton
              label={aligningBoundary ? "Aligning…" : "Fix chapter alignment"}
              running={aligningBoundary}
              disabled={
                isRunning
                || aligningBoundary
                || formattingParagraphs
                || expanding
                || regenerating
                || redrafting
                || !hasRegenerateSource
                || hasActivePreview
              }
              resume={lastFn === "align-boundary"}
              resumeLabel={CHAPTER_FUNCTION_LABELS["align-boundary"]}
              tipId="chapter.alignBoundary"
              onClick={onAlignBoundary}
            />
          )}
          </div>
        </WorkflowSection>
      )}

      {showRevise && (
        <WorkflowSection
          hint={
            <>
              Edit <strong className="font-medium text-ink-text">Revised</strong> directly; autosaves.
              Use{" "}
              <code className="rounded bg-ink/5 px-1 py-0.5 text-[10px]">[[expand: …]]</code>
              {" "}then Expand placeholders.
            </>
          }
        >
          <div className="flex flex-col gap-1.5">
            {showNotesInputs && (
              <ToolTip id="chapter.revisionNotes" className="block max-w-xl">
                <input
                  className="w-full rounded-md border border-paper-line bg-paper-card px-2.5 py-1.5 text-[12.5px] text-ink-text placeholder:text-ink-muted"
                  value={regenInstructions}
                  onChange={(e) => setRegenInstructions(e.target.value)}
                  placeholder="Revision notes for Revise & Regenerate (e.g. cut exposition, fix the ending…)"
                  disabled={regenerating || redrafting || isRunning}
                />
              </ToolTip>
            )}
            <div className="flex flex-wrap items-center gap-1.5">
              <RunButton
                label="Revise"
                running={runningStage === "edit"}
                disabled={isRunning || (stages.draft == null && stages.revised == null)}
                resume={lastFn === "edit"}
                resumeLabel={CHAPTER_FUNCTION_LABELS.edit}
                tipId="chapter.revise"
                onClick={onRevise}
              />
              <RunButton
                label={regenerating ? "Regenerating…" : "Regenerate"}
                running={regenerating}
                disabled={isRunning || regenerating || expanding || formattingParagraphs || redrafting || !hasRegenerateSource}
                resume={lastFn === "regenerate"}
                resumeLabel={CHAPTER_FUNCTION_LABELS.regenerate}
                tipId="chapter.regenerate"
                onClick={onRegenerate}
              />
              <RunButton
                label={redrafting ? "Redrafting…" : "Redraft from brief"}
                running={redrafting}
                disabled={isRunning || redrafting || regenerating || expanding || !hasRegenerateSource || !hasSavedBrief}
                resume={lastFn === "redraft-from-brief"}
                resumeLabel={CHAPTER_FUNCTION_LABELS["redraft-from-brief"]}
                tipId="chapter.redraftFromBrief"
                onClick={onRedraftFromBrief}
              />
              <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-muted">
                <span className="font-medium text-ink-text">Mode</span>
                <ToolTip id="chapter.redraftModeAlign">
                  <label className="inline-flex cursor-pointer items-center gap-1">
                    <input
                      type="radio"
                      name="redraftMode"
                      checked={redraftMode === "align"}
                      onChange={() => setRedraftMode("align")}
                      disabled={redrafting || isRunning}
                      className="rounded-full border-paper-line"
                    />
                    Align
                  </label>
                </ToolTip>
                <ToolTip id="chapter.redraftModePreserve">
                  <label className="inline-flex cursor-pointer items-center gap-1">
                    <input
                      type="radio"
                      name="redraftMode"
                      checked={redraftMode === "preserve"}
                      onChange={() => setRedraftMode("preserve")}
                      disabled={redrafting || isRunning}
                      className="rounded-full border-paper-line"
                    />
                    Preserve
                  </label>
                </ToolTip>
              </span>
              <RunButton
                label={
                  expanding
                    ? "Expanding…"
                    : expandMarkerCount > 0
                      ? `Expand placeholders (${expandMarkerCount})`
                      : "Expand placeholders"
                }
                running={expanding}
                disabled={isRunning || expanding || regenerating || redrafting || expandMarkerCount === 0}
                resume={lastFn === "expand"}
                resumeLabel={CHAPTER_FUNCTION_LABELS.expand}
                tipId="chapter.expandPlaceholders"
                onClick={onExpandPlaceholders}
              />
              {reviseUses && (
                <span className="text-[11px] text-ink-muted">
                  Revise reads <strong className="font-medium text-ink-text">{reviseUses}</strong>
                </span>
              )}
            </div>
          </div>
        </WorkflowSection>
      )}

      {showFinalize && (
        <WorkflowSection hint="When happy with Revised, promote on the Final stage.">
          <div className="flex flex-wrap items-center gap-1.5">
            <RunButton
              label="Validate"
              running={runningStage === "validate"}
              disabled={isRunning || (stages.draft == null && stages.revised == null)}
              resume={lastFn === "validate"}
              resumeLabel={CHAPTER_FUNCTION_LABELS.validate}
              tipId="chapter.validate"
              onClick={onValidate}
            />
            <RunButton
              label="Approve"
              running={runningStage === "approve"}
              disabled={isRunning}
              resume={lastFn === "approve"}
              resumeLabel={CHAPTER_FUNCTION_LABELS.approve}
              tipId="chapter.approve"
              onClick={onApprove}
            />
            <ToolTip id="chapter.reviewMentions">
              <button
                type="button"
                onClick={onReviewMentions}
                disabled={isRunning || !hasRegenerateSource}
                className="rounded-md border border-paper-line px-3 py-1 text-[12px] font-medium text-ink-text hover:bg-ink/5 disabled:opacity-40"
              >
                Review mentions
              </button>
            </ToolTip>
            {canReopen && (
              <ToolTip id="chapter.reopen">
                <button
                  type="button"
                  onClick={onReopen}
                  disabled={isRunning || busy != null}
                  className="rounded-md border border-paper-line px-3 py-1 text-[12px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
                >
                  {busy === "reopening" ? "Reopening…" : "Reopen for revision"}
                </button>
              </ToolTip>
            )}
          </div>
        </WorkflowSection>
      )}

      {(longChapterText || isRunning) && (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">Advanced</p>
          <div className="rounded-md border border-paper-line/60 bg-paper/40 px-3 py-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {longChapterText && (
              <RunButton
                label={splittingChapter ? "Splitting…" : "Split into parts (1a, 1b…)"}
                running={splittingChapter}
                disabled={isRunning || splittingChapter || outlineGenerating || aligningBoundary || !hasRegenerateSource}
                tipId="chapter.splitChapter"
                onClick={onSplitChapter}
              />
            )}
            {isRunning && (
              <span className="inline-flex items-center gap-2 text-[11px] text-ink-muted" aria-live="polite">
                <span className="h-2 w-2 animate-pulse rounded-full bg-amber-deep" />
                Agent working…
              </span>
            )}
          </div>
          </div>
        </div>
      )}
    </div>
  );
}
