import type { Edge, Node } from "@xyflow/react";
import { circularLayout, type RelationshipEdge } from "./characterRelationships";

export type RelationshipFlowNodeData = {
  characterId: string;
  name: string;
  role: string;
  selected: boolean;
  linkHighlight: boolean;
  searchMatch: boolean;
  activeSearchMatch: boolean;
};

export type RelationshipFlowEdgeData = {
  edge: RelationshipEdge;
  label: string;
  curvature: number;
  labelSide: number;
  labelPosition: number;
  sourceHandle: string;
  targetHandle: string;
};

export type FocusedRelationshipGraph = {
  nodeIds: string[];
  edges: RelationshipEdge[];
  focusId: string | null;
  incomingIds: Set<string>;
  outgoingIds: Set<string>;
  hiddenNodeCount: number;
};

const DEFAULT_CURVATURE = 0.25;
const LABEL_OFFSET_PX = 22;

const HANDLE_PRIMARY_SOURCE = "source-bottom";
const HANDLE_PRIMARY_TARGET = "target-top";
const HANDLE_ALT_SOURCE = "source-right";
const HANDLE_ALT_TARGET = "target-left";

export type ReciprocalEdgeLayout = {
  curvature: number;
  labelSide: number;
  labelPosition: number;
  sourceHandle: string;
  targetHandle: string;
};

/** Route reciprocal A→B / B→A edges on opposite sides with separated labels. */
export function reciprocalEdgeStyle(
  edge: RelationshipEdge,
  edgeKeys: Set<string>,
): ReciprocalEdgeLayout {
  if (!edgeKeys.has(`${edge.toId}|${edge.fromId}`)) {
    return {
      curvature: DEFAULT_CURVATURE,
      labelSide: 0,
      labelPosition: 0.5,
      sourceHandle: HANDLE_PRIMARY_SOURCE,
      targetHandle: HANDLE_PRIMARY_TARGET,
    };
  }
  const lo = edge.fromId < edge.toId ? edge.fromId : edge.toId;
  const loToHi = edge.fromId === lo;
  if (loToHi) {
    return {
      curvature: 0.22,
      labelSide: 1,
      labelPosition: 0.34,
      sourceHandle: HANDLE_PRIMARY_SOURCE,
      targetHandle: HANDLE_PRIMARY_TARGET,
    };
  }
  return {
    curvature: 0.22,
    labelSide: -1,
    labelPosition: 0.66,
    sourceHandle: HANDLE_ALT_SOURCE,
    targetHandle: HANDLE_ALT_TARGET,
  };
}

export { LABEL_OFFSET_PX };

const LAYOUT_KEY_PREFIX = "novelos-relationship-layout-";
const DEFAULT_CENTER = { x: 400, y: 300 };
const NODE_OFFSET = { x: -74, y: -28 };

export function relationshipLayoutKey(projectId: string): string {
  return `${LAYOUT_KEY_PREFIX}${projectId}`;
}

export function readRelationshipLayout(projectId: string): Record<string, { x: number; y: number }> {
  try {
    const raw = localStorage.getItem(relationshipLayoutKey(projectId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, { x: number; y: number }>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeRelationshipLayout(
  projectId: string,
  layout: Record<string, { x: number; y: number }>,
): void {
  try {
    localStorage.setItem(relationshipLayoutKey(projectId), JSON.stringify(layout));
  } catch {
    /* ignore quota errors */
  }
}

/** Focus relationship maps to one character plus immediate incoming/outgoing links. */
export function focusedRelationshipGraph(
  nodeIds: string[],
  edges: RelationshipEdge[],
  focusId?: string | null,
): FocusedRelationshipGraph {
  if (!focusId || !nodeIds.includes(focusId)) {
    return {
      nodeIds,
      edges,
      focusId: null,
      incomingIds: new Set(),
      outgoingIds: new Set(),
      hiddenNodeCount: 0,
    };
  }

  const visibleIds = new Set([focusId]);
  const incomingIds = new Set<string>();
  const outgoingIds = new Set<string>();

  for (const edge of edges) {
    if (edge.fromId === focusId) {
      visibleIds.add(edge.toId);
      outgoingIds.add(edge.toId);
    }
    if (edge.toId === focusId) {
      visibleIds.add(edge.fromId);
      incomingIds.add(edge.fromId);
    }
  }

  const focusedNodeIds = nodeIds.filter((id) => visibleIds.has(id));
  return {
    nodeIds: focusedNodeIds,
    edges: edges.filter((edge) => visibleIds.has(edge.fromId) && visibleIds.has(edge.toId)),
    focusId,
    incomingIds,
    outgoingIds,
    hiddenNodeCount: Math.max(0, nodeIds.length - focusedNodeIds.length),
  };
}

/** Merge saved positions with a radial fallback for new characters. */
export function computeRelationshipLayout(
  nodeIds: string[],
  savedLayout: Record<string, { x: number; y: number }>,
  center = DEFAULT_CENTER,
  radius = 260,
): Map<string, { x: number; y: number }> {
  const auto = circularLayout(nodeIds, center.x * 2, center.y * 2, radius);
  const positions = new Map<string, { x: number; y: number }>();
  for (const id of nodeIds) {
    const saved = savedLayout[id];
    const fallback = auto.get(id);
    if (saved) {
      positions.set(id, saved);
    } else if (fallback) {
      positions.set(id, {
        x: fallback.x + NODE_OFFSET.x,
        y: fallback.y + NODE_OFFSET.y,
      });
    }
  }
  return positions;
}

export function toRelationshipFlowNodes(
  nodeIds: string[],
  nameById: Map<string, string>,
  roleById: Map<string, string>,
  positions: Map<string, { x: number; y: number }>,
  options: {
    selectedId?: string | null;
    linkSourceId?: string | null;
    matchedIds?: Set<string>;
    activeMatchId?: string | null;
  } = {},
): Node<RelationshipFlowNodeData>[] {
  return nodeIds.map((id) => {
    const pos = positions.get(id) ?? { x: 0, y: 0 };
    return {
      id,
      type: "relationshipNode",
      position: pos,
      draggable: true,
      data: {
        characterId: id,
        name: nameById.get(id) ?? id,
        role: roleById.get(id) ?? "minor",
        selected: options.selectedId === id,
        linkHighlight: options.linkSourceId === id,
        searchMatch: options.matchedIds?.has(id) ?? false,
        activeSearchMatch: options.activeMatchId === id,
      },
    };
  });
}

export function toRelationshipFlowEdges(edges: RelationshipEdge[]): Edge<RelationshipFlowEdgeData>[] {
  const edgeKeys = new Set(edges.map((e) => `${e.fromId}|${e.toId}`));
  return edges.map((edge) => {
    const style = reciprocalEdgeStyle(edge, edgeKeys);
    return {
      id: `${edge.fromId}|${edge.toId}|${edge.label}`,
      source: edge.fromId,
      target: edge.toId,
      sourceHandle: style.sourceHandle,
      targetHandle: style.targetHandle,
      type: "relationshipEdge",
      label: edge.label,
      data: { edge, label: edge.label, ...style },
      markerEnd: "url(#rel-flow-arrow)",
    };
  });
}
