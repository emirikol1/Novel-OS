import type { StoryGraphEdgeSummary, StoryGraphNodeSummary } from "../api/client";

export const NODE_KINDS = [
  "main",
  "plot_thread",
  "subplot",
  "beat",
  "character_arc",
  "mystery",
  "theme",
  "other",
] as const;

export const NODE_STATUSES = ["active", "resolved", "abandoned", "foreshadowed"] as const;

export const EDGE_KINDS = [
  "contains",
  "advances",
  "relates",
  "foreshadows",
  "resolves",
] as const;

export type GraphPosition = { x: number; y: number };

export type LayoutNode = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

const NODE_W = 148;
const NODE_H = 52;
const LAYER_GAP = 88;
const SIBLING_GAP = 24;

/** Edges whose endpoints are both story-graph node ids (excludes character_relationship). */
export function nodeDisplayEdges(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
): StoryGraphEdgeSummary[] {
  const ids = new Set(nodes.map((n) => n.id));
  return edges.filter((e) => ids.has(e.source_id) && ids.has(e.target_id));
}

export function kindLabel(kind: string): string {
  return kind.replace(/_/g, " ");
}

export const NODE_KIND_COLOR: Record<string, string> = {
  main: "var(--color-st-approved)",
  plot_thread: "var(--color-st-approved)",
  subplot: "var(--color-st-drafted)",
  beat: "var(--color-amber-deep)",
  character_arc: "var(--color-st-planned)",
  mystery: "var(--color-ink-muted)",
};

export function edgeStroke(kind: string, active = false): string {
  if (active) return "var(--color-amber-deep)";
  const map: Record<string, string> = {
    contains: "var(--color-st-approved)",
    advances: "var(--color-st-drafted)",
    foreshadows: "var(--color-st-planned)",
    resolves: "var(--color-amber-deep)",
    relates: "var(--color-paper-line)",
  };
  return map[kind] ?? "var(--color-paper-line)";
}

/** Curved SVG path between two box centers (quadratic bezier). */
export function edgeCurvePath(
  from: GraphPosition,
  to: GraphPosition,
  bend = 0.22,
): string {
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const cx = mx - dy * bend;
  const cy = my + dx * bend;
  return `M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`;
}

/**
 * Layered mind-map layout: roots (no incoming "contains") on top,
 * children below via contains edges; orphans in a bottom row.
 */
export function mindMapLayout(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
  width = 900,
): { layout: LayoutNode[]; height: number } {
  if (nodes.length === 0) {
    return { layout: [], height: 200 };
  }

  const displayEdges = nodeDisplayEdges(nodes, edges);
  const containsChildren = new Map<string, string[]>();
  const hasParent = new Set<string>();

  for (const e of displayEdges) {
    if (e.kind !== "contains") continue;
    const kids = containsChildren.get(e.source_id) ?? [];
    kids.push(e.target_id);
    containsChildren.set(e.source_id, kids);
    hasParent.add(e.target_id);
  }

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const sortNodes = (ids: string[]) =>
    [...ids].sort((a, b) => {
      const na = byId.get(a);
      const nb = byId.get(b);
      const pa = na?.priority ?? 0;
      const pb = nb?.priority ?? 0;
      if (pa !== pb) return pb - pa;
      return (na?.title ?? "").localeCompare(nb?.title ?? "");
    });

  const roots = sortNodes(
    nodes
      .filter((n) => !hasParent.has(n.id))
      .map((n) => n.id),
  );

  const layers: string[][] = [];
  const placed = new Set<string>();
  let frontier = roots;
  while (frontier.length > 0) {
    layers.push(frontier);
    frontier.forEach((id) => placed.add(id));
    const next: string[] = [];
    for (const pid of frontier) {
      for (const cid of sortNodes(containsChildren.get(pid) ?? [])) {
        if (!placed.has(cid)) next.push(cid);
      }
    }
    frontier = sortNodes([...new Set(next)]);
  }

  const orphans = sortNodes(nodes.filter((n) => !placed.has(n.id)).map((n) => n.id));
  if (orphans.length > 0) layers.push(orphans);

  const layout: LayoutNode[] = [];
  let maxRowWidth = 0;

  layers.forEach((row, layerIdx) => {
    const rowWidth = row.length * NODE_W + Math.max(0, row.length - 1) * SIBLING_GAP;
    maxRowWidth = Math.max(maxRowWidth, rowWidth);
    const startX = (width - rowWidth) / 2 + NODE_W / 2;
    const y = 48 + layerIdx * (NODE_H + LAYER_GAP) + NODE_H / 2;
    row.forEach((id, i) => {
      const x = startX + i * (NODE_W + SIBLING_GAP);
      layout.push({ id, x, y, width: NODE_W, height: NODE_H });
    });
  });

  const height = Math.max(220, 48 + layers.length * (NODE_H + LAYER_GAP) + 40);
  return { layout, height: Math.max(height, maxRowWidth > width ? height + 20 : height) };
}

export function layoutCenter(node: LayoutNode): GraphPosition {
  return { x: node.x, y: node.y };
}

export function nodeById(
  nodes: StoryGraphNodeSummary[],
): Map<string, StoryGraphNodeSummary> {
  return new Map(nodes.map((n) => [n.id, n]));
}

/** Sample graph fixtures for unit tests only — not real project data. */
export const SAMPLE_GRAPH_NODES: StoryGraphNodeSummary[] = [
  {
    id: "sg_main",
    kind: "main",
    title: "The Heist",
    description: "Steal the vault key",
    status: "active",
    priority: 5,
    linked_character_ids: ["char_a"],
    legacy_plot_thread_id: "plot_main",
    created_from: "migration",
    sort_order: 0,
    start_chapter: 1,
    resolution_chapter: null,
  },
  {
    id: "sg_sub1",
    kind: "subplot",
    title: "Vault alarm subplot",
    description: "",
    status: "active",
    priority: 3,
    linked_character_ids: [],
    legacy_plot_thread_id: "",
    created_from: "migration",
    sort_order: 1,
    start_chapter: 2,
    resolution_chapter: 8,
  },
  {
    id: "sg_sub2",
    kind: "subplot",
    title: "Inside man betrayal",
    description: "",
    status: "foreshadowed",
    priority: 4,
    linked_character_ids: ["char_b"],
    legacy_plot_thread_id: "",
    created_from: "migration",
    sort_order: 2,
    start_chapter: 1,
    resolution_chapter: null,
  },
];

export const ELIGIBILITY_GRAPH_NODES: StoryGraphNodeSummary[] = [
  ...SAMPLE_GRAPH_NODES,
  {
    id: "sg_past",
    kind: "beat",
    title: "Prologue only beat",
    description: "",
    status: "resolved",
    priority: 1,
    linked_character_ids: [],
    legacy_plot_thread_id: "",
    created_from: "migration",
    sort_order: 3,
    start_chapter: 1,
    resolution_chapter: 1,
  },
  {
    id: "sg_future",
    kind: "main",
    title: "Epilogue arc",
    description: "",
    status: "foreshadowed",
    priority: 2,
    linked_character_ids: [],
    legacy_plot_thread_id: "",
    created_from: "migration",
    sort_order: 4,
    start_chapter: 20,
    resolution_chapter: null,
  },
];

export const SAMPLE_GRAPH_EDGES: StoryGraphEdgeSummary[] = [
  { id: "e1", source_id: "sg_main", target_id: "sg_sub1", kind: "contains", label: "" },
  { id: "e2", source_id: "sg_main", target_id: "sg_sub2", kind: "contains", label: "" },
  { id: "e3", source_id: "sg_sub2", target_id: "sg_sub1", kind: "relates", label: "timed with" },
];
