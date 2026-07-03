"""Single source for POV and writing-style blocks in AI prompts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from state_manager import ChapterState, StoryState
    from story_graph import ChapterBrief

POV_MODE_LABELS: dict[str, str] = {
    "first_person": "First person",
    "third_limited": "Third person limited",
    "third_omniscient": "Third person omniscient",
    "second_person": "Second person",
    "multiple_pov": "Multiple POV",
    "epistolary": "Epistolary",
    "other": "Other",
}


def format_pov_mode_label(mode: str) -> str:
    key = (mode or "").strip()
    if not key:
        return ""
    return POV_MODE_LABELS.get(key, key.replace("_", " "))


def project_chapter_target_default(state: "StoryState") -> int:
    """Project-wide chapter length default (Chapter style defaults)."""
    sp = state.style_profile
    if sp is not None and (getattr(sp, "chapter_target_words", 0) or 0) > 0:
        return int(sp.chapter_target_words)
    return 2500


def effective_target_word_count(
    brief: Optional["ChapterBrief"],
    state: "StoryState",
    chapter: Optional["ChapterState"] = None,
) -> int:
    """Resolve chapter length: brief override (if >0), else project default."""
    if brief is not None and (getattr(brief, "target_word_count", 0) or 0) > 0:
        return int(brief.target_word_count)
    return project_chapter_target_default(state)


def normalize_brief_target_for_storage(brief: "ChapterBrief", state: "StoryState") -> None:
    """Store 0 on the brief when length matches the project default (inherit, not duplicate)."""
    target = int(getattr(brief, "target_word_count", 0) or 0)
    if target <= 0:
        brief.target_word_count = 0
        return
    if target == project_chapter_target_default(state):
        brief.target_word_count = 0


def normalize_brief_for_storage(brief: "ChapterBrief", state: "StoryState") -> None:
    """Clear brief fields that match project defaults so storage means override only."""
    sp = state.style_profile
    normalize_brief_target_for_storage(brief, state)
    if (brief.pov_mode or "").strip() == (getattr(sp, "point_of_view", "") or "third_limited").strip():
        brief.pov_mode = ""
    if (brief.tone or "").strip() == (getattr(sp, "tone", "") or "neutral").strip():
        brief.tone = ""
    if (brief.tense or "").strip() == (getattr(sp, "tense", "") or "past").strip():
        brief.tense = ""
    if (brief.prose_style or "").strip() == (getattr(sp, "prose_style", "") or "balanced").strip():
        brief.prose_style = ""
    if (brief.vocabulary_level or "").strip() == (getattr(sp, "vocabulary_level", "") or "moderate").strip():
        brief.vocabulary_level = ""
    if (brief.style_notes or "").strip() == (getattr(sp, "description", "") or "").strip():
        brief.style_notes = ""


def _strip_markdown_section(text: str, heading: str) -> str:
    pattern = rf"(?ms)^##\s+{re.escape(heading)}\s*\n.*?(?=^##\s+|\Z)"
    return re.sub(pattern, "", text).strip()


def strip_outline_brief_duplicate_sections(
    outline: str,
    brief: Optional["ChapterBrief"],
) -> str:
    """Drop outline sections already defined on the chapter brief (avoid duplicate prompt blocks)."""
    if not (outline or "").strip() or brief is None:
        return outline
    text = outline
    if (brief.continuity_notes or "").strip():
        text = _strip_markdown_section(text, "Continuity Notes")
    if (brief.ending_hook or "").strip():
        text = _strip_markdown_section(text, "Ending Hook")
    return text.strip()


def effective_pov_mode(brief: Optional["ChapterBrief"], style_profile) -> str:
    """Chapter brief owns perspective; project style profile is the default."""
    if brief is not None and (getattr(brief, "pov_mode", "") or "").strip():
        return brief.pov_mode.strip()
    if style_profile is not None:
        return (getattr(style_profile, "point_of_view", "") or "third_limited").strip()
    return "third_limited"


def _brief_field(brief: Optional["ChapterBrief"], name: str, fallback: str) -> str:
    if brief is not None:
        value = (getattr(brief, name, "") or "").strip()
        if value:
            return value
    return fallback


def resolve_brief_style(brief: Optional["ChapterBrief"], style_profile) -> dict[str, str]:
    """Effective writing-style values: brief overrides, else project defaults."""
    sp = style_profile
    return {
        "tone": _brief_field(brief, "tone", (getattr(sp, "tone", "") or "neutral").strip()),
        "tense": _brief_field(brief, "tense", (getattr(sp, "tense", "") or "past").strip()),
        "prose_style": _brief_field(
            brief, "prose_style", (getattr(sp, "prose_style", "") or "balanced").strip(),
        ),
        "vocabulary_level": _brief_field(
            brief, "vocabulary_level", (getattr(sp, "vocabulary_level", "") or "moderate").strip(),
        ),
        "style_notes": _brief_field(brief, "style_notes", (getattr(sp, "description", "") or "").strip()),
        "pov_mode": effective_pov_mode(brief, style_profile),
    }


def format_brief_style_section(brief: Optional["ChapterBrief"], style_profile) -> str:
    """Writing-style block for prompts — always emitted from resolved brief + project defaults."""
    resolved = resolve_brief_style(brief, style_profile)
    lines = [
        f"- **Tone:** {resolved['tone']}",
        f"- **Tense:** {resolved['tense']}",
        f"- **Prose style:** {resolved['prose_style']}",
        f"- **Vocabulary level:** {resolved['vocabulary_level']}",
    ]
    sp = style_profile
    if sp is not None:
        if getattr(sp, "avg_sentence_length", 0):
            lines.append(f"- **Target average sentence length:** {sp.avg_sentence_length} words")
        if getattr(sp, "paragraph_max_sentences", 0):
            lines.append(f"- **Max sentences per paragraph:** {sp.paragraph_max_sentences}")
        dialogue = getattr(sp, "dialogue_ratio", 0) or 0
        description = getattr(sp, "description_ratio", 0) or 0
        internal = getattr(sp, "internal_monologue_ratio", 0) or 0
        if dialogue or description or internal:
            ratio_bits = []
            if dialogue:
                ratio_bits.append(f"dialogue ~{int(dialogue * 100)}%")
            if description:
                ratio_bits.append(f"description ~{int(description * 100)}%")
            if internal:
                ratio_bits.append(f"internal monologue ~{int(internal * 100)}%")
            lines.append(f"- **Composition targets:** {', '.join(ratio_bits)}")
        dialect = (getattr(sp, "dialect_notes", "") or "").strip()
        if dialect:
            lines.append(f"- **Dialect / voice notes:** {dialect}")
        genre = [g.strip() for g in (getattr(sp, "genre_conventions", None) or []) if (g or "").strip()]
        if genre:
            lines.append(f"- **Genre conventions:** {', '.join(genre)}")
        forbidden = [w.strip() for w in (getattr(sp, "forbidden_words", None) or []) if (w or "").strip()]
        if forbidden:
            lines.append(f"- **Words to avoid:** {', '.join(forbidden)}")
        preferred = getattr(sp, "preferred_words", None) or {}
        pref_pairs = [
            f"{k} → {v}" for k, v in preferred.items() if (k or "").strip() and (v or "").strip()
        ]
        if pref_pairs:
            lines.append(f"- **Preferred word choices:** {'; '.join(pref_pairs)}")
    if resolved["style_notes"]:
        lines.append(f"- **Style notes:** {resolved['style_notes']}")
    inherit_bits = []
    if brief is not None:
        if not (getattr(brief, "tone", "") or "").strip():
            inherit_bits.append("tone")
        if not (getattr(brief, "tense", "") or "").strip():
            inherit_bits.append("tense")
        if not (getattr(brief, "prose_style", "") or "").strip():
            inherit_bits.append("prose")
        if not (getattr(brief, "vocabulary_level", "") or "").strip():
            inherit_bits.append("vocabulary")
        if not (getattr(brief, "style_notes", "") or "").strip():
            inherit_bits.append("style notes")
    if inherit_bits:
        lines.append(
            f"- _(Inherited from project defaults: {', '.join(inherit_bits)})_"
        )
    return "### Writing Style\n" + "\n".join(lines)


def effective_pov_character_name(
    state: "StoryState",
    brief: Optional["ChapterBrief"],
    chapter: "ChapterState",
) -> str:
    """Chapter brief owns viewpoint character; chapter.pov_character is synced legacy display."""
    from story_graph import character_display_name  # noqa: WPS433

    pov_id = ""
    if brief is not None:
        pov_id = (getattr(brief, "pov_character_id", "") or "").strip()
    if pov_id:
        name = character_display_name(state, pov_id)
        if not name.startswith("[unknown"):
            return name
    return (chapter.pov_character or "").strip()


def format_chapter_pov_display(
    state: "StoryState",
    chapter_number: int,
    *,
    chapter: Optional["ChapterState"] = None,
    brief: Optional["ChapterBrief"] = None,
) -> str:
    """Human-readable POV for UI badges (character · perspective)."""
    if chapter is None:
        chapter = state.get_chapter(chapter_number)
    if brief is None:
        brief = state.get_chapter_brief(chapter_number)
    if chapter is None:
        return ""

    name = effective_pov_character_name(state, brief, chapter)
    mode = format_pov_mode_label(effective_pov_mode(brief, state.style_profile))
    if name and mode:
        return f"{name} · {mode}"
    if name:
        return name
    if mode:
        return mode
    return ""


def _is_pov_metadata_line(line: str) -> bool:
    text = re.sub(r"\*\*", "", line.strip()).strip()
    if not text:
        return False
    lower = text.lower()
    if re.match(r"^pov\s*:", lower):
        return True
    return bool(
        re.match(
            r"^(?:pov|point of view|narrative perspective|viewpoint character)\s*[:—\-]",
            lower,
        )
    )


def strip_outline_pov_metadata(text: str) -> str:
    """Remove POV header/metadata from outline markdown — POV lives on the chapter brief."""
    if not (text or "").strip():
        return text
    kept: list[str] = []
    for raw in text.splitlines():
        if _is_pov_metadata_line(raw):
            continue
        kept.append(raw)
    collapsed: list[str] = []
    blank_run = 0
    for line in kept:
        if not line.strip():
            blank_run += 1
            if blank_run <= 2:
                collapsed.append(line)
            continue
        blank_run = 0
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def build_chapter_context_block(
    state: "StoryState",
    chapter: "ChapterState",
    *,
    hint_text: str = "",
    outline_text: Optional[str] = None,
    budget=None,
) -> str:
    """Chapter brief (canonical) + plot + outline beats (metadata stripped, brief sections deduped)."""
    from context_resolver import BUDGET_DRAFT  # noqa: WPS433
    from plot_prompts import format_plot_threads_block  # noqa: WPS433
    from story_graph import ChapterBrief, format_chapter_brief_prompt_context  # noqa: WPS433

    if budget is None:
        budget = BUDGET_DRAFT

    sections: list[str] = []
    saved = state.get_chapter_brief(chapter.number)
    brief = saved if saved is not None else ChapterBrief(chapter_number=chapter.number)
    brief_block = format_chapter_brief_prompt_context(
        state,
        brief,
        hint_text=hint_text,
        budget=budget,
    )
    if brief_block.strip():
        sections.append(brief_block)

    plot_block = format_plot_threads_block(state.get_active_plot_threads(), max_threads=8)
    if plot_block.strip():
        sections.append(plot_block)

    outline = strip_outline_pov_metadata((outline_text or "").strip())
    outline = strip_outline_brief_duplicate_sections(outline, brief)
    if outline:
        from chapter_brief_utils import beats_for_prompt  # noqa: WPS433

        beat_note = (
            "_(Story beats — POV/style/continuity/hook are in the chapter brief above.)_"
        )
        chapter_beats = beats_for_prompt(state, chapter.number, brief)
        if chapter_beats:
            beat_note = (
                "_(Outline beats below; **Chapter Beats** in the chapter brief take precedence on conflict.)_"
            )
        elif any((b or "").strip() for b in (brief.required_beats or [])):
            beat_note = (
                "_(Outline beats below; **Required Beats** in the chapter brief take precedence on conflict.)_"
            )
        sections.append(f"## Beat sheet\n{beat_note}\n\n{outline}")

    return "\n\n".join(sections)
