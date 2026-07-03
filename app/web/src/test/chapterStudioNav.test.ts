import { describe, expect, it, beforeEach } from "vitest";
import type { ChapterStages } from "../api/client";
import {
  bestProseStage,
  readStudioPlace,
  stageForStudioPlace,
  studioPlaceFromSelection,
  writeStudioPlace,
} from "../lib/chapterStudioNav";

const STAGES: ChapterStages = {
  number: 1,
  status: "edited",
  outline: "# beats",
  draft: "draft text",
  revised: "revised text",
  final: null,
  continuity: null,
};

beforeEach(() => {
  sessionStorage.clear();
});

describe("bestProseStage", () => {
  it("prefers final, then revised, then draft", () => {
    expect(bestProseStage({ ...STAGES, final: "final text" })).toBe("final");
    expect(bestProseStage(STAGES)).toBe("revised");
    expect(bestProseStage({ ...STAGES, revised: null })).toBe("draft");
    expect(bestProseStage({ ...STAGES, draft: null, revised: null })).toBe("outline");
  });
});

describe("stageForStudioPlace", () => {
  it("keeps outline mode on outline", () => {
    expect(stageForStudioPlace("outline", STAGES)).toBe("outline");
  });

  it("uses best prose for prose and brief modes", () => {
    expect(stageForStudioPlace("prose", STAGES)).toBe("revised");
    expect(stageForStudioPlace("brief", STAGES)).toBe("revised");
  });
});

describe("studio place persistence", () => {
  it("round-trips per project", () => {
    writeStudioPlace("novel-a", "brief");
    expect(readStudioPlace("novel-a")).toBe("brief");
    expect(readStudioPlace("novel-b")).toBeNull();
  });
});

describe("studioPlaceFromSelection", () => {
  it("maps UI state to place", () => {
    expect(studioPlaceFromSelection(true, "draft")).toBe("brief");
    expect(studioPlaceFromSelection(false, "outline")).toBe("outline");
    expect(studioPlaceFromSelection(false, "final")).toBe("prose");
  });
});
