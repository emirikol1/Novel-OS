import type { ChapterBriefSummary, CharacterSummary, StoryGraphNodeSummary } from "../api/client";

export type ProjectStyleDefaults = {
  tone: string;
  point_of_view: string;
  tense: string;
  prose_style: string;
  vocabulary_level: string;
  description: string;
  chapter_target_words: number;
};

export const DEFAULT_PROJECT_STYLE: ProjectStyleDefaults = {
  tone: "neutral",
  point_of_view: "third_limited",
  tense: "past",
  prose_style: "balanced",
  vocabulary_level: "moderate",
  description: "",
  chapter_target_words: 2500,
};

export type CharacterBriefPresence = "none" | "mentioned" | "active";

export type ChapterBriefDraft = {
  pov_character_id: string;
  pov_mode: string;
  tone: string;
  tense: string;
  prose_style: string;
  vocabulary_level: string;
  style_notes: string;
  target_word_count: number;
  mentioned_character_ids: string[];
  active_character_ids: string[];
  active_node_ids: string[];
  continuity_notes: string;
  ending_hook: string;
};

export const EMPTY_BRIEF_DRAFT: ChapterBriefDraft = {
  pov_character_id: "",
  pov_mode: "",
  tone: "",
  tense: "",
  prose_style: "",
  vocabulary_level: "",
  style_notes: "",
  target_word_count: 0,
  mentioned_character_ids: [],
  active_character_ids: [],
  active_node_ids: [],
  continuity_notes: "",
  ending_hook: "",
};

export const CHAPTER_TARGET_LENGTH_STEP = 100;

export function effectiveChapterTargetWords(
  override: number,
  projectDefault: number,
): number {
  if (override > 0) return override;
  const fallback = projectDefault > 0 ? projectDefault : DEFAULT_PROJECT_STYLE.chapter_target_words;
  return fallback;
}

/** Step chapter target length by ~100 words; blank override uses project default as the base. */
export function stepChapterTargetWords(
  currentOverride: number,
  projectDefault: number,
  direction: 1 | -1,
): number {
  const base = effectiveChapterTargetWords(currentOverride, projectDefault);
  const next = base + direction * CHAPTER_TARGET_LENGTH_STEP;
  return Math.max(CHAPTER_TARGET_LENGTH_STEP, next);
}

export function projectStyleFromRecord(style?: Record<string, string>): ProjectStyleDefaults {
  const rawTarget = style?.chapter_target_words;
  const parsedTarget = rawTarget ? Number.parseInt(rawTarget, 10) : NaN;
  return {
    tone: style?.tone ?? DEFAULT_PROJECT_STYLE.tone,
    point_of_view: style?.point_of_view ?? DEFAULT_PROJECT_STYLE.point_of_view,
    tense: style?.tense ?? DEFAULT_PROJECT_STYLE.tense,
    prose_style: style?.prose_style ?? DEFAULT_PROJECT_STYLE.prose_style,
    vocabulary_level: style?.vocabulary_level ?? DEFAULT_PROJECT_STYLE.vocabulary_level,
    description: style?.description ?? DEFAULT_PROJECT_STYLE.description,
    chapter_target_words: Number.isFinite(parsedTarget) && parsedTarget > 0
      ? parsedTarget
      : DEFAULT_PROJECT_STYLE.chapter_target_words,
  };
}

/** Return draft unchanged — empty style fields inherit from project defaults at prompt time. */
export function draftWithProjectDefaults(
  draft: ChapterBriefDraft,
  _style: ProjectStyleDefaults,
): ChapterBriefDraft {
  return draft;
}

export function briefFromSummary(brief: ChapterBriefSummary): ChapterBriefDraft {
  const active = [...(brief.active_character_ids ?? [])];
  const mentionedRaw = [...(brief.mentioned_character_ids ?? [])];
  const mentioned = mentionedRaw.length > 0
    ? mentionedRaw
    : [...active];
  return {
    pov_character_id: brief.pov_character_id ?? "",
    pov_mode: brief.pov_mode ?? "",
    tone: brief.tone ?? "",
    tense: brief.tense ?? "",
    prose_style: brief.prose_style ?? "",
    vocabulary_level: brief.vocabulary_level ?? "",
    style_notes: brief.style_notes ?? "",
    target_word_count: brief.target_word_count ?? 0,
    mentioned_character_ids: mentioned,
    active_character_ids: active,
    active_node_ids: [...(brief.active_node_ids ?? [])],
    continuity_notes: brief.continuity_notes ?? "",
    ending_hook: brief.ending_hook ?? "",
  };
}

/** Map a generated brief into the form; beats are managed on the beat board, not the brief draft. */
export function briefFromGeneratedSummary(
  generated: ChapterBriefSummary,
  existingDraft: ChapterBriefDraft,
): ChapterBriefDraft {
  const next = briefFromSummary(generated);
  const hasGeneratedMentioned = (generated.mentioned_character_ids ?? []).length > 0;
  if (!hasGeneratedMentioned && existingDraft.mentioned_character_ids.length > 0) {
    return {
      ...next,
      mentioned_character_ids: [...existingDraft.mentioned_character_ids],
    };
  }
  return next;
}

export function briefToPayload(draft: ChapterBriefDraft) {
  const mentioned = [...draft.mentioned_character_ids];
  const active = [...draft.active_character_ids];
  for (const id of active) {
    if (!mentioned.includes(id)) mentioned.push(id);
  }
  return {
    pov_character_id: draft.pov_character_id,
    pov_mode: draft.pov_mode,
    tone: draft.tone,
    tense: draft.tense,
    prose_style: draft.prose_style,
    vocabulary_level: draft.vocabulary_level,
    style_notes: draft.style_notes,
    target_word_count: draft.target_word_count > 0 ? draft.target_word_count : 0,
    mentioned_character_ids: mentioned,
    active_character_ids: active,
    active_node_ids: draft.active_node_ids,
    continuity_notes: draft.continuity_notes,
    ending_hook: draft.ending_hook,
  };
}

export function characterPresence(draft: ChapterBriefDraft, characterId: string): CharacterBriefPresence {
  if (draft.active_character_ids.includes(characterId)) return "active";
  if (draft.mentioned_character_ids.includes(characterId)) return "mentioned";
  return "none";
}

export function setCharacterPresence(
  draft: ChapterBriefDraft,
  characterId: string,
  presence: CharacterBriefPresence,
): ChapterBriefDraft {
  const mentioned = draft.mentioned_character_ids.filter((id) => id !== characterId);
  const active = draft.active_character_ids.filter((id) => id !== characterId);
  if (presence === "mentioned" || presence === "active") {
    mentioned.push(characterId);
  }
  if (presence === "active") {
    active.push(characterId);
  }
  return { ...draft, mentioned_character_ids: mentioned, active_character_ids: active };
}

export function promoteCharacterToActive(draft: ChapterBriefDraft, characterId: string): ChapterBriefDraft {
  return setCharacterPresence(draft, characterId, "active");
}

export function demoteCharacterFromActive(draft: ChapterBriefDraft, characterId: string): ChapterBriefDraft {
  const mentioned = draft.mentioned_character_ids.includes(characterId)
    ? [...draft.mentioned_character_ids]
    : [...draft.mentioned_character_ids, characterId];
  return {
    ...draft,
    mentioned_character_ids: mentioned,
    active_character_ids: draft.active_character_ids.filter((id) => id !== characterId),
  };
}

export function cycleCharacterPresence(draft: ChapterBriefDraft, characterId: string): ChapterBriefDraft {
  const current = characterPresence(draft, characterId);
  if (current === "none") return setCharacterPresence(draft, characterId, "mentioned");
  if (current === "mentioned") return setCharacterPresence(draft, characterId, "active");
  return setCharacterPresence(draft, characterId, "none");
}

export function toggleId(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export function characterNameById(characters: CharacterSummary[]): Map<string, string> {
  return new Map(characters.map((c) => [c.id, c.full_name]));
}

export function nodeTitleById(nodes: StoryGraphNodeSummary[]): Map<string, string> {
  return new Map(nodes.map((n) => [n.id, n.title]));
}

export function briefHasContent(draft: ChapterBriefDraft): boolean {
  return Boolean(
    draft.pov_character_id
    || draft.pov_mode
    || draft.tone.trim()
    || draft.tense.trim()
    || draft.prose_style.trim()
    || draft.vocabulary_level.trim()
    || draft.style_notes.trim()
    || draft.target_word_count > 0
    || draft.mentioned_character_ids.length
    || draft.active_character_ids.length
    || draft.active_node_ids.length
    || draft.continuity_notes.trim()
    || draft.ending_hook.trim(),
  );
}

/** Sample brief for unit tests only — not real project data. */
export const SAMPLE_CHAPTER_BRIEF: ChapterBriefSummary = {
  chapter_number: 3,
  pov_character_id: "char_a",
  pov_mode: "third_limited",
  tone: "tense",
  tense: "past",
  prose_style: "cinematic",
  vocabulary_level: "moderate",
  style_notes: "Short sentences under stress.",
  target_word_count: 2800,
  mentioned_character_ids: ["char_a", "char_b"],
  active_character_ids: ["char_a", "char_b"],
  active_node_ids: ["sg_main", "sg_sub2"],
  required_beats: ["Alice discovers the alarm code", "Bob hints at betrayal"],
  landed_beats: ["Vault alarm triggered"],
  continuity_notes: "Alice still has the keycard from ch. 2.",
  ending_hook: "The vault door opens — but someone is already inside.",
};

export const SAMPLE_BRIEF_CHARACTERS: CharacterSummary[] = [
  { id: "char_a", full_name: "Alice", role: "protagonist" },
  { id: "char_b", full_name: "Bob", role: "antagonist" },
];
