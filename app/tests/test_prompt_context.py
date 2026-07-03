"""Tests for canonical POV/style prompt assembly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from prompt_context import (  # noqa: E402
    build_chapter_context_block,
    effective_target_word_count,
    format_brief_style_section,
    normalize_brief_for_storage,
    normalize_brief_target_for_storage,
    project_chapter_target_default,
    resolve_brief_style,
    strip_outline_brief_duplicate_sections,
    strip_outline_pov_metadata,
)
from state_manager import Character, PlotThread, StoryState, initialize_project  # noqa: E402
from story_graph import ChapterBeat, ChapterBrief, StoryGraphNode, format_chapter_brief_prompt_context  # noqa: E402


def _project(tmp_path):
    proj = tmp_path / "style_novel"
    initialize_project(str(proj), "Style Novel", "Literary")
    state = StoryState(str(proj))
    state.style_profile.tone = "noir"
    state.style_profile.tense = "past"
    state.style_profile.prose_style = "minimalist"
    state.style_profile.vocabulary_level = "literary"
    state.style_profile.description = "Avoid adverbs."
    state.style_profile.point_of_view = "third_limited"
    state.style_profile.chapter_target_words = 3000
    state.add_character(Character(id="char_a", full_name="Alice", role="protagonist"))
    state.create_chapter(1)
    state.save_state()
    return proj, state


def test_resolve_brief_style_uses_project_defaults(tmp_path):
    _, state = _project(tmp_path)
    resolved = resolve_brief_style(ChapterBrief(chapter_number=1), state.style_profile)
    assert resolved["tone"] == "noir"
    assert resolved["tense"] == "past"
    assert resolved["prose_style"] == "minimalist"
    assert resolved["style_notes"] == "Avoid adverbs."


def test_resolve_brief_style_prefers_brief_overrides(tmp_path):
    _, state = _project(tmp_path)
    brief = ChapterBrief(chapter_number=1, tone="hopeful", tense="present", style_notes="More warmth.")
    resolved = resolve_brief_style(brief, state.style_profile)
    assert resolved["tone"] == "hopeful"
    assert resolved["tense"] == "present"
    assert resolved["style_notes"] == "More warmth."
    assert resolved["prose_style"] == "minimalist"


def test_format_brief_style_section_includes_tone_and_notes(tmp_path):
    _, state = _project(tmp_path)
    block = format_brief_style_section(ChapterBrief(chapter_number=1), state.style_profile)
    assert "### Writing Style" in block
    assert "**Tone:** noir" in block
    assert "**Style notes:** Avoid adverbs." in block


def test_strip_outline_pov_metadata_removes_header_line():
    raw = (
        "# Chapter 1: Open\n\n"
        "**POV:** Alice | **Source:** draft\n\n"
        "## Beats\n"
        "1. **Start** — Alice wakes.\n"
    )
    cleaned = strip_outline_pov_metadata(raw)
    assert "POV:" not in cleaned
    assert "Alice wakes" in cleaned


def test_build_chapter_context_always_includes_style_without_saved_brief(tmp_path):
    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    block = build_chapter_context_block(state, chapter)
    assert "## Chapter Brief" in block
    assert "### Writing Style" in block
    assert "### Target Length" in block
    assert "**Tone:** noir" in block
    assert "Beat sheet" not in block


def test_format_chapter_brief_prompt_context_includes_target_length(tmp_path):
    _, state = _project(tmp_path)
    brief = ChapterBrief(chapter_number=1, target_word_count=3200)
    ctx = format_chapter_brief_prompt_context(state, brief)
    assert "### Target Length" in ctx
    assert "3,200 words" in ctx


def test_effective_target_word_count_ignores_chapter_record(tmp_path):
    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    chapter.target_word_count = 1800
    assert effective_target_word_count(ChapterBrief(chapter_number=1), state, chapter) == 3000


def test_effective_target_word_count_prefers_brief(tmp_path):
    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    chapter.target_word_count = 1800
    brief = ChapterBrief(chapter_number=1, target_word_count=3200)
    assert effective_target_word_count(brief, state, chapter) == 3200


def test_normalize_brief_for_storage_clears_project_defaults(tmp_path):
    _, state = _project(tmp_path)
    brief = ChapterBrief(
        chapter_number=1,
        pov_mode="third_limited",
        tone="noir",
        tense="past",
        prose_style="minimalist",
        vocabulary_level="literary",
        style_notes="Avoid adverbs.",
        target_word_count=3000,
    )
    normalize_brief_for_storage(brief, state)
    assert brief.pov_mode == ""
    assert brief.tone == ""
    assert brief.tense == ""
    assert brief.prose_style == ""
    assert brief.vocabulary_level == ""
    assert brief.style_notes == ""
    assert brief.target_word_count == 0
    brief.tone = "hopeful"
    normalize_brief_for_storage(brief, state)
    assert brief.tone == "hopeful"


def test_strip_outline_brief_duplicate_sections():
    outline = (
        "## Beats\n1. Alice enters.\n\n"
        "## Continuity Notes\nOld note from outline.\n\n"
        "## Ending Hook\nOld hook.\n"
    )
    brief = ChapterBrief(
        chapter_number=1,
        continuity_notes="Brief continuity wins.",
        ending_hook="Brief hook wins.",
    )
    cleaned = strip_outline_brief_duplicate_sections(outline, brief)
    assert "Continuity Notes" not in cleaned
    assert "Ending Hook" not in cleaned
    assert "Alice enters" in cleaned


def test_build_chapter_context_strips_duplicate_outline_sections(tmp_path):
    from story_graph import ChapterBeat

    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    brief = ChapterBrief(
        chapter_number=1,
        continuity_notes="From brief.",
        ending_hook="Brief hook.",
    )
    state.set_chapter_brief(brief)
    state.set_chapter_beats(
        1,
        [ChapterBeat(id="beat_1_001", title="Must include the vault", status="planned")],
    )
    state.save_state()
    outline = (
        "## Beats\n1. Scene one.\n\n"
        "## Continuity Notes\nFrom outline.\n\n"
        "## Ending Hook\nFrom outline.\n"
    )
    block = build_chapter_context_block(state, chapter, outline_text=outline)
    assert "From brief." in block
    assert "From outline." not in block
    assert "Required Beats" in block or "take precedence" in block


def test_build_chapter_context_prefers_chapter_beats_precedence_note(tmp_path):
    from story_graph import ChapterBeat

    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    brief = ChapterBrief(chapter_number=1)
    state.set_chapter_brief(brief)
    state.set_chapter_beats(
        1,
        [ChapterBeat(id="beat_1_001", title="Canonical beat", status="planned")],
    )
    state.save_state()
    outline = "## Beats\n1. Outline beat only.\n"
    block = build_chapter_context_block(state, chapter, outline_text=outline)
    assert "**Chapter Beats** in the chapter brief take precedence" in block


def test_build_chapter_context_uses_chapter_beats(tmp_path):
    from story_graph import ChapterBeat

    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    brief = ChapterBrief(chapter_number=1)
    state.set_chapter_brief(brief)
    state.set_chapter_beats(
        1,
        [ChapterBeat(id="beat_1_001", title="Must include the vault", status="planned")],
    )
    state.save_state()
    outline = "## Beats\n1. Outline beat only.\n"
    block = build_chapter_context_block(state, chapter, outline_text=outline)
    assert "**Chapter Beats** in the chapter brief take precedence" in block


def test_build_chapter_context_graph_focus_suppresses_legacy_plots(tmp_path):
    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    state.add_plot_thread(
        PlotThread(
            id="plot_legacy",
            name="Legacy Active Thread",
            description="Old broad plot context",
            thread_type="main",
            status="active",
        ),
    )
    state.story_graph_nodes["node_current"] = StoryGraphNode(
        id="node_current",
        kind="plot_thread",
        title="Current Graph Focus",
        description="Use this graph node",
        priority=5,
    )
    state.set_chapter_brief(ChapterBrief(chapter_number=1, active_node_ids=["node_current"]))

    block = build_chapter_context_block(state, chapter)

    assert "Current Graph Focus" in block
    assert "Legacy Active Thread" not in block


def test_build_chapter_context_legacy_plots_fallback_without_graph_focus(tmp_path):
    _, state = _project(tmp_path)
    chapter = state.get_chapter(1)
    assert chapter is not None
    state.add_plot_thread(
        PlotThread(
            id="plot_legacy",
            name="Legacy Active Thread",
            description="Fallback plot context",
            thread_type="main",
            status="active",
        ),
    )
    state.set_chapter_brief(ChapterBrief(chapter_number=1))

    block = build_chapter_context_block(state, chapter)

    assert "Legacy Active Thread" in block


def test_build_chapter_context_recent_facts_require_current_graph_link(tmp_path):
    _, state = _project(tmp_path)
    state.create_chapter(2)
    chapter = state.get_chapter(2)
    assert chapter is not None
    state.story_graph_nodes["node_current"] = StoryGraphNode(
        id="node_current",
        kind="plot_thread",
        title="Current Graph Focus",
        priority=5,
    )
    state.story_graph_nodes["node_other"] = StoryGraphNode(
        id="node_other",
        kind="plot_thread",
        title="Unrelated Graph Focus",
        priority=5,
    )
    state.set_chapter_beats(
        1,
        [
            ChapterBeat(
                id="beat_1_001",
                title="Related landed fact",
                status="landed",
                linked_node_ids=["node_current"],
            ),
            ChapterBeat(
                id="beat_1_002",
                title="Unrelated landed fact",
                status="landed",
                linked_node_ids=["node_other"],
            ),
        ],
    )
    state.set_chapter_brief(ChapterBrief(chapter_number=2, active_node_ids=["node_current"]))

    block = build_chapter_context_block(state, chapter)

    assert "Related landed fact" in block
    assert "Unrelated landed fact" not in block


def test_normalize_brief_target_for_storage_clears_project_default(tmp_path):
    _, state = _project(tmp_path)
    brief = ChapterBrief(chapter_number=1, target_word_count=3000)
    normalize_brief_target_for_storage(brief, state)
    assert brief.target_word_count == 0
    brief.target_word_count = 3200
    normalize_brief_target_for_storage(brief, state)
    assert brief.target_word_count == 3200
