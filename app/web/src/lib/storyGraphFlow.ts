import type { Edge, Node } from "@xyflow/react";
import type {
  ChapterSummary,
  StoryGraphEdgeSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { actSplitIndices } from "./blueprintCanvas";
import { isChapterBeatGraphNodeId, kindLabel, nodeDisplayEdges } from "./storyGraph";

export const FLOW_NODE_WIDTH = 168;
export const FLOW_NODE_HEIGHT = 56;

export const GRAPH_VIEW_MODE_KEY = "novel-os:graph-view-mode";

export type GraphViewMode = "radial" | "acts" | "timeline";
export type GraphLayoutMode = "radial" | "acts" | "timeline-acts" | "timeline-chapters";
export type TimelineScope = "acts" | "chapters";
export type ActNumber = 1 | 2 | 3;

export const ACT_NUMBERS: ActNumber[] = [1, 2, 3];

export const ACT_LABELS: Record<ActNumber, string> = {
  1: "Act I — Setup",
  2: "Act II — Confrontation",
  3: "Act III — Resolution",
};

export const ACT_BAND_HEIGHT = 220;
export const ACT_BAND_GAP = 28;
export const ACT_LAYOUT_WIDTH = 960;
export const ACT_LAYOUT_PADDING = 48;
export const ACT_NODE_SLOT_W = 176;
export const ACT_NODE_SLOT_H = 68;

export const TIMELINE_ACT_COL_WIDTH = 280;
export const TIMELINE_CHAPTER_POOL_WIDTH = 200;
export const TIMELINE_CHAPTER_COL_WIDTH = 132;
export const TIMELINE_LAYOUT_PADDING = 40;
export const TIMELINE_ROW_HEIGHT = 72;

export type StoryGraphFlowNodeData = {
  node: StoryGraphNodeSummary;
  charNames: Map<string, string>;
  selected: boolean;
  linkHighlight: boolean;
  searchMatch: boolean;
  activeSearchMatch: boolean;
};

export type StoryGraphFlowEdgeData = {
  edge: StoryGraphEdgeSummary;
  label: string;
};

export interface ActBandRect {
  act: ActNumber;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
}

export interface ActLayerLayoutResult {
  positions: Map<string, { x: number; y: number }>;
  bands: ActBandRect[];
}

export interface TimelineActColumn {
  act: ActNumber;
  label: string;
  x: number;
  width: number;
}

export interface TimelineChapterColumn {
  chapterNumber: number;
  label: string;
  x: number;
  width: number;
  pool?: boolean;
}

const BASE_RADIUS = 130;
const RADIUS_STEP = 110;

function sortNodes(
  nodes: StoryGraphNodeSummary[],
): StoryGraphNodeSummary[] {
  return [...nodes].sort((a, b) => {
    const pa = a.priority ?? 0;
    const pb = b.priority ?? 0;
    if (pa !== pb) return pb - pa;
    return (a.title ?? "").localeCompare(b.title ?? "");
  });
}

function sortNodeIds(
  ids: string[],
  byId: Map<string, StoryGraphNodeSummary>,
): string[] {
  return [...ids].sort((a, b) => {
    const na = byId.get(a);
    const nb = byId.get(b);
    const pa = na?.priority ?? 0;
    const pb = nb?.priority ?? 0;
    if (pa !== pb) return pb - pa;
    return (na?.title ?? "").localeCompare(nb?.title ?? "");
  });
}

function buildContainsTree(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
): { children: Map<string, string[]>; roots: string[]; orphans: string[] } {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const displayEdges = nodeDisplayEdges(nodes, edges);
  const children = new Map<string, string[]>();
  const hasParent = new Set<string>();

  for (const edge of displayEdges) {
    if (edge.kind !== "contains") continue;
    const kids = children.get(edge.source_id) ?? [];
    kids.push(edge.target_id);
    children.set(edge.source_id, kids);
    hasParent.add(edge.target_id);
  }

  for (const [id, kids] of children) {
    children.set(id, sortNodeIds(kids, byId));
  }

  const roots = sortNodeIds(
    nodes.filter((n) => !hasParent.has(n.id)).map((n) => n.id),
    byId,
  );
  const placed = new Set<string>();
  const markPlaced = (id: string) => {
    placed.add(id);
    for (const kid of children.get(id) ?? []) markPlaced(kid);
  };
  roots.forEach(markPlaced);
  const orphans = sortNodeIds(
    nodes.filter((n) => !placed.has(n.id)).map((n) => n.id),
    byId,
  );

  return { children, roots, orphans };
}

function layoutSubtree(
  nodeId: string,
  angle: number,
  depth: number,
  center: { x: number; y: number },
  children: Map<string, string[]>,
  positions: Map<string, { x: number; y: number }>,
): void {
  const radius = depth === 0 ? 0 : BASE_RADIUS + (depth - 1) * RADIUS_STEP;
  const x = center.x + radius * Math.cos(angle);
  const y = center.y + radius * Math.sin(angle);
  positions.set(nodeId, { x, y });

  const kids = children.get(nodeId) ?? [];
  if (kids.length === 0) return;

  const span =
    kids.length === 1
      ? 0
      : Math.min(Math.PI * 1.6, Math.max((Math.PI / 5) * kids.length, Math.PI / 2));
  const start = angle - span / 2;
  const step = kids.length === 1 ? 0 : span / Math.max(1, kids.length - 1);

  kids.forEach((childId, index) => {
    const childAngle = kids.length === 1 ? angle : start + index * step;
    layoutSubtree(childId, childAngle, depth + 1, center, children, positions);
  });
}

/** Resolve act assignment: explicit act field, else infer from start_chapter. */
export function resolveNodeAct(
  node: StoryGraphNodeSummary,
  chapterCount = 0,
): ActNumber {
  const act = node.act ?? 0;
  if (act >= 1 && act <= 3) return act as ActNumber;

  const start = node.start_chapter ?? 0;
  if (start > 0 && chapterCount > 0) {
    const [act1Len, act2Len] = actSplitIndices(chapterCount);
    if (start <= act1Len) return 1;
    if (start <= act1Len + act2Len) return 2;
    return 3;
  }

  return 1;
}

export function readGraphViewMode(): GraphViewMode {
  try {
    const value = localStorage.getItem(GRAPH_VIEW_MODE_KEY);
    if (value === "radial" || value === "acts" || value === "timeline") return value;
  } catch {
    /* ignore */
  }
  return "radial";
}

export function writeGraphViewMode(mode: GraphViewMode): void {
  try {
    localStorage.setItem(GRAPH_VIEW_MODE_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function layoutModeForView(
  viewMode: GraphViewMode,
  timelineScope: TimelineScope,
): GraphLayoutMode {
  if (viewMode === "acts") return "acts";
  if (viewMode === "timeline") {
    return timelineScope === "chapters" ? "timeline-chapters" : "timeline-acts";
  }
  return "radial";
}

/** Radial tree layout from contains edges; orphans on an outer ring. */
export function computeRadialLayout(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
  center = { x: 400, y: 320 },
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (nodes.length === 0) return positions;

  const { children, roots, orphans } = buildContainsTree(nodes, edges);

  if (roots.length === 0) {
    const span = Math.PI * 2;
    nodes.forEach((node, index) => {
      const angle = (index / nodes.length) * span - Math.PI / 2;
      positions.set(node.id, {
        x: center.x + BASE_RADIUS * Math.cos(angle),
        y: center.y + BASE_RADIUS * Math.sin(angle),
      });
    });
    return positions;
  }

  if (roots.length === 1) {
    layoutSubtree(roots[0], -Math.PI / 2, 0, center, children, positions);
  } else {
    const span = Math.PI * 2;
    roots.forEach((rootId, index) => {
      const angle = (index / roots.length) * span - Math.PI / 2;
      layoutSubtree(rootId, angle, 1, center, children, positions);
    });
  }

  if (orphans.length > 0) {
    const outer = BASE_RADIUS + RADIUS_STEP * 3;
    orphans.forEach((id, index) => {
      const angle = (index / orphans.length) * Math.PI * 2 - Math.PI / 2;
      positions.set(id, {
        x: center.x + outer * Math.cos(angle),
        y: center.y + outer * Math.sin(angle),
      });
    });
  }

  return positions;
}

export function computeActBandRects(
  width = ACT_LAYOUT_WIDTH,
): ActBandRect[] {
  const innerWidth = width - ACT_LAYOUT_PADDING * 2;
  return ACT_NUMBERS.map((act, index) => ({
    act,
    label: ACT_LABELS[act],
    x: ACT_LAYOUT_PADDING,
    y: ACT_LAYOUT_PADDING + index * (ACT_BAND_HEIGHT + ACT_BAND_GAP),
    width: innerWidth,
    height: ACT_BAND_HEIGHT,
    depth: (3 - index) * 4,
  }));
}

/** Stack nodes in horizontal act bands (2.5D canvas coordinates). */
export function computeActLayerLayout(
  nodes: StoryGraphNodeSummary[],
  options?: { chapterCount?: number; width?: number },
): ActLayerLayoutResult {
  const width = options?.width ?? ACT_LAYOUT_WIDTH;
  const chapterCount = options?.chapterCount ?? 0;
  const bands = computeActBandRects(width);
  const positions = new Map<string, { x: number; y: number }>();
  const byAct = new Map<ActNumber, StoryGraphNodeSummary[]>(
    ACT_NUMBERS.map((act) => [act, []]),
  );

  for (const node of sortNodes(nodes)) {
    const act = resolveNodeAct(node, chapterCount);
    byAct.get(act)?.push(node);
  }

  for (const band of bands) {
    const row = byAct.get(band.act) ?? [];
    row.forEach((node, index) => {
      const col = index % Math.max(1, Math.floor(band.width / ACT_NODE_SLOT_W));
      const rowIndex = Math.floor(index / Math.max(1, Math.floor(band.width / ACT_NODE_SLOT_W)));
      positions.set(node.id, {
        x: band.x + 24 + col * ACT_NODE_SLOT_W,
        y: band.y + 36 + rowIndex * ACT_NODE_SLOT_H,
      });
    });
  }

  return { positions, bands };
}

export function actAtPosition(
  y: number,
  bands: ActBandRect[],
): ActNumber {
  for (const band of bands) {
    if (y >= band.y && y < band.y + band.height) return band.act;
  }
  const last = bands[bands.length - 1];
  if (last && y >= last.y + last.height) return 3;
  return 1;
}

export function computeTimelineActColumns(
  width = ACT_LAYOUT_WIDTH,
): TimelineActColumn[] {
  const colWidth = Math.floor((width - TIMELINE_LAYOUT_PADDING * 2) / 3);
  return ACT_NUMBERS.map((act, index) => ({
    act,
    label: ACT_LABELS[act],
    x: TIMELINE_LAYOUT_PADDING + index * colWidth,
    width: colWidth,
  }));
}

/** Timeline act overview — three columns by act assignment. */
export function computeTimelineActOverviewLayout(
  nodes: StoryGraphNodeSummary[],
  options?: { chapterCount?: number; width?: number },
): Map<string, { x: number; y: number }> {
  const width = options?.width ?? ACT_LAYOUT_WIDTH;
  const chapterCount = options?.chapterCount ?? 0;
  const columns = computeTimelineActColumns(width);
  const positions = new Map<string, { x: number; y: number }>();
  const byAct = new Map<ActNumber, StoryGraphNodeSummary[]>(
    ACT_NUMBERS.map((act) => [act, []]),
  );

  for (const node of sortNodes(nodes)) {
    byAct.get(resolveNodeAct(node, chapterCount))?.push(node);
  }

  for (const column of columns) {
    const row = byAct.get(column.act) ?? [];
    row.forEach((node, index) => {
      positions.set(node.id, {
        x: column.x + 16,
        y: TIMELINE_LAYOUT_PADDING + 48 + index * TIMELINE_ROW_HEIGHT,
      });
    });
  }

  return positions;
}

export function timelineActAtPosition(
  x: number,
  columns: TimelineActColumn[],
): ActNumber {
  for (const column of columns) {
    if (x >= column.x && x < column.x + column.width) return column.act;
  }
  return columns[columns.length - 1]?.act ?? 1;
}

export function primaryPinChapter(node: StoryGraphNodeSummary): number | null {
  const pins = [...(node.chapter_pins ?? [])].sort((a, b) => a - b);
  return pins[0] ?? null;
}

export function computeTimelineChapterColumns(
  chapters: ChapterSummary[],
): TimelineChapterColumn[] {
  const sorted = [...chapters].sort((a, b) => a.number - b.number);
  const pool: TimelineChapterColumn = {
    chapterNumber: 0,
    label: "Unpinned",
    x: TIMELINE_LAYOUT_PADDING,
    width: TIMELINE_CHAPTER_POOL_WIDTH,
    pool: true,
  };
  const chapterCols = sorted.map((chapter, index) => ({
    chapterNumber: chapter.number,
    label: `Ch. ${chapter.number}`,
    x:
      TIMELINE_LAYOUT_PADDING
      + TIMELINE_CHAPTER_POOL_WIDTH
      + 16
      + index * TIMELINE_CHAPTER_COL_WIDTH,
    width: TIMELINE_CHAPTER_COL_WIDTH,
  }));
  return [pool, ...chapterCols];
}

/** Timeline chapter drill-down — pool column + one column per chapter. */
export function computeTimelineChapterLayout(
  nodes: StoryGraphNodeSummary[],
  chapters: ChapterSummary[],
): Map<string, { x: number; y: number }> {
  const columns = computeTimelineChapterColumns(chapters);
  const positions = new Map<string, { x: number; y: number }>();
  const byColumn = new Map<number, StoryGraphNodeSummary[]>();
  for (const column of columns) {
    byColumn.set(column.chapterNumber, []);
  }

  for (const node of sortNodes(nodes)) {
    const pin = primaryPinChapter(node);
    const key = pin ?? 0;
    byColumn.get(key)?.push(node);
  }

  for (const column of columns) {
    const row = byColumn.get(column.chapterNumber) ?? [];
    row.forEach((node, index) => {
      positions.set(node.id, {
        x: column.x + 12,
        y: TIMELINE_LAYOUT_PADDING + 48 + index * TIMELINE_ROW_HEIGHT,
      });
    });
  }

  return positions;
}

export function timelineChapterAtPosition(
  x: number,
  columns: TimelineChapterColumn[],
): number {
  for (const column of columns) {
    if (x >= column.x && x < column.x + column.width) return column.chapterNumber;
  }
  return columns[columns.length - 1]?.chapterNumber ?? 0;
}

/** Prefer persisted node.layout over auto-computed positions (radial only). */
export function mergePersistedLayout(
  nodes: StoryGraphNodeSummary[],
  computed: Map<string, { x: number; y: number }>,
): Map<string, { x: number; y: number }> {
  const positions = new Map(computed);
  for (const node of nodes) {
    if (node.layout != null) {
      positions.set(node.id, { x: node.layout.x, y: node.layout.y });
    }
  }
  return positions;
}

export function fromFlowPosition(position: { x: number; y: number }): { x: number; y: number } {
  return {
    x: Math.round(position.x * 10) / 10,
    y: Math.round(position.y * 10) / 10,
  };
}

export function computeLayoutPositions(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
  layoutMode: GraphLayoutMode,
  options?: {
    center?: { x: number; y: number };
    chapterCount?: number;
    chapters?: ChapterSummary[];
  },
): Map<string, { x: number; y: number }> {
  switch (layoutMode) {
    case "acts": {
      return computeActLayerLayout(nodes, {
        chapterCount: options?.chapterCount ?? 0,
      }).positions;
    }
    case "timeline-acts":
      return computeTimelineActOverviewLayout(nodes, {
        chapterCount: options?.chapterCount ?? 0,
      });
    case "timeline-chapters":
      return computeTimelineChapterLayout(nodes, options?.chapters ?? []);
    default: {
      const computed = computeRadialLayout(nodes, edges, options?.center);
      return mergePersistedLayout(nodes, computed);
    }
  }
}

export function toFlowNodes(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
  options: {
    charNames: Map<string, string>;
    selectedId?: string | null;
    linkSourceId?: string | null;
    matchedIds?: Set<string>;
    activeMatchId?: string | null;
    center?: { x: number; y: number };
    layoutMode?: GraphLayoutMode;
    chapterCount?: number;
    chapters?: ChapterSummary[];
  },
): Node<StoryGraphFlowNodeData>[] {
  const layoutMode = options.layoutMode ?? "radial";
  const positions = computeLayoutPositions(nodes, edges, layoutMode, {
    center: options.center,
    chapterCount: options.chapterCount,
    chapters: options.chapters,
  });

  return nodes.map((node) => ({
    id: node.id,
    type: "storyGraphNode",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    draggable: !isChapterBeatGraphNodeId(node.id),
    data: {
      node,
      charNames: options.charNames,
      selected: options.selectedId === node.id,
      linkHighlight: options.linkSourceId === node.id,
      searchMatch: options.matchedIds?.has(node.id) ?? false,
      activeSearchMatch: options.activeMatchId === node.id,
    },
  }));
}

export function toFlowEdges(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
): Edge<StoryGraphFlowEdgeData>[] {
  return nodeDisplayEdges(nodes, edges).map((edge) => ({
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    type: "storyGraphEdge",
    data: {
      edge,
      label: edge.label || kindLabel(edge.kind),
    },
  }));
}
