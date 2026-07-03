import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  applyNodeChanges,
  useReactFlow,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type {
  ChapterSummary,
  CharacterSummary,
  StoryGraphEdgeSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { api } from "../api/client";
import ActLayerBands from "./graph/ActLayerBands";
import GraphInspector from "./graph/GraphInspector";
import GraphViewToolbar from "./graph/GraphViewToolbar";
import ToolTip from "./ToolTip";
import StoryGraphEdge from "./graph/StoryGraphEdge";
import StoryGraphNodeCard from "./graph/StoryGraphNodeCard";
import { TimelineActColumns, TimelineChapterColumns } from "./graph/TimelineColumns";
import { nodeById, nodeDisplayEdges } from "../lib/storyGraph";
import {
  actAtPosition,
  computeActBandRects,
  computeActLayerLayout,
  computeTimelineActColumns,
  computeTimelineChapterColumns,
  fromFlowPosition,
  layoutModeForView,
  primaryPinChapter,
  readGraphViewMode,
  timelineActAtPosition,
  timelineChapterAtPosition,
  toFlowEdges,
  toFlowNodes,
  writeGraphViewMode,
  type GraphViewMode,
  type StoryGraphFlowNodeData,
  type TimelineScope,
} from "../lib/storyGraphFlow";

const INSPECTOR_WIDTH_KEY = "novelos-graph-inspector-width";
const MIN_INSPECTOR = 220;
const MAX_INSPECTOR = 480;
const DEFAULT_INSPECTOR = 288;
const RADIAL_LAYOUT_SAVE_MS = 700;
const STRUCTURED_LAYOUT_SAVE_MS = 400;

const nodeTypes = { storyGraphNode: StoryGraphNodeCard };
const edgeTypes = { storyGraphEdge: StoryGraphEdge };

function readInspectorWidth(): number {
  try {
    const raw = localStorage.getItem(INSPECTOR_WIDTH_KEY);
    const n = raw ? Number(raw) : DEFAULT_INSPECTOR;
    if (!Number.isFinite(n)) return DEFAULT_INSPECTOR;
    return Math.min(MAX_INSPECTOR, Math.max(MIN_INSPECTOR, n));
  } catch {
    return DEFAULT_INSPECTOR;
  }
}

function writeInspectorWidth(width: number): void {
  try {
    localStorage.setItem(INSPECTOR_WIDTH_KEY, String(width));
  } catch {
    /* ignore quota errors */
  }
}

type GraphWorkbenchProps = {
  projectId: string;
  nodes: StoryGraphNodeSummary[];
  edges: StoryGraphEdgeSummary[];
  characters: CharacterSummary[];
  chapters?: ChapterSummary[];
  selectedId: string | null;
  linkSourceId: string | null;
  onSelectNode: (id: string | null) => void;
  onNodeClick: (id: string) => void;
  onEditNode: (node: StoryGraphNodeSummary) => void;
  onDeleteNode: (id: string) => void;
  onDeleteEdge: (edgeId: string) => void;
  onNodesChange?: (nodes: StoryGraphNodeSummary[]) => void;
};

function GraphWorkbenchInner({
  projectId,
  nodes,
  edges,
  characters,
  chapters = [],
  selectedId,
  linkSourceId,
  onSelectNode,
  onNodeClick,
  onEditNode,
  onDeleteNode,
  onDeleteEdge,
  onNodesChange,
}: GraphWorkbenchProps) {
  const { fitView, setCenter } = useReactFlow();
  const [viewMode, setViewMode] = useState<GraphViewMode>(() => readGraphViewMode());
  const [timelineScope, setTimelineScope] = useState<TimelineScope>("acts");
  const [searchQuery, setSearchQuery] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const [inspectorWidth, setInspectorWidth] = useState(readInspectorWidth);
  const [flowNodes, setFlowNodes] = useState<Node<StoryGraphFlowNodeData>[]>([]);
  const [flowEdges, setFlowEdges] = useState(() => toFlowEdges(nodes, edges));
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingLayout = useRef<Map<string, { x: number; y: number }>>(new Map());
  const dragRef = useRef<{ active: boolean; startX: number; startWidth: number }>({
    active: false,
    startX: 0,
    startWidth: DEFAULT_INSPECTOR,
  });

  const chapterCount = chapters.length;
  const layoutMode = layoutModeForView(viewMode, timelineScope);

  const charNames = useMemo(
    () => new Map(characters.map((c) => [c.id, c.full_name])),
    [characters],
  );
  const nodesMap = useMemo(() => nodeById(nodes), [nodes]);
  const displayEdges = useMemo(() => nodeDisplayEdges(nodes, edges), [nodes, edges]);

  const actBands = useMemo(
    () => (viewMode === "acts" ? computeActLayerLayout(nodes, { chapterCount }).bands : []),
    [viewMode, nodes, chapterCount],
  );
  const timelineActColumns = useMemo(
    () => (viewMode === "timeline" && timelineScope === "acts" ? computeTimelineActColumns() : []),
    [viewMode, timelineScope],
  );
  const timelineChapterColumns = useMemo(
    () =>
      viewMode === "timeline" && timelineScope === "chapters"
        ? computeTimelineChapterColumns(chapters)
        : [],
    [viewMode, timelineScope, chapters],
  );

  const searchItems = useMemo(
    () =>
      nodes.map((node) => ({
        id: node.id,
        haystack: [
          node.title,
          node.kind,
          node.description,
          node.status,
          ...node.linked_character_ids.map((cid) => charNames.get(cid) ?? cid),
        ].join(" ").toLowerCase(),
      })),
    [nodes, charNames],
  );

  const matchedIds = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return new Set<string>();
    return new Set(searchItems.filter((item) => item.haystack.includes(q)).map((item) => item.id));
  }, [searchQuery, searchItems]);

  const matchList = useMemo(
    () => searchItems.filter((item) => matchedIds.has(item.id)).map((item) => item.id),
    [searchItems, matchedIds],
  );

  const flowNodeOptions = useMemo(
    () => ({
      charNames,
      selectedId,
      linkSourceId,
      matchedIds,
      activeMatchId: matchList[matchIndex] ?? null,
      layoutMode,
      chapterCount,
      chapters,
    }),
    [charNames, selectedId, linkSourceId, matchedIds, matchList, matchIndex, layoutMode, chapterCount, chapters],
  );

  useEffect(() => {
    setMatchIndex(0);
  }, [searchQuery]);

  useEffect(() => {
    setFlowNodes(toFlowNodes(nodes, edges, flowNodeOptions));
    setFlowEdges(toFlowEdges(nodes, edges));
  }, [nodes, edges, flowNodeOptions]);

  useEffect(() => {
    fitView({ padding: 0.2, duration: 200 });
  }, [nodes.length, viewMode, timelineScope, fitView]);

  useEffect(() => {
    const activeId = matchList[matchIndex];
    if (!activeId) return;
    const target = flowNodes.find((n) => n.id === activeId);
    if (!target) return;
    setCenter(target.position.x + 80, target.position.y + 28, { zoom: 1.1, duration: 250 });
  }, [matchIndex, matchList, flowNodes, setCenter]);

  const updateLocalNode = useCallback(
    (nodeId: string, patch: Partial<StoryGraphNodeSummary>) => {
      if (!onNodesChange) return;
      onNodesChange(nodes.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)));
    },
    [nodes, onNodesChange],
  );

  const flushLayoutSave = useCallback(async () => {
    const batch = new Map(pendingLayout.current);
    pendingLayout.current.clear();
    if (batch.size === 0) return;

    const updates = [...batch.entries()];
    await Promise.all(
      updates.map(([nodeId, layout]) =>
        api.updateStoryGraphNode(projectId, nodeId, { layout }),
      ),
    );

    if (onNodesChange) {
      const next = nodes.map((node) => {
        const pos = batch.get(node.id);
        return pos ? { ...node, layout: pos } : node;
      });
      onNodesChange(next);
    }
  }, [projectId, nodes, onNodesChange]);

  const queueLayoutSave = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      pendingLayout.current.set(nodeId, fromFlowPosition(position));
      if (saveTimer.current) clearTimeout(saveTimer.current);
      const delay = viewMode === "radial" ? RADIAL_LAYOUT_SAVE_MS : STRUCTURED_LAYOUT_SAVE_MS;
      saveTimer.current = setTimeout(() => {
        saveTimer.current = null;
        void flushLayoutSave();
      }, delay);
    },
    [flushLayoutSave, viewMode],
  );

  useEffect(
    () => () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      void flushLayoutSave();
    },
    [flushLayoutSave],
  );

  const patchNodeAct = useCallback(
    async (nodeId: string, act: 1 | 2 | 3) => {
      const node = nodesMap.get(nodeId);
      if (!node || node.act === act) return;

      updateLocalNode(nodeId, { act });
      try {
        const updated = await api.updateStoryGraphNode(projectId, nodeId, { act });
        updateLocalNode(nodeId, updated);
      } catch {
        updateLocalNode(nodeId, { act: node.act });
      }
    },
    [nodesMap, projectId, updateLocalNode],
  );

  const patchNodePin = useCallback(
    async (nodeId: string, fromChapter: number | null, toChapter: number) => {
      const node = nodesMap.get(nodeId);
      if (!node || fromChapter === toChapter) return;

      const prevPins = [...(node.chapter_pins ?? [])];

      try {
        if (fromChapter && fromChapter > 0) {
          const updated = await api.pinStoryGraphNode(projectId, nodeId, {
            chapter_number: fromChapter,
            pinned: false,
          });
          updateLocalNode(nodeId, updated);
        }
        if (toChapter > 0) {
          const updated = await api.pinStoryGraphNode(projectId, nodeId, {
            chapter_number: toChapter,
            pinned: true,
          });
          updateLocalNode(nodeId, updated);
        }
      } catch {
        updateLocalNode(nodeId, { chapter_pins: prevPins });
      }
    },
    [nodesMap, projectId, updateLocalNode],
  );

  const handleStructuredDragStop = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      const node = nodesMap.get(nodeId);
      if (!node) return;

      if (viewMode === "acts") {
        const bands = actBands.length > 0 ? actBands : computeActBandRects();
        const nextAct = actAtPosition(position.y, bands);
        if ((node.act ?? 0) !== nextAct) {
          void patchNodeAct(nodeId, nextAct);
        }
        return;
      }

      if (viewMode === "timeline" && timelineScope === "acts") {
        const columns = timelineActColumns.length > 0 ? timelineActColumns : computeTimelineActColumns();
        const nextAct = timelineActAtPosition(position.x, columns);
        if ((node.act ?? 0) !== nextAct) {
          void patchNodeAct(nodeId, nextAct);
        }
        return;
      }

      if (viewMode === "timeline" && timelineScope === "chapters") {
        const columns =
          timelineChapterColumns.length > 0
            ? timelineChapterColumns
            : computeTimelineChapterColumns(chapters);
        const targetChapter = timelineChapterAtPosition(position.x, columns);
        const fromChapter = primaryPinChapter(node);
        if (fromChapter !== targetChapter) {
          void patchNodePin(nodeId, fromChapter, targetChapter);
        }
      }
    },
    [
      actBands,
      chapterCount,
      chapters,
      nodesMap,
      patchNodeAct,
      patchNodePin,
      timelineActColumns,
      timelineChapterColumns,
      timelineScope,
      viewMode,
    ],
  );

  const onNodesChangeHandler = useCallback(
    (changes: NodeChange<Node<StoryGraphFlowNodeData>>[]) => {
      setFlowNodes((current) => {
        const next = applyNodeChanges(changes, current);
        for (const change of changes) {
          if (change.type === "position" && change.dragging === false && change.position) {
            if (viewMode === "radial") {
              queueLayoutSave(change.id, change.position);
            } else {
              handleStructuredDragStop(change.id, change.position);
            }
          }
        }
        return next;
      });
    },
    [handleStructuredDragStop, queueLayoutSave, viewMode],
  );

  const changeViewMode = useCallback((mode: GraphViewMode) => {
    setViewMode(mode);
    writeGraphViewMode(mode);
    if (mode !== "timeline") {
      setTimelineScope("acts");
    }
  }, []);

  const onPaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  const onNodeClickHandler = useCallback(
    (_event: React.MouseEvent, node: Node<StoryGraphFlowNodeData>) => {
      onNodeClick(node.id);
    },
    [onNodeClick],
  );

  const onResizePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      dragRef.current = { active: true, startX: event.clientX, startWidth: inspectorWidth };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [inspectorWidth],
  );

  const onResizePointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current.active) return;
    const delta = dragRef.current.startX - event.clientX;
    const next = Math.min(MAX_INSPECTOR, Math.max(MIN_INSPECTOR, dragRef.current.startWidth + delta));
    setInspectorWidth(next);
  }, []);

  const onResizePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragRef.current.active) return;
      dragRef.current.active = false;
      event.currentTarget.releasePointerCapture(event.pointerId);
      writeInspectorWidth(inspectorWidth);
    },
    [inspectorWidth],
  );

  const selected = selectedId ? nodesMap.get(selectedId) ?? null : null;

  const timelineBreadcrumb =
    viewMode === "timeline" ? (
      <nav
        aria-label="Timeline view"
        className="flex flex-wrap items-center gap-1 border-t border-paper-line/60 px-3 py-1.5 text-[11.5px]"
      >
        <span className="font-semibold text-ink-muted">Timeline</span>
        <span className="text-ink-muted/60">›</span>
        <ToolTip id="graph.chapterDrillDown">
          <button
            type="button"
            onClick={() => setTimelineScope("acts")}
            className={`rounded px-1.5 py-0.5 font-semibold ${
              timelineScope === "acts"
                ? "bg-ink/10 text-ink-text"
                : "text-amber-deep hover:underline"
            }`}
          >
            Act overview
          </button>
        </ToolTip>
        {timelineScope === "chapters" && (
          <>
            <span className="text-ink-muted/60">›</span>
            <span className="font-semibold text-ink-text">Chapter pins</span>
          </>
        )}
        {timelineScope === "acts" ? (
          <ToolTip id="graph.chapterDrillDown">
            <button
              type="button"
              onClick={() => setTimelineScope("chapters")}
              className="ml-auto rounded-lg border border-paper-line px-2 py-0.5 text-[11px] font-semibold text-ink-text hover:bg-ink/5"
            >
              Chapter drill-down
            </button>
          </ToolTip>
        ) : (
          <ToolTip id="graph.chapterDrillDown">
            <button
              type="button"
              onClick={() => setTimelineScope("acts")}
              className="ml-auto rounded-lg border border-paper-line px-2 py-0.5 text-[11px] font-semibold text-ink-text hover:bg-ink/5"
            >
              Back to acts
            </button>
          </ToolTip>
        )}
      </nav>
    ) : undefined;

  return (
    <div className="overflow-hidden rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]">
      <GraphViewToolbar
        viewMode={viewMode}
        onViewModeChange={changeViewMode}
        onFitView={() => fitView({ padding: 0.2, duration: 300 })}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        matchCount={matchList.length}
        matchIndex={matchIndex}
        onPrevMatch={() => setMatchIndex((i) => (matchList.length ? (i - 1 + matchList.length) % matchList.length : 0))}
        onNextMatch={() => setMatchIndex((i) => (matchList.length ? (i + 1) % matchList.length : 0))}
        timelineBreadcrumb={timelineBreadcrumb}
      />
      <div className="flex min-h-[520px]">
        <div className="relative min-w-0 flex-1">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodesChange={onNodesChangeHandler}
            onNodeClick={onNodeClickHandler}
            onPaneClick={onPaneClick}
            fitView
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
            className="bg-paper/40"
          >
            <defs>
              <marker
                id="sg-flow-arrow"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-ink-muted)" />
              </marker>
            </defs>
            {viewMode === "acts" && actBands.length > 0 && <ActLayerBands bands={actBands} />}
            {viewMode === "timeline" && timelineScope === "acts" && timelineActColumns.length > 0 && (
              <TimelineActColumns columns={timelineActColumns} />
            )}
            {viewMode === "timeline" && timelineScope === "chapters" && timelineChapterColumns.length > 0 && (
              <TimelineChapterColumns columns={timelineChapterColumns} />
            )}
            <Background gap={20} size={1} color="var(--color-paper-line)" />
            <Controls showInteractive={false} className="!border-paper-line !bg-paper-card !shadow-[var(--shadow-paper)]" />
          </ReactFlow>
        </div>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize inspector"
          className="w-1 shrink-0 cursor-col-resize bg-paper-line hover:bg-amber/40"
          onPointerDown={onResizePointerDown}
          onPointerMove={onResizePointerMove}
          onPointerUp={onResizePointerUp}
        />
        <ToolTip id="graph.inspector" className="shrink-0">
          <aside
            className="shrink-0 overflow-y-auto border-l border-paper-line p-4"
            style={{ width: inspectorWidth }}
          >
            <GraphInspector
              node={selected}
              charNames={charNames}
              edges={displayEdges}
              nodesMap={nodesMap}
              onEdit={() => selected && onEditNode(selected)}
              onDelete={() => selected && onDeleteNode(selected.id)}
              onDeleteEdge={onDeleteEdge}
            />
          </aside>
        </ToolTip>
      </div>
    </div>
  );
}

export default function GraphWorkbench(props: GraphWorkbenchProps) {
  return (
    <ReactFlowProvider>
      <GraphWorkbenchInner {...props} />
    </ReactFlowProvider>
  );
}
