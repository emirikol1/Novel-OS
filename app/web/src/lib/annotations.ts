import type { AnnotationStage, CommentItem } from "../api/client";

export const ANNOTATION_STAGES: AnnotationStage[] = ["draft", "revised", "final", "comment"];

export const STAGE_LABELS: Record<AnnotationStage, string> = {
  draft: "Draft",
  revised: "Revised",
  final: "Final",
  comment: "General",
};

export function commentStage(c: CommentItem): AnnotationStage {
  const s = c.stage ?? "comment";
  return ANNOTATION_STAGES.includes(s as AnnotationStage) ? (s as AnnotationStage) : "comment";
}

export function isManuscriptStage(stage: AnnotationStage): stage is "draft" | "revised" | "final" {
  return stage === "draft" || stage === "revised" || stage === "final";
}

export function isManuscriptAnnotation(c: CommentItem): boolean {
  return isManuscriptStage(commentStage(c));
}

export interface HighlightRange {
  start: number;
  end: number;
  id: string;
  body: string;
  paragraphHash?: string;
}

/** Normalize whitespace the same way the backend hashes paragraph anchors. */
export function normalizeAnchorText(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(" ");
}

function isWordChar(ch: string | undefined): boolean {
  return !!ch && /[\p{L}\p{N}_]/u.test(ch);
}

function hasWordBoundary(source: string, start: number, end: number): boolean {
  return !isWordChar(source[start - 1]) && !isWordChar(source[end]);
}

function findAllExactRanges(source: string, quote: string): { start: number; end: number }[] {
  const q = quote.trim();
  if (!q) return [];
  const ranges: { start: number; end: number }[] = [];
  let idx = source.indexOf(q);
  while (idx >= 0) {
    ranges.push({ start: idx, end: idx + q.length });
    idx = source.indexOf(q, idx + 1);
  }
  return ranges;
}

export function findQuoteRange(
  source: string,
  quote: string,
  preferredStart?: number | null,
): { start: number; end: number } | null {
  const q = quote.trim();
  if (!q) return null;

  const exact = findAllExactRanges(source, q);
  if (exact.length === 0) return null;

  const hasWordLikeEdges = isWordChar(q[0]) || isWordChar(q[q.length - 1]);
  const candidates = exact
    .map((range) => ({
      ...range,
      boundary: !hasWordLikeEdges || hasWordBoundary(source, range.start, range.end),
    }))
    // Very short word-like quotes are too ambiguous if they only appear inside another word.
    .filter((range) => range.boundary || q.length >= 8);

  if (candidates.length === 0) return null;

  if (preferredStart == null) {
    const best = candidates[0];
    return { start: best.start, end: best.end };
  }

  const best = candidates
    .map((range) => ({
      ...range,
      score: Math.abs(range.start - preferredStart) + (range.boundary ? 0 : 1000),
    }))
    .sort((a, b) => a.score - b.score || a.start - b.start)[0];
  return { start: best.start, end: best.end };
}

export function computeHighlightRanges(
  source: string,
  annotations: CommentItem[],
  stage?: AnnotationStage | "all",
): HighlightRange[] {
  const ranges: HighlightRange[] = [];
  for (const ann of annotations) {
    if (ann.resolved) continue;
    const annStage = commentStage(ann);
    if (stage && stage !== "all" && annStage !== stage) continue;

    let start: number | null = null;
    let end: number | null = null;
    if (
      ann.start_offset != null
      && ann.end_offset != null
      && ann.start_offset >= 0
      && ann.end_offset > ann.start_offset
      && ann.end_offset <= source.length
    ) {
      const slice = source.slice(ann.start_offset, ann.end_offset);
      const quote = ann.quote.trim();
      const offsetsMatchQuote = !quote || normalizeAnchorText(slice) === normalizeAnchorText(quote);
      if (offsetsMatchQuote) {
        start = ann.start_offset;
        end = ann.end_offset;
      } else if (quote) {
        const found = findQuoteRange(source, ann.quote, ann.start_offset);
        if (found) {
          start = found.start;
          end = found.end;
        }
      }
    } else if (ann.quote.trim()) {
      const found = findQuoteRange(source, ann.quote, ann.start_offset);
      if (found) {
        start = found.start;
        end = found.end;
      }
    }
    if (start == null || end == null || end <= start) continue;
    ranges.push({ start, end, id: ann.id, body: ann.body, paragraphHash: ann.paragraph_hash });
  }

  ranges.sort((a, b) => a.start - b.start || a.end - b.end);
  const merged: HighlightRange[] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start < last.end) {
      if (r.end > last.end) last.end = r.end;
      continue;
    }
    merged.push({ ...r });
  }
  return merged;
}

export interface SourceSegment {
  text: string;
  highlight?: HighlightRange;
}

export function splitSourceByHighlights(source: string, ranges: HighlightRange[]): SourceSegment[] {
  if (ranges.length === 0) return [{ text: source }];
  const segments: SourceSegment[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) {
      segments.push({ text: source.slice(cursor, r.start) });
    }
    if (r.end > r.start) {
      segments.push({
        text: source.slice(r.start, r.end),
        highlight: r,
      });
    }
    cursor = Math.max(cursor, r.end);
  }
  if (cursor < source.length) {
    segments.push({ text: source.slice(cursor) });
  }
  return segments;
}
