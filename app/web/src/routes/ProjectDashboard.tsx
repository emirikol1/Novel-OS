import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, characterPortraitUrl, type BatchExtractOutlineStats, type ChapterStructureReport, type EntityDedupStatus, type ProjectDetail, type ChapterSummary, type CharacterSummary, type PlotThreadSummary, type TimelineEventSummary, type ResearchSparkSummary, type PlanOutlinePreview } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";
import Outliner from "../components/Outliner";
import TimelinePanel, { TimelineEventModal } from "../components/TimelinePanel";
import RelationshipGraphPanel from "../components/RelationshipGraphPanel";
import GenealogyPanel from "../components/GenealogyPanel";
import StoryGraphPanel from "../components/StoryGraphPanel";
import BlueprintCanvasPanel from "../components/BlueprintCanvasPanel";
import ResearchBoardPanel, { ResearchSparkModal } from "../components/ResearchBoardPanel";
import MapPanel from "../components/MapPanel";
import DeleteButton from "../components/DeleteButton";
import {
  CharacterEditorModal, GenericImporterPanel, PasteChapterModal, PlotThreadModal,
  QuickAddCharacterModal, RenumberChapterModal, StoryBiblePanel,
} from "../components/CodexEditors";
import ResolveDuplicatesModal from "../components/ResolveDuplicatesModal";
import PlotPanelIssuesModal from "../components/PlotPanelIssuesModal";
import ManualMergeModal, { type MergeKind } from "../components/ManualMergeModal";
import ProjectBackupsModal from "../components/ProjectBackupsModal";
import Modal, { Field, fieldClass } from "../components/Modal";
import TargetLengthInput from "../components/TargetLengthInput";
import { DEFAULT_PROJECT_STYLE } from "../lib/chapterBrief";
import { useToast } from "../components/Toaster";
import { useConfirm } from "../components/Confirm";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import { useRunPhase } from "../hooks/useRunPhase";
import PendingAiStar from "../components/PendingAiStar";
import { ChapterPipelineLegend } from "../components/ChapterPipelineStatus";
import { projectChaptersWithPendingPreviews, remapChapterPreviewPending } from "../lib/chapterPreviewPending";
import { projectMinePreviewsPending, syncMinePreviewPendingFromApi } from "../lib/minePreviewPending";
import type { MineKind } from "../api/client";
import { syncProjectPreviewPendingFromApi } from "../lib/syncChapterPreviewPending";
import ChapterMinePreviewModal from "../components/ChapterMinePreviewModal";
import BatchExtractSettingsModal from "../components/BatchExtractSettingsModal";
import StoryPanelToggles from "../components/StoryPanelToggles";
import { remapChapterWorkflowMarkers } from "../lib/chapterWorkflow";
import { PIPELINE_LABELS, pipelineStepFromSummary, type PipelineStep } from "../lib/chapterPipeline";
import { buildWritingStats, PIPELINE_BUCKETS } from "../lib/writingStats";
import { notifyStashChanged } from "../components/StashPanel";
import { isNotFoundError, redirectOnProjectNotFound } from "../lib/apiHealth";
import ToolTip from "../components/ToolTip";
import type { ToolTipId } from "../lib/toolRegistry";

const ROLE_COLOR: Record<string, string> = {
  protagonist: "var(--color-st-approved)",
  antagonist: "var(--color-st-planned)",
  supporting: "var(--color-st-drafted)",
  minor: "var(--color-ink-muted)",
};

const TOOLBAR_CHIP =
  "inline-flex items-center rounded-md border border-paper-line bg-paper px-2.5 py-1 text-[12px] font-medium text-ink-text transition-colors hover:border-amber/40 hover:bg-amber/5 disabled:opacity-40";
const TOOLBAR_CHIP_ACTIVE = "border-amber/40 bg-amber/5 text-ink-text";
const TOOLBAR_CHIP_DANGER =
  "inline-flex items-center rounded-md border border-red-500/40 bg-paper px-2.5 py-1 text-[12px] font-medium text-red-600 transition-colors hover:border-red-500/60 hover:bg-red-500/5 disabled:opacity-40";
const TOOLBAR_FIELD =
  "rounded-md border border-paper-line bg-paper px-2.5 py-1 text-[12px] font-medium text-ink-text";

type CodexTab = "importer" | "chapters" | "cast" | "relationships" | "family" | "storygraph" | "blueprint" | "timeline" | "research" | "map" | "bible";

const CODEX_TAB_TIPS: Record<Exclude<CodexTab, "importer">, ToolTipId> = {
  chapters: "dashboard.tabChapters",
  cast: "dashboard.tabCast",
  relationships: "dashboard.tabRelationships",
  family: "dashboard.tabFamily",
  storygraph: "dashboard.tabStoryGraph",
  blueprint: "dashboard.tabBlueprint",
  timeline: "dashboard.tabTimeline",
  research: "dashboard.tabResearch",
  map: "dashboard.tabMap",
  bible: "dashboard.tabBible",
};

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const confirm = useConfirm();
  const toast = useToast();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [plotThreads, setPlotThreads] = useState<PlotThreadSummary[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEventSummary[]>([]);
  const [researchSparks, setResearchSparks] = useState<ResearchSparkSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [charOpen, setCharOpen] = useState(false);
  const [dedupOpen, setDedupOpen] = useState(false);
  const [entityDedupStatus, setEntityDedupStatus] = useState<EntityDedupStatus>({
    ai_suggestions_ready: false,
    ai_group_count: 0,
    has_ai_file: false,
    ai_scan_completed: false,
  });
  const [bibleDedupReady, setBibleDedupReady] = useState(false);
  const [previewTick, setPreviewTick] = useState(0);
  const { isProjectJobRunning, watchBackgroundJob } = useBackgroundJob();
  const entityScanning = isProjectJobRunning("entity-dedup", id);
  const batchOutlinesRunning = isProjectJobRunning("batch-outlines", id);
  const batchCodexRunning = isProjectJobRunning("batch-codex", id);
  const [plotPanelIssuesOpen, setPlotPanelIssuesOpen] = useState(false);
  const [manualMerge, setManualMerge] = useState<MergeKind | null>(null);
  const plotMergeMode = "parallel" as const;
  const [dedupKind, setDedupKind] = useState<MergeKind>("character");
  const [backupsOpen, setBackupsOpen] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [editCharId, setEditCharId] = useState<string | null>(null);
  const [plotModal, setPlotModal] = useState<PlotThreadSummary | null | "new">(null);
  const [timelineModalOpen, setTimelineModalOpen] = useState(false);
  const [researchModalOpen, setResearchModalOpen] = useState(false);
  const [styleOpen, setStyleOpen] = useState(false);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [renumberChapter, setRenumberChapter] = useState<ChapterSummary | null>(null);
  const [codexTab, setCodexTab] = useState<CodexTab>("chapters");
  const [chapterView, setChapterView] = useState<"board" | "outline">("board");
  const [chapterStatusFilter, setChapterStatusFilter] = useState<PipelineStep | "all">("all");
  const [structureReport, setStructureReport] = useState<ChapterStructureReport | null>(null);
  const [structureLoading, setStructureLoading] = useState(false);
  const [chapterOrderBusy, setChapterOrderBusy] = useState(false);
  const [mineReview, setMineReview] = useState<{ chapter: number; kind: MineKind } | null>(null);
  const [minePreviewTick, setMinePreviewTick] = useState(0);
  const [outlineBatchOpen, setOutlineBatchOpen] = useState(false);
  const [outlineBatchStats, setOutlineBatchStats] = useState<BatchExtractOutlineStats | null>(null);
  const [outlineBatchLoading, setOutlineBatchLoading] = useState(false);
  const [codexBatchOpen, setCodexBatchOpen] = useState(false);
  const [codexBatchStats, setCodexBatchStats] = useState<BatchExtractOutlineStats | null>(null);
  const [codexBatchLoading, setCodexBatchLoading] = useState(false);
  const [briefBatchOpen, setBriefBatchOpen] = useState(false);
  const [briefBatchStats, setBriefBatchStats] = useState<BatchExtractOutlineStats | null>(null);
  const [briefsBatchRunning, setBriefsBatchRunning] = useState(false);
  const [titleBatchOpen, setTitleBatchOpen] = useState(false);
  const [titleBatchStats, setTitleBatchStats] = useState<BatchExtractOutlineStats | null>(null);
  const [titleBatchLoading, setTitleBatchLoading] = useState(false);
  const [titlesBatchRunning, setTitlesBatchRunning] = useState(false);
  const [projectOpsCollapsed, setProjectOpsCollapsed] = useState(true);

  const load = useCallback(() => {
    setError(null);
    api.project(id).then(setProject).catch((e) => {
      if (redirectOnProjectNotFound(e, navigate, toast)) return;
      setError(String(e));
    });
    api.chapters(id).then((chs) => {
      setChapters(chs);
      void syncProjectPreviewPendingFromApi(
        id,
        chs.map((c) => c.number),
      );
    }).catch((e) => {
      if (!isNotFoundError(e)) setError(String(e));
    });
    api.characters(id).then(setCharacters).catch(() => setCharacters([]));
    api.plotThreads(id).then(setPlotThreads).catch(() => setPlotThreads([]));
    api.timelineEvents(id).then(setTimelineEvents).catch(() => setTimelineEvents([]));
    api.researchSparks(id).then(setResearchSparks).catch(() => setResearchSparks([]));
    void syncMinePreviewPendingFromApi(id).catch(() => {});
    setStructureReport(null);
  }, [id, navigate, toast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab === "importer") {
      setCodexTab("importer");
    } else if (tab === "plots") {
      setCodexTab("storygraph");
    } else if (tab === "chapters" || tab === "cast" || tab === "relationships"
        || tab === "family" || tab === "storygraph" || tab === "blueprint" || tab === "timeline"
        || tab === "research" || tab === "map" || tab === "bible") {
      setCodexTab(tab);
    }
    const characterId = searchParams.get("character");
    if (characterId) {
      setCodexTab("cast");
      setEditCharId(characterId);
    }
    if (searchParams.get("section")) {
      setCodexTab("bible");
    }
  }, [searchParams]);

  const bibleScrollSection = searchParams.get("section");

  const refreshEntityDedupStatus = useCallback(() => {
    api.duplicatesStatus(id).then(setEntityDedupStatus).catch(() => {
      setEntityDedupStatus({
        ai_suggestions_ready: false,
        ai_group_count: 0,
        has_ai_file: false,
        ai_scan_completed: false,
      });
    });
  }, [id]);

  useEffect(() => { refreshEntityDedupStatus(); }, [refreshEntityDedupStatus]);

  useEffect(() => {
    api.bibleDedupStatus(id).then((s) => setBibleDedupReady(s.ai_suggestions_ready)).catch(() => setBibleDedupReady(false));
  }, [id, dedupOpen, codexTab]);

  useEffect(() => {
    const bump = () => setPreviewTick((n) => n + 1);
    window.addEventListener("novel-os:preview-pending", bump);
    return () => window.removeEventListener("novel-os:preview-pending", bump);
  }, []);

  useEffect(() => {
    const bump = () => setMinePreviewTick((n) => n + 1);
    window.addEventListener("novel-os:mine-preview-pending", bump);
    return () => window.removeEventListener("novel-os:mine-preview-pending", bump);
  }, []);

  const chapterPreviewPending = projectChaptersWithPendingPreviews(id).size > 0;
  void previewTick;
  void minePreviewTick;

  function openDedup(kind: MergeKind) {
    setDedupKind(kind);
    setDedupOpen(true);
  }

  function dedupBadge() {
    if (entityScanning) return <span className="ml-1.5 rounded-full bg-amber/25 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-deep">scanning</span>;
    if (entityDedupStatus.ai_suggestions_ready) {
      const plotOnly = entityDedupStatus.plot_thread_group_count ?? 0;
      const label = plotOnly > 0 && (entityDedupStatus.character_group_count ?? 0) === 0
        ? `${plotOnly} plot AI`
        : `${entityDedupStatus.ai_group_count} AI`;
      return (
        <span className="ml-1.5 rounded-full bg-amber/25 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-deep">
          {label}
        </span>
      );
    }
    if (entityDedupStatus.ai_scan_completed) {
      return (
        <span className="ml-1.5 rounded-full bg-ink/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-muted">
          AI done
        </span>
      );
    }
    return null;
  }

  const { run, runningStage, isRunning } = useRunPhase(id, load);

  async function deleteChapter(c: ChapterSummary) {
    try {
      await api.deleteChapter(id, c.number);
      toast(`Deleted chapter ${c.number}`, "success");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function deleteCharacter(ch: CharacterSummary) {
    try {
      await api.deleteCharacter(id, ch.id);
      toast(`Removed ${ch.full_name}`, "success");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function stashProject() {
    if (!project) return;
    const ok = await confirm({
      title: "Stash manuscript",
      message: `Stash "${project.title}"? It will be removed from your library and kept in the sidebar Stash lockbox until you unstash it.`,
      confirmLabel: "Stash manuscript",
    });
    if (!ok) return;
    try {
      await api.stashProject(id);
      toast(`Stashed "${project.title}"`, "success");
      notifyStashChanged();
      navigate("/");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function deleteProject() {
    if (!project) return;
    const ok = await confirm({
      title: "Delete manuscript",
      message: `Permanently delete "${project.title}" and everything in it? This cannot be undone.`,
      confirmLabel: "Delete manuscript",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteProject(id);
      toast(`Deleted "${project.title}"`, "success");
      navigate("/");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  function openChapters(filter: PipelineStep | "all" = "all") {
    setCodexTab("chapters");
    setChapterStatusFilter(filter);
  }

  async function generateMissingChapterBriefs() {
    await openBatchPopulateBriefsModal();
  }

  function chapterBriefBatchStats(): BatchExtractOutlineStats {
    const withProse = chapters.filter((chapter) => (chapter.word_count ?? 0) > 0);
    const missing = withProse.filter((chapter) => !chapter.has_brief);
    return {
      total_with_prose: withProse.length,
      missing_count: missing.length,
      missing_chapters: missing.map((chapter) => chapter.number),
    };
  }

  async function openBatchPopulateBriefsModal() {
    if (chaptersWithProseCount() === 0) {
      toast("No chapters with prose to brief", "error");
      return;
    }
    setBriefBatchStats(chapterBriefBatchStats());
    setBriefBatchOpen(true);
  }

  async function runBatchPopulateBriefs({
    skipExisting,
  }: {
    skipExisting: boolean;
    autoAccept: boolean;
  }) {
    const stats = briefBatchStats ?? chapterBriefBatchStats();
    const count = skipExisting ? stats.missing_count : stats.total_with_prose;
    if (count === 0) return;

    const ok = await confirm({
      title: "Populate chapter briefs?",
      message:
        `${skipExisting ? "Generate and save missing" : "Regenerate and save"} chapter briefs for ${count} chapter${count === 1 ? "" : "s"} `
        + "from chapter text, cast, and Story Graph nodes? Briefs are saved directly — this may take a while.",
      confirmLabel: skipExisting ? "Populate missing briefs" : "Populate all briefs",
    });
    if (!ok) return;

    setBriefBatchOpen(false);
    setBriefBatchStats(null);
    setBriefsBatchRunning(true);
    try {
      const result = await api.generateChapterBriefs(id, {
        source: "best",
        max_beats: 5,
        overwrite_existing: !skipExisting,
      });
      toast(
        `Generated ${result.generated.length} brief(s); skipped ${result.skipped.length}.`,
        result.generated.length ? "success" : "info",
      );
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBriefsBatchRunning(false);
    }
  }

  async function startBatchPopulateBriefs() {
    await openBatchPopulateBriefsModal();
  }

  async function openBatchAutoTitleModal() {
    if (chaptersWithProseCount() === 0) {
      toast("No chapters with prose to title", "error");
      return;
    }
    setTitleBatchLoading(true);
    setTitleBatchOpen(true);
    setTitleBatchStats(null);
    try {
      const stats = await api.autoTitleChapterStats(id);
      setTitleBatchStats(stats);
    } catch (err) {
      setTitleBatchOpen(false);
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setTitleBatchLoading(false);
    }
  }

  async function runBatchAutoTitle({
    titleScope,
  }: {
    skipExisting: boolean;
    autoAccept: boolean;
    titleScope?: "eligible" | "auto_only";
  }) {
    const scope = titleScope ?? "eligible";
    const stats = titleBatchStats;
    const count =
      scope === "eligible"
        ? stats?.missing_count ?? 0
        : stats?.secondary_count ?? 0;
    if (count === 0) return;

    const ok = await confirm({
      title: "Auto-title chapters?",
      message:
        `${scope === "eligible" ? "Generate titles for" : "Regenerate auto-titles on"} ${count} chapter${count === 1 ? "" : "s"} `
        + "from chapter prose? Manually titled chapters are never changed unless you pick All auto-titles.",
      confirmLabel: scope === "eligible" ? "Auto-title chapters" : "Regenerate auto-titles",
    });
    if (!ok) return;

    setTitleBatchOpen(false);
    setTitleBatchStats(null);
    setTitlesBatchRunning(true);
    try {
      const result = await api.generateChapterTitles(id, { source: "best", scope });
      toast(
        `Generated ${result.generated.length} title(s); skipped ${result.skipped.length}.`,
        result.generated.length ? "success" : "info",
      );
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setTitlesBatchRunning(false);
    }
  }

  async function startBatchAutoTitle() {
    await openBatchAutoTitleModal();
  }

  function chaptersWithProseCount(): number {
    return chapters.filter((chapter) => (chapter.word_count ?? 0) > 0).length;
  }

  async function openBatchExtractOutlinesModal() {
    if (chaptersWithProseCount() === 0) {
      toast("No chapters with prose to outline", "error");
      return;
    }
    setOutlineBatchLoading(true);
    setOutlineBatchOpen(true);
    setOutlineBatchStats(null);
    try {
      const stats = await api.batchExtractOutlinesStats(id, "best");
      setOutlineBatchStats(stats);
    } catch (err) {
      setOutlineBatchOpen(false);
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setOutlineBatchLoading(false);
    }
  }

  async function runBatchExtractOutlines({
    skipExisting,
    autoAccept,
  }: {
    skipExisting: boolean;
    autoAccept: boolean;
  }) {
    const count = skipExisting
      ? outlineBatchStats?.missing_count ?? 0
      : outlineBatchStats?.total_with_prose ?? 0;
    if (count === 0) return;

    const ok = await confirm({
      title: "Run outline extraction?",
      message:
        `Extract outlines for ${count} chapter${count === 1 ? "" : "s"} sequentially in the background. `
        + `${autoAccept ? "Auto-accept is on — outlines will be saved without preview review." : "Results stay as previews until you review each chapter."} `
        + "Cancel anytime from System Settings → LLM queue.",
      confirmLabel: "Run extraction",
    });
    if (!ok) return;

    setOutlineBatchOpen(false);
    setOutlineBatchStats(null);
    try {
      const job = await api.batchExtractOutlines(id, {
        source: "best",
        skip_existing: skipExisting,
        auto_accept: autoAccept,
      });
      toast("Extracting outlines — running in background…", "success");
      watchBackgroundJob(job.job_id, {
        kind: "batch-outlines",
        projectId: id,
        label: "Extract all outlines",
        successMessage: autoAccept
          ? "Outline extraction finished — saved outlines are ready"
          : "Outline extraction finished — review previews on each chapter",
        onSuccess: () => {
          load();
          window.dispatchEvent(new Event("novel-os:preview-pending"));
        },
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function startBatchExtractOutlines() {
    await openBatchExtractOutlinesModal();
  }

  async function openBatchExtractCodexModal() {
    if (chaptersWithProseCount() === 0) {
      toast("No chapters with prose to mine", "error");
      return;
    }
    setCodexBatchLoading(true);
    setCodexBatchOpen(true);
    setCodexBatchStats(null);
    try {
      const stats = await api.batchExtractCodexStats(id, "best");
      setCodexBatchStats(stats);
    } catch (err) {
      setCodexBatchOpen(false);
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setCodexBatchLoading(false);
    }
  }

  async function runBatchExtractCodex({
    skipExisting,
    autoAccept,
  }: {
    skipExisting: boolean;
    autoAccept: boolean;
  }) {
    const count = skipExisting
      ? codexBatchStats?.missing_count ?? 0
      : codexBatchStats?.total_with_prose ?? 0;
    if (count === 0) return;
    const passes = count * 3;

    const ok = await confirm({
      title: "Run codex extraction?",
      message:
        `Mine plots, characters, and story bible from ${count} chapter${count === 1 ? "" : "s"} sequentially `
        + `(${passes} LLM passes total). Expect many hours on a full manuscript. `
        + `${autoAccept ? "Auto-accept is on — mined updates will be applied without preview review." : "Each pass saves a preview for review — nothing is applied until you approve it on the chapter page."} `
        + "Cancel anytime from System Settings → LLM queue.",
      confirmLabel: "Run extraction",
    });
    if (!ok) return;

    setCodexBatchOpen(false);
    setCodexBatchStats(null);
    try {
      const job = await api.batchExtractCodex(id, {
        source: "best",
        skip_existing: skipExisting,
        auto_accept: autoAccept,
      });
      toast("Extracting codex — running in background…", "success");
      watchBackgroundJob(job.job_id, {
        kind: "batch-codex",
        projectId: id,
        label: "Extract all codex",
        successMessage: autoAccept
          ? "Codex extraction finished — mined updates were applied"
          : "Codex extraction finished — review mine previews on each chapter",
        onSuccess: () => {
          load();
          window.dispatchEvent(new Event("novel-os:mine-preview-pending"));
        },
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function startBatchExtractCodex() {
    await openBatchExtractCodexModal();
  }

  async function validateChapterStructure() {
    setStructureLoading(true);
    try {
      const report = await api.validateChapterStructure(id);
      setStructureReport(report);
      if (report.error_count > 0) {
        toast(`Found ${report.error_count} chapter structure error(s)`, "error");
      } else {
        toast(`Structure check complete: ${report.warning_count} warning(s)`, "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setStructureLoading(false);
    }
  }

  function firstMissingChapterNumber(): number | null {
    const nums = new Set(chapters.map((chapter) => chapter.number));
    const max = chapters.length ? Math.max(...chapters.map((chapter) => chapter.number)) : 0;
    for (let n = 1; n <= max; n += 1) {
      if (!nums.has(n)) return n;
    }
    return null;
  }

  async function refreshStructureReport() {
    try {
      setStructureReport(await api.validateChapterStructure(id));
    } catch {
      setStructureReport(null);
    }
  }

  async function removeChapterGaps() {
    const ok = await confirm({
      title: "Remove chapter number gaps?",
      message: "Renumber chapters sequentially from 1 while preserving their current order. This preflights file collisions first and cancels without moving anything if a collision is found.",
      confirmLabel: "Remove gaps",
    });
    if (!ok) return;
    setChapterOrderBusy(true);
    try {
      const result = await api.renumberChaptersSequential(id);
      remapChapterPreviewPending(id, result.mapping);
      remapChapterWorkflowMarkers(id, result.mapping);
      setChapters(result.chapters);
      api.project(id).then(setProject).catch(() => {});
      await refreshStructureReport();
      if (result.action === "unchanged") {
        toast("Chapter numbers already have no gaps", "success");
      } else {
        toast(`Removed gaps; renumbered ${result.mapping.length} chapter(s)`, "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setChapterOrderBusy(false);
    }
  }

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          {isNotFoundError(error) ? (
            <>
              <p>This project no longer exists or was moved.</p>
              <Link to="/" className="mt-3 inline-block font-semibold text-amber-deep hover:underline">
                ← Back to Library
              </Link>
            </>
          ) : (
            <>Failed to load: {error}</>
          )}
        </div>
      </div>
    );
  if (!project)
    return (
      <div className="mx-auto max-w-5xl px-10 py-12">
        <div className="h-3.5 w-24 animate-pulse rounded bg-paper-card" />
        <div className="mt-4 h-10 w-2/3 animate-pulse rounded bg-paper-card" />
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-paper-card" />
          ))}
        </div>
      </div>
    );

  const nextChapter = chapters.length ? Math.max(...chapters.map((c) => c.number)) + 1 : 1;
  const writingStats = buildWritingStats(chapters, nextChapter);
  const pendingPreviewCount = projectChaptersWithPendingPreviews(id).size;
  const firstGap = firstMissingChapterNumber();
  const filteredChapters = chapterStatusFilter === "all"
    ? chapters
    : chapters.filter((chapter) => pipelineStepFromSummary(chapter) === chapterStatusFilter);

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <ToolTip id="dashboard.backToLibrary">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
          >
            ← Library
          </Link>
        </ToolTip>
        <div className="flex flex-wrap items-center gap-3">
          <StoryPanelToggles />
          <ToolTip id="library.help">
            <Link
              to="/help"
              className={TOOLBAR_CHIP}
            >
              Help
            </Link>
          </ToolTip>
        </div>
      </div>

      <header className="mb-6 border-b border-paper-line pb-5">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-amber-deep">
          {project.genre}
        </p>
        <h1 className="font-display text-[38px] font-semibold leading-tight tracking-tight text-ink-text text-balance">
          {project.title}
        </h1>
        <p className="mt-2 text-[14px] text-ink-muted">by {project.author || "Unknown"}</p>
      </header>

      <section className="mb-6 rounded-xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)]">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <ToolTip id="dashboard.writingProgress">
            <div>
              <h2 className="font-display text-[18px] font-semibold tracking-tight text-ink-text">
                Writing progress
              </h2>
              <p className="mt-1 text-[13px] text-ink-muted">
                {writingStats.completionPct}% complete — {writingStats.pipeline.final} of{" "}
                {writingStats.chapterCount || project.chapter_count} chapters finalized
              </p>
            </div>
          </ToolTip>
          <div className="text-right">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Next action
            </p>
            {writingStats.nextChapter != null ? (
              <ToolTip id="dashboard.nextAction">
                <Link
                  to={`/projects/${id}/chapters/${writingStats.nextChapter}`}
                  className="mt-1 inline-block text-[14px] font-semibold text-amber-deep hover:underline"
                >
                  {writingStats.nextAction} →
                </Link>
              </ToolTip>
            ) : (
              <ToolTip id="dashboard.nextAction">
                <p className="mt-1 text-[14px] font-semibold text-ink-text">
                  {writingStats.nextAction}
                </p>
              </ToolTip>
            )}
            <ToolTip id="dashboard.validateStructure">
              <button
                type="button"
                onClick={() => void validateChapterStructure()}
                disabled={structureLoading}
                className={TOOLBAR_CHIP}
              >
                {structureLoading ? "Checking…" : "Validate structure"}
              </button>
            </ToolTip>
          </div>
        </div>

        <div className="mb-3 h-2 overflow-hidden rounded-full bg-ink/8">
          <div
            className="h-full rounded-full bg-amber-deep transition-all"
            style={{ width: `${writingStats.completionPct}%` }}
            role="progressbar"
            aria-valuenow={writingStats.completionPct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Manuscript completion"
          />
        </div>

        <div className="mb-3 rounded-lg border border-paper-line bg-paper/60 px-3 py-2 text-[12px] text-ink-muted">
          <div className="grid gap-1 md:grid-cols-2">
            <p className="min-w-0">
              <span className="font-semibold text-ink-text">Story data:</span>{" "}
              <code className="break-all font-mono text-[11.5px]">{project.project_path}</code>
            </p>
            <p className="min-w-0">
              <span className="font-semibold text-ink-text">Manuscript:</span>{" "}
              <code className="break-all font-mono text-[11.5px]">{project.manuscript_path}</code>
            </p>
          </div>
        </div>

        <div className="mb-3">
          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Pipeline
            </p>
            <p className="text-[12px] text-ink-muted">
              <span className="nums font-semibold text-ink-text">{writingStats.totalWords.toLocaleString()}</span>
              {" "}words ·{" "}
              <span className="nums font-semibold text-ink-text">{writingStats.chapterCount}</span>
              {" "}chapters
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PIPELINE_BUCKETS.map((step) => {
              const count = writingStats.pipeline[step as PipelineStep];
              const label = step === "none" ? "None / planned" : PIPELINE_LABELS[step];
              return (
                <ToolTip key={step} id="dashboard.pipelineFilter">
                  <button
                    type="button"
                    onClick={() => openChapters(step as PipelineStep)}
                    className={`${TOOLBAR_CHIP} gap-1.5`}
                    aria-label={`Show ${label} chapters (${count})`}
                  >
                    <span
                      className="chapter-pipeline-dot h-2 w-2 rounded-full"
                      data-pipeline={step}
                      aria-hidden
                    />
                    <span className="text-ink-muted">{label}</span>
                    <span className="nums font-semibold text-ink-text">{count}</span>
                  </button>
                </ToolTip>
              );
            })}
          </div>
        </div>

        <div className="mb-3 border-t border-paper-line pt-3">
          <button
            type="button"
            onClick={() => setProjectOpsCollapsed((c) => !c)}
            aria-expanded={!projectOpsCollapsed}
            className="flex w-full items-center justify-between gap-3 rounded-lg border border-paper-line bg-paper/70 px-3 py-2 text-left shadow-[var(--shadow-paper)] transition-colors hover:bg-ink/[0.04]"
          >
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Project Operations
            </span>
            <span className="inline-flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-ink-muted">
              {projectOpsCollapsed ? "Expand" : "Collapse"}
              <span aria-hidden className="text-[12px]">{projectOpsCollapsed ? "▸" : "▾"}</span>
            </span>
          </button>

          {!projectOpsCollapsed && (
          <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
            <div className="shrink-0">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Import
              </p>
              <ToolTip id="codex.genericImporter">
                <button
                  type="button"
                  onClick={() => setCodexTab("importer")}
                  className={`${TOOLBAR_CHIP} ${codexTab === "importer" ? TOOLBAR_CHIP_ACTIVE : ""}`}
                >
                  Generic Importer
                </button>
              </ToolTip>
            </div>
            <div className="shrink-0">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Export
              </p>
              <div className="flex flex-wrap gap-2">
                <ToolTip id="dashboard.exportManuscript">
                  <a
                    href={api.exportUrl(id)}
                    download={`${id}.md`}
                    className={TOOLBAR_CHIP}
                  >
                    Export manuscript
                  </a>
                </ToolTip>
                <ToolTip id="dashboard.exportEpub">
                  <a
                    href={api.exportEpubUrl(id)}
                    download={`${id}.epub`}
                    className={TOOLBAR_CHIP}
                  >
                    Export EPUB
                  </a>
                </ToolTip>
                <ToolTip id="dashboard.exportProject">
                  <a
                    href={api.exportProjectPackageUrl(id)}
                    download
                    className={TOOLBAR_CHIP}
                  >
                    Export project
                  </a>
                </ToolTip>
              </div>
            </div>
            <div className="shrink-0">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Workspace
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <ToolTip id="dashboard.batchExtractOutlines">
                  <button
                    type="button"
                    onClick={() => void startBatchExtractOutlines()}
                    disabled={batchOutlinesRunning || batchCodexRunning || briefsBatchRunning || titlesBatchRunning}
                    className={TOOLBAR_CHIP}
                  >
                    {batchOutlinesRunning ? "Extracting outlines…" : "Extract all outlines"}
                  </button>
                </ToolTip>
                <ToolTip id="dashboard.batchExtractCodex">
                  <button
                    type="button"
                    onClick={() => void startBatchExtractCodex()}
                    disabled={batchOutlinesRunning || batchCodexRunning || briefsBatchRunning || titlesBatchRunning}
                    className={TOOLBAR_CHIP}
                  >
                    {batchCodexRunning ? "Extracting codex…" : "Extract all codex"}
                  </button>
                </ToolTip>
                <ToolTip id="dashboard.populateChapterBriefs">
                  <button
                    type="button"
                    onClick={() => void startBatchPopulateBriefs()}
                    disabled={batchOutlinesRunning || batchCodexRunning || briefsBatchRunning || titlesBatchRunning}
                    className={TOOLBAR_CHIP}
                  >
                    {briefsBatchRunning ? "Populating briefs…" : "Populate all chapter briefs"}
                  </button>
                </ToolTip>
                <ToolTip id="dashboard.autoTitleChapters">
                  <button
                    type="button"
                    onClick={() => void startBatchAutoTitle()}
                    disabled={batchOutlinesRunning || batchCodexRunning || briefsBatchRunning || titlesBatchRunning}
                    className={TOOLBAR_CHIP}
                  >
                    {titlesBatchRunning ? "Auto-titling…" : "Auto-title chapters"}
                  </button>
                </ToolTip>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
            <div className="shrink-0">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Archive & backup
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <ToolTip id="dashboard.stashManuscript">
                  <button
                    type="button"
                    onClick={() => void stashProject()}
                    className={TOOLBAR_CHIP}
                  >
                    Stash manuscript
                  </button>
                </ToolTip>
                <ToolTip id="dashboard.backups">
                  <button
                    type="button"
                    onClick={() => setBackupsOpen(true)}
                    className={TOOLBAR_CHIP}
                  >
                    Backups
                  </button>
                </ToolTip>
              </div>
            </div>
            <div className="shrink-0">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Danger zone
              </p>
              <ToolTip id="dashboard.deleteManuscript">
                <button
                  type="button"
                  onClick={deleteProject}
                  className={TOOLBAR_CHIP_DANGER}
                >
                  Delete manuscript
                </button>
              </ToolTip>
            </div>
          </div>
          </div>
          )}
        </div>

        {(writingStats.zeroWordChapters.length > 0
          || writingStats.missingFinalChapters.length > 0
          || pendingPreviewCount > 0
          || structureReport != null) && (
          <div className="border-t border-paper-line pt-3">
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Health signals
            </p>
            <ul className="space-y-1 text-[13px] text-ink-muted">
              {structureReport != null && (
                <li>
                  <span className={`font-medium ${structureReport.ok ? "text-ink-text" : "text-red-600"}`}>
                    Structure check: {structureReport.error_count} error
                    {structureReport.error_count === 1 ? "" : "s"}, {structureReport.warning_count} warning
                    {structureReport.warning_count === 1 ? "" : "s"}
                  </span>
                  {structureReport.issues.length === 0 && " — no issues found"}
                </li>
              )}
              {structureReport?.issues.map((issue, idx) => (
                <li key={`${issue.component}-${issue.chapter ?? "project"}-${idx}`} className="pl-3">
                  <span className={issue.severity === "error" ? "font-medium text-red-600" : "font-medium text-amber-deep"}>
                    {issue.severity.toUpperCase()}
                  </span>
                  {" "}{issue.chapter != null ? `ch. ${issue.chapter}: ` : ""}
                  {issue.message}
                  {issue.action_url && (
                    <>
                      {" "}
                      <Link to={issue.action_url} className="font-semibold text-amber-deep underline-offset-2 hover:underline">
                        Open
                      </Link>
                    </>
                  )}
                  {issue.path && (
                    <code className="ml-1 break-all font-mono text-[11.5px] text-paper-muted">
                      {issue.path}
                    </code>
                  )}
                  {issue.resolution && (
                    <p className="mt-0.5 pl-5 text-[12px] text-paper-muted">
                      Resolve: {issue.resolution}
                    </p>
                  )}
                </li>
              ))}
              {writingStats.zeroWordChapters.length > 0 && (
                <li>
                  <span className="font-medium text-amber-deep">
                    {writingStats.zeroWordChapters.length} zero-word chapter
                    {writingStats.zeroWordChapters.length === 1 ? "" : "s"}
                  </span>
                  {" "}(ch. {writingStats.zeroWordChapters.join(", ")})
                </li>
              )}
              {writingStats.missingFinalChapters.length > 0 && (
                <li>
                  <span className="font-medium text-ink-text">
                    {writingStats.missingFinalChapters.length} chapter
                    {writingStats.missingFinalChapters.length === 1 ? "" : "s"} without Final
                  </span>
                  {" "}(ch. {writingStats.missingFinalChapters.join(", ")})
                </li>
              )}
              {pendingPreviewCount > 0 && (
                <li>
                  <span className="font-medium text-amber-deep">
                    {pendingPreviewCount} pending AI preview
                    {pendingPreviewCount === 1 ? "" : "s"}
                  </span>
                  {" "}awaiting review
                </li>
              )}
            </ul>
          </div>
        )}
      </section>

      <div className="mb-6 flex flex-wrap gap-x-1 gap-y-0 border-b border-paper-line pb-px">
        {([
          ["chapters", "Chapters"],
          ["cast", "Cast"],
          ["relationships", "Relationships"],
          ["family", "Family Tree"],
          ["storygraph", "Story Graph"],
          ["blueprint", "Blueprint"],
          ["timeline", "Timeline"],
          ["research", "Research Board"],
          ["map", "Map"],
          ["bible", "Story Bible"],
        ] as const).map(([tab, label]) => (
          <ToolTip key={tab} id={CODEX_TAB_TIPS[tab]}>
            <button onClick={() => setCodexTab(tab)}
                    className={`px-4 py-2.5 text-[13px] font-semibold transition-colors ${
                      codexTab === tab
                        ? "border-b-2 border-amber-deep text-ink-text"
                        : "text-ink-muted hover:text-ink-text"
                    }`}>
              {label}
              {tab === "chapters" && chapterPreviewPending && (
                <PendingAiStar title="Chapter AI preview ready to review" />
              )}
              {tab === "cast" && entityDedupStatus.ai_suggestions_ready
                && (entityDedupStatus.character_group_count ?? entityDedupStatus.ai_group_count) > 0 && (
                <PendingAiStar title="Character dedup results ready" />
              )}
              {tab === "storygraph" && entityDedupStatus.ai_suggestions_ready
                && (entityDedupStatus.plot_thread_group_count ?? 0) > 0 && (
                <PendingAiStar title="Plot dedup results ready" />
              )}
              {tab === "bible" && bibleDedupReady && (
                <PendingAiStar title="Story bible dedup results ready" />
              )}
            </button>
          </ToolTip>
        ))}
      </div>

      {codexTab === "importer" && (
        <GenericImporterPanel projectId={id} onExtracted={load} />
      )}

      {codexTab === "chapters" && (
      <>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
            Chapters
          </h2>
          <div className="mt-1.5">
            <ChapterPipelineLegend compact />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-[12px] font-semibold text-ink-muted">
            Status
            <ToolTip id="dashboard.chapterStatusFilter">
              <select
                value={chapterStatusFilter}
                onChange={(event) => setChapterStatusFilter(event.target.value as PipelineStep | "all")}
                className={TOOLBAR_FIELD}
                aria-label="Filter chapters by status"
              >
                <option value="all">All chapters</option>
                {PIPELINE_BUCKETS.map((step) => (
                  <option key={step} value={step}>
                    {step === "none" ? "Needs outline" : PIPELINE_LABELS[step]}
                  </option>
                ))}
              </select>
            </ToolTip>
          </label>
          <label className="flex items-center gap-2 text-[12px] font-semibold text-ink-muted">
            Order
            <span
              className={`rounded-md border px-2.5 py-1 text-[12px] font-medium ${
                firstGap != null
                  ? "border-red-500/40 bg-paper text-red-600"
                  : "border-st-approved/40 bg-paper text-st-approved"
              }`}
              title={firstGap != null
                ? `First gap at chapter ${firstGap}. Remove gaps to renumber sequentially.`
                : "Chapter numbers are consecutive"}
            >
              {firstGap != null ? `Gap at ch. ${firstGap}` : "Consecutive"}
            </span>
          </label>
          <ToolTip id="dashboard.removeGaps">
            <button
              type="button"
              onClick={() => void removeChapterGaps()}
              disabled={chapterOrderBusy}
              className={TOOLBAR_CHIP}
            >
              {chapterOrderBusy ? "Working…" : "Remove Gaps"}
            </button>
          </ToolTip>
          {(["board", "outline"] as const).map((v) => (
            <ToolTip key={v} id={v === "board" ? "dashboard.chapterBoard" : "dashboard.chapterOutliner"}>
              <button
                type="button"
                onClick={() => setChapterView(v)}
                className={`${TOOLBAR_CHIP} capitalize ${chapterView === v ? TOOLBAR_CHIP_ACTIVE : ""}`}
              >
                {v === "outline" ? "Outliner" : "Board"}
              </button>
            </ToolTip>
          ))}
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <ToolTip id="dashboard.pasteChapter">
          <ToolbarChip onClick={() => setPasteOpen(true)}>
            + Paste Chapter
          </ToolbarChip>
        </ToolTip>
        <ToolTip id="dashboard.chapterStyleDefaults">
          <ToolbarChip onClick={() => setStyleOpen(true)}>
            Chapter style defaults
          </ToolbarChip>
        </ToolTip>
        <ToolTip id="dashboard.planOutline">
          <ToolbarChip onClick={() => setOutlineOpen(true)}>
            Plan Outline…
          </ToolbarChip>
        </ToolTip>
        <ToolTip id="dashboard.planChapter">
          <ToolbarChip
            onClick={() => run("plan_chapter", { number: nextChapter })}
            busy={runningStage === "plan_chapter"}
            disabled={isRunning}
          >
            Plan Chapter {nextChapter}
          </ToolbarChip>
        </ToolTip>
      </div>
      {chapterStatusFilter !== "all" && (
        <p className="mb-4 rounded-lg border border-amber/25 bg-amber/5 px-4 py-2 text-[13px] text-ink-muted">
          Showing {filteredChapters.length} {chapterStatusFilter === "none" ? "Needs outline" : PIPELINE_LABELS[chapterStatusFilter]} chapter
          {filteredChapters.length === 1 ? "" : "s"}.{" "}
          <ToolTip id="dashboard.clearFilter" className="inline">
            <button
              type="button"
              onClick={() => setChapterStatusFilter("all")}
              className="font-semibold text-amber-deep hover:underline"
            >
              Clear filter
            </button>
          </ToolTip>
        </p>
      )}
      {filteredChapters.length === 0 && chapterStatusFilter !== "all" ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No chapters match this status filter.
        </div>
      ) : chapterView === "board"
        ? <ChapterBoard chapters={filteredChapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />
        : filteredChapters.length > 0
          ? <Outliner id={id} chapters={filteredChapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />
          : <ChapterBoard chapters={filteredChapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />}
      </>
      )}

      {codexTab === "cast" && (
      <>
      <MinePreviewReviewBanner
        projectId={id}
        kind="characters"
        label="character"
        onReview={(chapter, kind) => setMineReview({ chapter, kind })}
      />
      {/* Codex — cast */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Cast
        </h2>
        <div className="flex items-center gap-2">
          <ToolTip id="codex.mergeCharactersManual">
            <button onClick={() => setManualMerge("character")}
                    className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
              Merge manually…
            </button>
          </ToolTip>
          <ToolTip id="codex.resolveDuplicates">
            <button onClick={() => openDedup("character")}
                    className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-amber/10">
              Resolve duplicates{dedupBadge()}
              {entityDedupStatus.ai_suggestions_ready && !entityScanning && (
                <PendingAiStar title="AI dedup results ready to review" />
              )}
            </button>
          </ToolTip>
          <ToolTip id="codex.addCharacter">
            <button onClick={() => setCharOpen(true)}
                    className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
              + Add Character
            </button>
          </ToolTip>
        </div>
      </div>
      {characters.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No characters yet. Use <ToolTip id="codex.genericImporter" className="inline"><button type="button" onClick={() => setCodexTab("importer")} className="font-semibold text-amber-deep underline-offset-2 hover:underline">Generic Importer</button></ToolTip> or add manually.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((ch) => (
            <button key={ch.id} type="button" onClick={() => setEditCharId(ch.id)}
                    className="group relative flex items-center gap-3 rounded-xl border border-paper-line bg-paper-card p-4 text-left shadow-[var(--shadow-paper)] transition-colors hover:border-amber/40">
              <DeleteButton
                label={`Delete ${ch.full_name}`}
                message={`Remove ${ch.full_name} from the cast?`}
                onConfirm={() => deleteCharacter(ch)}
                tipId="codex.deleteCharacter"
                className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
              />
              <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full font-display text-[15px] font-semibold text-on-ink"
                    style={ch.portrait_url ? undefined : { backgroundColor: ROLE_COLOR[ch.role] ?? "var(--color-ink-muted)" }}>
                {ch.portrait_url ? (
                  <img
                    src={characterPortraitUrl(id, ch.id)}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  ch.full_name.charAt(0).toUpperCase()
                )}
              </span>
              <div className="min-w-0 pr-6">
                <p className="truncate font-display text-[15px] font-medium text-ink-text">{ch.full_name}</p>
                <p className="text-[12px] capitalize text-ink-muted">{ch.role}</p>
                {ch.aliases && ch.aliases.length > 0 && (
                  <p className="truncate text-[11px] text-ink-muted/80">
                    aka {ch.aliases.slice(0, 3).join(", ")}{ch.aliases.length > 3 ? "…" : ""}
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
      </>
      )}

      {codexTab === "relationships" && (
      <>
      <div className="mb-5">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Character Relationships
        </h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Map of labeled links between cast members. Edit labels in each character&apos;s editor.
        </p>
      </div>
      <RelationshipGraphPanel
        projectId={id}
        characters={characters}
        onSelectCharacter={(charId) => {
          setEditCharId(charId);
        }}
      />
      </>
      )}

      {codexTab === "family" && (
      <>
      <div className="mb-5">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Family Tree
        </h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Parent, child, spouse, and sibling labels arranged as a genealogy view.
        </p>
      </div>
      <GenealogyPanel
        projectId={id}
        characters={characters}
        onSelectCharacter={(charId) => {
          setEditCharId(charId);
        }}
      />
      </>
      )}

      {codexTab === "storygraph" && (
      <>
      <MinePreviewReviewBanner
        projectId={id}
        kind="plots"
        label="plot"
        onReview={(chapter, kind) => setMineReview({ chapter, kind })}
      />
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
            Story Graph / Mind Map
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            Visual plot and subplot planning — link beats to characters, then map active nodes through chapter briefs.
          </p>
        </div>
        <ToolTip id="dashboard.generateChapterBriefs">
          <button
            type="button"
            onClick={() => void generateMissingChapterBriefs()}
            className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-amber/10"
          >
            Generate chapter briefs
          </button>
        </ToolTip>
      </div>
      <StoryGraphPanel
        projectId={id}
        characters={characters}
        chapters={chapters}
      />
      </>
      )}

      {codexTab === "blueprint" && (
      <>
      <div className="mb-5">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Blueprint / Plot Canvas
        </h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Chapter cards grouped by act with story graph assignments from chapter briefs, plus plot-thread hints from outlines.
          Edit briefs on each chapter page or nodes in{" "}
          <ToolTip id="dashboard.tabStoryGraph" className="inline">
            <button type="button" onClick={() => setCodexTab("storygraph")} className="font-semibold text-amber-deep underline-offset-2 hover:underline">
              Story Graph
            </button>
          </ToolTip>.
        </p>
      </div>
      <BlueprintCanvasPanel
        projectId={id}
        chapters={chapters}
        characters={characters}
        plotThreads={plotThreads}
        onSelectPlotThread={(threadId) => {
          const thread = plotThreads.find((t) => t.id === threadId);
          if (thread) setPlotModal(thread);
        }}
        onGoToStoryGraph={() => setCodexTab("storygraph")}
      />
      </>
      )}

      {codexTab === "timeline" && (
      <>
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Timeline
        </h2>
        <ToolTip id="codex.timelineEvent">
          <button onClick={() => setTimelineModalOpen(true)}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            + Add Event
          </button>
        </ToolTip>
      </div>
      <TimelinePanel
        projectId={id}
        events={timelineEvents}
        characters={characters}
        chapters={chapters}
        onChange={load}
        onAdd={() => setTimelineModalOpen(true)}
      />
      </>
      )}

      {codexTab === "research" && (
      <>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
            Research Board
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            Pre-canon sparks — notes, links, and references that stay out of StoryState and prompts.
          </p>
        </div>
        <ToolTip id="codex.researchSpark">
          <button onClick={() => setResearchModalOpen(true)}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            + Add Spark
          </button>
        </ToolTip>
      </div>
      <ResearchBoardPanel
        projectId={id}
        sparks={researchSparks}
        characters={characters}
        chapters={chapters}
        plotThreads={plotThreads}
        onChange={load}
        onAdd={() => setResearchModalOpen(true)}
      />
      </>
      )}

      {codexTab === "map" && (
      <>
      <div className="mb-5">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Map
        </h2>
        <p className="mt-1 text-[13px] text-ink-muted">
          Upload a map image and place pins with optional lore references. Does not change Story Bible or manuscript text.
        </p>
      </div>
      <MapPanel
        projectId={id}
        onGoToBible={(section) => {
          setCodexTab("bible");
          if (section) {
            navigate(`/projects/${id}?tab=bible&section=${encodeURIComponent(section)}`);
          }
        }}
      />
      </>
      )}

      {codexTab === "bible" && (
      <>
      <MinePreviewReviewBanner
        projectId={id}
        kind="bible"
        label="story bible"
        onReview={(chapter, kind) => setMineReview({ chapter, kind })}
      />
      <StoryBiblePanel projectId={id} scrollToSection={bibleScrollSection} />
      </>
      )}

      {!dedupOpen && entityScanning && (
        <p className="fixed bottom-4 right-4 z-40 max-w-sm rounded-lg border border-amber/30 bg-paper-card px-4 py-2 text-[12.5px] text-ink-text shadow-[var(--shadow-lift)]">
          Duplicate AI scan running —{" "}
          <ToolTip id="codex.resolveDuplicates" className="inline">
            <button type="button" onClick={() => setDedupOpen(true)} className="font-semibold text-amber-deep underline-offset-2 hover:underline">
              open resolve duplicates
            </button>
          </ToolTip>
        </p>
      )}

      <StoryStyleModal
        projectId={id}
        project={project}
        open={styleOpen}
        onClose={() => setStyleOpen(false)}
        onSaved={load}
      />
      <PlanOutlineModal
        projectId={id}
        open={outlineOpen}
        onClose={() => setOutlineOpen(false)}
        onApplied={load}
      />
      <PasteChapterModal projectId={id} open={pasteOpen} onClose={() => setPasteOpen(false)}
                         onDone={load} defaultNumber={nextChapter} />
      <QuickAddCharacterModal projectId={id} open={charOpen} onClose={() => setCharOpen(false)}
                              onAdded={(c) => { load(); setEditCharId(c.id); }} />
      <CharacterEditorModal projectId={id} characterId={editCharId} open={editCharId != null}
                            onClose={() => setEditCharId(null)} onSaved={load} />
      <PlotThreadModal projectId={id} thread={plotModal === "new" ? null : plotModal}
                       open={plotModal != null} onClose={() => setPlotModal(null)} onSaved={load} />
      <TimelineEventModal
        projectId={id}
        event={null}
        open={timelineModalOpen}
        onClose={() => setTimelineModalOpen(false)}
        onSaved={load}
        characters={characters}
        defaultChapter={chapters.length > 0 ? Math.max(...chapters.map((c) => c.number)) : 1}
      />
      <ResearchSparkModal
        projectId={id}
        spark={null}
        open={researchModalOpen}
        onClose={() => setResearchModalOpen(false)}
        onSaved={load}
        characters={characters}
        chapters={chapters}
        plotThreads={plotThreads}
      />
      <RenumberChapterModal projectId={id} chapter={renumberChapter}
                           open={renumberChapter != null} onClose={() => setRenumberChapter(null)}
                           onDone={(n) => { load(); navigate(`/projects/${id}/chapters/${n}`); }} />
      <ResolveDuplicatesModal projectId={id} open={dedupOpen} onClose={() => setDedupOpen(false)}
                                onDone={load} defaultKind={dedupKind} onStatusChange={refreshEntityDedupStatus} />
      <PlotPanelIssuesModal projectId={id} open={plotPanelIssuesOpen} onClose={() => setPlotPanelIssuesOpen(false)}
                              onDone={load} />
      {manualMerge != null && (
        <ManualMergeModal projectId={id} kind={manualMerge} open
                          defaultPlotMode={manualMerge === "plot_thread" ? plotMergeMode : "parallel"}
                          onClose={() => setManualMerge(null)} onDone={load} />
      )}
      {backupsOpen && (
        <ProjectBackupsModal projectId={id} open onClose={() => setBackupsOpen(false)} onDone={load} />
      )}
      {mineReview != null && (
        <ChapterMinePreviewModal
          open
          onClose={() => setMineReview(null)}
          projectId={id}
          chapterNumber={mineReview.chapter}
          kind={mineReview.kind}
          onApplied={load}
        />
      )}
      <BatchExtractSettingsModal
        open={outlineBatchOpen}
        title="Extract chapter outlines"
        description="Run outline-from-text sequentially (one chapter at a time inside a single background job). Long chapters may use multiple LLM passes."
        loading={outlineBatchLoading}
        stats={outlineBatchStats}
        missingLabel="an outline (no saved outline or pending preview)"
        runTipId="dashboard.batchExtractOutlines"
        onClose={() => {
          setOutlineBatchOpen(false);
          setOutlineBatchStats(null);
        }}
        onRun={(opts) => void runBatchExtractOutlines(opts)}
      />
      <BatchExtractSettingsModal
        open={codexBatchOpen}
        title="Extract all codex"
        description="Mine plots, characters, and story bible from chapter prose sequentially (three LLM passes per chapter inside one background job)."
        loading={codexBatchLoading}
        stats={codexBatchStats}
        missingLabel="complete codex coverage (plots, characters, or bible preview)"
        runTipId="dashboard.batchExtractCodex"
        onClose={() => {
          setCodexBatchOpen(false);
          setCodexBatchStats(null);
        }}
        onRun={(opts) => void runBatchExtractCodex(opts)}
      />
      <BatchExtractSettingsModal
        open={briefBatchOpen}
        title="Populate chapter briefs"
        description="Generate and save chapter briefs from prose, cast, and Story Graph nodes. Briefs are written directly — there is no preview step."
        loading={false}
        stats={briefBatchStats}
        missingLabel="a saved chapter brief"
        runTipId="dashboard.populateChapterBriefs"
        showAutoAccept={false}
        onClose={() => {
          setBriefBatchOpen(false);
          setBriefBatchStats(null);
        }}
        onRun={(opts) => void runBatchPopulateBriefs(opts)}
      />
      <BatchExtractSettingsModal
        open={titleBatchOpen}
        title="Auto-title chapters"
        description="Generate short chapter titles from prose using the Architect. Manually edited titles are tracked separately and skipped unless you choose All auto-titles."
        loading={titleBatchLoading}
        stats={titleBatchStats}
        missingLabel="a manual chapter title"
        runTipId="dashboard.autoTitleChapters"
        showAutoAccept={false}
        scopeVariant="eligible-auto"
        onClose={() => {
          setTitleBatchOpen(false);
          setTitleBatchStats(null);
        }}
        onRun={(opts) => void runBatchAutoTitle(opts)}
      />
    </div>
  );
}

function StoryStyleModal({
  projectId,
  project,
  open,
  onClose,
  onSaved,
}: {
  projectId: string;
  project: ProjectDetail;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [tone, setTone] = useState("");
  const [pointOfView, setPointOfView] = useState("");
  const [tense, setTense] = useState("");
  const [proseStyle, setProseStyle] = useState("");
  const [vocabularyLevel, setVocabularyLevel] = useState("");
  const [chapterTargetWords, setChapterTargetWords] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTone(project.style?.tone ?? "neutral");
    setPointOfView(project.style?.point_of_view ?? "third_limited");
    setTense(project.style?.tense ?? "past");
    setProseStyle(project.style?.prose_style ?? "balanced");
    setVocabularyLevel(project.style?.vocabulary_level ?? "moderate");
    setChapterTargetWords(project.style?.chapter_target_words ?? "2500");
    setDescription(project.style?.description ?? "");
  }, [open, project]);

  async function save() {
    setBusy(true);
    try {
      await api.updateProjectStyle(projectId, {
        tone,
        point_of_view: pointOfView,
        tense,
        prose_style: proseStyle,
        vocabulary_level: vocabularyLevel,
        chapter_target_words: chapterTargetWords,
        description,
      });
      toast("Chapter style defaults saved", "success");
      onSaved();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title="Chapter style defaults" size="wide">
      <div className="space-y-4">
        <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
          Default tone, POV, tense, prose, and chapter length for every chapter brief. Each chapter
          inherits these until you override that field on the chapter page.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Tone default">
            <input className={fieldClass} value={tone} onChange={(e) => setTone(e.target.value)} placeholder="noir, hopeful, comic, austere..." />
          </Field>
          <Field label="Narrative POV default">
            <select className={fieldClass} value={pointOfView} onChange={(e) => setPointOfView(e.target.value)}>
              <option value="first_person">First person</option>
              <option value="second_person">Second person</option>
              <option value="third_limited">Third person limited</option>
              <option value="third_omniscient">Third person omniscient</option>
              <option value="third_objective">Third person objective</option>
              <option value="multiple_pov">Multiple POV</option>
              <option value="epistolary">Epistolary / documents</option>
              <option value="stream_of_consciousness">Stream of consciousness</option>
            </select>
          </Field>
          <Field label="Tense default">
            <select className={fieldClass} value={tense} onChange={(e) => setTense(e.target.value)}>
              <option value="past">Past</option>
              <option value="present">Present</option>
              <option value="future">Future</option>
            </select>
          </Field>
          <Field label="Prose style default">
            <input className={fieldClass} value={proseStyle} onChange={(e) => setProseStyle(e.target.value)} placeholder="balanced, lyrical, cinematic..." />
          </Field>
          <Field label="Vocabulary default">
            <input className={fieldClass} value={vocabularyLevel} onChange={(e) => setVocabularyLevel(e.target.value)} placeholder="simple, moderate, literary..." />
          </Field>
          <Field label="Target length default">
            <TargetLengthInput
              value={Number.parseInt(chapterTargetWords, 10) || DEFAULT_PROJECT_STYLE.chapter_target_words}
              onChange={(n) => setChapterTargetWords(String(n))}
              tipId="dashboard.chapterTargetDefault"
            />
          </Field>
        </div>
        <Field label="Style notes default">
          <textarea className={fieldClass} rows={4} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Any durable style/tone rules..." />
        </Field>
        <div className="flex justify-end gap-2">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="dashboard.chapterStyleDefaults">
            <button type="button" onClick={() => void save()} disabled={busy} className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Saving..." : "Save defaults"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

function PlanOutlineModal({
  projectId,
  open,
  onClose,
  onApplied,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}) {
  const toast = useToast();
  const [chapters, setChapters] = useState(12);
  const [words, setWords] = useState(24000);
  const [preview, setPreview] = useState<PlanOutlinePreview | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) setPreview(null);
  }, [open]);

  async function generatePreview() {
    setBusy(true);
    try {
      const result = await api.previewPlanOutline(projectId, { chapters, words });
      setPreview(result);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setBusy(true);
    try {
      await api.applyPlanOutline(projectId, { chapters, words });
      toast("Outline saved and missing planned chapters created", "success");
      onApplied();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title="Plan Outline" size="wide">
      <div className="space-y-4">
        <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
          Preview what will be written before saving. This uses project metadata, style, cast counts,
          Story Graph node counts, and timeline counts. Applying saves <code>outputs/outline.json</code>,
          creates missing planned chapter cards, and seeds missing chapter briefs.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Chapters">
            <input type="number" min={1} max={120} className={fieldClass} value={chapters} onChange={(e) => setChapters(Number(e.target.value) || 1)} />
          </Field>
          <Field label="Target words">
            <input type="number" min={1000} className={fieldClass} value={words} onChange={(e) => setWords(Number(e.target.value) || 1000)} />
          </Field>
        </div>
        <ToolTip id="modal.planOutline">
          <button type="button" onClick={() => void generatePreview()} disabled={busy} className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
            {busy ? "Building preview..." : "Preview outline"}
          </button>
        </ToolTip>
        {preview && (
          <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="rounded-lg border border-paper-line bg-paper px-4 py-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Context used</p>
              <ul className="space-y-1 text-[12.5px] text-ink-muted">
                {preview.context_summary.map((line) => <li key={line}>{line}</li>)}
              </ul>
            </div>
            <pre className="max-h-[48vh] overflow-auto rounded-lg border border-paper-line bg-ink p-4 text-[11.5px] leading-relaxed text-on-ink">
              {JSON.stringify(preview.outline, null, 2)}
            </pre>
          </div>
        )}
        <div className="flex justify-end gap-2">
          <ToolTip id="global.modalClose">
            <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
              Close
            </button>
          </ToolTip>
          <ToolTip id="modal.planOutline">
            <button type="button" onClick={() => void apply()} disabled={busy || !preview} className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              Save outline
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

function ToolbarChip({
  children, onClick, busy, disabled,
}: {
  children: React.ReactNode; onClick: () => void; busy?: boolean; disabled?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={TOOLBAR_CHIP}>
      {busy ? "Running…" : children}
    </button>
  );
}

function MinePreviewReviewBanner({
  projectId,
  kind,
  label,
  onReview,
}: {
  projectId: string;
  kind: MineKind;
  label: string;
  onReview: (chapter: number, kind: MineKind) => void;
}) {
  const pending = projectMinePreviewsPending(projectId, kind);
  if (pending.length === 0) return null;
  const chapters = pending.map((p) => p.chapter).join(", ");
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber/35 bg-amber/10 px-4 py-3">
      <p className="text-[13px] text-ink-text">
        <span className="font-semibold">AI {label} mining ready</span>
        {" "}for chapter{pending.length > 1 ? "s" : ""} {chapters}. Nothing changes until you review and apply.
      </p>
      <ToolTip id="modal.minePreviewReview">
        <button
          type="button"
          onClick={() => onReview(pending[0].chapter, kind)}
          className="rounded-lg bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper hover:bg-ink/90"
        >
          Review…
        </button>
      </ToolTip>
    </div>
  );
}
