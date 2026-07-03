import type {
  CharacterSummary,
  StoryGraphEdgeSummary,
  StoryGraphNodeSummary,
} from "../api/client";
import { kindLabel } from "./storyGraph";

export type GraphFocusFilters = {
  search: string;
  kind: string;
  status: string;
};

export type ContainsHierarchy = {
  roots: string[];
  children: Map<string, string[]>;
  orphans: string[];
};

export function characterNameMap(characters: CharacterSummary[]): Map<string, string> {
  return new Map(characters.map((c) => [c.id, c.full_name]));
}

export function nodeMatchesSearch(
  node: StoryGraphNodeSummary,
  query: string,
  characterNames: Map<string, string>,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    node.title,
    node.description,
    kindLabel(node.kind),
    node.kind,
    node.status,
    ...node.linked_character_ids.map((id) => characterNames.get(id) ?? id),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

export function nodeMatchesFilters(
  node: StoryGraphNodeSummary,
  filters: GraphFocusFilters,
  characterNames: Map<string, string>,
): boolean {
  if (filters.kind !== "all" && node.kind !== filters.kind) return false;
  if (filters.status !== "all" && node.status !== filters.status) return false;
  return nodeMatchesSearch(node, filters.search, characterNames);
}

export function filterMatchingNodes(
  nodes: StoryGraphNodeSummary[],
  filters: GraphFocusFilters,
  characterNames: Map<string, string>,
): StoryGraphNodeSummary[] {
  return nodes.filter((node) => nodeMatchesFilters(node, filters, characterNames));
}

export function buildContainsHierarchy(
  nodes: StoryGraphNodeSummary[],
  edges: StoryGraphEdgeSummary[],
): ContainsHierarchy {
  const ids = new Set(nodes.map((n) => n.id));
  const children = new Map<string, string[]>();
  const hasParent = new Set<string>();

  for (const edge of edges) {
    if (edge.kind !== "contains") continue;
    if (!ids.has(edge.source_id) || !ids.has(edge.target_id)) continue;
    const kids = children.get(edge.source_id) ?? [];
    kids.push(edge.target_id);
    children.set(edge.source_id, kids);
    hasParent.add(edge.target_id);
  }

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const sortIds = (nodeIds: string[]) =>
    [...nodeIds].sort((a, b) => {
      const na = byId.get(a);
      const nb = byId.get(b);
      const pa = na?.priority ?? 0;
      const pb = nb?.priority ?? 0;
      if (pa !== pb) return pb - pa;
      return (na?.title ?? "").localeCompare(nb?.title ?? "");
    });

  for (const [parentId, kids] of children) {
    children.set(parentId, sortIds(kids));
  }

  const roots = sortIds(nodes.filter((n) => !hasParent.has(n.id)).map((n) => n.id));
  const inTree = new Set<string>();
  const visit = (id: string) => {
    if (inTree.has(id)) return;
    inTree.add(id);
    for (const kid of children.get(id) ?? []) visit(kid);
  };
  for (const root of roots) visit(root);

  const orphans = sortIds(nodes.filter((n) => !inTree.has(n.id)).map((n) => n.id));

  return { roots, children, orphans };
}

export function collectBranchIds(
  rootId: string,
  children: Map<string, string[]>,
): string[] {
  const out: string[] = [];
  const visit = (id: string) => {
    out.push(id);
    for (const kid of children.get(id) ?? []) visit(kid);
  };
  visit(rootId);
  return out;
}

export function mergeIds(selected: string[], add: string[]): string[] {
  const next = new Set(selected);
  for (const id of add) next.add(id);
  return [...next];
}

export function removeIds(selected: string[], remove: string[]): string[] {
  const drop = new Set(remove);
  return selected.filter((id) => !drop.has(id));
}

export function normalizeStartChapter(startChapter?: number): number {
  const value = startChapter ?? 0;
  return value <= 0 ? 1 : value;
}

export function nodeEligibleAtChapter(
  node: StoryGraphNodeSummary,
  chapterNumber: number,
): boolean {
  if (chapterNumber < 1) return false;
  const start = normalizeStartChapter(node.start_chapter);
  if (chapterNumber < start) return false;
  const resolution = node.resolution_chapter;
  if (resolution != null && chapterNumber > resolution) return false;
  return true;
}

export function lifespanLabel(node: StoryGraphNodeSummary): string {
  const start = normalizeStartChapter(node.start_chapter);
  const resolution = node.resolution_chapter;
  if (resolution == null) return `Ch. ${start}–`;
  if (start === resolution) return `Ch. ${start}`;
  return `Ch. ${start}–${resolution}`;
}

export type BriefEligibilityPartition = {
  inEffect: StoryGraphNodeSummary[];
  eligibleNotInEffect: StoryGraphNodeSummary[];
  outOfRange: StoryGraphNodeSummary[];
};

export function partitionNodesByBriefEligibility(
  nodes: StoryGraphNodeSummary[],
  chapterNumber: number,
  activeIds: string[],
): BriefEligibilityPartition {
  const activeSet = new Set(activeIds);
  const inEffect: StoryGraphNodeSummary[] = [];
  const eligibleNotInEffect: StoryGraphNodeSummary[] = [];
  const outOfRange: StoryGraphNodeSummary[] = [];

  for (const node of nodes) {
    if (activeSet.has(node.id)) {
      inEffect.push(node);
      continue;
    }
    if (nodeEligibleAtChapter(node, chapterNumber)) {
      eligibleNotInEffect.push(node);
    } else {
      outOfRange.push(node);
    }
  }

  return { inEffect, eligibleNotInEffect, outOfRange };
}

export function groupNodesByKind(
  nodes: StoryGraphNodeSummary[],
): { kind: string; nodes: StoryGraphNodeSummary[] }[] {
  const byKind = new Map<string, StoryGraphNodeSummary[]>();
  for (const node of nodes) {
    const list = byKind.get(node.kind) ?? [];
    list.push(node);
    byKind.set(node.kind, list);
  }
  return [...byKind.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([kind, groupNodes]) => ({
      kind,
      nodes: [...groupNodes].sort((a, b) => {
        const pa = a.priority ?? 0;
        const pb = b.priority ?? 0;
        if (pa !== pb) return pb - pa;
        return a.title.localeCompare(b.title);
      }),
    }));
}
