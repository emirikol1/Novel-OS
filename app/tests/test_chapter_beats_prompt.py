"""Structure V2 P5: chapter beat prompt helpers (synthetic projects only)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_brief_utils import (  # noqa: E402
    beats_for_prompt,
    format_chapter_beats_for_outline_prompt,
    format_chapter_beats_section,
    infer_cast_from_text,
    merge_cast_ids,
)
from state_manager import Character, StoryState, initialize_project  # noqa: E402
from story_graph import ChapterBeat, ChapterBrief  # noqa: E402


def _seed_cast_project(tmp_path):
    proj = tmp_path / "cast_novel"
    initialize_project(str(proj), "Cast Novel", "Drama")
    state = StoryState(str(proj))
    state.add_character(Character(id="char_a", full_name="Alice", role="protagonist"))
    state.add_character(Character(id="char_b", full_name="Bob", role="antagonist"))
    state.create_chapter(1)
    state.save_state()
    return proj, state


def test_infer_cast_from_text_splits_mentioned_and_active(tmp_path):
    _, state = _seed_cast_project(tmp_path)
    text = (
        "Alice walked through the vault. They whispered about Bob, "
        "but he never appeared on the page."
    )
    mentioned, active = infer_cast_from_text(state, text, pov_name="Alice")
    assert "char_a" in mentioned
    assert "char_b" in mentioned
    assert "char_a" in active
    assert "char_b" not in active


def test_infer_cast_from_text_includes_char_mentions(tmp_path):
    _, state = _seed_cast_project(tmp_path)
    text = "They talked about [[char:Bob]] while Alice watched."
    mentioned, active = infer_cast_from_text(state, text, pov_name="Alice")
    assert "char_b" in mentioned
    assert "char_a" in mentioned


def test_beats_for_prompt_prefers_chapter_beats(tmp_path):
    _, state = _seed_cast_project(tmp_path)
    brief = ChapterBrief(
        chapter_number=1,
        required_beats=["Legacy required"],
        landed_beats=["Legacy landed"],
    )
    state.set_chapter_beats(
        1,
        [
            ChapterBeat(id="beat_1_001", title="Planned beat", status="planned"),
            ChapterBeat(id="beat_1_002", title="Landed beat", status="landed"),
        ],
    )
    beats = beats_for_prompt(state, 1, brief)
    assert len(beats) == 2
    assert beats[0].title == "Planned beat"


def test_beats_for_prompt_synthesizes_from_legacy_strings(tmp_path):
    _, state = _seed_cast_project(tmp_path)
    brief = ChapterBrief(
        chapter_number=1,
        required_beats=["Plan the heist"],
        landed_beats=["Vault opens"],
    )
    beats = beats_for_prompt(state, 1, brief)
    assert len(beats) == 2
    assert beats[0].status == "planned"
    assert beats[1].status == "landed"


def test_format_chapter_beats_section_includes_status(tmp_path):
    beats = [
        ChapterBeat(id="b1", title="Alarm fails", status="planned", sort_order=0),
        ChapterBeat(id="b2", title="Vault opens", status="landed", sort_order=1),
    ]
    block = format_chapter_beats_section(beats, include_status=True)
    assert "### Chapter Beats" in block
    assert "**[planned]** Alarm fails" in block
    assert "**[landed]** Vault opens" in block


def test_merge_cast_ids_unions_without_duplicates():
    merged = merge_cast_ids(["char_a"], ["char_b", "char_a"])
    assert merged == ["char_a", "char_b"]


def test_format_chapter_beats_for_outline_prompt(tmp_path):
    proj = tmp_path / "outline_novel"
    initialize_project(str(proj), "Outline Novel", "Drama")
    state = StoryState(str(proj))
    state.set_chapter_beats(
        1,
        [
            ChapterBeat(id="b1", title="Setup", status="planned", sort_order=0),
            ChapterBeat(id="b2", title="Payoff", status="landed", sort_order=1),
        ],
    )
    state.save_state()
    reloaded = StoryState(str(proj))
    brief = ChapterBrief(chapter_number=1)
    block = format_chapter_beats_for_outline_prompt(reloaded, 1, brief)
    assert "Chapter beats (authoritative" in block
    assert "[planned]" in block
    assert "[landed]" in block
    assert "**Setup**" in block
    assert "**Payoff**" in block
