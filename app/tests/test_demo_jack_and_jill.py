"""Tests for the Jack and Jill demo seed."""

import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from demo_jack_and_jill import (  # noqa: E402
    CHAPTER_NUMBER,
    populate_jack_and_jill_demo,
    write_jack_and_jill_artifacts,
)
from api.services import build_orchestrator  # noqa: E402
from state_manager import StoryState, initialize_project  # noqa: E402


@pytest.fixture
def demo_state(tmp_path):
    project_dir = tmp_path / "jack-and-jill"
    build_orchestrator(str(project_dir)).init_project("Jack and Jill", "Children's Nursery Rhyme")
    state = StoryState(str(project_dir))
    populate_jack_and_jill_demo(state)
    state.save_state()
    write_jack_and_jill_artifacts(project_dir)
    return project_dir, state


def test_demo_populates_cast_graph_and_chapter(demo_state):
    project_dir, state = demo_state
    assert len(state.characters) == 3
    assert len(state.story_graph_nodes) == 3
    assert len(state.story_graph_edges) == 4
    assert CHAPTER_NUMBER in state.chapters
    assert state.chapters[CHAPTER_NUMBER].status == "complete"
    assert state.get_chapter_brief(CHAPTER_NUMBER) is not None
    assert len(state.get_chapter_beats(CHAPTER_NUMBER)) == 5
    assert len(state.timeline) == 3
    assert state.story_bible.get("logline")

    final = project_dir / "outputs" / "manuscript" / "chapter_001_final.md"
    assert final.is_file()
    assert final.read_text(encoding="utf-8").strip()


def test_demo_idempotent_on_empty_init(tmp_path):
    state = initialize_project(str(tmp_path / "x"), "Jack and Jill", "Rhyme")
    populate_jack_and_jill_demo(state)
    assert state.characters["char_jack"].full_name == "Jack"
