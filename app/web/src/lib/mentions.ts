import { autocompletion, type Completion, type CompletionContext } from "@codemirror/autocomplete";
import type { CharacterSummary } from "../api/client";

export type MentionKind = "char" | "lore";

export type MentionTarget = {
  kind: MentionKind;
  label: string;
  id?: string;
  section?: string;
  aliases?: string[];
};

export type ParsedMention = {
  kind: MentionKind;
  label: string;
  section?: string;
  raw: string;
  start: number;
  end: number;
};

/** Story bible section keys — mirrors CodexEditors BIBLE_SECTIONS. */
export const BIBLE_SECTION_META: { key: string; label: string; asList?: boolean }[] = [
  { key: "logline", label: "Logline" },
  { key: "themes", label: "Themes", asList: true },
  { key: "setting_summary", label: "Setting", asList: true },
  { key: "historical_context", label: "Historical context", asList: true },
  { key: "premise_beats", label: "Premise beats", asList: true },
  { key: "world_rules", label: "World rules" },
  { key: "import_notes", label: "Story notes" },
];

const RE_CHAR = /\[\[char:([^\]]+)\]\]/g;
const RE_LORE_SECTION = /\[\[lore:([^:\]]+):([^\]]+)\]\]/g;
const RE_LORE = /\[\[lore:([^\]]+)\]\]/g;

export function normalizeLabel(label: string): string {
  return label.trim().toLowerCase();
}

export function buildMentionMarkup(target: MentionTarget): string {
  if (target.kind === "char") return `[[char:${target.label}]]`;
  if (target.section) return `[[lore:${target.section}:${target.label}]]`;
  return `[[lore:${target.label}]]`;
}

/** Replace mention markup with plain labels (matches backend epub_exporter). */
export function stripMentions(text: string): string {
  return text
    .replace(/\[\[char:([^\]]+)\]\]/g, "$1")
    .replace(/\[\[lore:[^:]+:([^\]]+)\]\]/g, "$1")
    .replace(/\[\[lore:([^\]]+)\]\]/g, "$1");
}

function loreItemLabel(item: unknown): string | null {
  if (typeof item === "string") {
    const t = item.trim();
    return t || null;
  }
  if (item && typeof item === "object") {
    const o = item as Record<string, string>;
    const t = (o.note ?? o.fact ?? o.relationship ?? "").trim();
    return t || null;
  }
  return null;
}

export function buildMentionTargets(
  characters: CharacterSummary[],
  storyBible: Record<string, unknown>,
): MentionTarget[] {
  const targets: MentionTarget[] = [];
  const seen = new Set<string>();

  function add(target: MentionTarget) {
    const key = `${target.kind}:${target.section ?? ""}:${normalizeLabel(target.label)}`;
    if (seen.has(key)) return;
    seen.add(key);
    targets.push(target);
  }

  for (const ch of characters) {
    add({ kind: "char", label: ch.full_name, id: ch.id, aliases: ch.aliases });
  }

  for (const sec of BIBLE_SECTION_META) {
    const val = storyBible[sec.key];
    if (Array.isArray(val)) {
      for (const item of val) {
        const label = loreItemLabel(item);
        if (label) add({ kind: "lore", label, section: sec.key });
      }
    } else if (typeof val === "string" && val.trim()) {
      add({ kind: "lore", label: sec.label, section: sec.key });
      for (const line of val.split("\n")) {
        const t = line.trim();
        if (t) add({ kind: "lore", label: t, section: sec.key });
      }
    }
  }

  return targets;
}

export function parseMentions(text: string): ParsedMention[] {
  const found: ParsedMention[] = [];

  function collect(re: RegExp, kind: MentionKind, withSection: boolean) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (withSection) {
        found.push({
          kind,
          section: m[1],
          label: m[2],
          raw: m[0],
          start: m.index,
          end: m.index + m[0].length,
        });
      } else {
        found.push({
          kind,
          label: m[1],
          raw: m[0],
          start: m.index,
          end: m.index + m[0].length,
        });
      }
    }
  }

  collect(RE_CHAR, "char", false);
  collect(RE_LORE_SECTION, "lore", true);
  collect(RE_LORE, "lore", false);

  found.sort((a, b) => a.start - b.start || b.raw.length - a.raw.length);
  const deduped: ParsedMention[] = [];
  let end = 0;
  for (const m of found) {
    if (m.start < end) continue;
    deduped.push(m);
    end = m.end;
  }
  return deduped;
}

export function resolveMention(
  parsed: Pick<ParsedMention, "kind" | "label" | "section">,
  targets: MentionTarget[],
): MentionTarget | null {
  const want = normalizeLabel(parsed.label);

  if (parsed.kind === "char") {
    for (const t of targets) {
      if (t.kind !== "char") continue;
      if (normalizeLabel(t.label) === want) return t;
      if (t.aliases?.some((a) => normalizeLabel(a) === want)) return { ...t, label: t.label };
    }
    return null;
  }

  if (parsed.section) {
    const sec = parsed.section.trim().toLowerCase();
    for (const t of targets) {
      if (t.kind !== "lore" || !t.section) continue;
      if (t.section.toLowerCase() === sec && normalizeLabel(t.label) === want) return t;
    }
    return null;
  }

  for (const t of targets) {
    if (t.kind === "lore" && normalizeLabel(t.label) === want) return t;
  }
  return null;
}

function targetSearchText(t: MentionTarget): string {
  const parts = [t.label, t.section ?? "", ...(t.aliases ?? [])];
  return parts.join(" ").toLowerCase();
}

function bracketQueryFilter(targets: MentionTarget[], query: string): MentionTarget[] {
  const q = query.toLowerCase();
  if (!q) return targets;
  if (q === "char" || q === "char:") return targets.filter((t) => t.kind === "char");
  if (q.startsWith("char:")) {
    const nameQ = q.slice(5);
    return targets.filter(
      (t) => t.kind === "char" && targetSearchText(t).includes(nameQ),
    );
  }
  if (q === "lore" || q === "lore:") return targets.filter((t) => t.kind === "lore");
  if (q.startsWith("lore:")) {
    const rest = q.slice(5);
    const colon = rest.indexOf(":");
    if (colon >= 0) {
      const sec = rest.slice(0, colon);
      const nameQ = rest.slice(colon + 1);
      return targets.filter(
        (t) =>
          t.kind === "lore"
          && (t.section?.toLowerCase().includes(sec) ?? false)
          && normalizeLabel(t.label).includes(nameQ),
      );
    }
    return targets.filter(
      (t) => t.kind === "lore" && targetSearchText(t).includes(rest),
    );
  }
  return targets.filter((t) => targetSearchText(t).includes(q));
}

function atQueryFilter(targets: MentionTarget[], query: string): MentionTarget[] {
  const q = query.toLowerCase();
  if (!q) return targets;
  return targets.filter((t) => targetSearchText(t).includes(q));
}

function toCompletion(t: MentionTarget): Completion {
  const detail =
    t.kind === "char"
      ? "Character"
      : t.section
        ? `Lore · ${t.section.replace(/_/g, " ")}`
        : "Lore";
  return {
    label: t.label,
    detail,
    type: t.kind === "char" ? "variable" : "text",
    apply: buildMentionMarkup(t),
  };
}

export function mentionAutocompleteExtension(targets: MentionTarget[]) {
  return autocompletion({
    activateOnTyping: true,
    override: [
      (context: CompletionContext) => {
        const bracket = context.matchBefore(/\[\[[^\]]*$/);
        const at = context.matchBefore(/(?:^|[\s([{"'])@([^\s\[]*)$/);

        if (!bracket && !at) return null;

        if (bracket) {
          const query = bracket.text.slice(2);
          const filtered = bracketQueryFilter(targets, query);
          return {
            from: bracket.from,
            options: filtered.slice(0, 40).map(toCompletion),
            validFor: /^\[\[[^\]]*$/,
          };
        }

        const atText = at!.text;
        const atIdx = atText.lastIndexOf("@");
        const query = atText.slice(atIdx + 1);
        const from = at!.from + atIdx;
        const filtered = atQueryFilter(targets, query);
        return {
          from,
          options: filtered.slice(0, 40).map((t) => ({
            ...toCompletion(t),
            apply: `${buildMentionMarkup(t)} `,
          })),
          validFor: /^@([^\s\[]*)?$/,
        };
      },
    ],
  });
}

/** Convert [[mentions]] to markdown links for react-markdown rendering. */
export function preprocessMentionsForMarkdown(text: string): string {
  return text
    .replace(
      /\[\[char:([^\]]+)\]\]/g,
      (_, name: string) => `[${name}](novel-mention:char:${encodeURIComponent(name)})`,
    )
    .replace(
      /\[\[lore:([^:\]]+):([^\]]+)\]\]/g,
      (_, section: string, label: string) =>
        `[${label}](novel-mention:lore:${encodeURIComponent(section)}:${encodeURIComponent(label)})`,
    )
    .replace(
      /\[\[lore:([^\]]+)\]\]/g,
      (_, label: string) => `[${label}](novel-mention:lore::${encodeURIComponent(label)})`,
    );
}

export function parseMentionHref(href: string): Pick<ParsedMention, "kind" | "label" | "section"> | null {
  if (!href.startsWith("novel-mention:")) return null;
  const rest = href.slice("novel-mention:".length);
  if (rest.startsWith("char:")) {
    return { kind: "char", label: decodeURIComponent(rest.slice(5)) };
  }
  if (rest.startsWith("lore:")) {
    const body = rest.slice(5);
    const colon = body.indexOf(":");
    if (colon >= 0) {
      const section = decodeURIComponent(body.slice(0, colon));
      return {
        kind: "lore",
        section: section || undefined,
        label: decodeURIComponent(body.slice(colon + 1)),
      };
    }
    return { kind: "lore", label: decodeURIComponent(body) };
  }
  return null;
}
