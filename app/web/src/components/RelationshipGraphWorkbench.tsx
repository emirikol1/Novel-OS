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
import type { CharacterSummary } from "../api/client";
import {
  computeRelationshipLayout,
  readRelationshipLayout,
  toRelationshipFlowEdges,
  toRelationshipFlowNodes,
  writeRelationshipLayout,
  type RelationshipFlowNodeData,
} from "../lib/relationshipGraphFlow";
import type { RelationshipEdge } from "../lib/characterRelationships";
import RelationshipEdgeComponent from "./graph/RelationshipEdge";
import ToolTip from "./ToolTip";
import RelationshipNodeCard from "./graph/RelationshipNodeCard";

const INSPECTOR_WIDTH_KEY = "novelos-relationship-inspector-width";
const MIN_INSPECTOR = 220;
const MAX_INSPECTOR = 420;
const DEFAULT_INSPECTOR = 280;
const LAYOUT_SAVE_MS = 700;

const nodeTypes = { relationshipNode: RelationshipNodeCard };
const edgeTypes = { relationshipEdge: RelationshipEdgeComponent };

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

type RelationshipGraphWorkbenchProps = {
  projectId: string;
  characters: CharacterSummary[];
  edges: RelationshipEdge[];
  selectedId: string | null;
  linkSourceId: string | null;
  onSelectCharacter: (id: string | null) => void;
  onNodeClick: (id: string) => void;
  onEditCharacter: (id: string) => void;
};

function RelationshipGraphWorkbenchInner({
  projectId,
  characters,
  edges,
  selectedId,
  linkSourceId,
  onSelectCharacter,
  onNodeClick,
  onEditCharacter,
}: RelationshipGraphWorkbenchProps) {
  const { fitView, setCenter } = useReactFlow();
  const [searchQuery, setSearchQuery] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const [inspectorWidth, setInspectorWidth] = useState(readInspectorWidth);
  const [flowNodes, setFlowNodes] = useState<Node<RelationshipFlowNodeData>[]>([]);
  const [flowEdges, setFlowEdges] = useState(() => toRelationshipFlowEdges(edges));
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingLayout = useRef<Record<string, { x: number; y: number }>>({});
  const dragRef = useRef<{ active: boolean; startX: number; startWidth: number }>({
    active: false,
    startX: 0,
    startWidth: DEFAULT_INSPECTOR,
  });

  const nameById = useMemo(
    () => new Map(characters.map((c) => [c.id, c.full_name])),
    [characters],
  );
  const roleById = useMemo(
    () => new Map(characters.map((c) => [c.id, c.role])),
    [characters],
  );

  const nodeIds = useMemo(
    () =>
      [...characters]
        .map((c) => c.id)
        .sort((a, b) => (nameById.get(a) ?? "").localeCompare(nameById.get(b) ?? "")),
    [characters, nameById],
  );

  const savedLayout = useMemo(() => readRelationshipLayout(projectId), [projectId]);
  const positions = useMemo(
    () => computeRelationshipLayout(nodeIds, savedLayout),
    [nodeIds, savedLayout],
  );

  const searchItems = useMemo(
    () =>
      characters.map((character) => ({
        id: character.id,
        haystack: [
          character.full_name,
          character.role,
          ...edges
            .filter((edge) => edge.fromId === character.id || edge.toId === character.id)
            .map((edge) => edge.label),
        ].join(" ").toLowerCase(),
      })),
    [characters, edges],
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
      selectedId,
      linkSourceId,
      matchedIds,
      activeMatchId: matchList[matchIndex] ?? null,
    }),
    [selectedId, linkSourceId, matchedIds, matchList, matchIndex],
  );

  useEffect(() => {
    setMatchIndex(0);
  }, [searchQuery]);

  useEffect(() => {
    setFlowNodes(toRelationshipFlowNodes(nodeIds, nameById, roleById, positions, flowNodeOptions));
    setFlowEdges(toRelationshipFlowEdges(edges));
  }, [nodeIds, nameById, roleById, positions, flowNodeOptions, edges]);

  useEffect(() => {
    fitView({ padding: 0.2, duration: 200 });
  }, [characters.length, fitView]);

  useEffect(() => {
    const activeId = matchList[matchIndex];
    if (!activeId) return;
    const target = flowNodes.find((n) => n.id === activeId);
    if (!target) return;
    setCenter(target.position.x + 74, target.position.y + 28, { zoom: 1.1, duration: 250 });
  }, [matchIndex, matchList, flowNodes, setCenter]);

  const flushLayoutSave = useCallback(() => {
    const batch = { ...pendingLayout.current };
    pendingLayout.current = {};
    if (Object.keys(batch).length === 0) return;
    const merged = { ...readRelationshipLayout(projectId), ...batch };
    writeRelationshipLayout(projectId, merged);
  }, [projectId]);

  const queueLayoutSave = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      pendingLayout.current[nodeId] = position;
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        saveTimer.current = null;
        flushLayoutSave();
      }, LAYOUT_SAVE_MS);
    },
    [flushLayoutSave],
  );

  useEffect(
    () => () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      flushLayoutSave();
    },
    [flushLayoutSave],
  );

  const onNodesChangeHandler = useCallback(
    (changes: NodeChange<Node<RelationshipFlowNodeData>>[]) => {
      setFlowNodes((current) => {
        const next = applyNodeChanges(changes, current);
        for (const change of changes) {
          if (change.type === "position" && change.dragging === false && change.position) {
            queueLayoutSave(change.id, change.position);
          }
        }
        return next;
      });
    },
    [queueLayoutSave],
  );

  const onPaneClick = useCallback(() => {
    onSelectCharacter(null);
  }, [onSelectCharacter]);

  const onNodeClickHandler = useCallback(
    (_event: React.MouseEvent, node: Node<RelationshipFlowNodeData>) => {
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

  const selected = selectedId ? characters.find((c) => c.id === selectedId) ?? null : null;
  const selectedEdges = selectedId
    ? edges.filter((edge) => edge.fromId === selectedId || edge.toId === selectedId)
    : [];

  return (
    <div className="overflow-hidden rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]">
      <div className="border-b border-paper-line bg-paper-card/80">
        <div className="flex flex-wrap items-center gap-2 px-3 py-2">
          <div className="flex min-w-[180px] flex-1 items-center gap-1">
            <ToolTip id="graph.searchRelationships" className="min-w-0 flex-1">
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search characters, roles, relationships…"
                className="w-full max-w-xs rounded-lg border border-paper-line bg-paper px-2.5 py-1 text-[12px] text-ink-text placeholder:text-ink-muted"
                aria-label="Search relationship graph"
              />
            </ToolTip>
            {matchList.length > 0 && (
              <div className="flex items-center gap-0.5 text-[11px] text-ink-muted">
                <ToolTip id="graph.searchPrevNext">
                  <button
                    type="button"
                    onClick={() => setMatchIndex((i) => (matchList.length ? (i - 1 + matchList.length) % matchList.length : 0))}
                    className="rounded px-1 hover:bg-ink/5"
                    aria-label="Previous match"
                  >
                    ‹
                  </button>
                </ToolTip>
                <span>{matchIndex + 1}/{matchList.length}</span>
                <ToolTip id="graph.searchPrevNext">
                  <button
                    type="button"
                    onClick={() => setMatchIndex((i) => (matchList.length ? (i + 1) % matchList.length : 0))}
                    className="rounded px-1 hover:bg-ink/5"
                    aria-label="Next match"
                  >
                    ›
                  </button>
                </ToolTip>
              </div>
            )}
          </div>
          <ToolTip id="graph.fitView">
            <button
              type="button"
              onClick={() => fitView({ padding: 0.2, duration: 300 })}
              className="rounded-lg border border-paper-line px-2.5 py-1 text-[11.5px] font-semibold text-ink-text hover:bg-ink/5"
            >
              Fit view
            </button>
          </ToolTip>
        </div>
      </div>
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
                id="rel-flow-arrow"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-ink-muted)" />
              </marker>
            </defs>
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
        <aside
          className="shrink-0 overflow-y-auto border-l border-paper-line p-4"
          style={{ width: inspectorWidth }}
        >
          {selected ? (
            <div className="space-y-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                  Character
                </p>
                <h3 className="mt-1 font-display text-[18px] font-semibold text-ink-text">
                  {selected.full_name}
                </h3>
                <p className="mt-0.5 text-[12px] capitalize text-ink-muted">{selected.role}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                  Relationships
                </p>
                {selectedEdges.length === 0 ? (
                  <p className="mt-2 text-[12.5px] text-ink-muted">No links yet.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {selectedEdges.map((edge) => {
                      const outbound = edge.fromId === selected.id;
                      const otherId = outbound ? edge.toId : edge.fromId;
                      const otherName = nameById.get(otherId) ?? otherId;
                      return (
                        <li
                          key={`${edge.fromId}|${edge.toId}|${edge.label}`}
                          className="rounded-lg border border-paper-line bg-paper px-2.5 py-2 text-[12px]"
                        >
                          {outbound ? (
                            <>
                              <span className="font-medium text-ink-text">{edge.label}</span>
                              <span className="text-ink-muted"> → </span>
                              <ToolTip id="codex.genealogyCharacter" className="inline">
                                <button
                                  type="button"
                                  className="font-semibold text-amber-deep hover:underline"
                                  onClick={() => onSelectCharacter(otherId)}
                                >
                                  {otherName}
                                </button>
                              </ToolTip>
                            </>
                          ) : (
                            <>
                              <ToolTip id="codex.genealogyCharacter" className="inline">
                                <button
                                  type="button"
                                  className="font-semibold text-amber-deep hover:underline"
                                  onClick={() => onSelectCharacter(otherId)}
                                >
                                  {otherName}
                                </button>
                              </ToolTip>
                              <span className="text-ink-muted"> — {edge.label}</span>
                            </>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <ToolTip id="graph.editCharacter">
                <button
                  type="button"
                  onClick={() => onEditCharacter(selected.id)}
                  className="w-full rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800"
                >
                  Edit character
                </button>
              </ToolTip>
            </div>
          ) : (
            <div className="text-[13px] text-ink-muted">
              <p className="font-semibold text-ink-text">Inspector</p>
              <p className="mt-2 leading-relaxed">
                Click a character to inspect relationships. Drag nodes to arrange the map.
                Use <span className="font-semibold text-ink-text">Link characters</span> to add a
                relationship from one cast member to another.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function RelationshipGraphWorkbench(props: RelationshipGraphWorkbenchProps) {
  return (
    <ReactFlowProvider>
      <RelationshipGraphWorkbenchInner {...props} />
    </ReactFlowProvider>
  );
}
