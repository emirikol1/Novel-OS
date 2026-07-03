"""Tests for chapter mining and plot nesting."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from entity_dedup import nest_plot_threads  # noqa: E402
from state_manager import Character, PlotThread, StoryState, initialize_project  # noqa: E402
from state_parser import apply_chapter_character_mine, apply_chapter_plot_mine, parse_chapter_character  # noqa: E402


def test_nest_plot_threads_adds_subplots(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    parent = PlotThread(id="plot_a", name="Main Arc", description="Primary", thread_type="main")
    child = PlotThread(
        id="plot_b", name="Side Quest", description="Find the key", thread_type="subplot",
        subplots=["Already had a beat"],
    )
    state.add_plot_thread(parent)
    state.add_plot_thread(child)

    log = nest_plot_threads(state, "plot_a", ["plot_b"])
    assert len(state.plot_threads) == 1
    kept = state.plot_threads["plot_a"]
    assert any("Side Quest" in s for s in kept.subplots)
    assert "Already had a beat" in kept.subplots
    assert any("Nested" in line for line in log)


def test_apply_chapter_plot_mine_subplot_beats(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.add_plot_thread(PlotThread(id="plot_x", name="Heist", description="", thread_type="main"))
    state.create_chapter(1)

    log = apply_chapter_plot_mine(
        state,
        1,
        {
            "subplot_beats": ["Heist | The vault alarm fails"],
            "plot_events": ["Team enters the building"],
        },
        source="test",
    )
    assert "The vault alarm fails" in state.plot_threads["plot_x"].subplots
    assert any("plot event" in line for line in log)


def test_apply_chapter_plot_mine_nests_subplot_threads(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.add_plot_thread(
        PlotThread(id="plot_main", name="Family Estate Arc", description="Family estate", thread_type="main"),
    )
    state.create_chapter(1)

    log = apply_chapter_plot_mine(
        state,
        1,
        {
            "subplot_threads": [
                "Family Estate Arc | Probate Hearing | Jordan skips the probate hearing",
            ],
        },
        source="test",
    )
    main = state.plot_threads["plot_main"]
    assert len(state.plot_threads) == 1
    assert any("Probate Hearing" in s for s in main.subplots)
    assert any("subplot" in line.lower() for line in log)


def test_apply_chapter_plot_mine_subplot_type_goes_under_main(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="Central Mystery",
            description="",
            thread_type="main",
            related_characters=[],
        ),
    )
    state.create_chapter(1)

    apply_chapter_plot_mine(
        state,
        1,
        {
            "plot_threads": [
                "Hidden Letter | subplot | Jordan finds a sealed letter in the attic | Jordan Lee",
            ],
        },
        source="test",
    )
    assert len(state.plot_threads) == 1
    main = state.plot_threads["plot_main"]
    assert any("Hidden Letter" in s for s in main.subplots)


def test_apply_chapter_plot_mine_removes_resolved_subplots(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="Family Estate Arc",
            description="",
            thread_type="main",
            subplots=["Probate Hearing: Jordan skips probate", "Hidden letter in attic"],
        ),
    )
    state.create_chapter(3)

    log = apply_chapter_plot_mine(
        state,
        3,
        {
            "resolved_subplots": [
                "Family Estate Arc | Probate Hearing | Jordan attends and settles the estate",
            ],
        },
        source="test",
    )
    subs = state.plot_threads["plot_main"].subplots
    assert not any("Probate Hearing" in s and "skips" in s for s in subs)
    assert any("Hidden letter" in s for s in subs)
    assert any("resolved subplot removed" in line for line in log)


def test_match_subplot_index_fuzzy(tmp_path):
    from entity_dedup import match_subplot_index  # noqa: E402

    lines = ["Marcus's Regret: Marcus hides the truth", "Side vault job"]
    assert match_subplot_index(lines, "Marcus's Regret") == 0
    assert match_subplot_index(lines, "Side vault") == 1


def test_character_mine_prompt_includes_mentioned_field():
    from chapter_miner import _character_prompt

    prompt = _character_prompt(1, "Sample prose.", "draft", "Opening")
    assert "Characters_Mentioned" in prompt
    assert "Characters_Present" in prompt
    assert "directly on-page" in prompt
    assert "Do not put the same character in both fields" in prompt
    assert "Relationship_Updates" in prompt
    assert "employer" in prompt
    assert "custom label" in prompt


def test_parse_chapter_character_relationship_updates():
    parsed = parse_chapter_character("""
[CHAPTER_CHARACTER_UPDATE]
Characters_Present:
  - Alice
Relationship_Updates:
  - Alice | employer | Bob | runs the workshop
[/CHAPTER_CHARACTER_UPDATE]
""")

    assert parsed["relationship_updates"] == ["Alice | employer | Bob | runs the workshop"]


def test_apply_chapter_character_mine_relationship_updates(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    state.add_character(Character(id="char_alice", full_name="Alice", role="protagonist"))
    state.add_character(Character(id="char_bob", full_name="Bob", role="supporting"))
    state.add_character(Character(id="char_clara", full_name="Clara", role="minor"))

    log = apply_chapter_character_mine(
        state,
        1,
        {
            "relationship_updates": [
                "Alice | employer | Bob | runs the workshop",
                "Bob | mentor | Clara",
                "Alice | secret informant | Clara",
            ],
        },
        source="test",
    )

    assert state.characters["char_alice"].relationships["char_bob"] == "employer: runs the workshop"
    assert state.characters["char_bob"].relationships["char_alice"] == "employee"
    assert state.characters["char_bob"].relationships["char_clara"] == "teacher(mentor)"
    assert state.characters["char_clara"].relationships["char_bob"] == "student"
    assert state.characters["char_alice"].relationships["char_clara"] == "secret informant"
    assert "char_alice: relationship to char_bob updated" in "\n".join(log)


def test_apply_chapter_character_mine_returns_presence_log(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    state.add_character(Character(id="char_alice", full_name="Alice", role="protagonist"))

    log = apply_chapter_character_mine(
        state,
        1,
        {"characters_present": ["Alice"]},
        source="test",
    )

    assert state.characters["char_alice"].last_appearance_chapter == 1
    assert any("char_alice: appeared in ch1" in line for line in log)


def test_apply_chapter_plot_mine_updates_graph_lifespan(tmp_path):
    from story_graph import StoryGraphNode

    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.story_graph_nodes["node_a"] = StoryGraphNode(
        id="node_a",
        kind="plot_thread",
        title="Central Mystery",
        start_chapter=1,
    )
    state.create_chapter(1)

    log = apply_chapter_plot_mine(
        state,
        1,
        {
            "plot_lifespan_updates": [
                "Central Mystery | 2 | 8 | Escalates this chapter",
            ],
        },
        source="test",
    )
    node = state.story_graph_nodes["node_a"]
    assert node.start_chapter == 2
    assert node.resolution_chapter == 8
    assert any("lifespan updated" in line for line in log)


def test_apply_chapter_plot_mine_skips_malformed_pipe_rows(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1)

    log = apply_chapter_plot_mine(
        state,
        1,
        {
            "subplot_threads": ["Missing delimiter"],
            "subplot_beats": ["Also missing delimiter"],
            "plot_lifespan_updates": ["No lifespan delimiter"],
        },
        source="test",
    )

    joined = "\n".join(log)
    assert "skipped malformed Subplot_Threads" in joined
    assert "skipped malformed Subplot_Beats" in joined
    assert "skipped malformed Plot_Lifespan_Updates" in joined


def test_locked_mine_apply_preserves_plot_and_character_updates(tmp_path):
    """Parallel miners reload under project_state_lock so saves do not clobber each other."""
    from state_manager import project_state_lock
    from state_parser import apply_chapter_character_mine, apply_chapter_plot_mine

    initialize_project(str(tmp_path), "Novel", "Drama")
    proj = str(tmp_path)
    lock = project_state_lock(proj)

    with lock:
        state = StoryState(proj)
        state.create_chapter(1)
        apply_chapter_plot_mine(
            state,
            1,
            {
                "plot_threads": ["Heist Arc | main | The vault job | Alice"],
                "subplot_threads": [],
                "subplot_beats": [],
                "resolved_subplots": [],
                "plot_events": [],
            },
            source="mine_plots",
        )
        state.save_state()

    with lock:
        state = StoryState(proj)
        apply_chapter_character_mine(
            state,
            1,
            {
                "characters_present": ["Alice"],
                "new_characters": ["Alice | supporting | Vault expert"],
                "character_updates": [],
                "emotional_shifts": [],
            },
            source="mine_characters",
        )
        state.save_state()

    final = StoryState(proj)
    assert any(t.name == "Heist Arc" for t in final.plot_threads.values())
    assert any(c.full_name == "Alice" for c in final.characters.values())
