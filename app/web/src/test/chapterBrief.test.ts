import { describe, expect, it } from "vitest";
import {
  EMPTY_BRIEF_DRAFT,
  SAMPLE_CHAPTER_BRIEF,
  briefFromGeneratedSummary,
  briefFromSummary,
  briefHasContent,
  briefToPayload,
  characterPresence,
  cycleCharacterPresence,
  promoteCharacterToActive,
  stepChapterTargetWords,
  toggleId,
} from "../lib/chapterBrief";

describe("chapterBrief utils", () => {
  it("converts API summary to editable draft", () => {
    const draft = briefFromSummary(SAMPLE_CHAPTER_BRIEF);
    expect(draft.pov_character_id).toBe("char_a");
    expect(draft.mentioned_character_ids).toEqual(["char_a", "char_b"]);
    expect(draft.active_node_ids).toEqual(["sg_main", "sg_sub2"]);
    expect(draft).not.toHaveProperty("required_beats");
    expect(draft).not.toHaveProperty("landed_beats");
  });

  it("round-trips mentioned_character_ids from API summary", () => {
    const draft = briefFromSummary({
      ...SAMPLE_CHAPTER_BRIEF,
      mentioned_character_ids: ["char_a"],
      active_character_ids: ["char_a"],
    });
    expect(briefToPayload(draft).mentioned_character_ids).toEqual(["char_a"]);
    expect(briefToPayload(draft).active_character_ids).toEqual(["char_a"]);
  });

  it("derives character presence and cycles none → mentioned → active → none", () => {
    let draft = EMPTY_BRIEF_DRAFT;
    expect(characterPresence(draft, "char_a")).toBe("none");

    draft = cycleCharacterPresence(draft, "char_a");
    expect(characterPresence(draft, "char_a")).toBe("mentioned");
    expect(draft.mentioned_character_ids).toEqual(["char_a"]);
    expect(draft.active_character_ids).toEqual([]);

    draft = cycleCharacterPresence(draft, "char_a");
    expect(characterPresence(draft, "char_a")).toBe("active");
    expect(draft.active_character_ids).toEqual(["char_a"]);

    draft = cycleCharacterPresence(draft, "char_a");
    expect(characterPresence(draft, "char_a")).toBe("none");
    expect(draft.mentioned_character_ids).toEqual([]);
  });

  it("promoteCharacterToActive adds to both lists", () => {
    const draft = promoteCharacterToActive(EMPTY_BRIEF_DRAFT, "char_b");
    expect(draft.mentioned_character_ids).toEqual(["char_b"]);
    expect(draft.active_character_ids).toEqual(["char_b"]);
  });

  it("detects planning content when only mentioned characters are set", () => {
    expect(
      briefHasContent({ ...EMPTY_BRIEF_DRAFT, mentioned_character_ids: ["char_a"] }),
    ).toBe(true);
  });

  it("preserves existing mentioned characters when generated summary omits them", () => {
    const existing = {
      ...EMPTY_BRIEF_DRAFT,
      mentioned_character_ids: ["char_a", "char_b"],
      active_character_ids: ["char_a"],
    };
    const generated = {
      ...SAMPLE_CHAPTER_BRIEF,
      mentioned_character_ids: [],
      active_character_ids: ["char_a"],
    };
    const draft = briefFromGeneratedSummary(generated, existing);
    expect(draft.mentioned_character_ids).toEqual(["char_a", "char_b"]);
  });

  it("omits beat lists from save payload", () => {
    const payload = briefToPayload({
      ...EMPTY_BRIEF_DRAFT,
      ending_hook: "Cliffhanger",
    });
    expect(payload).not.toHaveProperty("required_beats");
    expect(payload).not.toHaveProperty("landed_beats");
    expect(payload.ending_hook).toBe("Cliffhanger");
  });

  it("toggles id membership", () => {
    expect(toggleId(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleId(["a", "b"], "a")).toEqual(["b"]);
  });

  it("detects whether draft has planning content without beat fields", () => {
    expect(briefHasContent(EMPTY_BRIEF_DRAFT)).toBe(false);
    expect(briefHasContent({ ...EMPTY_BRIEF_DRAFT, pov_character_id: "x" })).toBe(true);
    expect(briefHasContent({ ...EMPTY_BRIEF_DRAFT, ending_hook: "Hook" })).toBe(true);
  });

  it("does not merge generated beat strings into draft", () => {
    const existing = EMPTY_BRIEF_DRAFT;
    const generated = {
      ...SAMPLE_CHAPTER_BRIEF,
      landed_beats: [],
      required_beats: ["Alice discovers the alarm code"],
    };
    const draft = briefFromGeneratedSummary(generated, existing);
    expect(draft).not.toHaveProperty("landed_beats");
    expect(draft).not.toHaveProperty("required_beats");
  });

  it("steps chapter target length by 100 words", () => {
    expect(stepChapterTargetWords(2800, 2500, 1)).toBe(2900);
    expect(stepChapterTargetWords(2800, 2500, -1)).toBe(2700);
    expect(stepChapterTargetWords(0, 2500, 1)).toBe(2600);
    expect(stepChapterTargetWords(0, 2500, -1)).toBe(2400);
    expect(stepChapterTargetWords(150, 2500, -1)).toBe(100);
  });
});
