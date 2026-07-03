import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type ChapterBriefSummary,
  type ChapterSummary,
  type CharacterSummary,
  type PlotThreadSummary,
  type StoryGraphNodeSummary,
} from "../api/client";
import ChapterPipelineStatus from "./ChapterPipelineStatus";
import MindMapViewport, { type MindMapSearchItem } from "./MindMapViewport";
import ToolTip from "./ToolTip";
import {
  applyBriefsToBlueprintCanvas,
  buildBlueprintCanvas,
  chapterMatchesGraphNode,
  graphNodesOnCanvas,
  readBlueprintViewMode,
  writeBlueprintViewMode,
  type BlueprintChapterCard,
  type BlueprintViewMode,
} from "../lib/blueprintCanvas";
import { kindLabel } from "../lib/storyGraph";

const THREAD_TYPE_COLOR: Record<string, string> = {
  main: "var(--color-amber-deep)",
  subplot: "var(--color-st-drafted)",
  character_arc: "var(--color-st-approved)",
  mystery: "var(--color-st-planned)",
};

const NODE_KIND_COLOR: Record<string, string> = {
  main: "var(--color-st-approved)",
  plot_thread: "var(--color-st-approved)",
  subplot: "var(--color-st-drafted)",
  beat: "var(--color-amber-deep)",
  character_arc: "var(--color-st-planned)",
  mystery: "var(--color-ink-muted)",
};

export default function BlueprintCanvasPanel({
  projectId,
  chapters,
  characters,
  plotThreads,
  onSelectPlotThread,
  onGoToStoryGraph,
}: {
  projectId: string;
  chapters: ChapterSummary[];
  characters: CharacterSummary[];
  plotThreads: PlotThreadSummary[];
  onSelectPlotThread: (threadId: string) => void;
  onGoToStoryGraph?: () => void;
}) {
  const [viewMode, setViewMode] = useState<BlueprintViewMode>(() => readBlueprintViewMode());
  const [outlinesByChapter, setOutlinesByChapter] = useState<Map<number, string | null>>(new Map());
  const [briefsByChapter, setBriefsByChapter] = useState<Map<number, ChapterBriefSummary | null>>(
    () => new Map(),
  );
  const [graphNodes, setGraphNodes] = useState<StoryGraphNodeSummary[]>([]);
  const [loadingOutlines, setLoadingOutlines] = useState(false);
  const [loadingBriefs, setLoadingBriefs] = useState(false);
  const [outlineError, setOutlineError] = useState<string | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [filterGraphNodeId, setFilterGraphNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (chapters.length === 0) {
      setOutlinesByChapter(new Map());
      return;
    }
    let cancelled = false;
    setLoadingOutlines(true);
    setOutlineError(null);
    Promise.all(
      chapters.map(async (c) => {
        try {
          const stages = await api.stages(projectId, c.number);
          return [c.number, stages.outline] as const;
        } catch {
          return [c.number, null] as const;
        }
      }),
    )
      .then((rows) => {
        if (cancelled) return;
        setOutlinesByChapter(new Map(rows));
      })
      .catch((e) => {
        if (!cancelled) setOutlineError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingOutlines(false);
      });
    return () => { cancelled = true; };
  }, [projectId, chapters]);

  useEffect(() => {
    let cancelled = false;
    api.storyGraphNodes(projectId)
      .then((nodes) => { if (!cancelled) setGraphNodes(nodes); })
      .catch(() => { if (!cancelled) setGraphNodes([]); });
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    if (chapters.length === 0) {
      setBriefsByChapter(new Map());
      return;
    }
    let cancelled = false;
    setLoadingBriefs(true);
    setBriefError(null);
    Promise.all(
      chapters.map(async (c) => {
        try {
          const brief = await api.getChapterBrief(projectId, c.number);
          return [c.number, brief] as const;
        } catch {
          return [c.number, null] as const;
        }
      }),
    )
      .then((rows) => {
        if (cancelled) return;
        setBriefsByChapter(new Map(rows));
      })
      .catch((e) => {
        if (!cancelled) setBriefError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingBriefs(false);
      });
    return () => { cancelled = true; };
  }, [projectId, chapters]);

  const lanes = useMemo(() => {
    const base = buildBlueprintCanvas(
      chapters,
      outlinesByChapter,
      plotThreads,
      viewMode === "compact" ? 72 : 140,
    );
    return applyBriefsToBlueprintCanvas(base, briefsByChapter, characters, graphNodes);
  }, [chapters, outlinesByChapter, briefsByChapter, characters, graphNodes, plotThreads, viewMode]);

  const threadsOnCanvas = useMemo(() => {
    const ids = new Set<string>();
    for (const lane of lanes) {
      for (const card of lane.chapters) {
        for (const t of card.plotThreads) ids.add(t.id);
      }
    }
    return plotThreads.filter((t) => ids.has(t.id));
  }, [lanes, plotThreads]);

  const nodesOnCanvas = useMemo(() => graphNodesOnCanvas(lanes), [lanes]);
  const searchItems = useMemo<MindMapSearchItem[]>(
    () =>
      lanes.flatMap((lane) =>
        lane.chapters.map((card) => ({
          id: String(card.chapter.number),
          label: `${card.chapter.title || "Untitled"} Chapter ${card.chapter.number}`,
          detail: [
            lane.label,
            card.chapter.pov,
            card.brief?.povName,
            card.brief?.activeCharacterNames.join(" "),
            card.brief?.activeNodes.map((node) => `${node.title} ${kindLabel(node.kind)}`).join(" "),
            card.brief?.requiredBeatsSummary,
            card.outlineSnippet,
            card.plotThreads.map((thread) => thread.name).join(" "),
          ].join(" "),
        })),
      ),
    [lanes],
  );

  useEffect(() => {
    if (filterGraphNodeId && !nodesOnCanvas.some((n) => n.id === filterGraphNodeId)) {
      setFilterGraphNodeId(null);
    }
  }, [filterGraphNodeId, nodesOnCanvas]);

  function changeViewMode(mode: BlueprintViewMode) {
    setViewMode(mode);
    writeBlueprintViewMode(mode);
  }

  function toggleGraphNodeFilter(nodeId: string) {
    setFilterGraphNodeId((prev) => (prev === nodeId ? null : nodeId));
  }

  const loadingMeta = loadingOutlines || loadingBriefs;

  if (chapters.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-12 text-center">
        <p className="font-display text-[18px] text-ink-text">No chapters to map yet</p>
        <p className="mt-2 text-[13.5px] text-ink-muted">
          Plan or paste a chapter first, then return here to see your blueprint board.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-ink-muted">
          Chapter planning board — story graph assignments from chapter briefs, with plot-thread hints from outlines.
          {loadingMeta && (
            <span className="ml-2 text-[12px] text-amber-deep">Loading chapter data…</span>
          )}
        </p>
        <div className="flex overflow-hidden rounded-lg border border-paper-line">
          {(["detailed", "compact"] as const).map((mode) => (
            <ToolTip key={mode} id="graph.blueprintViewMode">
              <button
                type="button"
                onClick={() => changeViewMode(mode)}
                className={`px-3.5 py-1.5 text-[12.5px] font-medium capitalize transition-colors ${
                  viewMode === mode ? "bg-ink text-on-ink" : "text-ink-muted hover:bg-ink/5"
                }`}
              >
                {mode}
              </button>
            </ToolTip>
          ))}
        </div>
      </div>

      {outlineError && (
        <p className="mb-4 rounded-lg border border-amber/30 bg-amber/5 px-4 py-2 text-[13px] text-ink-text">
          Some outlines could not be loaded — thread badges may be incomplete.
        </p>
      )}

      {briefError && (
        <p className="mb-4 rounded-lg border border-amber/30 bg-amber/5 px-4 py-2 text-[13px] text-ink-text">
          Some chapter briefs could not be loaded — graph assignments may be incomplete.
        </p>
      )}

      {nodesOnCanvas.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            Graph nodes on board
          </span>
          {nodesOnCanvas.map((n) => (
            <ToolTip key={n.id} id="graph.blueprintFilterNode">
              <button
                type="button"
                onClick={() => toggleGraphNodeFilter(n.id)}
                className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[12px] font-medium transition-colors ${
                  filterGraphNodeId === n.id
                    ? "border-amber-deep bg-amber/10 text-amber-deep"
                    : "border-paper-line bg-paper text-ink-text hover:border-amber/40"
                }`}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: NODE_KIND_COLOR[n.kind] ?? "var(--color-ink-muted)" }}
                  aria-hidden
                />
                {n.title}
              </button>
            </ToolTip>
          ))}
          {filterGraphNodeId && (
            <ToolTip id="graph.blueprintFilterNode">
              <button
                type="button"
                onClick={() => setFilterGraphNodeId(null)}
                className="text-[12px] font-semibold text-amber-deep hover:underline"
              >
                Clear filter
              </button>
            </ToolTip>
          )}
        </div>
      )}

      {nodesOnCanvas.length === 0 && graphNodes.length > 0 && !loadingBriefs && (
        <div className="mb-5 rounded-lg border border-dashed border-paper-line bg-paper-card/40 px-5 py-4 text-[13px] text-ink-muted">
          Story graph nodes exist but none are assigned in chapter briefs yet. Open a chapter and use{" "}
          <span className="font-semibold text-ink-text">Chapter brief</span>
          {" "}to link active nodes, or edit them in{" "}
          {onGoToStoryGraph ? (
            <ToolTip id="dashboard.tabStoryGraph" className="inline">
              <button
                type="button"
                onClick={onGoToStoryGraph}
                className="font-semibold text-amber-deep hover:underline"
              >
                Story Graph
              </button>
            </ToolTip>
          ) : (
            "Story Graph"
          )}.
        </div>
      )}

      {plotThreads.length === 0 ? (
        <div className="mb-5 rounded-lg border border-dashed border-paper-line bg-paper-card/40 px-5 py-4 text-[13px] text-ink-muted">
          No plot threads defined.{" "}
          {onGoToStoryGraph ? (
            <ToolTip id="dashboard.tabStoryGraph" className="inline">
              <button
                type="button"
                onClick={onGoToStoryGraph}
                className="font-semibold text-amber-deep hover:underline"
              >
                Add plots in Story Graph
              </button>
            </ToolTip>
          ) : (
            "Add plots in Story Graph"
          )}
          {" "}to see outline-based thread badges as secondary context.
        </div>
      ) : threadsOnCanvas.length === 0 && !loadingOutlines ? (
        <div className="mb-5 rounded-lg border border-dashed border-paper-line bg-paper-card/40 px-5 py-4 text-[13px] text-ink-muted">
          Plot threads exist but none appear in chapter outlines yet. Mention thread names in outlines
          or open{" "}
          {onGoToStoryGraph ? (
            <ToolTip id="dashboard.tabStoryGraph" className="inline">
              <button
                type="button"
                onClick={onGoToStoryGraph}
                className="font-semibold text-amber-deep hover:underline"
              >
                Story Graph
              </button>
            </ToolTip>
          ) : (
            "Story Graph"
          )}
          {" "}to edit them.
        </div>
      ) : threadsOnCanvas.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            Threads from outlines
          </span>
          {threadsOnCanvas.map((t) => (
            <ToolTip key={t.id} id="graph.legacyPlotThreads">
              <button
                type="button"
                onClick={() => onSelectPlotThread(t.id)}
                className="inline-flex items-center gap-1.5 rounded-md border border-paper-line bg-paper px-2.5 py-1 text-[12px] font-medium text-ink-text transition-colors hover:border-amber/40"
                title={`Open ${t.name}`}
              >
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: THREAD_TYPE_COLOR[t.thread_type] ?? "var(--color-ink-muted)" }}
                aria-hidden
              />
              {t.name}
              </button>
            </ToolTip>
          ))}
        </div>
      )}

      <ToolTip id="graph.blueprintCanvas" className="block">
        <MindMapViewport
          title="Blueprint Mind Map"
          searchItems={searchItems}
          searchPlaceholder="Search chapters, POV, graph nodes, beats..."
        >
        {({ matchedIds, activeMatchId }) => (
          <div className="w-max min-w-[960px] space-y-6 pr-8">
            {lanes.map((lane) => (
              <section
                key={lane.act}
                className="rounded-xl border border-paper-line bg-paper-card/50 p-4 shadow-[var(--shadow-paper)]"
                aria-label={lane.label}
              >
                <div className="mb-3 flex items-baseline justify-between gap-2">
                  <h3 className="font-display text-[15px] font-semibold text-ink-text">{lane.label}</h3>
                  <span className="text-[12px] text-ink-muted">
                    {lane.chapters.length} chapter{lane.chapters.length === 1 ? "" : "s"}
                  </span>
                </div>

                {lane.chapters.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-paper-line/80 px-4 py-6 text-center text-[13px] text-ink-muted">
                    No chapters in this act yet.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-3">
                    {lane.chapters.map((card) => (
                      <BlueprintChapterCard
                        key={card.chapter.number}
                        projectId={projectId}
                        card={card}
                        compact={viewMode === "compact"}
                        dimmed={!chapterMatchesGraphNode(card, filterGraphNodeId)}
                        searchMatch={matchedIds.has(String(card.chapter.number))}
                        activeSearchMatch={activeMatchId === String(card.chapter.number)}
                        onSelectPlotThread={onSelectPlotThread}
                      />
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </MindMapViewport>
      </ToolTip>
    </div>
  );
}

function BlueprintChapterCard({
  projectId,
  card,
  compact,
  dimmed,
  searchMatch,
  activeSearchMatch,
  onSelectPlotThread,
}: {
  projectId: string;
  card: BlueprintChapterCard;
  compact: boolean;
  dimmed: boolean;
  searchMatch: boolean;
  activeSearchMatch: boolean;
  onSelectPlotThread: (threadId: string) => void;
}) {
  const { chapter, outlineSnippet: snippet, plotThreads, brief } = card;
  const chapterUrl = `/projects/${projectId}/chapters/${chapter.number}`;
  const povLabel = brief?.povName ?? (chapter.pov ? chapter.pov : null);
  const castLabel = brief?.activeCharacterNames.length
    ? compact
      ? `${brief.activeCharacterNames.length} cast`
      : brief.activeCharacterNames.join(", ")
    : null;

  return (
    <article
      className={`flex w-full flex-col rounded-xl border bg-paper-card shadow-[var(--shadow-paper)] transition-[transform,box-shadow,opacity] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] sm:w-[calc(50%-0.375rem)] lg:w-[calc(33.333%-0.5rem)] ${
        compact ? "p-3" : "p-4"
      } ${searchMatch ? "border-amber-deep ring-2 ring-amber/30" : "border-paper-line"} ${
        activeSearchMatch ? "bg-amber/10" : ""
      } ${dimmed ? "opacity-40" : ""}`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="nums text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-muted">
            Ch. {chapter.number}
          </p>
          <Link
            to={chapterUrl}
            className="mt-0.5 block truncate font-display text-[15px] font-medium text-ink-text hover:text-amber-deep"
          >
            {chapter.title || "Untitled"}
          </Link>
        </div>
        <ChapterPipelineStatus chapter={chapter} />
      </div>

      {!compact && (
        <div className="mb-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-ink-muted">
          {povLabel && (
            <span>
              POV <span className="font-medium text-ink-text">{povLabel}</span>
              {brief?.povName && !chapter.pov && (
                <span className="text-[11px] text-ink-muted"> (brief)</span>
              )}
            </span>
          )}
          {castLabel && (
            <span title={brief?.activeCharacterNames.join(", ")}>
              Cast: <span className="font-medium text-ink-text">{castLabel}</span>
            </span>
          )}
          <span className="nums">{chapter.word_count.toLocaleString()} words</span>
        </div>
      )}

      {compact && povLabel && (
        <p className="mb-1 text-[11px] text-ink-muted">
          POV <span className="font-medium text-ink-text">{povLabel}</span>
        </p>
      )}

      {brief?.requiredBeatsSummary && (
        <p
          className={`mb-2 text-[12px] leading-snug text-ink-text ${compact ? "line-clamp-2" : "line-clamp-3"}`}
          title={brief.requiredBeatsSummary}
        >
          <span className="font-semibold text-ink-muted">Beats: </span>
          {brief.requiredBeatsSummary}
        </p>
      )}

      {snippet && (
        <p className={`mb-2 text-[12px] leading-snug text-ink-muted ${compact ? "line-clamp-2" : "line-clamp-3"}`}>
          {snippet}
        </p>
      )}

      {(brief?.activeNodes.length ?? 0) > 0 && (
        <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
          {brief!.activeNodes.map((n) => (
            <span
              key={n.id}
              className="inline-flex max-w-full items-center gap-1 rounded-md border border-amber/25 bg-amber/5 px-2 py-0.5 text-[11px] font-medium text-ink-text"
              title={`${kindLabel(n.kind)} — from chapter brief`}
            >
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: NODE_KIND_COLOR[n.kind] ?? "var(--color-ink-muted)" }}
                aria-hidden
              />
              <span className="truncate">{n.title}</span>
            </span>
          ))}
        </div>
      )}

      {plotThreads.length > 0 && (
        <div className={`flex flex-wrap gap-1.5 ${brief?.activeNodes.length ? "mt-1.5" : "mt-auto pt-1"}`}>
          {plotThreads.map((t) => (
            <ToolTip key={t.id} id="graph.legacyPlotThreads">
              <button
                type="button"
                onClick={() => onSelectPlotThread(t.id)}
                className="inline-flex max-w-full items-center gap-1 rounded-md border border-paper-line bg-paper px-2 py-0.5 text-[11px] font-medium text-ink-muted transition-colors hover:border-amber/40 hover:text-ink-text"
                title={`Matched “${t.matchedLabel}” in outline — open plot thread`}
              >
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: THREAD_TYPE_COLOR[t.thread_type] ?? "var(--color-ink-muted)" }}
                aria-hidden
              />
              <span className="truncate">{t.name}</span>
              </button>
            </ToolTip>
          ))}
        </div>
      )}

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[12px]">
        <Link
          to={chapterUrl}
          className="font-semibold text-amber-deep hover:underline"
        >
          Open chapter →
        </Link>
        <Link
          to={chapterUrl}
          className="font-semibold text-ink-muted hover:text-amber-deep hover:underline"
        >
          Edit brief →
        </Link>
      </div>
    </article>
  );
}
