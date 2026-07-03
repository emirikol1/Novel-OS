"""Tests for plot description generator parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from plot_generator import collect_bible_supporting_context, parse_plot_thread_update
from state_manager import StoryState, initialize_project


def test_parse_plot_thread_update_block():
    raw = """
Some analysis here.

[PLOT_THREAD_UPDATE]
Description: Jordan uncovers museum secrets while investigating a theft.
Bible_Suggestions:
- Theme of truth vs loyalty from the story bible
- Coastal Maine setting atmosphere
[/PLOT_THREAD_UPDATE]
"""
    parsed = parse_plot_thread_update(raw)
    assert "Jordan uncovers" in parsed["description"]
    assert len(parsed["bible_suggestions"]) == 2


def test_collect_bible_supporting_context(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.update_story_bible("themes", ["grief", "identity"])
    ctx = collect_bible_supporting_context(state)
    assert "grief" in ctx
    assert "Themes" in ctx
    assert "Tone" not in ctx


def test_collect_bible_supporting_context_budget_omits_extras(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.update_story_bible("logline", "A long logline about betrayal in the vault district.")
    state.update_story_bible("themes", ["grief", "identity", "memory", "loss"])
    state.update_story_bible("setting_summary", "Rain-soaked coastal city with flooded archives.")
    state.update_story_bible("world_rules", ["No resurrection", "Magic costs memory"])
    state.update_story_bible("historical_context", "Fifty years of floods and sealed vaults.")
    state.update_story_bible(
        "premise_beats",
        [f"Beat {i}: vault alarm Jordan skeptical thread detail {i} " * 6 for i in range(16)],
    )
    state.update_story_bible(
        "import_notes",
        [f"Note {i}: vault alarm Jordan skeptical thread {i} " * 6 for i in range(16)],
    )

    ctx = collect_bible_supporting_context(state, hint_text="vault alarm Jordan")
    assert "Omitted" in ctx
    assert "Logline" in ctx or "Themes" in ctx
