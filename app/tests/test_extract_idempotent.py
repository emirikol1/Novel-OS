"""Extraction should not duplicate characters, plots, subplots, or bible facts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from state_manager import PlotThread, StoryState, initialize_project
from state_parser import (
    apply_chapter_bible_mine,
    apply_chapter_character_mine,
    apply_chapter_plot_mine,
    apply_import_to_state,
)


def test_repeated_plot_mine_is_idempotent(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    state.add_plot_thread(
        PlotThread(id="plot_main", name="Heist Arc", description="Vault job", thread_type="main"),
    )
    payload = {
        "plot_threads": ["Heist Arc | main | The vault job | Alice"],
        "subplot_threads": ["Heist Arc | Hidden Letter | Jordan finds a sealed letter"],
        "subplot_beats": ["Heist Arc | The vault alarm fails"],
        "plot_events": ["Alice reaches the vault door"],
        "resolved_subplots": [],
    }
    apply_chapter_plot_mine(state, 1, payload, source="mine_plots")
    apply_chapter_plot_mine(state, 1, payload, source="mine_plots")

    assert len(state.plot_threads) == 1
    main = state.plot_threads["plot_main"]
    assert len(main.subplots) == 2
    assert len(state.chapters[1].plot_advances) == 1


def test_repeated_character_mine_is_idempotent(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    payload = {
        "characters_present": ["Alice"],
        "new_characters": ["Alice | supporting | Vault expert"],
        "character_updates": [],
        "emotional_shifts": [],
        "key_events": ["Alice picks the lock"],
    }
    apply_chapter_character_mine(state, 1, payload, source="mine_characters")
    apply_chapter_character_mine(state, 1, payload, source="mine_characters")

    assert len(state.characters) == 1
    assert len(state.chapters[1].plot_advances) == 1


def test_repeated_bible_mine_is_idempotent(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    payload = {
        "story_bible_notes": ["Magic drains stamina quickly"],
        "world_facts": ["The city bans unsanctioned magic"],
        "relationships": ["Alice mentors Jordan"],
        "setting_details": ["Coastal port city with fog"],
    }
    apply_chapter_bible_mine(state, 1, payload, source="mine_bible")
    apply_chapter_bible_mine(state, 1, payload, source="mine_bible")

    assert len(state.story_bible["import_notes"]) == 1
    assert len(state.story_bible["world_rules"]) == 1
    assert len(state.story_bible["relationships"]) == 1
    assert state.story_bible["setting_summary"] == ["Coastal port city with fog"]


def test_archivist_import_skips_duplicate_subplot_across_threads(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="Main arc",
            description="Main",
            thread_type="main",
            subplots=["Hidden inheritance: protagonist learns the truth"],
        ),
    )
    state.add_plot_thread(PlotThread(id="plot_other", name="Side cases", description="Side", thread_type="main"))

    log = apply_import_to_state(
        state,
        1,
        {
            "subplot_threads": [
                "Side cases | Hidden inheritance | protagonist learns the truth",
            ],
            "plot_threads": [],
            "subplot_beats": [],
            "resolved_subplots": [],
            "plot_events": [],
            "new_characters": [],
            "character_updates": [],
        },
        source="archivist",
    )
    side = state.plot_threads["plot_other"]
    assert len(side.subplots) == 0
    assert any("skipped duplicate subplot" in line for line in log)
