import { describe, expect, it } from "vitest";
import {
  computeHighlightRanges,
  findQuoteRange,
  normalizeAnchorText,
  splitSourceByHighlights,
  commentStage,
} from "../lib/annotations";
import type { CommentItem } from "../api/client";

function ann(partial: Partial<CommentItem> & Pick<CommentItem, "id" | "body">): CommentItem {
  return {
    quote: "",
    created_at: "2026-01-01T00:00:00Z",
    resolved: false,
    ...partial,
  };
}

describe("annotations", () => {
  it("normalizes anchor text like the backend", () => {
    expect(normalizeAnchorText("  First   paragraph.  ")).toBe("First paragraph.");
  });

  it("finds exact quote ranges", () => {
    const source = "Hello world.\nSecond line.";
    expect(findQuoteRange(source, "world")).toEqual({ start: 6, end: 11 });
    expect(findQuoteRange(source, "missing")).toBeNull();
  });

  it("computes highlight ranges from offsets", () => {
    const source = "Alpha beta gamma";
    const ranges = computeHighlightRanges(source, [
      ann({ id: "1", body: "note", quote: "beta", stage: "draft", start_offset: 6, end_offset: 10 }),
    ], "draft");
    expect(ranges).toEqual([{ start: 6, end: 10, id: "1", body: "note" }]);
  });

  it("falls back to quote when offsets are stale", () => {
    const source = "Alpha beta gamma";
    const ranges = computeHighlightRanges(source, [
      ann({ id: "1", body: "note", quote: "gamma", stage: "revised", start_offset: 0, end_offset: 1 }),
    ], "revised");
    expect(ranges[0]).toMatchObject({ start: 11, end: 16, id: "1" });
  });

  it("reanchors by quote when offsets no longer match", () => {
    const source = "the cat sat";
    const ranges = computeHighlightRanges(source, [
      ann({ id: "1", body: "note", quote: "the", stage: "draft", start_offset: 4, end_offset: 7 }),
    ], "draft");
    expect(ranges[0]).toMatchObject({ start: 0, end: 3, id: "1" });
  });

  it("does not reanchor short quotes inside longer words", () => {
    const source = "there cat sat";
    const ranges = computeHighlightRanges(source, [
      ann({ id: "1", body: "note", quote: "the", stage: "draft", start_offset: 4, end_offset: 7 }),
    ], "draft");
    expect(ranges).toEqual([]);
  });

  it("prefers the duplicate quote nearest the original offset", () => {
    const source = "Alpha beta. Middle words. Alpha beta.";
    const ranges = computeHighlightRanges(source, [
      ann({ id: "1", body: "note", quote: "Alpha beta", stage: "draft", start_offset: 25, end_offset: 35 }),
    ], "draft");
    expect(ranges[0]).toMatchObject({ start: 26, end: 36, id: "1" });
  });

  it("filters by stage and splits highlighted source", () => {
    const source = "One two three";
    const comments = [
      ann({ id: "a", body: "d", quote: "One", stage: "draft" }),
      ann({ id: "b", body: "r", quote: "two", stage: "revised" }),
    ];
    const draftRanges = computeHighlightRanges(source, comments, "draft");
    expect(draftRanges).toHaveLength(1);
    const segments = splitSourceByHighlights(source, draftRanges);
    expect(segments.map((s) => s.text)).toEqual(["One", " two three"]);
    expect(segments[0].highlight?.id).toBe("a");
  });

  it("labels legacy comments as general", () => {
    expect(commentStage(ann({ id: "1", body: "x" }))).toBe("comment");
  });
});
