import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  api,
  type CharacterSummary,
  type ChapterBeatCandidate,
  type ChapterBeatCandidatesResult,
  type ChapterContextPreview,
  type ChapterContextPreviewMode,
  type ContextPreviewSection,
  type StoryGraphEdgeSummary,
  type StoryGraphNodeSummary,
} from "../api/client";
import { useConfirm } from "./Confirm";
import Modal, { fieldClass } from "./Modal";
import PendingAiStar from "./PendingAiStar";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import {
  hasChapterPreviewPending,
  setChapterPreviewPending,
} from "../lib/chapterPreviewPending";
import { syncChapterPreviewPendingFromApi } from "../lib/syncChapterPreviewPending";
import {
  EMPTY_BRIEF_DRAFT,
  briefFromSummary,
  briefHasContent,
  briefToPayload,
  draftWithProjectDefaults,
  projectStyleFromRecord,
  DEFAULT_PROJECT_STYLE,
  promoteCharacterToActive,
  type ChapterBriefDraft,
  type ProjectStyleDefaults,
} from "../lib/chapterBrief";
import BriefCharacterToggle from "./BriefCharacterToggle";
import ChapterBeatBoard from "./ChapterBeatBoard";
import ChapterGraphFocusSection from "./ChapterGraphFocusSection";
import TargetLengthInput from "./TargetLengthInput";

const POV_MODES = [
  ["", "— use project default —"],
  ["first_person", "First person (I / we)"],
  ["second_person", "Second person (you)"],
  ["third_limited", "Third person limited"],
  ["third_omniscient", "Third person omniscient"],
  ["third_objective", "Third person objective"],
  ["multiple_pov", "Multiple POV"],
  ["epistolary", "Epistolary / documents"],
  ["stream_of_consciousness", "Stream of consciousness"],
  ["other", "Other / custom direction in notes"],
] as const;

const CONTEXT_PREVIEW_MODES: { value: ChapterContextPreviewMode; label: string }[] = [
  { value: "outline", label: "Outline" },
  { value: "draft", label: "Draft" },
  { value: "revise", label: "Revise" },
  { value: "validation", label: "Validation" },
];

function previewSnippet(text: string, max = 180): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

function formatPreviewReason(reason: string): string {
  if (reason === "section_default") return "Default section priority";
  if (reason === "text_match") return "Matched chapter outline/text";
  if (reason === "explicit_selection") return "Selected in chapter brief";
  if (reason.startsWith("related")) return reason.replace(/_/g, " ");
  return reason.replace(/_/g, " ");
}

function ContextPreviewSectionBlock({
  title,
  section,
  emptyMessage,
}: {
  title: string;
  section: ContextPreviewSection;
  emptyMessage: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
        {section.omitted_count > 0 && (
          <p className="text-[11.5px] text-amber-deep">
            Omitted {section.omitted_count} ({section.omitted_reason})
          </p>
        )}
      </div>
      {section.items.length === 0 ? (
        <p className="text-[12.5px] text-ink-muted">{emptyMessage}</p>
      ) : (
        <ul className="max-h-[28vh] space-y-2 overflow-auto pr-1">
          {section.items.map((item) => (
            <li
              key={item.key || item.label}
              className="rounded-lg border border-paper-line bg-paper/60 px-3 py-2"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-[13px] font-semibold text-ink-text">{item.label}</p>
                <span className="text-[11px] text-ink-muted">
                  {formatPreviewReason(item.reason)}
                  {item.score > 0 ? ` · score ${Math.round(item.score)}` : ""}
                </span>
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">{previewSnippet(item.body)}</p>
            </li>
          ))}
        </ul>
      )}
      {section.omitted_count > 0 && section.omitted_labels.length > 0 && (
        <p className="text-[11.5px] text-ink-muted">
          Not included: {section.omitted_labels.slice(0, 6).join(", ")}
          {section.omitted_count > section.omitted_labels.length
            ? `, +${section.omitted_count - section.omitted_labels.length} more`
            : ""}
        </p>
      )}
    </div>
  );
}

function ContextPreviewModal({
  open,
  onClose,
  projectId,
  chapterNumber,
  draft,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapterNumber: number;
  draft: ChapterBriefDraft;
}) {
  const toast = useToast();
  const [mode, setMode] = useState<ChapterContextPreviewMode>("draft");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<ChapterContextPreview | null>(null);

  const loadPreview = useCallback(async (nextMode: ChapterContextPreviewMode) => {
    setLoading(true);
    try {
      const result = await api.getChapterContextPreview(
        projectId,
        chapterNumber,
        nextMode,
        briefToPayload(draft),
      );
      setPreview(result);
    } catch (e) {
      toast(String(e), "error");
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterNumber, draft, toast]);

  useEffect(() => {
    if (!open) return;
    void loadPreview(mode);
  }, [open, mode, loadPreview]);

  return (
    <Modal open={open} onClose={loading ? () => {} : onClose} title="Context preview" size="wide">
      <div className="space-y-4">
        <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
          Shows which <strong className="font-medium text-ink-text">Story Bible</strong> sections and{" "}
          <strong className="font-medium text-ink-text">Story Graph</strong> nodes would be injected into
          AI prompts for this chapter, and why items were included or left out by the context budget.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted" htmlFor="context-preview-mode">
            Pipeline mode
          </label>
          <select
            id="context-preview-mode"
            className={fieldClass}
            value={mode}
            onChange={(e) => setMode(e.target.value as ChapterContextPreviewMode)}
            disabled={loading}
          >
            {CONTEXT_PREVIEW_MODES.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          {loading && <span className="text-[12px] text-ink-muted">Loading…</span>}
        </div>

        {preview && !loading && (
          <>
            {preview.active_characters.length > 0 && (
              <div>
                <h3 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                  Active characters
                </h3>
                <p className="text-[12.5px] text-ink-text">
                  {preview.active_characters.map((c) => c.name).join(", ")}
                </p>
              </div>
            )}

            <div>
              <h3 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                Chapter beats
              </h3>
              {preview.beats.length === 0 ? (
                <p className="text-[12.5px] text-ink-muted">
                  No beat-board rows would be included for this chapter.
                </p>
              ) : (
                <ol className="max-h-[24vh] space-y-2 overflow-auto pr-1">
                  {preview.beats.map((beat, index) => (
                    <li
                      key={beat.id || `${index}-${beat.title}`}
                      className="rounded-lg border border-paper-line bg-paper/60 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
                          {beat.status}
                        </span>
                        <p className="text-[13px] font-semibold text-ink-text">{beat.title}</p>
                      </div>
                      {beat.summary && beat.summary.trim().toLowerCase() !== beat.title.trim().toLowerCase() && (
                        <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">{beat.summary}</p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <ContextPreviewSectionBlock
              title="Story Bible"
              section={preview.bible}
              emptyMessage="No bible sections would be included for this budget."
            />

            <ContextPreviewSectionBlock
              title="Story Graph"
              section={preview.graph}
              emptyMessage="No graph nodes selected or budgeted for this chapter brief."
            />
          </>
        )}

        {!loading && !preview && (
          <p className="text-[12.5px] text-ink-muted">Could not load context preview.</p>
        )}

        <div className="flex justify-end border-t border-paper-line/60 pt-3">
          <ToolTip id="chapter.contextPreviewClose">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-lg border border-paper-line bg-paper px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
            >
              Close
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

function LandedBeatCandidatesModal({
  open,
  onClose,
  projectId,
  chapterNumber,
  onApplied,
  onGenerateAgain,
  running,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapterNumber: number;
  onApplied: () => void;
  onGenerateAgain: () => Promise<void>;
  running: boolean;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<ChapterBeatCandidatesResult | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!open) return;
    void loadPreview();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when modal opens
  }, [open, projectId, chapterNumber, running]);

  async function loadPreview() {
    setLoading(true);
    try {
      const preview = await api.getChapterBeatCandidatesPreview(projectId, chapterNumber);
      setResult(preview);
      setSelected(new Set((preview?.candidates ?? []).map((_, index) => index)));
      if (preview) setChapterPreviewPending(projectId, chapterNumber, true);
      else void syncChapterPreviewPendingFromApi(projectId, chapterNumber);
      if (preview && preview.candidates.length === 0) {
        toast("No landed beat candidates found in chapter text", "info");
      }
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setLoading(false);
    }
  }

  async function generateAgain() {
    setResult(null);
    setSelected(new Set());
    void syncChapterPreviewPendingFromApi(projectId, chapterNumber);
    await onGenerateAgain();
  }

  function toggle(index: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function closeAndDiscard() {
    if (!result) {
      onClose();
      return;
    }
    try {
      await api.discardChapterBeatCandidatesPreview(projectId, chapterNumber);
      void syncChapterPreviewPendingFromApi(projectId, chapterNumber);
      setResult(null);
      onClose();
    } catch (e) {
      toast(String(e), "error");
    }
  }

  async function applySelected() {
    if (!result) return;
    const beats = result.candidates
      .filter((_, index) => selected.has(index))
      .map((c) => c.beat);
    if (beats.length === 0) {
      toast("Select at least one candidate to apply", "error");
      return;
    }
    setApplying(true);
    try {
      await api.applyChapterBeatCandidates(projectId, chapterNumber, {
        selected_beats: beats,
        mode: "append",
      });
      void syncChapterPreviewPendingFromApi(projectId, chapterNumber);
      onApplied();
      toast(`Applied ${beats.length} landed beat(s) to beat board`, "success");
      onClose();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setApplying(false);
    }
  }

  const selectedCandidateCount = result
    ? result.candidates.filter((_, index) => selected.has(index)).length
    : 0;

  return (
    <Modal
      open={open}
      onClose={loading || applying ? () => {} : onClose}
      title="Review landed beat candidates"
      size="wide"
    >
      <div className="space-y-4">
        <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
          Scans chapter manuscript text for beats that already landed on the page. Selected candidates
          are added to the <strong className="font-medium text-ink-text">beat board</strong> as landed — they do not
          replace planned beats or update Story Bible canon.
        </p>

        {running && (
          <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2 text-[12.5px] text-ink-muted">
            Archivist is extracting landed beats. You can leave this panel; the chapter list will mark this chapter while the work is outstanding.
          </p>
        )}

        {result && (
          <p className="text-[12.5px] text-ink-muted">
            Source used: <span className="font-medium text-ink-text">{result.source_used}</span>
            {" · "}
            {result.candidates.length} candidate(s)
          </p>
        )}

        {loading && !result && (
          <p className="text-[12.5px] text-ink-muted">Checking for completed landed beat candidates…</p>
        )}

        {!loading && !running && !result && (
          <p className="text-[12.5px] text-ink-muted">
            No landed beat candidates are ready yet. Start extraction to queue an Archivist scan.
          </p>
        )}

        {result && result.candidates.length > 0 && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12px] text-ink-muted">
                Check beats to add to the beat board.
              </p>
              <ToolTip id="chapter.landedBeatsSelectAll">
                <button
                  type="button"
                  onClick={() =>
                    setSelected(
                      selected.size === result.candidates.length
                        ? new Set()
                        : new Set(result.candidates.map((_, index) => index)),
                    )
                  }
                  className="text-[12px] font-semibold text-amber-deep hover:underline"
                >
                  {selected.size === result.candidates.length ? "Select none" : "Select all"}
                </button>
              </ToolTip>
            </div>
            <ol className="max-h-[46vh] space-y-2 overflow-auto pr-1">
              {result.candidates.map((candidate, index) => (
                <BeatCandidateRow
                  key={`${candidate.rank}-${index}-${candidate.beat}`}
                  candidate={candidate}
                  selected={selected.has(index)}
                  onToggle={() => toggle(index)}
                />
              ))}
            </ol>
          </div>
        )}

        {result && result.candidates.length === 0 && !loading && (
          <p className="text-[12.5px] text-ink-muted">
            No candidates were extracted. Try Generate again or ensure the chapter has draft/revised/final text.
          </p>
        )}

        <div className="flex flex-wrap justify-end gap-2 border-t border-paper-line/60 pt-3">
          <ToolTip id="chapter.landedBeatsDiscard">
            <button
              type="button"
              onClick={() => void closeAndDiscard()}
              disabled={applying || loading || (running && !result)}
              className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
            >
              Discard / Close
            </button>
          </ToolTip>
          <ToolTip id="chapter.landedBeatsGenerate">
            <button
              type="button"
              onClick={() => void generateAgain()}
              disabled={loading || applying || running}
              className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-amber/10 disabled:opacity-40"
            >
              {running ? "Extracting…" : result ? "Generate again" : "Start extraction"}
            </button>
          </ToolTip>
          <ToolTip id="chapter.landedBeatsApply">
            <button
              type="button"
              onClick={() => void applySelected()}
              disabled={applying || loading || !result || selectedCandidateCount === 0}
              className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {applying ? "Applying…" : `Apply selected (${selectedCandidateCount})`}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

/*
 * Candidate rows are intentionally below the modal so the review UI can be reused
 * if landed-beat extraction later moves into a broader chapter planning surface.
 */
function BeatCandidateRow({
  candidate,
  selected,
  onToggle,
}: {
  candidate: ChapterBeatCandidate;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="rounded-lg border border-paper-line bg-paper-card p-3">
      <label className="flex cursor-pointer items-start gap-3">
        <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-semibold text-amber-deep">
              #{candidate.rank}
            </span>
            {candidate.category && (
              <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] capitalize text-ink-muted">
                {candidate.category}
              </span>
            )}
            {candidate.significance && (
              <span className="rounded-full bg-amber/10 px-2 py-0.5 text-[11px] text-ink-muted">
                {candidate.significance}
              </span>
            )}
          </span>
          <span className="mt-1 block text-[13px] font-medium text-ink-text">{candidate.beat}</span>
          {candidate.story_relevance && (
            <span className="mt-1 block text-[12px] text-ink-muted">{candidate.story_relevance}</span>
          )}
          {candidate.involved_characters.length > 0 && (
            <span className="mt-1 block text-[11px] text-ink-muted">
              Characters: {candidate.involved_characters.join(", ")}
            </span>
          )}
        </span>
      </label>
    </li>
  );
}
export default function ChapterBriefPanel({
  projectId,
  chapterNumber,
  characters,
  graphNodes: graphNodesProp,
  refreshToken,
  onBriefPresenceChange,
  embedded = false,
  trailingSection,
  operationsSection,
  onCollapsedChange,
  expandedFocus = false,
}: {
  projectId: string;
  chapterNumber: number;
  characters: CharacterSummary[];
  graphNodes?: StoryGraphNodeSummary[];
  refreshToken?: number;
  onBriefPresenceChange?: (hasContent: boolean) => void;
  /** Tighter layout for the sticky chapter studio chrome. */
  embedded?: boolean;
  /** Rendered inside the collapsible body (e.g. Codex sync). */
  trailingSection?: ReactNode;
  /** Chapter insert/duplicate/renumber/delete controls — nested inside the panel body. */
  operationsSection?: ReactNode;
  /** Notifies parent when the panel is collapsed or expanded. */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** When expanded, fill available studio height instead of a short scroll region. */
  expandedFocus?: boolean;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [draft, setDraft] = useState<ChapterBriefDraft>(EMPTY_BRIEF_DRAFT);
  const [saved, setSaved] = useState<ChapterBriefDraft>(EMPTY_BRIEF_DRAFT);
  const [hasBrief, setHasBrief] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState(true);
  const [graphNodes, setGraphNodes] = useState<StoryGraphNodeSummary[]>(graphNodesProp ?? []);
  const [graphEdges, setGraphEdges] = useState<StoryGraphEdgeSummary[]>([]);
  const [projectStyle, setProjectStyle] = useState<ProjectStyleDefaults>(DEFAULT_PROJECT_STYLE);
  const [beatCandidatesOpen, setBeatCandidatesOpen] = useState(false);
  const [beatBoardRefresh, setBeatBoardRefresh] = useState(0);
  const [contextPreviewOpen, setContextPreviewOpen] = useState(false);
  const { watchBackgroundJob, isProjectJobRunning } = useBackgroundJob();
  const beatScope = String(chapterNumber);
  const briefGenerationRunning = isProjectJobRunning("chapter-brief", projectId, beatScope);
  const beatExtractionRunning = isProjectJobRunning("landed-beats", projectId, beatScope);
  const beatCandidatesPending = hasChapterPreviewPending(projectId, chapterNumber);

  const loadBrief = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.getChapterBrief(projectId, chapterNumber).catch(() => null),
      api.project(projectId).catch(() => null),
    ])
      .then(([brief, project]) => {
        const style = projectStyleFromRecord(project?.style);
        setProjectStyle(style);
        if (brief) {
          const d = draftWithProjectDefaults(briefFromSummary(brief), style);
          setDraft(d);
          setSaved(d);
          setHasBrief(true);
          onBriefPresenceChange?.(briefHasContent(d));
        } else {
          const d = draftWithProjectDefaults(EMPTY_BRIEF_DRAFT, style);
          setDraft(d);
          setSaved(d);
          setHasBrief(false);
          onBriefPresenceChange?.(briefHasContent(d));
        }
      })
      .catch(() => {
        const d = draftWithProjectDefaults(EMPTY_BRIEF_DRAFT, DEFAULT_PROJECT_STYLE);
        setDraft(d);
        setSaved(d);
        setHasBrief(false);
      })
      .finally(() => setLoading(false));
  }, [projectId, chapterNumber, onBriefPresenceChange]);

  useEffect(() => {
    loadBrief();
  }, [loadBrief, refreshToken]);

  useEffect(() => {
    setCollapsed(true);
  }, [projectId, chapterNumber]);

  // Notify parent only when `collapsed` actually changes. The parent's inline
  // arrow callback would otherwise cause this effect to fire on every parent
  // re-render, stomping any pending state updates in the parent (e.g. an
  // explicit pipeline-stage click). We also skip the very first invocation on
  // mount — the parent already knows the initial state and doesn't need a
  // synthetic collapse callback that would mutate persisted studio place.
  const onCollapsedChangeRef = useRef(onCollapsedChange);
  useEffect(() => {
    onCollapsedChangeRef.current = onCollapsedChange;
  }, [onCollapsedChange]);
  const firstCollapsedReportRef = useRef(true);
  useEffect(() => {
    if (firstCollapsedReportRef.current) {
      firstCollapsedReportRef.current = false;
      return;
    }
    onCollapsedChangeRef.current?.(collapsed);
  }, [collapsed]);

  useEffect(() => {
    if (graphNodesProp) {
      setGraphNodes(graphNodesProp);
      return;
    }
    api.storyGraphNodes(projectId)
      .then(setGraphNodes)
      .catch(() => setGraphNodes([]));
  }, [projectId, graphNodesProp]);

  useEffect(() => {
    api.storyGraphEdges(projectId)
      .then(setGraphEdges)
      .catch(() => setGraphEdges([]));
  }, [projectId]);

  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(saved),
    [draft, saved],
  );

  async function save() {
    setBusy(true);
    try {
      const result = await api.saveChapterBrief(
        projectId,
        chapterNumber,
        briefToPayload(draft),
      );
      const d = briefFromSummary(result);
      setDraft(d);
      setSaved(d);
      setHasBrief(true);
      onBriefPresenceChange?.(briefHasContent(d));
      toast("Chapter brief saved", "success");
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteChapterBrief(projectId, chapterNumber);
      const d = draftWithProjectDefaults(EMPTY_BRIEF_DRAFT, projectStyle);
      setDraft(d);
      setSaved(d);
      setHasBrief(false);
      onBriefPresenceChange?.(false);
      toast("Chapter brief removed", "success");
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function generateBrief() {
    if (dirty || briefHasContent(draft)) {
      const ok = await confirm({
        title: "Generate chapter brief?",
        message: "Generate and save a chapter brief from the current chapter text? This will replace the current brief fields and refresh the beat board.",
        confirmLabel: "Generate brief",
      });
      if (!ok) return;
    }
    setBusy(true);
    try {
      const job = await api.generateChapterBriefAsync(projectId, chapterNumber, {
        source: "best",
        ...(dirty ? { current_brief: briefToPayload(draft) } : {}),
      });
      watchBackgroundJob(job.job_id, {
        label: "Chapter brief",
        kind: "chapter-brief",
        projectId,
        scope: beatScope,
        successMessage: `Chapter ${chapterNumber} brief generated`,
        onSuccess: () => {
          loadBrief();
          setBeatBoardRefresh((n) => n + 1);
          setCollapsed(false);
        },
      });
      setCollapsed(false);
      toast("Generating chapter brief in the background", "success");
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  function handleBeatCandidatesApplied() {
    setBeatBoardRefresh((n) => n + 1);
    setCollapsed(false);
  }

  async function startBeatExtraction() {
    try {
      void syncChapterPreviewPendingFromApi(projectId, chapterNumber);
      const job = await api.generateChapterBeatCandidatesAsync(projectId, chapterNumber, {
        source: "best",
        count: 10,
      });
      watchBackgroundJob(job.job_id, {
        label: "Landed beats",
        kind: "landed-beats",
        projectId,
        scope: beatScope,
        successMessage: `Landed beats ready for chapter ${chapterNumber}`,
        onSuccess: () => {
          setChapterPreviewPending(projectId, chapterNumber, true);
          setBeatCandidatesOpen(true);
        },
      });
      setBeatCandidatesOpen(true);
      toast("Extracting landed beats in the background", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  if (loading) {
    return (
      <div className={`text-[12px] text-ink-muted ${embedded ? "mt-1 px-1 py-1" : "mt-4 px-4 py-3"}`}>
        Loading chapter brief…
      </div>
    );
  }

  return (
    <section
      className={`${
        embedded
          ? `mt-2 ${collapsed ? "" : "rounded-lg border border-paper-line bg-paper-card/40 shadow-[var(--shadow-paper)]"}`
          : "mt-4 rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]"
      } ${expandedFocus && !collapsed ? "flex min-h-0 flex-1 flex-col overflow-hidden" : ""}`}
    >
      <ToolTip id="chapter.briefCollapse">
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
          className={`flex w-full items-center justify-between gap-3 text-left transition-colors ${
            embedded
              ? `rounded-lg border border-paper-line bg-paper/70 px-3 py-2 shadow-[var(--shadow-paper)] hover:bg-ink/[0.04] ${
                  !collapsed ? "rounded-b-none border-b-paper-line/80" : ""
                }`
              : `hover:bg-ink/[0.03] ${collapsed ? "px-4 py-3" : "border-b border-paper-line px-4 py-2.5"}`
          }`}
        >
          <span className="inline-flex min-w-0 flex-wrap items-center gap-2 font-display text-[13px] font-bold tracking-tight text-ink-text">
            Chapter Brief and Operations
            {beatCandidatesPending && <PendingAiStar title="Landed beat candidates ready to review" />}
            {hasBrief && !dirty && (
              <span className="text-[10px] font-normal text-st-approved">saved</span>
            )}
            {dirty && (
              <span className="text-[10px] font-normal text-amber-deep">unsaved</span>
            )}
          </span>
          <span className="inline-flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-ink-muted">
            {collapsed ? "Expand" : "Collapse"}
            <span aria-hidden className="text-[12px]">{collapsed ? "▸" : "▾"}</span>
          </span>
        </button>
      </ToolTip>

      {!collapsed && (
        <div
          className={
            expandedFocus
              ? `min-h-0 flex-1 overflow-y-auto ${embedded ? "px-1 py-3" : "px-4 py-4"}`
              : `max-h-[min(38vh,400px)] overflow-y-auto ${embedded ? "px-1 py-3" : "px-4 py-4"}`
          }
        >
          <div className="space-y-4">
          <p className="rounded-lg border border-amber/20 bg-amber/5 px-3 py-2 text-[12px] leading-relaxed text-ink-muted">
            This brief is the <strong className="font-medium text-ink-text">single source of truth</strong> for POV and
            writing style in AI prompts. Chapter style defaults on the project page supply starting values; override any field here per
            chapter. Beats live on the beat board below — the outline is export/sync.
          </p>

          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Writing style
            </p>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div>
                <label htmlFor="brief-tone" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Tone
                </label>
                <input
                  id="brief-tone"
                  className={fieldClass}
                  value={draft.tone}
                  onChange={(e) => setDraft((d) => ({ ...d, tone: e.target.value }))}
                  placeholder={projectStyle.tone}
                />
              </div>
              <div>
                <label htmlFor="brief-tense" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Tense
                </label>
                <select
                  id="brief-tense"
                  className={fieldClass}
                  value={draft.tense}
                  onChange={(e) => setDraft((d) => ({ ...d, tense: e.target.value }))}
                >
                  <option value="">— project default —</option>
                  <option value="past">Past</option>
                  <option value="present">Present</option>
                  <option value="future">Future</option>
                </select>
              </div>
              <div>
                <label htmlFor="brief-prose" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Prose style
                </label>
                <input
                  id="brief-prose"
                  className={fieldClass}
                  value={draft.prose_style}
                  onChange={(e) => setDraft((d) => ({ ...d, prose_style: e.target.value }))}
                  placeholder={projectStyle.prose_style}
                />
              </div>
              <div>
                <label htmlFor="brief-vocab" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Vocabulary
                </label>
                <input
                  id="brief-vocab"
                  className={fieldClass}
                  value={draft.vocabulary_level}
                  onChange={(e) => setDraft((d) => ({ ...d, vocabulary_level: e.target.value }))}
                  placeholder={projectStyle.vocabulary_level}
                />
              </div>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="brief-target-length" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Target length (words)
                </label>
                <TargetLengthInput
                  id="brief-target-length"
                  value={draft.target_word_count}
                  onChange={(target_word_count) => setDraft((d) => ({ ...d, target_word_count }))}
                  projectDefault={projectStyle.chapter_target_words}
                  allowBlank
                  placeholder={String(projectStyle.chapter_target_words)}
                  tipId="chapter.briefTargetLength"
                />
                <p className="mt-1 text-[11px] text-ink-muted">
                  Blank uses the project Target length default ({projectStyle.chapter_target_words.toLocaleString()} words).
                </p>
              </div>
              <div>
                <label htmlFor="brief-style-notes" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Style notes
                </label>
                <textarea
                  id="brief-style-notes"
                  className={fieldClass}
                  rows={2}
                  value={draft.style_notes}
                  onChange={(e) => setDraft((d) => ({ ...d, style_notes: e.target.value }))}
                  placeholder={projectStyle.description || "Chapter-specific voice or rhythm notes…"}
                />
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label htmlFor="brief-pov" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                POV character
              </label>
              <select
                id="brief-pov"
                className={fieldClass}
                value={draft.pov_character_id}
                onChange={(e) => {
                  const povCharacterId = e.target.value;
                  setDraft((current) => {
                    const next = povCharacterId
                      ? promoteCharacterToActive({ ...current, pov_character_id: povCharacterId }, povCharacterId)
                      : { ...current, pov_character_id: "" };
                    return next;
                  });
                }}
              >
                <option value="">— none —</option>
                {characters.map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="brief-pov-mode" className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Narrative perspective
              </label>
              <select
                id="brief-pov-mode"
                className={fieldClass}
                value={draft.pov_mode}
                onChange={(e) => setDraft((d) => ({ ...d, pov_mode: e.target.value }))}
              >
                {POV_MODES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Ending hook
              </label>
              <input
                className={fieldClass}
                value={draft.ending_hook}
                onChange={(e) => setDraft((d) => ({ ...d, ending_hook: e.target.value }))}
                placeholder="How should this chapter end?"
              />
            </div>
          </div>

          {characters.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Cast in this chapter
              </p>
              <BriefCharacterToggle
                characters={characters}
                draft={draft}
                onChange={setDraft}
              />
            </div>
          )}

          {graphNodes.length > 0 ? (
            <ChapterGraphFocusSection
              projectId={projectId}
              chapterNumber={chapterNumber}
              nodes={graphNodes}
              edges={graphEdges}
              characters={characters}
              selectedIds={draft.active_node_ids}
              onChange={(active_node_ids) => setDraft((d) => ({ ...d, active_node_ids }))}
              onGraphNodesChange={setGraphNodes}
            />
          ) : (
            <p className="text-[12px] text-ink-muted">
              No story-graph nodes yet — add them in the project Story Graph tab to link chapters to plots.
            </p>
          )}

          <ChapterBeatBoard
            projectId={projectId}
            chapterNumber={chapterNumber}
            graphNodes={graphNodes}
            disabled={busy}
            refreshToken={(refreshToken ?? 0) + beatBoardRefresh}
          />

          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Continuity notes
            </label>
            <textarea
              className={fieldClass}
              rows={3}
              value={draft.continuity_notes}
              onChange={(e) => setDraft((d) => ({ ...d, continuity_notes: e.target.value }))}
              placeholder="Props, injuries, secrets the reader should remember…"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-paper-line/60 pt-3">
            <ToolTip id="chapter.generateBrief">
              <button
                type="button"
                onClick={() => void generateBrief()}
                disabled={busy || briefGenerationRunning}
                className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-amber/10 disabled:opacity-40"
              >
                {briefGenerationRunning ? "Generating brief…" : "Generate brief"}
              </button>
            </ToolTip>
            <ToolTip id="chapter.landedBeats">
              <button
                type="button"
                onClick={() => {
                  if (beatCandidatesPending || beatExtractionRunning) {
                    setBeatCandidatesOpen(true);
                  } else {
                    void startBeatExtraction();
                  }
                }}
                disabled={busy}
                className="rounded-lg border border-paper-line bg-paper px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
              >
                {beatExtractionRunning
                  ? "Extracting landed beats…"
                  : beatCandidatesPending
                    ? (
                      <span className="inline-flex items-center gap-1">
                        Review landed beats
                        <PendingAiStar title="Landed beat candidates ready to review" />
                      </span>
                    )
                    : "Extract landed beats"}
              </button>
            </ToolTip>
            <ToolTip id="chapter.contextPreview">
              <button
                type="button"
                onClick={() => setContextPreviewOpen(true)}
                disabled={busy}
                className="rounded-lg border border-paper-line bg-paper px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
              >
                Context preview
              </button>
            </ToolTip>
            <ToolTip id="chapter.saveBrief">
              <button
                type="button"
                onClick={() => void save()}
                disabled={busy || (!dirty && hasBrief)}
                className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
              >
                {busy ? "Saving…" : "Save brief"}
              </button>
            </ToolTip>
            {hasBrief && (
              <ToolTip id="chapter.deleteBrief">
                <button
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    const ok = await confirm({
                      title: "Delete chapter brief",
                      message: "Remove this chapter brief? Outline and draft prompts will no longer include these selections.",
                      confirmLabel: "Delete brief",
                      danger: true,
                    });
                    if (ok) void remove();
                  }}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-red-700 hover:bg-red-50 disabled:opacity-40"
                >
                  Delete brief
                </button>
              </ToolTip>
            )}
            {!hasBrief && !briefHasContent(draft) && (
              <span className="text-[12px] text-ink-muted">Optional — fill in planning context when ready.</span>
            )}
          </div>
          {operationsSection && <div className="mt-4">{operationsSection}</div>}
          {trailingSection && <div className="mt-4">{trailingSection}</div>}
          </div>
        </div>
      )}

      <ContextPreviewModal
        open={contextPreviewOpen}
        onClose={() => setContextPreviewOpen(false)}
        projectId={projectId}
        chapterNumber={chapterNumber}
        draft={draft}
      />

      <LandedBeatCandidatesModal
        open={beatCandidatesOpen}
        onClose={() => setBeatCandidatesOpen(false)}
        projectId={projectId}
        chapterNumber={chapterNumber}
        onApplied={handleBeatCandidatesApplied}
        onGenerateAgain={startBeatExtraction}
        running={beatExtractionRunning}
      />
    </section>
  );
}
