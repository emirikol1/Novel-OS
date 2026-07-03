import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  api,
  type ChapterDetail,
  type ChapterStages,
  type ChapterSummary,
  type CharacterSummary,
  type RegeneratePreview,
  type RedraftPreview,
  type BoundaryAlignmentPreview,
  type CommentItem,
  type AddCommentPayload,
} from "../api/client";
import PipelineFlow, { type StageKey } from "../components/PipelineFlow";
import FinalEditor from "../components/FinalEditor";
import ManuscriptEditor from "../components/ManuscriptEditor";
import MarkdownEditor from "../components/MarkdownEditor";
import Inspector from "../components/Inspector";
import Breadcrumbs from "../components/Breadcrumbs";
import ToolTip from "../components/ToolTip";
import { RenumberChapterModal } from "../components/CodexEditors";
import { useToast } from "../components/Toaster";
import { useConfirm } from "../components/Confirm";
import { useRunPhase } from "../hooks/useRunPhase";
import { isJobCancelledError, pollJob } from "../lib/jobPolling";
import { useBackgroundJob, type BackgroundJobKind } from "../hooks/useBackgroundJob";
import { formatSavedAt, SaveStatus } from "../components/EditorSaveBar";
import PanelResizeHandle from "../components/PanelResizeHandle";
import StoryPanelToggles from "../components/StoryPanelToggles";
import { useManuscriptPrefs } from "../components/ManuscriptControls";
import { useElementWidth } from "../hooks/useElementWidth";
import { usePanelResize } from "../hooks/usePanelResize";
import {
  BINDER_WIDTH,
  CENTER_STUDIO_GUTTER_PX,
  INSPECTOR_WIDTH_MIN,
  MANUSCRIPT_REF_WIDTH_PX,
  computeFluidManuscriptLayout,
  computeInspectorMaxWidth,
} from "../lib/chapterStudioLayout";
import { ChapterPipelineDot } from "../components/ChapterPipelineStatus";
import PendingAiStar from "../components/PendingAiStar";
import ChapterWorkflowToolbar, { CodexSyncSection, type MineKind } from "../components/ChapterWorkflowToolbar";
import { pipelineStepFromSummary } from "../lib/chapterPipeline";
import { useLayoutPrefs } from "../context/LayoutPrefs";
import { useWorkflowMarkers } from "../hooks/useWorkflowMarkers";
import { isNotFoundError, redirectOnChapterNotFound } from "../lib/apiHealth";
import {
  setChapterPreviewPending,
  hasChapterPreviewPending,
  remapChapterPreviewPending,
} from "../lib/chapterPreviewPending";
import {
  previewPendingStages,
  syncChapterPreviewPendingFromApi,
} from "../lib/syncChapterPreviewPending";
import { commentStage, isManuscriptStage } from "../lib/annotations";
import {
  recordChapterFunction,
  recordChapterVisit,
  remapChapterWorkflowMarkers,
  type ChapterFunction,
} from "../lib/chapterWorkflow";
import {
  readStudioPlace,
  stageForStudioPlace,
  studioPlaceFromSelection,
  writeStudioPlace,
  type ChapterStudioPlace,
} from "../lib/chapterStudioNav";
import MentionMarkdown from "../components/MentionMarkdown";
import MentionReviewPanel from "../components/MentionReviewPanel";
import ChapterBriefPanel from "../components/ChapterBriefPanel";
import ChapterOperationsSection from "../components/ChapterOperationsSection";
import ChapterMinePreviewModal from "../components/ChapterMinePreviewModal";
import { briefFromSummary, briefHasContent } from "../lib/chapterBrief";
import { setMinePreviewPending } from "../lib/minePreviewPending";
import { buildMentionTargets, type MentionTarget } from "../lib/mentions";

const STAGE_KEYS: StageKey[] = ["outline", "draft", "revised", "final"];

const MINE_JOB_KIND: Record<MineKind, BackgroundJobKind> = {
  plots: "mine-plots",
  characters: "mine-characters",
  bible: "mine-bible",
};

const MINE_LABELS: Record<MineKind, string> = {
  plots: "Plots & subplots",
  characters: "Characters",
  bible: "Story bible",
};

const EXPAND_MARKER_RE = /\[\[(?:expand|ai)\s*:/gi;

function countExpandMarkers(text: string): number {
  return (text.match(EXPAND_MARKER_RE) || []).length;
}

function regenerateSource(stages: ChapterStages, selected: StageKey): string {
  if (selected === "draft" && stages.draft) return "draft";
  if (selected === "revised" && stages.revised) return "revised";
  if (selected === "final" && stages.final) return "final";
  if (stages.draft) return "draft";
  if (stages.final) return "final";
  if (stages.revised) return "revised";
  return "draft";
}

function hasRegenerateSource(stages: ChapterStages): boolean {
  return !!(stages.draft || stages.revised || stages.final);
}

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const num = Number(n);
  const toast = useToast();
  const confirm = useConfirm();
  const [searchParams, setSearchParams] = useSearchParams();

  const [meta, setMeta] = useState<ChapterDetail | null>(null);
  const [stages, setStages] = useState<ChapterStages | null>(null);
  const [siblings, setSiblings] = useState<ChapterSummary[]>([]);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [storyBible, setStoryBible] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);

  const [finalText, setFinalText] = useState("");
  const [draftText, setDraftText] = useState("");
  const [revisedText, setRevisedText] = useState("");
  const [outlineText, setOutlineText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [revisedDirty, setRevisedDirty] = useState(false);
  const [outlineDirty, setOutlineDirty] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [expandPreview, setExpandPreview] = useState<RegeneratePreview | null>(null);
  const [expandPreviewText, setExpandPreviewText] = useState("");
  const [paragraphsPreview, setParagraphsPreview] = useState<RegeneratePreview | null>(null);
  const [paragraphsPreviewText, setParagraphsPreviewText] = useState("");
  const [formattingParagraphs, setFormattingParagraphs] = useState(false);
  const [aligningBoundary, setAligningBoundary] = useState(false);
  const [alignmentPreview, setAlignmentPreview] = useState<BoundaryAlignmentPreview | null>(null);
  const [alignmentTextA, setAlignmentTextA] = useState("");
  const [alignmentTextB, setAlignmentTextB] = useState("");
  const [regeneratePreview, setRegeneratePreview] = useState<RegeneratePreview | null>(null);
  const [previewText, setPreviewText] = useState("");
  const [redraftPreview, setRedraftPreview] = useState<RedraftPreview | null>(null);
  const [redraftPreviewText, setRedraftPreviewText] = useState("");
  const [redrafting, setRedrafting] = useState(false);
  const [redraftMode, setRedraftMode] = useState<"align" | "preserve">("align");
  const [hasSavedBrief, setHasSavedBrief] = useState(false);
  const [regenInstructions, setRegenInstructions] = useState("");
  const [applyNotesToOutline, setApplyNotesToOutline] = useState(false);
  const [outlineGenerating, setOutlineGenerating] = useState(false);
  const [splittingChapter, setSplittingChapter] = useState(false);
  const [outlinePreview, setOutlinePreview] = useState<RegeneratePreview | null>(null);
  const [outlinePreviewText, setOutlinePreviewText] = useState("");
  const [outlineInstructions, setOutlineInstructions] = useState("");
  const [busy, setBusy] = useState<null | "saving" | "promoting" | "reopening">(null);
  const [focus, setFocus] = useState(false);
  const [briefExpanded, setBriefExpanded] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [draftLastSaved, setDraftLastSaved] = useState<string | null>(null);
  const [revisedLastSaved, setRevisedLastSaved] = useState<string | null>(null);
  const [outlineLastSaved, setOutlineLastSaved] = useState<string | null>(null);
  const [renumberOpen, setRenumberOpen] = useState(false);
  const [mentionPanelOpen, setMentionPanelOpen] = useState(false);
  const [minePreviewOpen, setMinePreviewOpen] = useState(false);
  const [minePreviewKind, setMinePreviewKind] = useState<MineKind>("plots");
  const [mentionFocusCharId, setMentionFocusCharId] = useState<string | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [focusAnnotationId, setFocusAnnotationId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"versions" | "cast" | "comments" | undefined>(undefined);
  const [commentPrefill, setCommentPrefill] = useState<AddCommentPayload | null>(null);
  const lastPipelinePhaseRef = useRef<string | null>(null);
  const studioPlaceRef = useRef<ChapterStudioPlace>(readStudioPlace(id) ?? "prose");
  // `selected` is the source of truth for the active pipeline stage. It is
  // recomputed exactly once per chapter (see the effect below) so that intra-
  // chapter stage clicks are never overridden by anything else.
  const [selected, setSelected] = useState<StageKey>(() => {
    const url = searchParams.get("stage") as StageKey | null;
    if (url && STAGE_KEYS.includes(url)) return url;
    return "outline";
  });
  const selectedForChapterRef = useRef<number | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [titleSaving, setTitleSaving] = useState(false);
  const [titleLastSaved, setTitleLastSaved] = useState<string | null>(null);
  const [contentRevision, setContentRevision] = useState(0);
  const navigate = useNavigate();
  const {
    showBinder,
    showInspector,
    setShowInspector,
    inspectorWidth,
    setInspectorWidth,
  } = useLayoutPrefs();
  const manuscriptPrefs = useManuscriptPrefs();
  const studioRef = useRef<HTMLDivElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);
  const studioWidth = useElementWidth(studioRef);
  const centerWidth = useElementWidth(centerRef);
  const [inspectorWidthLive, setInspectorWidthLive] = useState(inspectorWidth);

  useEffect(() => {
    setInspectorWidthLive(inspectorWidth);
  }, [inspectorWidth]);

  const fluidLayout = useMemo(
    () => computeFluidManuscriptLayout(
      centerWidth || MANUSCRIPT_REF_WIDTH_PX,
      manuscriptPrefs.measure,
    ),
    [centerWidth, manuscriptPrefs.measure],
  );

  const inspectorMaxWidth = useMemo(
    () => computeInspectorMaxWidth(
      studioWidth,
      manuscriptPrefs.measure,
      showBinder && !focus,
    ),
    [studioWidth, manuscriptPrefs.measure, showBinder, focus],
  );

  useEffect(() => {
    if (inspectorWidthLive > inspectorMaxWidth) {
      setInspectorWidthLive(inspectorMaxWidth);
      setInspectorWidth(inspectorMaxWidth);
    }
  }, [inspectorMaxWidth, inspectorWidthLive, setInspectorWidth]);

  const studioColumnStyle = useMemo(
    () => ({
      width: fluidLayout.columnMaxPx,
      maxWidth: fluidLayout.columnMaxPx,
      minWidth: fluidLayout.columnMaxPx,
      marginInline: "auto" as const,
    }),
    [fluidLayout.columnMaxPx],
  );

  const inspectorResize = usePanelResize({
    width: inspectorWidthLive,
    onWidthChange: setInspectorWidthLive,
    onCommit: setInspectorWidth,
    min: INSPECTOR_WIDTH_MIN,
    max: inspectorMaxWidth,
    side: "right",
  });
  const { lastAccessedChapter, lastFunction: lastFn } = useWorkflowMarkers(id, num);
  const hasPreviewPending =
    Boolean(regeneratePreview || outlinePreview || expandPreview || paragraphsPreview || redraftPreview)
    || hasChapterPreviewPending(id, num);

  // refs so the unmount/unload/autosave handlers see the latest values
  const dirtyRef = useRef(false);
  const draftDirtyRef = useRef(false);
  const revisedDirtyRef = useRef(false);
  const outlineDirtyRef = useRef(false);
  const titleFocused = useRef(false);
  const titleDraftRef = useRef("");
  const textRef = useRef("");
  const draftTextRef = useRef("");
  const revisedTextRef = useRef("");
  const outlineTextRef = useRef("");
  const busyRef = useRef<typeof busy>(null);
  const phaseAfterDone = useRef<StageKey | null>(null);
  const pendingOutlineAfterReviseRef = useRef(false);
  const startGenerateOutlineRef = useRef<(mode?: "text" | "notes") => Promise<void>>(async () => {});
  const saveDraftRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  const saveRevisedRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  const saveOutlineRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  const saveChapterTitleRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  const reloadGenRef = useRef(0);
  dirtyRef.current = dirty;
  draftDirtyRef.current = draftDirty;
  revisedDirtyRef.current = revisedDirty;
  outlineDirtyRef.current = outlineDirty;
  textRef.current = finalText;
  draftTextRef.current = draftText;
  revisedTextRef.current = revisedText;
  outlineTextRef.current = outlineText;
  titleDraftRef.current = titleDraft;
  busyRef.current = busy;

  function selectStage(s: StageKey) {
    setSelected(s);
    selectedForChapterRef.current = num;
    if (s === "outline") {
      studioPlaceRef.current = "outline";
      writeStudioPlace(id, "outline");
    } else {
      studioPlaceRef.current = "prose";
      writeStudioPlace(id, "prose");
    }
    setBriefExpanded(false);
    setSearchParams(
      (prev) => {
        prev.set("stage", s);
        return prev;
      },
      { replace: true },
    );
  }

  function setBriefPanelExpanded(expanded: boolean) {
    // Skip if the panel is already in the requested state. Prevents spurious
    // side effects (place ref / sessionStorage / re-render) when child panels
    // fire lifecycle-style callbacks that don't represent user actions.
    if (expanded === briefExpanded) return;
    setBriefExpanded(expanded);
    if (expanded) {
      studioPlaceRef.current = "brief";
      writeStudioPlace(id, "brief");
      return;
    }
    // Collapse only updates the persisted place — never overrides the user's
    // explicit stage selection.
    studioPlaceRef.current = selected === "outline" ? "outline" : "prose";
    writeStudioPlace(id, studioPlaceRef.current);
  }

  function combinedOutlineInstructions(): string {
    const outline = outlineInstructions.trim();
    const revision = regenInstructions.trim();
    if (applyNotesToOutline && revision) {
      if (outline) {
        return `${outline}\n\n## Revision notes\n${revision}`;
      }
      return revision;
    }
    return outline;
  }

  const hasOutlineNotes = Boolean(combinedOutlineInstructions().trim());

  const chapterNumValid = Number.isFinite(num) && num >= 1;

  useEffect(() => {
    const stored = readStudioPlace(id);
    if (stored) studioPlaceRef.current = stored;
  }, [id]);

  useEffect(() => {
    reloadGenRef.current += 1;
    setMeta(null);
    setStages(null);
    setError(null);
    setRegeneratePreview(null);
    setPreviewText("");
    setRedraftPreview(null);
    setRedraftPreviewText("");
    setHasSavedBrief(false);
    setOutlinePreview(null);
    setOutlinePreviewText("");
    setExpandPreview(null);
    setExpandPreviewText("");
    setParagraphsPreview(null);
    setParagraphsPreviewText("");
    setBriefExpanded(studioPlaceRef.current === "brief");
    setDirty(false);
    setDraftDirty(false);
    setRevisedDirty(false);
    setOutlineDirty(false);
    dirtyRef.current = false;
    draftDirtyRef.current = false;
    revisedDirtyRef.current = false;
    outlineDirtyRef.current = false;
    if (!titleFocused.current) setTitleDraft("");
    // Force landing-stage recomputation on the next stages-load for this chapter.
    selectedForChapterRef.current = null;
  }, [id, num]);

  // Compute landing stage exactly once per chapter, after stages load.
  // - Deep link `?stage=xxx` wins on first render.
  // - Otherwise use the persisted studio place mapped against the new stages.
  // Intra-chapter clicks bypass this entirely because selectedForChapterRef
  // is already set to `num` after the first computation.
  useEffect(() => {
    if (!stages) return;
    if (selectedForChapterRef.current === num) return;
    selectedForChapterRef.current = num;
    const urlStage = searchParams.get("stage") as StageKey | null;
    if (urlStage && STAGE_KEYS.includes(urlStage)) {
      setSelected(urlStage);
      return;
    }
    setSelected(stageForStudioPlace(studioPlaceRef.current, stages));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stages, num, id]);

  const reload = useCallback((opts?: { force?: boolean }) => {
    if (!chapterNumValid) {
      setError(`Invalid chapter number: ${n}`);
      return Promise.resolve();
    }
    const gen = ++reloadGenRef.current;
    const stamp = (fn: () => void) => {
      if (reloadGenRef.current === gen) fn();
    };
    if (opts?.force) {
      dirtyRef.current = false;
      draftDirtyRef.current = false;
      revisedDirtyRef.current = false;
      outlineDirtyRef.current = false;
      setDirty(false);
      setDraftDirty(false);
      setRevisedDirty(false);
      setOutlineDirty(false);
    }
    setError(null);
    let regPreview: RegeneratePreview | null = null;
    let outlinePrev: RegeneratePreview | null = null;
    let expandPrev: RegeneratePreview | null = null;
    let paragraphsPrev: RegeneratePreview | null = null;
    let redraftPrev: RedraftPreview | null = null;
    const applyStages = (s: ChapterStages) => {
      stamp(() => {
        setStages(s);
        const force = opts?.force ?? false;
        if (force || !dirtyRef.current) {
          setFinalText(s.final ?? "");
          setDirty(false);
          if (force) dirtyRef.current = false;
        }
        if (force || !draftDirtyRef.current) {
          setDraftText(s.draft ?? "");
          if (force) draftDirtyRef.current = false;
        }
        if (force || !revisedDirtyRef.current) {
          setRevisedText(s.revised ?? "");
          if (force) revisedDirtyRef.current = false;
        }
        if (force || !outlineDirtyRef.current) {
          setOutlineText(s.outline ?? "");
          if (force) outlineDirtyRef.current = false;
        }
      });
    };
    return Promise.all([
      api.chapter(id, num).then((m) => stamp(() => setMeta(m))).catch((e) => {
        void redirectOnChapterNotFound(e, id, navigate, toast, api.project).then((handled) => {
          if (!handled) stamp(() => setError(String(e)));
        });
      }),
      api.chapters(id).then((s) => stamp(() => setSiblings(s))).catch(() => stamp(() => setSiblings([]))),
      api.characters(id).then((c) => stamp(() => setCharacters(c))).catch(() => stamp(() => setCharacters([]))),
      api.storyBible(id).then((r) => stamp(() => setStoryBible(r.data))).catch(() => stamp(() => setStoryBible({}))),
      api.stages(id, num).then(applyStages).catch((e) => {
        void redirectOnChapterNotFound(e, id, navigate, toast, api.project).then((handled) => {
          if (!handled) stamp(() => setError(String(e)));
        });
      }),
      api.getRegeneratePreview(id, num).then((p) => {
        regPreview = p;
        stamp(() => {
          setRegeneratePreview(p);
          if (p) setPreviewText(p.text);
          else setPreviewText("");
        });
      }).catch(() => stamp(() => {
        regPreview = null;
        setRegeneratePreview(null);
        setPreviewText("");
      })),
      api.getOutlinePreview(id, num).then((p) => {
        outlinePrev = p;
        stamp(() => {
          setOutlinePreview(p);
          if (p) setOutlinePreviewText(p.text);
          else setOutlinePreviewText("");
        });
      }).catch(() => stamp(() => {
        outlinePrev = null;
        setOutlinePreview(null);
        setOutlinePreviewText("");
      })),
      api.getExpandPreview(id, num).then((p) => {
        expandPrev = p;
        stamp(() => {
          setExpandPreview(p);
          if (p) setExpandPreviewText(p.text);
          else setExpandPreviewText("");
        });
      }).catch(() => stamp(() => {
        expandPrev = null;
        setExpandPreview(null);
        setExpandPreviewText("");
      })),
      api.getParagraphsPreview(id, num).then((p) => {
        paragraphsPrev = p;
        stamp(() => {
          setParagraphsPreview(p);
          if (p) setParagraphsPreviewText(p.text);
          else setParagraphsPreviewText("");
        });
      }).catch(() => stamp(() => {
        paragraphsPrev = null;
        setParagraphsPreview(null);
        setParagraphsPreviewText("");
      })),
      api.getAlignmentPreview(id, num).then((p) => {
        stamp(() => {
          setAlignmentPreview(p);
          if (p) {
            setAlignmentTextA(p.text_a);
            setAlignmentTextB(p.text_b);
          } else {
            setAlignmentTextA("");
            setAlignmentTextB("");
          }
        });
      }).catch(() => stamp(() => {
        setAlignmentPreview(null);
        setAlignmentTextA("");
        setAlignmentTextB("");
      })),
      api.getRedraftPreview(id, num).then((p) => {
        redraftPrev = p;
        stamp(() => {
          setRedraftPreview(p);
          if (p) setRedraftPreviewText(p.text);
          else setRedraftPreviewText("");
        });
      }).catch(() => stamp(() => {
        redraftPrev = null;
        setRedraftPreview(null);
        setRedraftPreviewText("");
      })),
      api.getChapterBrief(id, num).then((b) => {
        stamp(() => setHasSavedBrief(b ? briefHasContent(briefFromSummary(b)) : false));
      }).catch(() => stamp(() => setHasSavedBrief(false))),
      api.comments(id, num).then((c) => stamp(() => setComments(c))).catch(() => stamp(() => setComments([]))),
    ]).then(async () => {
      if (reloadGenRef.current !== gen) return;
      let beats = null;
      try {
        beats = await api.getChapterBeatCandidatesPreview(id, num);
      } catch {
        beats = null;
      }
      stamp(() => {
        setChapterPreviewPending(
          id,
          num,
          Boolean(regPreview || outlinePrev || expandPrev || paragraphsPrev || redraftPrev || beats),
        );
      });
    });
  }, [id, num, n, chapterNumValid, navigate, toast]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    recordChapterVisit(id, num);
  }, [id, num]);

  useEffect(() => {
    if (regeneratePreview || outlinePreview || expandPreview || paragraphsPreview || redraftPreview) {
      setChapterPreviewPending(id, num, true);
    }
  }, [id, num, regeneratePreview, outlinePreview, expandPreview, paragraphsPreview, redraftPreview]);

  const previewStageStars = useMemo(
    () => previewPendingStages(regeneratePreview, outlinePreview, expandPreview, paragraphsPreview, redraftPreview),
    [regeneratePreview, outlinePreview, expandPreview, paragraphsPreview, redraftPreview],
  );

  useEffect(() => {
    if (!titleFocused.current) {
      setTitleDraft(meta?.title ?? "");
    }
  }, [meta?.title, num]);

  async function saveChapterTitle(opts?: { silent?: boolean }) {
    if (meta?.number !== num) return;
    const trimmed = titleDraftRef.current.trim();
    if (trimmed === (meta?.title ?? "").trim()) return;
    setTitleSaving(true);
    try {
      const updated = await api.updateChapter(id, num, { title: trimmed });
      setMeta((m) => (m ? { ...m, title: updated.title } : m));
      setSiblings((list) =>
        list.map((c) => (c.number === num ? { ...c, title: updated.title } : c)),
      );
      setTitleDraft(updated.title);
      setTitleLastSaved(formatSavedAt());
      if (!opts?.silent) {
        toast(trimmed ? "Chapter title saved" : "Chapter title cleared", "success");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      setTitleDraft(meta?.title ?? "");
    } finally {
      setTitleSaving(false);
    }
  }
  saveChapterTitleRef.current = saveChapterTitle;

  useEffect(() => {
    if (meta?.number !== num) return;
    const trimmed = titleDraft.trim();
    if (trimmed === (meta?.title ?? "").trim()) return;
    const t = setTimeout(() => {
      if (busyRef.current == null) void saveChapterTitleRef.current({ silent: true });
    }, 1500);
    return () => clearTimeout(t);
  }, [titleDraft, meta?.title, meta?.number, num]);

  const handlePhaseDone = useCallback(() => {
    reload();
    if (phaseAfterDone.current) {
      selectStage(phaseAfterDone.current);
      phaseAfterDone.current = null;
    }
    if (pendingOutlineAfterReviseRef.current) {
      pendingOutlineAfterReviseRef.current = false;
      void startGenerateOutlineRef.current("notes");
    }
    if (lastPipelinePhaseRef.current === "validate" && stages) {
      const source = regenerateSource(stages, selected);
      void api.suggestMentions(id, num, { source, use_llm: false }).catch(() => {});
      setMentionPanelOpen(true);
    }
    lastPipelinePhaseRef.current = null;
  }, [reload, stages, selected, id, num]);

  const { run, runningStage, isRunning } = useRunPhase(id, handlePhaseDone);
  const { watchBackgroundJob, isProjectJobRunning } = useBackgroundJob();
  const chapterScope = String(num);

  function isMining(kind: MineKind) {
    return isProjectJobRunning(MINE_JOB_KIND[kind], id, chapterScope);
  }

  function runChapter(fn: ChapterFunction, phase: string, params: Record<string, unknown> = {}) {
    recordChapterFunction(id, num, fn);
    lastPipelinePhaseRef.current = phase;
    void run(phase, params);
  }

  function runRevise() {
    void (async () => {
      recordChapterFunction(id, num, "edit");
      if (revisedDirtyRef.current) await saveRevised();
      else if (draftDirtyRef.current) await saveDraft();
      pendingOutlineAfterReviseRef.current =
        applyNotesToOutline && Boolean(regenInstructions.trim());
      phaseAfterDone.current = "revised";
      void run("edit", {
        number: num,
        instructions: regenInstructions.trim(),
      });
    })();
  }

  async function copyRevisedToDraft() {
    if (!stages?.revised && !revisedText.trim()) {
      toast("No revised text to copy", "error");
      return;
    }
    if (revisedDirtyRef.current) await saveRevised();
    setBusy("saving");
    try {
      const text = revisedTextRef.current;
      const r = await api.saveDraft(id, num, text);
      setDraftText(r.draft);
      setDraftDirty(false);
      setDraftLastSaved(formatSavedAt());
      setStages((s) => (s ? { ...s, draft: r.draft } : s));
      toast("Copied Revised → Draft (optional — Revise already uses Revised)", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  // Warn on tab close / refresh with unsaved edits
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current || draftDirtyRef.current || revisedDirtyRef.current || outlineDirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      if (dirtyRef.current) api.saveFinal(id, num, textRef.current).catch(() => {});
      if (draftDirtyRef.current) api.saveDraft(id, num, draftTextRef.current).catch(() => {});
      if (revisedDirtyRef.current) api.saveRevised(id, num, revisedTextRef.current).catch(() => {});
      if (outlineDirtyRef.current) api.saveOutline(id, num, outlineTextRef.current).catch(() => {});
      const trimmedTitle = titleDraftRef.current.trim();
      if (trimmedTitle !== (meta?.title ?? "").trim()) {
        api.updateChapter(id, num, { title: trimmedTitle }).catch(() => {});
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, num]);

  // Debounced autosave — final, draft, and revised
  const saveRef = useRef<() => void>(() => {});
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      if (dirtyRef.current && busyRef.current == null) saveRef.current();
    }, 1500);
    return () => clearTimeout(t);
  }, [finalText, dirty]);

  useEffect(() => {
    if (!draftDirty) return;
    const t = setTimeout(() => {
      if (draftDirtyRef.current && busyRef.current == null) {
        void saveDraftRef.current({ silent: true });
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [draftText, draftDirty]);

  useEffect(() => {
    if (!revisedDirty) return;
    const t = setTimeout(() => {
      if (revisedDirtyRef.current && busyRef.current == null) {
        void saveRevisedRef.current({ silent: true });
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [revisedText, revisedDirty]);

  useEffect(() => {
    if (!outlineDirty || meta?.number !== num) return;
    const t = setTimeout(() => {
      if (outlineDirtyRef.current && busyRef.current == null) {
        void saveOutlineRef.current({ silent: true });
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [outlineText, outlineDirty, meta?.number, num]);

  async function saveOutline(opts?: { silent?: boolean }) {
    if (meta?.number !== num) return;
    setBusy("saving");
    try {
      const r = await api.saveOutline(id, num, outlineTextRef.current);
      setStages((s) => (s ? { ...s, outline: r.outline } : s));
      setOutlineDirty(false);
      outlineDirtyRef.current = false;
      setOutlineLastSaved(formatSavedAt());
      if (!opts?.silent) toast("Outline saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveOutlineRef.current = saveOutline;

  // [ / ] jump between chapters (ignored while typing in an editor/field)
  useEffect(() => {
    const isTyping = () => {
      const el = document.activeElement as HTMLElement | null;
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
    };
    const onKey = (e: KeyboardEvent) => {
      if (isTyping() || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key !== "[" && e.key !== "]") return;
      const ordered = [...siblings].sort((a, b) => a.number - b.number);
      const idx = ordered.findIndex((c) => c.number === num);
      if (e.key === "[" && idx > 0) {
        writeStudioPlace(id, studioPlaceFromSelection(briefExpanded, selected));
        navigate(`/projects/${id}/chapters/${ordered[idx - 1].number}`);
      }
      if (e.key === "]" && idx >= 0 && idx < ordered.length - 1) {
        writeStudioPlace(id, studioPlaceFromSelection(briefExpanded, selected));
        navigate(`/projects/${id}/chapters/${ordered[idx + 1].number}`);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [siblings, num, id, navigate, briefExpanded, selected]);

  const mentionTargets = useMemo(
    () => buildMentionTargets(characters, storyBible),
    [characters, storyBible],
  );

  const openMentionReview = useCallback((characterId?: string | null) => {
    setMentionFocusCharId(characterId ?? null);
    setMentionPanelOpen(true);
  }, []);

  const onCharacterMentionAction = useCallback(
    (_parsed: unknown, resolved: MentionTarget) => {
      if (resolved.id) openMentionReview(resolved.id);
    },
    [openMentionReview],
  );

  const mentionSource = stages ? regenerateSource(stages, selected) : "revised";

  const reloadComments = useCallback(() => {
    api.comments(id, num).then(setComments).catch(() => setComments([]));
  }, [id, num]);

  const createAnnotation = useCallback(async (payload: AddCommentPayload) => {
    await api.addComment(id, num, payload);
    reloadComments();
    setInspectorTab("comments");
    setShowInspector(true);
    toast("Annotation added", "success");
  }, [id, num, reloadComments, setShowInspector, toast]);

  const stageAnnotations = comments;

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          {isNotFoundError(error) ? (
            <>
              <p>Chapter or project not found.</p>
              <Link to={`/projects/${id}`} className="mt-3 mr-4 inline-block font-semibold text-amber-deep hover:underline">
                ← Project dashboard
              </Link>
              <Link to="/" className="mt-3 inline-block font-semibold text-amber-deep hover:underline">
                Library
              </Link>
            </>
          ) : (
            <>Failed to load: {error}</>
          )}
        </div>
      </div>
    );
  if (!stages)
    return (
      <div className="mx-auto max-w-[760px] px-10 py-12">
        <div className="h-3.5 w-40 animate-pulse rounded bg-paper-card" />
        <div className="mt-4 h-8 w-1/2 animate-pulse rounded bg-paper-card" />
        <div className="mt-6 h-16 w-full animate-pulse rounded-lg bg-paper-card" />
        <div className="mt-8 h-[50vh] w-full animate-pulse rounded-md bg-paper-card" />
      </div>
    );

  async function saveDraft(opts?: { silent?: boolean }) {
    setBusy("saving");
    try {
      const r = await api.saveDraft(id, num, draftTextRef.current);
      setStages((s) => (s ? { ...s, draft: r.draft, status: "drafted" } : s));
      setDraftDirty(false);
      setDraftLastSaved(formatSavedAt());
      if (!opts?.silent) {
        toast("Draft saved", "success");
        reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveDraftRef.current = saveDraft;

  async function saveRevised(opts?: { silent?: boolean }) {
    setBusy("saving");
    try {
      const r = await api.saveRevised(id, num, revisedTextRef.current);
      setStages((s) => (s ? { ...s, revised: r.revised, status: "edited" } : s));
      setRevisedDirty(false);
      setRevisedLastSaved(formatSavedAt());
      if (!opts?.silent) {
        toast("Revision saved", "success");
        reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveRevisedRef.current = saveRevised;

  async function prepareForRenumber() {
    setBusy("saving");
    try {
      if (dirtyRef.current) {
        const r = await api.saveFinal(id, num, textRef.current);
        setStages((s) => (s ? { ...s, final: r.final } : s));
        setDirty(false);
        dirtyRef.current = false;
        setLastSaved(formatSavedAt());
      }
      if (draftDirtyRef.current) {
        const r = await api.saveDraft(id, num, draftTextRef.current);
        setStages((s) => (s ? { ...s, draft: r.draft, status: "drafted" } : s));
        setDraftDirty(false);
        draftDirtyRef.current = false;
        setDraftLastSaved(formatSavedAt());
      }
      if (revisedDirtyRef.current) {
        const r = await api.saveRevised(id, num, revisedTextRef.current);
        setStages((s) => (s ? { ...s, revised: r.revised, status: "edited" } : s));
        setRevisedDirty(false);
        revisedDirtyRef.current = false;
        setRevisedLastSaved(formatSavedAt());
      }
      if (outlineDirtyRef.current) {
        const r = await api.saveOutline(id, num, outlineTextRef.current);
        setStages((s) => (s ? { ...s, outline: r.outline } : s));
        setOutlineDirty(false);
        outlineDirtyRef.current = false;
        setOutlineLastSaved(formatSavedAt());
      }
    } finally {
      setBusy(null);
    }
  }

  async function insertChapterAt(number: number) {
    try {
      await prepareForRenumber();
      setBusy("saving");
      const result = await api.insertChapterAt(id, number);
      remapChapterPreviewPending(id, result.mapping);
      remapChapterWorkflowMarkers(id, result.mapping);
      setSiblings(result.chapters);
      toast(`Inserted chapter ${result.inserted_number}`, "success");
      navigate(`/projects/${id}/chapters/${result.inserted_number ?? number}`, { replace: false });
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function duplicateThisChapter() {
    const ok = await confirm({
      title: "Duplicate this chapter?",
      message: "Create a copy immediately after this chapter and shift later chapters up. You will still need to split the prose and regenerate/review the new chapter brief.",
      confirmLabel: "Duplicate chapter",
    });
    if (!ok) return;
    try {
      await prepareForRenumber();
      setBusy("saving");
      const result = await api.duplicateChapter(id, num);
      remapChapterPreviewPending(id, result.mapping);
      remapChapterWorkflowMarkers(id, result.mapping);
      setSiblings(result.chapters);
      toast(`Duplicated chapter ${num}`, "success");
      navigate(`/projects/${id}/chapters/${result.inserted_number ?? num + 1}`, { replace: false });
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function mergeNextChapter() {
    const next = siblings
      .map((chapter) => chapter.number)
      .filter((chapterNumber) => chapterNumber > num)
      .sort((a, b) => a - b)[0];
    if (next == null) {
      toast("No next chapter to merge", "error");
      return;
    }
    if (next !== num + 1) {
      toast("Remove chapter gaps before merging", "error");
      return;
    }
    const ok = await confirm({
      title: `Merge chapter ${next} into chapter ${num}?`,
      message:
        "This appends the next chapter's manuscript stages to this chapter and removes the next chapter. "
        + "All saved version snapshots for both chapters will be deleted — restoring one after merge could overwrite the combined text with only one source. "
        + "Numbering gaps are left alone; consider using Remove Gaps from the story dashboard when you are ready. "
        + "You will need to regenerate/review the chapter brief and start/end state.",
      confirmLabel: "Merge next chapter",
      danger: true,
    });
    if (!ok) return;
    try {
      await prepareForRenumber();
      setBusy("saving");
      const result = await api.mergeChapter(id, num, next);
      remapChapterPreviewPending(id, result.mapping);
      remapChapterWorkflowMarkers(id, result.mapping);
      setContentRevision((v) => v + 1);
      await reload({ force: true });
      const snapNote = result.removed_snapshot_count
        ? ` Removed ${result.removed_snapshot_count} version snapshot${result.removed_snapshot_count === 1 ? "" : "s"}.`
        : "";
      toast(`Merged chapter ${next} into chapter ${num}.${snapNote} Consider Remove Gaps when ready.`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  function toastJobFailure(e: unknown) {
    if (isJobCancelledError(e)) {
      toast("Cancelled", "success");
      return;
    }
    toast(e instanceof Error ? e.message : String(e), "error");
  }

  async function startRegenerate() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to regenerate from", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setRegenerating(true);
    recordChapterFunction(id, num, "regenerate");
    try {
      const job = await api.regenerateChapter(id, num, {
        source,
        instructions: regenInstructions.trim(),
      });
      toast("Regenerating chapter…", "success");
      await pollJob(job.job_id);
      const preview = await api.getRegeneratePreview(id, num);
      if (!preview) throw new Error("Regeneration finished but no preview was saved");
      setRegeneratePreview(preview);
      setPreviewText(preview.text);
      setChapterPreviewPending(id, num, true);
      toast("Regeneration ready — review and keep or discard", "success");
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setRegenerating(false);
    }
  }

  async function startExpandPlaceholders() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to expand in", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setExpanding(true);
    recordChapterFunction(id, num, "expand");
    try {
      const job = await api.expandPlaceholders(id, num, {
        source,
        instructions: regenInstructions.trim(),
      });
      toast("Expanding placeholders…", "success");
      await pollJob(job.job_id);
      const preview = await api.getExpandPreview(id, num);
      if (!preview) throw new Error("Expansion finished but no preview was saved");
      setExpandPreview(preview);
      setExpandPreviewText(preview.text);
      setChapterPreviewPending(id, num, true);
      toast("Expansion ready — review and keep or discard", "success");
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setExpanding(false);
    }
  }

  async function applyExpandPreview() {
    if (!expandPreview) return;
    try {
      const r = await api.applyExpandPreview(id, num, {
        text: expandPreviewText,
        target: expandPreview.source,
      });
      setExpandPreview(null);
      setExpandPreviewText("");
      setChapterPreviewPending(id, num, false);
      toast(`Kept expansion → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      if (r.target === "draft") selectStage("draft");
      else if (r.target === "final") selectStage("final");
      else selectStage("revised");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardExpandPreview() {
    const ok = await confirm({
      title: "Discard expansion",
      message: "Discard this expanded preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardExpandPreview(id, num);
      setExpandPreview(null);
      setExpandPreviewText("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded expansion", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function startFormatParagraphs() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to format", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setFormattingParagraphs(true);
    recordChapterFunction(id, num, "format-paragraphs");
    try {
      const job = await api.formatParagraphs(id, num, { source });
      toast("Formatting paragraphs…", "success");
      await pollJob(job.job_id);
      const preview = await api.getParagraphsPreview(id, num);
      if (!preview) throw new Error("Formatting finished but no preview was saved");
      setParagraphsPreview(preview);
      setParagraphsPreviewText(preview.text);
      setChapterPreviewPending(id, num, true);
      toast("Paragraph preview ready — review and keep or discard", "success");
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setFormattingParagraphs(false);
    }
  }

  async function applyParagraphsPreview() {
    if (!paragraphsPreview) return;
    try {
      const r = await api.applyParagraphsPreview(id, num, {
        text: paragraphsPreviewText,
        target: paragraphsPreview.source,
      });
      setParagraphsPreview(null);
      setParagraphsPreviewText("");
      setChapterPreviewPending(id, num, false);
      toast(`Kept formatting → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      if (r.target === "draft") selectStage("draft");
      else if (r.target === "final") selectStage("final");
      else selectStage("revised");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardParagraphsPreview() {
    const ok = await confirm({
      title: "Discard paragraph preview",
      message: "Discard this formatted preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardParagraphsPreview(id, num);
      setParagraphsPreview(null);
      setParagraphsPreviewText("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded paragraph preview", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function startAlignBoundary() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to align", "error");
      return;
    }
    const hasNext = siblings.some((c) => c.number === num + 1);
    if (!hasNext) {
      toast("No next chapter to align with", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setAligningBoundary(true);
    recordChapterFunction(id, num, "align-boundary");
    try {
      const job = await api.alignBoundary(id, num, { source });
      toast("Aligning chapter boundary…", "success");
      await pollJob(job.job_id);
      const preview = await api.getAlignmentPreview(id, num);
      if (!preview) throw new Error("Alignment finished but no preview was saved");
      setAlignmentPreview(preview);
      setAlignmentTextA(preview.text_a);
      setAlignmentTextB(preview.text_b);
      setChapterPreviewPending(id, num, true);
      toast(
        preview.adjusted
          ? "Boundary preview ready — review both chapters, then keep or discard"
          : "Boundary already aligned — review and keep or discard",
        "success",
      );
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setAligningBoundary(false);
    }
  }

  async function applyAlignmentPreview() {
    if (!alignmentPreview) return;
    try {
      const r = await api.applyAlignmentPreview(id, num, {
        text_a: alignmentTextA,
        text_b: alignmentTextB,
      });
      setAlignmentPreview(null);
      setAlignmentTextA("");
      setAlignmentTextB("");
      setChapterPreviewPending(id, num, false);
      toast(
        `Kept alignment → chapters ${r.chapter_a} & ${r.chapter_b} `
        + `(${r.word_count_a.toLocaleString()} + ${r.word_count_b.toLocaleString()} words)`,
        "success",
      );
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardAlignmentPreview() {
    const ok = await confirm({
      title: "Discard alignment preview",
      message: "Discard this boundary alignment preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardAlignmentPreview(id, num);
      setAlignmentPreview(null);
      setAlignmentTextA("");
      setAlignmentTextB("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded alignment preview", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function applyRegenerate() {
    if (!regeneratePreview) return;
    try {
      const r = await api.applyRegenerate(id, num, {
        text: previewText,
        target: regeneratePreview.source,
      });
      setRegeneratePreview(null);
      setPreviewText("");
      setChapterPreviewPending(id, num, false);
      toast(`Kept regeneration → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      if (r.target === "draft") selectStage("draft");
      else if (r.target === "final") selectStage("final");
      else selectStage("revised");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardRegenerate() {
    const ok = await confirm({
      title: "Discard regeneration",
      message: "Discard this regenerated draft? The preview will be deleted.",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardRegenerate(id, num);
      setRegeneratePreview(null);
      setPreviewText("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded regeneration", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function startRedraftFromBrief() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to redraft from", "error");
      return;
    }
    if (!hasSavedBrief) {
      toast("Save a chapter brief with content first", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected) as "final" | "draft" | "revised";
    setRedrafting(true);
    recordChapterFunction(id, num, "redraft-from-brief");
    try {
      const instructions = regenInstructions.trim();
      const job = await api.redraftFromBrief(id, num, {
        source,
        mode: redraftMode,
        ...(instructions ? { instructions } : {}),
      });
      toast("Redrafting from brief…", "success");
      await pollJob(job.job_id);
      const preview = await api.getRedraftPreview(id, num);
      if (!preview) throw new Error("Redraft finished but no preview was saved");
      setRedraftPreview(preview);
      setRedraftPreviewText(preview.text);
      setChapterPreviewPending(id, num, true);
      toast("Redraft ready — review and keep or discard", "success");
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setRedrafting(false);
    }
  }

  async function applyRedraftPreview() {
    if (!redraftPreview) return;
    try {
      const r = await api.applyRedraftPreview(id, num, { text: redraftPreviewText });
      setRedraftPreview(null);
      setRedraftPreviewText("");
      setChapterPreviewPending(id, num, false);
      toast(`Kept redraft → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      selectStage("draft");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardRedraftPreview() {
    const ok = await confirm({
      title: "Discard redraft",
      message: "Discard this redrafted preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardRedraftPreview(id, num);
      setRedraftPreview(null);
      setRedraftPreviewText("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded redraft", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function startSplitChapter() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to split — add draft or final prose first", "error");
      return;
    }
    const source = regenerateSource(stages, selected);
    const ok = await confirm({
      title: "Split into parts",
      message:
        "Split this chapter into smaller parts (1a, 1b, 1c…) at ~6,000 words each? "
        + "Later parts are inserted immediately after this chapter. This cannot be undone automatically.",
      confirmLabel: "Split chapter",
      danger: true,
    });
    if (!ok) return;
    setSplittingChapter(true);
    try {
      const result = await api.splitChapter(id, num, { source });
      if (result.parts.length <= 1) {
        toast("Chapter is already within the split size — no parts created", "success");
        return;
      }
      const labels = result.parts.map((p) => p.display_label).join(", ");
      toast(
        `Split into ${result.parts.length} parts (${labels})${
          result.recovered_from_backup ? " — restored from backup" : ""
        }`,
        "success",
      );
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setSplittingChapter(false);
    }
  }

  async function startSplitAtTargetAndAlign() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to split — add draft or final prose first", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    const ok = await confirm({
      title: "Split at target length & align",
      message:
        "Split this chapter at the brief / project target word count, insert parts immediately after, "
        + "then automatically align each new boundary with AI? "
        + "Run AI Paragraphs first if prose is still dense. This cannot be undone automatically.",
      confirmLabel: "Split & align",
      danger: true,
    });
    if (!ok) return;
    setSplittingChapter(true);
    try {
      const result = await api.splitChapter(id, num, {
        source,
        use_target_length: true,
        align_boundaries: true,
      });
      if (result.parts.length <= 1) {
        toast("Chapter is already within target length — no parts created", "success");
        return;
      }
      const labels = result.parts.map((p) => p.display_label).join(", ");
      const aligned = result.alignments_applied ?? 0;
      toast(
        `Split into ${result.parts.length} parts (${labels}) — ${aligned} boundar${aligned === 1 ? "y" : "ies"} aligned${
          result.recovered_from_backup ? " — restored from backup" : ""
        }`,
        "success",
      );
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setSplittingChapter(false);
    }
  }

  async function startGenerateOutline(mode: "text" | "notes" = "text") {
    if (mode === "text" && (!stages || !hasRegenerateSource(stages))) {
      toast("No chapter text to outline — add draft or final prose first", "error");
      return;
    }
    if (mode === "notes" && !combinedOutlineInstructions()) {
      toast("Enter outline notes or revision notes (with “apply to outline” checked)", "error");
      return;
    }
    const hasOutline = stages?.outline != null;
    const ok = await confirm({
      title: hasOutline ? "Regenerate outline?" : "Generate outline?",
      message: mode === "notes"
        ? "Generate a new beat-sheet outline from your notes? You will review the result before it replaces the saved outline."
        : "Generate a new beat-sheet outline from chapter prose? You will review the result before it replaces the saved outline.",
      confirmLabel: hasOutline ? "Regenerate outline" : "Generate outline",
    });
    if (!ok) return;
    if (mode === "text") {
      if (selected === "draft" && draftDirty) await saveDraft();
      if (selected === "revised" && revisedDirty) await saveRevised();
      if (selected === "final" && dirty) await save();
    }
    const source = mode === "notes" ? "notes" : regenerateSource(stages!, selected);
    setOutlineGenerating(true);
    recordChapterFunction(id, num, mode === "notes" ? "outline-notes" : "outline-text");
    try {
      const job = await api.generateOutline(id, num, {
        source,
        instructions: combinedOutlineInstructions(),
      });
      toast(
        mode === "notes"
          ? "Generating outline from your notes…"
          : "Generating outline from chapter text…",
        "success",
      );
      await pollJob(job.job_id);
      const preview = await api.getOutlinePreview(id, num);
      if (!preview) throw new Error("Outline generation finished but no preview was saved");
      setOutlinePreview(preview);
      setOutlinePreviewText(preview.text);
      setChapterPreviewPending(id, num, true);
      toast("Outline ready — review and keep or discard", "success");
      selectStage("outline");
    } catch (e) {
      toastJobFailure(e);
    } finally {
      setOutlineGenerating(false);
    }
  }
  const chapterLabel = meta?.display_label?.trim() || String(num);
  const hasNextChapter = siblings.some((c) => c.number === num + 1);
  const longChapterText =
    stages != null &&
    hasRegenerateSource(stages) &&
    (meta?.word_count ?? 0) > 6000;
  startGenerateOutlineRef.current = startGenerateOutline;

  async function applyOutlinePreview() {
    if (!outlinePreview) return;
    try {
      const r = await api.applyOutlinePreview(id, num, { text: outlinePreviewText });
      setOutlinePreview(null);
      setOutlinePreviewText("");
      setChapterPreviewPending(id, num, false);
      toast(`Outline saved (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      selectStage("outline");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardOutlinePreview() {
    const ok = await confirm({
      title: "Discard outline",
      message: "Discard this generated outline preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardOutlinePreview(id, num);
      setOutlinePreview(null);
      setOutlinePreviewText("");
      void syncChapterPreviewPendingFromApi(id, num);
      toast("Discarded outline preview", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function mineFromChapter(kind: MineKind) {
    if (isMining(kind)) return;
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to mine — add draft, revised, or final prose first", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    const mineFn: ChapterFunction =
      kind === "plots" ? "mine-plots" : kind === "characters" ? "mine-characters" : "mine-bible";
    recordChapterFunction(id, num, mineFn);
    try {
      const job = await api.mineChapter(id, num, kind, source);
      toast(`Mining ${MINE_LABELS[kind].toLowerCase()} from chapter text…`, "success");
      watchBackgroundJob(job.job_id, {
        label: MINE_LABELS[kind],
        kind: MINE_JOB_KIND[kind],
        projectId: id,
        scope: chapterScope,
        successMessage: `${MINE_LABELS[kind]} ready — review before applying`,
        onSuccess: () => {
          setMinePreviewPending(id, kind, num, true);
          setMinePreviewKind(kind);
          setMinePreviewOpen(true);
        },
      });
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function deleteThisChapter() {
    try {
      await api.deleteChapter(id, num);
      toast(`Deleted chapter ${num}`, "success");
      navigate(`/projects/${id}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function confirmDeleteChapter() {
    const ok = await confirm({
      title: "Delete chapter",
      message: `Delete chapter ${num}${meta?.title ? `: "${meta.title}"` : ""}? All files and notes for this chapter will be removed.`,
      confirmLabel: "Delete chapter",
      danger: true,
    });
    if (!ok) return;
    await deleteThisChapter();
  }

  async function promote() {
    setBusy("promoting");
    try {
      const r = await api.promoteFinal(id, num);
      setFinalText(r.final);
      setDirty(false);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      selectStage("final");
      api.chapters(id).then(setSiblings).catch(() => {});
      toast("Promoted to Final", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function reopenForRevision() {
    const ok = await confirm({
      title: "Reopen for revision?",
      message:
        "This removes Final, clears validation and approval, and copies Final text into Draft "
        + "and Revised (when a Final exists) so you can run Revise again.",
      confirmLabel: "Reopen",
      danger: true,
    });
    if (!ok) return;
    setBusy("reopening");
    try {
      const r = await api.unfinalizeChapter(id, num);
      setStages({
        number: r.number,
        status: r.status,
        outline: r.outline,
        draft: r.draft,
        revised: r.revised,
        final: r.final,
        continuity: null,
      });
      setMeta((m) => (m ? { ...m, status: r.status, word_count: r.word_count } : m));
      setFinalText("");
      setDraftText(r.draft ?? "");
      setRevisedText(r.revised ?? "");
      setOutlineText(r.outline ?? "");
      setDirty(false);
      setDraftDirty(false);
      setRevisedDirty(false);
      setOutlineDirty(false);
      selectStage("revised");
      api.chapters(id).then(setSiblings).catch(() => {});
      toast("Chapter reopened for revision", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy("saving");
    try {
      const r = await api.saveFinal(id, num, textRef.current);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      setDirty(false);
      setLastSaved(formatSavedAt());
      api.chapters(id).then(setSiblings).catch(() => {});
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveRef.current = save;

  async function flush() {
    if (dirtyRef.current && busyRef.current == null) await save();
  }

  const canPromote = stages.revised != null || stages.draft != null;
  const promoteFrom = stages.revised != null ? "Revised" : "Draft";
  const canReopen = stages.status === "complete";
  const reviseUses = stages.revised != null ? "Revised" : stages.draft != null ? "Draft" : null;
  const stageEditorText =
    selected === "draft" ? draftText
      : selected === "revised" ? revisedText
        : selected === "final" ? finalText
          : "";
  const expandMarkerCount = countExpandMarkers(stageEditorText);
  const titleDirty = titleDraft.trim() !== (meta?.title ?? "").trim();
  const stageSave = (() => {
    switch (selected) {
      case "outline":
        return { dirty: outlineDirty, lastSaved: outlineLastSaved };
      case "draft":
        return { dirty: draftDirty, lastSaved: draftLastSaved };
      case "revised":
        return { dirty: revisedDirty, lastSaved: revisedLastSaved };
      case "final":
        return { dirty, lastSaved };
      default:
        return { dirty: false, lastSaved: null as string | null };
    }
  })();
  const bannerSaving = titleSaving || busy === "saving";
  const bannerDirty = titleDirty || stageSave.dirty;
  const bannerLastSaved = stageSave.lastSaved ?? titleLastSaved;

  return (
    <div ref={studioRef} className="flex h-full min-h-0 overflow-hidden">
      {/* Binder */}
      {showBinder && !focus && (
          <nav
            className="flex min-h-0 shrink-0 flex-col overflow-hidden border-r border-paper-line bg-paper-card/40"
            style={{ width: BINDER_WIDTH }}
          >
        <div className="shrink-0 px-3 pb-3 pt-6">
          <Link
            to={`/projects/${id}`}
            className="block truncate text-[12.5px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
          >
            ← {id.replace(/-/g, " ")}
          </Link>
        </div>
        <p className="shrink-0 px-3 pb-2 text-[10.5px] font-bold uppercase tracking-[0.16em] text-paper-muted">
          Binder
        </p>
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-1.5 pb-4">
          {siblings.map((c) => {
            const isLastAccessed = lastAccessedChapter === c.number;
            const cPreview = hasChapterPreviewPending(id, c.number);
            return (
            <Link
              key={c.number}
              to={`/projects/${id}/chapters/${c.number}`}
              onClick={() => {
                studioPlaceRef.current = studioPlaceFromSelection(briefExpanded, selected);
                writeStudioPlace(id, studioPlaceRef.current);
              }}
              className={`flex items-center gap-1 rounded-md px-1.5 py-1.5 text-[13px] transition-colors ${
                c.number === num
                  ? "bg-amber/15 font-medium text-ink-text"
                  : "text-ink-muted hover:bg-ink/5"
              }`}
            >
              <ChapterPipelineDot step={pipelineStepFromSummary(c)} size="sm" />
              <span
                className={`nums shrink-0 font-mono text-[11px] ${
                  isLastAccessed ? "text-amber-deep" : "text-paper-muted"
                }`}
                title={isLastAccessed ? "Last chapter you worked in" : undefined}
              >
                {c.number}
              </span>
              <span
                className={`min-w-0 truncate ${isLastAccessed ? "text-amber-deep" : ""}`}
                title={isLastAccessed ? "Last chapter you worked in" : undefined}
              >
                {c.title || "Untitled"}
              </span>
              {cPreview && <PendingAiStar title="AI preview ready to review" />}
            </Link>
          );})}
        </div>
          </nav>
      )}

      {/* Pipeline editor — center column; width drives fluid manuscript scale */}
      <div
        ref={centerRef}
        className={`flex min-h-0 min-w-0 flex-1 flex-col ${
          focus || briefExpanded ? "overflow-hidden" : "overflow-x-auto overflow-y-auto"
        }`}
        style={{ minWidth: fluidLayout.columnMaxPx + CENTER_STUDIO_GUTTER_PX }}
      >
        {!focus && (
        <div
          className={`border-b border-paper-line bg-paper-card/30 px-8 ${
            briefExpanded ? "flex min-h-0 flex-1 flex-col overflow-hidden py-3" : "py-4"
          }`}
        >
          <div
            className={briefExpanded ? "flex min-h-0 flex-1 flex-col" : undefined}
            style={studioColumnStyle}
          >
            <div
              className={`mb-3 grid min-h-7 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-3 ${briefExpanded ? "shrink-0" : ""}`}
            >
              <div className="flex min-w-0 items-center self-center overflow-hidden">
                <Breadcrumbs
                  className="mb-0 min-w-0"
                  items={[
                  { label: "Library", to: "/" },
                  { label: id.replace(/-/g, " "), to: `/projects/${id}` },
                ]}
                titleEdit={{
                  value: titleDraft,
                  onChange: setTitleDraft,
                  onFocus: () => { titleFocused.current = true; },
                  onBlur: () => {
                    titleFocused.current = false;
                    void saveChapterTitle({ silent: true });
                  },
                  onKeyDown: (e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      (e.target as HTMLInputElement).blur();
                    }
                  },
                  placeholder: meta?.title?.trim() ? undefined : `Chapter ${chapterLabel}`,
                  disabled: titleSaving,
                  trailing: hasPreviewPending ? (
                    <PendingAiStar title="AI preview ready to review" />
                  ) : undefined,
                }}
                />
              </div>
              <SaveStatus
                dirty={bannerDirty}
                saving={bannerSaving}
                lastSaved={bannerLastSaved}
                className="self-center"
              />
              <div className="flex items-center justify-end self-center">
                <StoryPanelToggles />
              </div>
            </div>

            {!briefExpanded && (
            <>
            <div className="mb-2.5">
              <PipelineFlow
                stages={stages}
                selected={selected}
                onSelect={selectStage}
                pendingStages={previewStageStars}
              />
            </div>
            </>
            )}

            <ChapterBriefPanel
              projectId={id}
              chapterNumber={num}
              characters={characters}
              refreshToken={contentRevision}
              onBriefPresenceChange={setHasSavedBrief}
              onCollapsedChange={(collapsed) => setBriefPanelExpanded(!collapsed)}
              expandedFocus={briefExpanded}
              embedded
              operationsSection={
                <ChapterOperationsSection
                  busy={busy != null}
                  splitAtTargetVisible={hasRegenerateSource(stages)}
                  splitAtTargetRunning={splittingChapter}
                  splitAtTargetDisabled={
                    isRunning
                    || splittingChapter
                    || outlineGenerating
                    || aligningBoundary
                    || !hasRegenerateSource(stages)
                  }
                  onSplitAtTargetAndAlign={() => void startSplitAtTargetAndAlign()}
                  onInsertBefore={() => void insertChapterAt(num)}
                  onInsertAfter={() => void insertChapterAt(num + 1)}
                  onDuplicate={() => void duplicateThisChapter()}
                  onMergeNext={() => void mergeNextChapter()}
                  onRenumber={() => setRenumberOpen(true)}
                  onDelete={() => void confirmDeleteChapter()}
                />
              }
              trailingSection={
                <CodexSyncSection
                  hasRegenerateSource={hasRegenerateSource(stages)}
                  mineSourceStage={regenerateSource(stages, selected)}
                  isRunning={isRunning}
                  isMining={isMining}
                  lastFn={lastFn}
                  onMine={mineFromChapter}
                />
              }
            />

            {!briefExpanded && (
            <>
            <ChapterWorkflowToolbar
              num={num}
              stages={stages}
              selected={selected}
              canReopen={canReopen && selected === "final"}
              reviseUses={reviseUses}
              hasRegenerateSource={hasRegenerateSource(stages)}
              mineSourceStage={regenerateSource(stages, selected)}
              expandMarkerCount={expandMarkerCount}
              longChapterText={longChapterText}
              hasSavedBrief={hasSavedBrief}
              hasOutlineNotes={hasOutlineNotes}
              isRunning={isRunning}
              runningStage={runningStage}
              lastFn={lastFn}
              regenerating={regenerating}
              expanding={expanding}
              redrafting={redrafting}
              outlineGenerating={outlineGenerating}
              splittingChapter={splittingChapter}
              aligningBoundary={aligningBoundary}
              hasNextChapter={hasNextChapter}
              busy={busy}
              hasActivePreview={Boolean(regeneratePreview || outlinePreview || expandPreview || paragraphsPreview || alignmentPreview || redraftPreview)}
              regenInstructions={regenInstructions}
              setRegenInstructions={setRegenInstructions}
              applyNotesToOutline={applyNotesToOutline}
              setApplyNotesToOutline={setApplyNotesToOutline}
              outlineInstructions={outlineInstructions}
              setOutlineInstructions={setOutlineInstructions}
              redraftMode={redraftMode}
              setRedraftMode={setRedraftMode}
              isMining={isMining}
              embedded
              onGenerateDraft={() => runChapter("write", "write", { number: num })}
              onRevise={runRevise}
              onValidate={() => runChapter("validate", "validate", { number: num })}
              onApprove={() => runChapter("approve", "approve", { number: num })}
              onReviewMentions={() => openMentionReview(null)}
              onReopen={reopenForRevision}
              onRegenerate={() => startRegenerate()}
              onRedraftFromBrief={() => startRedraftFromBrief()}
              onExpandPlaceholders={() => startExpandPlaceholders()}
              onFormatParagraphs={() => void startFormatParagraphs()}
              formattingParagraphs={formattingParagraphs}
              onAlignBoundary={() => void startAlignBoundary()}
              onRegenerateOutline={(mode) => void startGenerateOutline(mode)}
              onSplitChapter={() => startSplitChapter()}
              onMine={mineFromChapter}
            />

            <MentionReviewPanel
              projectId={id}
              chapterNumber={num}
              source={mentionSource}
              open={mentionPanelOpen}
              onClose={() => {
                setMentionPanelOpen(false);
                setMentionFocusCharId(null);
              }}
              focusCharacterId={mentionFocusCharId}
              onApplied={() => reload()}
            />
            </>
            )}
          </div>
        </div>
        )}

        {!briefExpanded && (
        <div className={focus ? "flex min-h-0 flex-1 flex-col px-6 py-3" : "px-8 py-10"}>
          <div
            className={`w-full ${focus ? "flex min-h-0 flex-1 flex-col" : ""}`}
            style={studioColumnStyle}
          >
            {outlinePreview && (
              <RegeneratePreviewPanel
                preview={outlinePreview}
                text={outlinePreviewText}
                onChange={setOutlinePreviewText}
                onKeep={applyOutlinePreview}
                onDiscard={discardOutlinePreview}
                title="Generated outline"
                keepLabel="Keep outline"
                description={
                  outlinePreview.source === "notes"
                    ? "Generated from your outline notes. Edit beats if needed, then keep to save as the chapter outline."
                    : `Reverse-engineered from ${outlinePreview.source} prose (${outlinePreview.original_word_count.toLocaleString()} words). Edit beats if needed, then keep to save as the chapter outline.`
                }
              />
            )}
            {expandPreview && (
              <RegeneratePreviewPanel
                preview={expandPreview}
                text={expandPreviewText}
                onChange={setExpandPreviewText}
                onKeep={applyExpandPreview}
                onDiscard={discardExpandPreview}
                title="Expanded placeholders"
                keepLabel={`Keep → ${expandPreview.source}`}
                description={`Filled ${expandPreview.placeholder_count ?? "?"} placeholder(s) in ${expandPreview.source} prose (${expandPreview.original_word_count.toLocaleString()} → ${expandPreview.preview_word_count.toLocaleString()} words). Edit if needed, then keep.`}
              />
            )}
            {paragraphsPreview && (
              <RegeneratePreviewPanel
                preview={paragraphsPreview}
                text={paragraphsPreviewText}
                onChange={setParagraphsPreviewText}
                onKeep={applyParagraphsPreview}
                onDiscard={discardParagraphsPreview}
                title="AI Paragraphs preview"
                keepLabel={`Keep → ${paragraphsPreview.source}`}
                description={
                  `Paragraph breaks and scene breaks only — wording must match the original. `
                  + `${paragraphsPreview.scene_break_count ?? 0} scene break(s) (... on its own line) in ${paragraphsPreview.source} prose. `
                  + "Edit if needed, then keep. Discard if any words changed."
                }
              />
            )}
            {alignmentPreview && (
              <BoundaryAlignmentPreviewPanel
                preview={alignmentPreview}
                textA={alignmentTextA}
                textB={alignmentTextB}
                onChangeA={setAlignmentTextA}
                onChangeB={setAlignmentTextB}
                onKeep={applyAlignmentPreview}
                onDiscard={discardAlignmentPreview}
              />
            )}
            {regeneratePreview && (
              <RegeneratePreviewPanel
                preview={regeneratePreview}
                text={previewText}
                onChange={setPreviewText}
                onKeep={applyRegenerate}
                onDiscard={discardRegenerate}
              />
            )}
            {redraftPreview && (
              <RegeneratePreviewPanel
                preview={redraftPreview}
                text={redraftPreviewText}
                onChange={setRedraftPreviewText}
                onKeep={applyRedraftPreview}
                onDiscard={discardRedraftPreview}
                title="Redraft preview"
                keepLabel="Keep → draft"
                description={
                  `Redrafted from ${redraftPreview.source} using chapter brief (${redraftPreview.mode} mode) · `
                  + `${redraftPreview.original_word_count.toLocaleString()} → `
                  + `${redraftPreviewText.split(/\s+/).filter(Boolean).length.toLocaleString()} words. `
                  + "Edit below if needed, then keep to save as draft or discard."
                }
              />
            )}
            {selected === "final" ? (
              <FinalEditor
                hasFinal={stages.final != null}
                canPromote={canPromote}
                promoteFrom={promoteFrom}
                text={finalText}
                onChange={(v) => {
                  setFinalText(v);
                  setDirty(true);
                }}
                onPromote={promote}
                onReopen={reopenForRevision}
                canReopen={canReopen}
                dirty={dirty}
                busy={busy}
                lastSaved={lastSaved}
                focus={focus}
                onToggleFocus={() => setFocus((f) => !f)}
                mentionTargets={mentionTargets}
                projectId={id}
                onCharacterMentionAction={onCharacterMentionAction}
                annotations={stageAnnotations}
                onCreateAnnotation={createAnnotation}
                focusAnnotationId={focusAnnotationId}
                fluidLayout={fluidLayout}
                showSaveStatus={false}
              />
            ) : selected === "revised" ? (
              stages.revised == null ? (
                <ProvenancePane
                  stage="revised"
                  text={null}
                  mentionTargets={mentionTargets}
                  projectId={id}
                  onCharacterMentionAction={onCharacterMentionAction}
                />
            ) : (
                <ManuscriptEditor
                  stage="revised"
                  text={revisedText}
                  onChange={(v) => { setRevisedText(v); setRevisedDirty(true); }}
                  placeholder="Revised chapter prose…"
                  dirty={revisedDirty}
                  saving={busy === "saving"}
                  lastSaved={revisedLastSaved}
                  focus={focus}
                  onToggleFocus={() => setFocus((f) => !f)}
                  mentionTargets={mentionTargets}
                  projectId={id}
                  onCharacterMentionAction={onCharacterMentionAction}
                  annotations={stageAnnotations}
                  onCreateAnnotation={createAnnotation}
                  focusAnnotationId={focusAnnotationId}
                  fluidLayout={fluidLayout}
                  showSaveStatus={false}
                  headerExtra={
                    <>
                      <p className="mb-2 text-[12px] text-ink-muted">
                        Edit this text, then click <strong>Revise</strong> again (or add notes above). Draft is unchanged.
                      </p>
                      <ToolTip id="chapter.copyRevisedToDraft">
                        <button
                          type="button"
                          onClick={() => void copyRevisedToDraft()}
                          disabled={busy != null || !revisedText.trim()}
                          className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-medium text-ink-muted hover:bg-ink/5 disabled:opacity-40"
                        >
                          Copy Revised → Draft
                        </button>
                      </ToolTip>
                    </>
                  }
                />
              )
            ) : selected === "draft" ? (
              <ManuscriptEditor
                stage="draft"
                text={draftText}
                onChange={(v) => { setDraftText(v); setDraftDirty(true); }}
                placeholder="Paste or write chapter draft…"
                dirty={draftDirty}
                saving={busy === "saving"}
                lastSaved={draftLastSaved}
                focus={focus}
                onToggleFocus={() => setFocus((f) => !f)}
                mentionTargets={mentionTargets}
                projectId={id}
                onCharacterMentionAction={onCharacterMentionAction}
                annotations={stageAnnotations}
                onCreateAnnotation={createAnnotation}
                focusAnnotationId={focusAnnotationId}
                fluidLayout={fluidLayout}
                showSaveStatus={false}
              />
            ) : (
              stages.outline == null ? (
                <ProvenancePane
                  stage="outline"
                  text={null}
                  mentionTargets={mentionTargets}
                  projectId={id}
                  onCharacterMentionAction={onCharacterMentionAction}
                />
              ) : (
                <OutlineEditor
                  text={outlineText}
                  onChange={(v) => { setOutlineText(v); setOutlineDirty(true); }}
                  dirty={outlineDirty}
                  saving={busy === "saving"}
                  lastSaved={outlineLastSaved}
                  focus={focus}
                  onToggleFocus={() => setFocus((f) => !f)}
                  fluidLayout={fluidLayout}
                />
              )
            )}
          </div>
        </div>
        )}
      </div>

      {showInspector && !focus && (
        <>
          <PanelResizeHandle
            label="Resize notes panel"
            onPointerDown={inspectorResize.onPointerDown}
            onPointerMove={inspectorResize.onPointerMove}
            onPointerUp={inspectorResize.onPointerUp}
          />
          <Inspector
          id={id}
          num={num}
          width={inspectorWidthLive}
          currentText={finalText}
          flush={flush}
          refreshToken={contentRevision}
          onRestored={(text) => {
            setFinalText(text);
            setDirty(false);
            reload();
          }}
          selectedStage={selected === "outline" ? undefined : selected}
          comments={comments}
          onCommentsChange={reloadComments}
          focusAnnotationId={focusAnnotationId}
          onFocusAnnotation={(annId) => {
            setFocusAnnotationId(annId);
            if (annId) {
              const ann = comments.find((c) => c.id === annId);
              const annStage = ann ? commentStage(ann) : null;
              if (annStage && isManuscriptStage(annStage)) {
                selectStage(annStage);
              }
            }
          }}
          commentPrefill={commentPrefill}
          onClearCommentPrefill={() => setCommentPrefill(null)}
          initialTab={inspectorTab}
          characters={characters}
        />
        </>
      )}
      <RenumberChapterModal
        projectId={id}
        chapter={meta ? { number: num, title: meta.title } : { number: num, title: "" }}
        open={renumberOpen}
        onClose={() => setRenumberOpen(false)}
        onBeforeReassign={prepareForRenumber}
        onDone={(newNum) => navigate(`/projects/${id}/chapters/${newNum}`, { replace: true })}
      />
      <ChapterMinePreviewModal
        open={minePreviewOpen}
        onClose={() => setMinePreviewOpen(false)}
        projectId={id}
        chapterNumber={num}
        kind={minePreviewKind}
        onApplied={() => reload()}
      />
    </div>
  );
}

function BoundaryAlignmentPreviewPanel({
  preview,
  textA,
  textB,
  onChangeA,
  onChangeB,
  onKeep,
  onDiscard,
}: {
  preview: BoundaryAlignmentPreview;
  textA: string;
  textB: string;
  onChangeA: (v: string) => void;
  onChangeB: (v: string) => void;
  onKeep: () => void;
  onDiscard: () => void;
}) {
  const moved = preview.adjusted && preview.move_text.trim();
  return (
    <section className="mb-8 rounded-xl border border-amber/35 bg-amber/5 p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold text-ink-text">
            Fix chapter alignment preview
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            Chapters {preview.chapter_a} → {preview.chapter_b} ({preview.source}) ·{" "}
            {moved
              ? `Text relocated (${preview.direction?.replace("to_", "") ?? "adjusted"}) — wording must stay identical.`
              : "Boundary already aligned — no text moved."}{" "}
            Run after AI Paragraphs or manual paragraph breaks.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <ToolTip id="chapter.previewDiscard">
            <button type="button" onClick={onDiscard}
                    className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5">
              Discard
            </button>
          </ToolTip>
          <ToolTip id="chapter.previewKeep">
            <button type="button" onClick={onKeep} disabled={!textA.trim() || !textB.trim()}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              Keep → both chapters
            </button>
          </ToolTip>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-md bg-paper-card px-4 py-6 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[200px]">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Chapter {preview.chapter_a} end · {textA.split(/\s+/).filter(Boolean).length.toLocaleString()} words
          </p>
          <MarkdownEditor value={textA} onChange={onChangeA} placeholder="Chapter text…" />
        </article>
        <article className="rounded-md bg-paper-card px-4 py-6 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[200px]">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Chapter {preview.chapter_b} start · {textB.split(/\s+/).filter(Boolean).length.toLocaleString()} words
          </p>
          <MarkdownEditor value={textB} onChange={onChangeB} placeholder="Next chapter text…" />
        </article>
      </div>
    </section>
  );
}

function RegeneratePreviewPanel({
  preview, text, onChange, onKeep, onDiscard,
  title = "Regenerated preview",
  keepLabel,
  description,
}: {
  preview: RegeneratePreview;
  text: string;
  onChange: (v: string) => void;
  onKeep: () => void;
  onDiscard: () => void;
  title?: string;
  keepLabel?: string;
  description?: string;
}) {
  const keep = keepLabel ?? `Keep → ${preview.source}`;
  return (
    <section className="mb-8 rounded-xl border border-amber/35 bg-amber/5 p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold text-ink-text">
            {title}
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            {description ?? (
              <>
                From {preview.source} · {preview.original_word_count.toLocaleString()} →{" "}
                {text.split(/\s+/).filter(Boolean).length.toLocaleString()} words.
                Edit below if needed, then keep or discard.
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <ToolTip id="chapter.previewDiscard">
            <button type="button" onClick={onDiscard}
                    className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5">
              Discard
            </button>
          </ToolTip>
          <ToolTip id="chapter.previewKeep">
            <button type="button" onClick={onKeep} disabled={!text.trim()}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {keep}
            </button>
          </ToolTip>
        </div>
      </div>
      <article className="rounded-md bg-paper-card px-6 py-8 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[240px]">
        <MarkdownEditor value={text} onChange={onChange} placeholder="Generated content…" />
      </article>
    </section>
  );
}

function OutlineEditor({
  text, onChange, dirty: _dirty, saving: _saving, lastSaved: _lastSaved, focus, onToggleFocus,
  fluidLayout,
}: {
  text: string;
  onChange: (v: string) => void;
  dirty: boolean;
  saving: boolean;
  lastSaved: string | null;
  focus: boolean;
  onToggleFocus: () => void;
  fluidLayout?: { columnMaxPx: number; fontRem: number };
}) {
  const editorFontRem = fluidLayout?.fontRem ?? 1.075;
  return (
    <section
      className={`rounded-md bg-paper-card shadow-[var(--shadow-paper)] ring-1 ring-paper-line ${
      focus ? "flex min-h-0 flex-1 flex-col px-6 py-4" : "min-h-[50vh] px-8 py-8"
    }`}
      style={fluidLayout ? {
        width: fluidLayout.columnMaxPx,
        maxWidth: fluidLayout.columnMaxPx,
        minWidth: fluidLayout.columnMaxPx,
        marginInline: "auto",
        ["--editor-size" as string]: `${editorFontRem}rem`,
      } : undefined}
    >
      <div className="mb-3 flex shrink-0 items-center justify-between gap-3 border-b border-paper-line pb-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-deep">
            {focus ? "Outline · editing" : "Chapter outline"}
          </p>
          {!focus && (
            <p className="mt-1 text-[12.5px] text-ink-muted">
              Edit beats directly — changes autosave even after Final is committed.
            </p>
          )}
        </div>
        <ToolTip id="chapter.focusMode">
          <button
            type="button"
            onClick={onToggleFocus}
            className={`shrink-0 rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors ${
              focus
                ? "bg-ink text-on-ink hover:bg-ink-800"
                : "border border-paper-line text-ink-text hover:bg-ink/5"
            }`}
          >
            {focus ? "Exit focus" : "Focus"}
          </button>
        </ToolTip>
      </div>
      <div className={`prose-outline ${focus ? "min-h-0 flex-1" : ""}`}>
        <MarkdownEditor
          value={text}
          onChange={onChange}
          placeholder="Chapter beat-sheet outline…"
        />
      </div>
    </section>
  );
}

function ProvenancePane({
  stage, text, mentionTargets, projectId, onCharacterMentionAction,
}: {
  stage: StageKey;
  text: string | null;
  mentionTargets?: MentionTarget[];
  projectId?: string;
  onCharacterMentionAction?: (
    parsed: unknown,
    resolved: MentionTarget,
  ) => void;
}) {
  if (text == null) {
    return (
      <Empty
        title={`${cap(stage)} not generated yet`}
        hint={
          stage === "outline"
            ? "Enter outline notes above, choose From notes or From text under Regenerate outline, then confirm to generate a beat sheet."
            : "Run the pipeline to produce this stage."
        }
      />
    );
  }
  const outline = stage === "outline";
  return (
    <article className="rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <div className="mb-6 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-paper-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-st-approved" />
        Provenance · read-only — the reviewed Final is canonical
      </div>
      <div className={outline ? "prose-outline" : "prose-manuscript"}>
        <MentionMarkdown
          source={text}
          className={outline ? "prose-outline" : "prose-manuscript"}
          mentionTargets={mentionTargets}
          projectId={projectId}
          onCharacterMentionAction={onCharacterMentionAction}
        />
      </div>
    </article>
  );
}

function Empty({ title, hint, action }: { title: string; hint: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <p className="font-display text-[18px] text-ink-text">{title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{hint}</p>
      {action}
    </div>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
