import type { ResearchSparkSummary } from "../api/client";

export const RESEARCH_KINDS = ["note", "link", "quote", "image", "idea"] as const;
export type ResearchKind = (typeof RESEARCH_KINDS)[number];

export const RESEARCH_KIND_LABELS: Record<ResearchKind, string> = {
  note: "Note",
  link: "Link",
  quote: "Quote",
  image: "Image",
  idea: "Idea",
};

export interface ResearchSparkFilters {
  q?: string;
  tag?: string;
  kind?: string;
}

export function parseTagsInput(text: string): string[] {
  return text
    .split(/[,;]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

export function formatTagsInput(tags: string[]): string {
  return tags.join(", ");
}

export function collectAllTags(sparks: ResearchSparkSummary[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const spark of sparks) {
    for (const tag of spark.tags) {
      const key = tag.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        out.push(tag);
      }
    }
  }
  return out.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

export function filterResearchSparks(
  sparks: ResearchSparkSummary[],
  filters: ResearchSparkFilters,
): ResearchSparkSummary[] {
  const needle = (filters.q ?? "").trim().toLowerCase();
  const tagNeedle = (filters.tag ?? "").trim().toLowerCase();
  const kindFilter = (filters.kind ?? "").trim().toLowerCase();

  return sparks.filter((spark) => {
    if (kindFilter && spark.kind.toLowerCase() !== kindFilter) return false;
    if (tagNeedle && !spark.tags.some((t) => t.toLowerCase() === tagNeedle)) return false;
    if (needle) {
      const hay = [
        spark.title,
        spark.body,
        spark.source_url,
        spark.attachment_ref,
        spark.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
}
