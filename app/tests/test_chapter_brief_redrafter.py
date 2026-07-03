"""Tests for redraft-from-brief (ChapterBriefRedrafter)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_brief_redrafter import ChapterBriefRedrafter, VALID_MODES  # noqa: E402
from chapter_brief_utils import brief_has_content  # noqa: E402
from state_manager import Character, PlotThread, StoryState, initialize_project  # noqa: E402
from story_graph import ChapterBrief, migrate_plot_threads_to_graph  # noqa: E402


def _seed_redraft_project(tmp_path):
    proj = tmp_path / "redraft_novel"
    initialize_project(str(proj), "Redraft Test", "Thriller")
    state = StoryState(str(proj))
    state.add_character(
        Character(id="char_a", full_name="Alice", role="protagonist"),
    )
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="The Heist",
            description="Steal the vault key",
            thread_type="main",
            status="active",
            priority=5,
        ),
    )
    migrate_plot_threads_to_graph(state)
    main_node_id = next(
        nid for nid, n in state.story_graph_nodes.items() if n.kind == "main"
    )
    state.set_chapter_brief(
        ChapterBrief(
            chapter_number=2,
            pov_character_id="char_a",
            pov_mode="third_limited",
            active_character_ids=["char_a"],
            active_node_ids=[main_node_id],
            required_beats=["Alarm fails"],
            continuity_notes="Alice has the keycard.",
            ending_hook="The vault opens.",
        ),
    )
    state.create_chapter(2)
    state.save_state()

    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_002_final.md").write_text(
        "Alice walked to the vault. The alarm blared.", encoding="utf-8",
    )
    (proj / "outputs" / "chapter_002_outline.md").write_text(
        "# Chapter 2\n\n## Beats\n1. Approach vault\n2. Alarm\n", encoding="utf-8",
    )
    return proj


def test_brief_has_content_matches_ts_logic():
    assert not brief_has_content(None)
    assert not brief_has_content(ChapterBrief(chapter_number=1))
    assert brief_has_content(ChapterBrief(chapter_number=1, pov_character_id="char_a"))
    assert brief_has_content(ChapterBrief(chapter_number=1, required_beats=["  beat  "]))
    assert brief_has_content(ChapterBrief(chapter_number=1, continuity_notes=" note "))


def test_redraft_dry_run_align_includes_brief_and_reference(tmp_path):
    proj = _seed_redraft_project(tmp_path)
    rd = ChapterBriefRedrafter(str(proj))

    _, prompt_path = rd.redraft(2, source="final", mode="align", dry_run=True)
    prompt = Path(prompt_path).read_text(encoding="utf-8")

    assert "CHAPTER REDRAFT FROM BRIEF" in prompt
    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "keycard" in prompt
    assert "## Beat sheet" in prompt
    assert "Approach vault" in prompt
    assert "Reference prose (final)" in prompt
    assert "Alice walked to the vault" in prompt
    assert "**Align mode:**" in prompt


def test_redraft_dry_run_preserve_mode_instructions(tmp_path):
    proj = _seed_redraft_project(tmp_path)
    rd = ChapterBriefRedrafter(str(proj))

    _, prompt_path = rd.redraft(2, source="final", mode="preserve", dry_run=True)
    prompt = Path(prompt_path).read_text(encoding="utf-8")

    assert "**Preserve mode:**" in prompt
    assert "scene order" in prompt.lower()


def test_redraft_requires_brief_with_content(tmp_path):
    proj = tmp_path / "empty"
    initialize_project(str(proj), "Empty", "Drama")
    state = StoryState(str(proj))
    state.create_chapter(1)
    state.save_state()
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_final.md").write_text("Some prose.", encoding="utf-8")

    rd = ChapterBriefRedrafter(str(proj))
    with pytest.raises(ValueError, match="no saved brief"):
        rd.redraft(1, dry_run=True)


def test_redraft_requires_readable_source(tmp_path):
    proj = _seed_redraft_project(tmp_path)
    rd = ChapterBriefRedrafter(str(proj))

    with pytest.raises(ValueError, match="Invalid source"):
        rd.redraft(2, source="bogus", dry_run=True)

    with pytest.raises(FileNotFoundError):
        rd.redraft(2, source="draft", dry_run=True)


def test_redraft_invalid_mode(tmp_path):
    proj = _seed_redraft_project(tmp_path)
    rd = ChapterBriefRedrafter(str(proj))

    with pytest.raises(ValueError, match="Invalid mode"):
        rd.redraft(2, mode="rewrite", dry_run=True)

    assert VALID_MODES == frozenset({"align", "preserve"})
