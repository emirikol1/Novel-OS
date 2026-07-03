/** Relationship role/subrole helpers for Character.relationships string values. */
export type FamilyKind =
  | "parent"
  | "child"
  | "spouse"
  | "sibling"
  | "guardian"
  | "adopted";

export type ParsedRelationshipLabel = {
  raw: string;
  role: string | null;
  subrole: string;
  note: string;
  displayLabel: string;
};

export type RelationshipEdge = {
  fromId: string;
  toId: string;
  rawLabel: string;
  label: string;
  canonicalRole: string | null;
  familyKind: FamilyKind | null;
};

export type CharacterRelationships = {
  id: string;
  full_name: string;
  role?: string;
  relationships?: Record<string, string>;
};

export const CANONICAL_RELATIONSHIP_ROLES = [
  "parent",
  "child",
  "sibling",
  "lover",
  "spouse",
  "ex",
  "friend",
  "ally",
  "rival",
  "enemy",
  "teacher",
  "student",
  "caretaker",
  "dependent",
  "employer",
  "employee",
  "household master",
  "servant",
  "provider",
  "client",
  "commander",
  "subordinate",
  "captor",
  "prisoner",
  "dominant",
  "submissive",
] as const;

export const RELATIONSHIP_SUBROLE_SUGGESTIONS = [
  "mother", "father", "son", "daughter", "brother", "sister", "twin",
  "husband", "wife", "lover", "ex-spouse", "ex-lover",
  "best friend", "teammate", "accomplice", "nemesis", "adversary",
  "mentor", "apprentice", "guardian", "ward", "boss", "manager",
  "master of house", "domestic servant", "doctor", "patient", "lawyer", "client",
  "officer", "soldier", "ruler", "subject", "jailer", "hostage", "blackmailer", "victim",
  "dom", "sub",
] as const;

const ADOPTED_LABELS = new Set(["adopted", "adoptive", "foster"]);
const CANONICAL_BY_KEY = new Map(CANONICAL_RELATIONSHIP_ROLES.map((role) => [normalizeRelationshipLabel(role), role]));
const AMBIGUOUS_LABELS = new Set(["partner", "master"]);
const ALIASES = new Map<string, string>([
  ["mother", "parent"],
  ["father", "parent"],
  ["mom", "parent"],
  ["dad", "parent"],
  ["mum", "parent"],
  ["ma", "parent"],
  ["pa", "parent"],
  ["son", "child"],
  ["daughter", "child"],
  ["kid", "child"],
  ["brother", "sibling"],
  ["sister", "sibling"],
  ["twin", "sibling"],
  ["husband", "spouse"],
  ["wife", "spouse"],
  ["ex spouse", "ex"],
  ["ex-spouse", "ex"],
  ["ex lover", "ex"],
  ["ex-lover", "ex"],
  ["best friend", "friend"],
  ["teammate", "ally"],
  ["accomplice", "ally"],
  ["nemesis", "enemy"],
  ["adversary", "rival"],
  ["mentor", "teacher"],
  ["apprentice", "student"],
  ["guardian", "caretaker"],
  ["ward", "dependent"],
  ["boss", "employer"],
  ["manager", "employer"],
  ["worker", "employee"],
  ["staff", "employee"],
  ["master of house", "household master"],
  ["domestic servant", "servant"],
  ["service provider", "provider"],
  ["doctor", "provider"],
  ["lawyer", "provider"],
  ["therapist", "provider"],
  ["patient", "client"],
  ["officer", "commander"],
  ["ruler", "commander"],
  ["soldier", "subordinate"],
  ["subject", "subordinate"],
  ["jailer", "captor"],
  ["blackmailer", "captor"],
  ["hostage", "prisoner"],
  ["victim", "prisoner"],
  ["dom", "dominant"],
  ["sub", "submissive"],
]);

/** Normalize a relationship label for token matching. */
export function normalizeRelationshipLabel(label: string): string {
  return label.trim().toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
}

function aliasRoleForKey(key: string): string | null {
  const exact = ALIASES.get(key);
  if (exact) return exact;
  for (const [alias, role] of ALIASES.entries()) {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(key)) {
      return role;
    }
  }
  return null;
}

/** Parse legacy free text or encoded `role(subrole): note` labels. */
export function parseRelationshipLabel(label: string): ParsedRelationshipLabel {
  const raw = label.trim();
  if (!raw) return { raw: "", role: null, subrole: "", note: "", displayLabel: "" };
  const [baseRaw, ...noteParts] = raw.split(":");
  const base = baseRaw.trim();
  const note = noteParts.join(":").trim();
  const encoded = base.match(/^\s*([^()]+?)\s*\(([^()]*)\)\s*$/);
  if (encoded) {
    const role = CANONICAL_BY_KEY.get(normalizeRelationshipLabel(encoded[1]));
    if (role) {
      const subrole = encoded[2].trim() || role;
      const displayLabel = note ? `${subrole}: ${note}` : subrole;
      return { raw, role, subrole, note, displayLabel };
    }
  }

  const key = normalizeRelationshipLabel(base);
  const canonical = CANONICAL_BY_KEY.get(key);
  if (canonical) {
    const displayLabel = note ? `${canonical}: ${note}` : canonical;
    return { raw, role: canonical, subrole: canonical, note, displayLabel };
  }
  if (AMBIGUOUS_LABELS.has(key)) {
    const displayLabel = note ? `${base}: ${note}` : base;
    return { raw, role: null, subrole: base, note, displayLabel };
  }
  const aliasRole = aliasRoleForKey(key);
  if (aliasRole) {
    const displayLabel = note ? `${base}: ${note}` : base;
    return { raw, role: aliasRole, subrole: base, note, displayLabel };
  }
  const displayLabel = note ? `${base}: ${note}` : base;
  return { raw, role: null, subrole: base, note, displayLabel };
}

/** Encode a canonical role, optional display subrole, and optional note for storage. */
export function stringifyRelationshipLabel(role: string | null, subrole: string, note = ""): string {
  const canonical = role ? CANONICAL_BY_KEY.get(normalizeRelationshipLabel(role)) : null;
  const cleanSubrole = subrole.trim();
  const cleanNote = note.trim();
  let label = cleanSubrole;
  if (canonical) {
    label = !cleanSubrole || normalizeRelationshipLabel(cleanSubrole) === normalizeRelationshipLabel(canonical)
      ? canonical
      : `${canonical}(${cleanSubrole})`;
  }
  return cleanNote && label ? `${label}: ${cleanNote}` : label;
}

export function displayRelationshipLabel(label: string): string {
  return parseRelationshipLabel(label).displayLabel;
}

/** Classify a free-text relationship label into a family category when possible. */
export function classifyRelationshipLabel(label: string): FamilyKind | null {
  return familyKindFromParsedRelationshipLabel(parseRelationshipLabel(label));
}

function familyKindFromParsedRelationshipLabel(parsed: ParsedRelationshipLabel): FamilyKind | null {
  const normalizedDisplay = normalizeRelationshipLabel(parsed.displayLabel || parsed.raw);
  if (!normalizedDisplay) return null;
  const hasAdopted = [...ADOPTED_LABELS].some((word) => normalizedDisplay.includes(word));
  if (hasAdopted) return "adopted";
  if (parsed.role === "parent") return "parent";
  if (parsed.role === "child") return "child";
  if (parsed.role === "sibling") return "sibling";
  if (parsed.role === "spouse") return "spouse";
  if (parsed.role === "caretaker" || parsed.role === "dependent") return "guardian";
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
      const parsed = parseRelationshipLabel(label);
      edges.push({
        fromId: char.id,
        toId: targetId,
        rawLabel: label.trim(),
        label: parsed.displayLabel,
        canonicalRole: parsed.role,
        familyKind: familyKindFromParsedRelationshipLabel(parsed),
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
      if (edge.canonicalRole === "dependent") {
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
