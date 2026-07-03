/** Family-oriented relationship labels stored on Character.relationships values. */
export type FamilyKind =
  | "parent"
  | "child"
  | "spouse"
  | "sibling"
  | "guardian"
  | "adopted";

export type RelationshipEdge = {
  fromId: string;
  toId: string;
  label: string;
  familyKind: FamilyKind | null;
};

export type CharacterRelationships = {
  id: string;
  full_name: string;
  role?: string;
  relationships?: Record<string, string>;
};

const PARENT_LABELS = new Set([
  "parent", "mother", "father", "mom", "dad", "mum", "ma", "pa",
]);
const CHILD_LABELS = new Set([
  "child", "son", "daughter", "kid",
]);
const SIBLING_LABELS = new Set([
  "sibling", "brother", "sister", "twin",
]);
const SPOUSE_LABELS = new Set([
  "spouse", "husband", "wife", "partner", "fiancé", "fiance", "fiancee",
]);
const GUARDIAN_LABELS = new Set(["guardian", "ward"]);
const ADOPTED_LABELS = new Set(["adopted", "adoptive", "foster"]);

/** Normalize a relationship label for token matching. */
export function normalizeRelationshipLabel(label: string): string {
  return label.trim().toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
}

/** Classify a free-text relationship label into a family category when possible. */
export function classifyRelationshipLabel(label: string): FamilyKind | null {
  const norm = normalizeRelationshipLabel(label);
  if (!norm) return null;
  const tokens = norm.split(" ");
  const has = (set: Set<string>) => tokens.some((t) => set.has(t)) || [...set].some((w) => norm.includes(w));

  if (has(ADOPTED_LABELS)) return "adopted";
  if (has(GUARDIAN_LABELS)) return "guardian";
  if (has(PARENT_LABELS)) return "parent";
  if (has(CHILD_LABELS)) return "child";
  if (has(SIBLING_LABELS)) return "sibling";
  if (has(SPOUSE_LABELS)) return "spouse";
  return null;
}

/** Build directed edges from each character's relationships map (keys = other character ids). */
export function buildRelationshipEdges(characters: CharacterRelationships[]): RelationshipEdge[] {
  const known = new Set(characters.map((c) => c.id));
  const edges: RelationshipEdge[] = [];

  for (const char of characters) {
    const rels = char.relationships ?? {};
    for (const [targetId, label] of Object.entries(rels)) {
      if (!known.has(targetId) || !label.trim()) continue;
      edges.push({
        fromId: char.id,
        toId: targetId,
        label: label.trim(),
        familyKind: classifyRelationshipLabel(label),
      });
    }
  }
  return edges;
}

export type FamilyLink = {
  fromId: string;
  toId: string;
  label: string;
  kind: FamilyKind;
  /** When true, `fromId` is the parent/guardian and `toId` is the child/ward. */
  directed: boolean;
};

/**
 * Derive normalized family links for genealogy layout.
 * Label is read from the source character's perspective toward the target.
 */
export function buildFamilyLinks(edges: RelationshipEdge[]): FamilyLink[] {
  const links: FamilyLink[] = [];

  for (const edge of edges) {
    if (!edge.familyKind) continue;
    const kind = edge.familyKind;

    if (kind === "parent") {
      links.push({
        fromId: edge.toId,
        toId: edge.fromId,
        label: edge.label,
        kind,
        directed: true,
      });
    } else if (kind === "child") {
      links.push({
        fromId: edge.fromId,
        toId: edge.toId,
        label: edge.label,
        kind,
        directed: true,
      });
    } else if (kind === "guardian") {
      const norm = normalizeRelationshipLabel(edge.label);
      if (norm.includes("ward")) {
        links.push({
          fromId: edge.toId,
          toId: edge.fromId,
          label: edge.label,
          kind,
          directed: true,
        });
      } else {
        links.push({
          fromId: edge.fromId,
          toId: edge.toId,
          label: edge.label,
          kind,
          directed: true,
        });
      }
    } else if (kind === "adopted") {
      const norm = normalizeRelationshipLabel(edge.label);
      if (norm.includes("adoptive") || norm.includes("foster")) {
        links.push({
          fromId: edge.fromId,
          toId: edge.toId,
          label: edge.label,
          kind,
          directed: true,
        });
      } else {
        links.push({
          fromId: edge.toId,
          toId: edge.fromId,
          label: edge.label,
          kind,
          directed: true,
        });
      }
    } else {
      links.push({
        fromId: edge.fromId,
        toId: edge.toId,
        label: edge.label,
        kind,
        directed: false,
      });
    }
  }
  return links;
}

export type GenealogyNode = {
  id: string;
  name: string;
  role?: string;
  children: GenealogyNode[];
  spouses: { id: string; name: string; label: string }[];
  depth: number;
};

/** Characters with no incoming parent link become roots (sorted by role then name). */
export function buildGenealogyForest(
  characters: CharacterRelationships[],
  familyLinks: FamilyLink[],
): GenealogyNode[] {
  const byId = new Map(characters.map((c) => [c.id, c]));
  const parentOf = new Map<string, string>();
  const childrenOf = new Map<string, Set<string>>();
  const spousePairs = new Map<string, { id: string; label: string }[]>();

  function addChild(parentId: string, childId: string) {
    if (parentId === childId) return;
    if (!childrenOf.has(parentId)) childrenOf.set(parentId, new Set());
    childrenOf.get(parentId)!.add(childId);
    if (!parentOf.has(childId)) parentOf.set(childId, parentId);
  }

  for (const link of familyLinks) {
    if (link.directed && (link.kind === "parent" || link.kind === "child" || link.kind === "guardian" || link.kind === "adopted")) {
      addChild(link.fromId, link.toId);
      continue;
    }
    if (link.kind === "spouse" || link.kind === "sibling") {
      const a = link.fromId;
      const b = link.toId;
      if (!spousePairs.has(a)) spousePairs.set(a, []);
      if (!spousePairs.get(a)!.some((s) => s.id === b)) {
        spousePairs.get(a)!.push({ id: b, label: link.label });
      }
      if (!spousePairs.has(b)) spousePairs.set(b, []);
      if (!spousePairs.get(b)!.some((s) => s.id === a)) {
        spousePairs.get(b)!.push({ id: a, label: link.label });
      }
    }
  }

  const roleRank = (role?: string) => {
    const order: Record<string, number> = {
      protagonist: 0, antagonist: 1, supporting: 2, minor: 3,
    };
    return order[role ?? ""] ?? 4;
  };

  const roots = characters
    .filter((c) => !parentOf.has(c.id))
    .sort((a, b) => roleRank(a.role) - roleRank(b.role) || a.full_name.localeCompare(b.full_name));

  const visiting = new Set<string>();

  function nodeFor(id: string, depth: number): GenealogyNode | null {
    const char = byId.get(id);
    if (!char || visiting.has(id)) return null;
    visiting.add(id);

    const childIds = [...(childrenOf.get(id) ?? [])].sort((a, b) =>
      (byId.get(a)?.full_name ?? "").localeCompare(byId.get(b)?.full_name ?? ""),
    );

    const spouses = (spousePairs.get(id) ?? [])
      .map((s) => ({
        id: s.id,
        name: byId.get(s.id)?.full_name ?? s.id,
        label: s.label,
      }))
      .filter((s) => s.id !== id);

    const children = childIds
      .map((cid) => nodeFor(cid, depth + 1))
      .filter((n): n is GenealogyNode => n != null);

    visiting.delete(id);
    return {
      id,
      name: char.full_name,
      role: char.role,
      children,
      spouses,
      depth,
    };
  }

  return roots
    .map((r) => nodeFor(r.id, 0))
    .filter((n): n is GenealogyNode => n != null);
}

/** Evenly space nodes on a circle for lightweight SVG graph layout. */
export function circularLayout(
  ids: string[],
  width: number,
  height: number,
  radius = 0,
): Map<string, { x: number; y: number }> {
  const cx = width / 2;
  const cy = height / 2;
  const r = radius || Math.min(width, height) * 0.36;
  const positions = new Map<string, { x: number; y: number }>();
  const n = ids.length;
  ids.forEach((id, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    positions.set(id, { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
  });
  return positions;
}
