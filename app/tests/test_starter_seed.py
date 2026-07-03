"""Tests for starter onboarding seed (Structure V2)."""

import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import StoryState, initialize_project  # noqa: E402
from state_migration import CURRENT_SCHEMA_VERSION  # noqa: E402
from starter_seed import seed_starter_project  # noqa: E402
from story_graph import node_eligible_at_chapter  # noqa: E402


@pytest.fixture
def fresh_state(tmp_path):
    return initialize_project(str(tmp_path / "proj"), "The Drowned City", "Fantasy")


def test_seed_starter_project_populates_minimum(fresh_state):
    seed_starter_project(fresh_state)

    assert len(fresh_state.characters) == 1
    assert len(fresh_state.chapters) == 1
    assert len(fresh_state.story_graph_nodes) == 1
    assert fresh_state.chapters[1].title == "Opening"
    assert fresh_state.get_chapter_brief(1) is not None
    assert fresh_state.schema_version == CURRENT_SCHEMA_VERSION


def test_seed_idempotent(fresh_state):
    seed_starter_project(fresh_state)
    seed_starter_project(fresh_state)

    assert len(fresh_state.characters) == 1
    assert len(fresh_state.chapters) == 1
    assert len(fresh_state.story_graph_nodes) == 1


def test_brief_invariants(fresh_state):
    seed_starter_project(fresh_state)
    brief = fresh_state.get_chapter_brief(1)
    assert brief is not None

    active = set(brief.active_character_ids)
    mentioned = set(brief.mentioned_character_ids)
    assert active <= mentioned
    assert brief.pov_character_id in active
    assert brief.active_node_ids == ["graph_node_001"]


def test_graph_lifespan_covers_chapter_1(fresh_state):
    seed_starter_project(fresh_state)
    node = fresh_state.story_graph_nodes["graph_node_001"]
    assert node.start_chapter == 1
    assert node.resolution_chapter is None
    assert node_eligible_at_chapter(node, 1)


def test_chapter_pins_sync(fresh_state):
    seed_starter_project(fresh_state)
    node = fresh_state.story_graph_nodes["graph_node_001"]
    assert 1 in node.chapter_pins


def test_schema_version_2(fresh_state):
    seed_starter_project(fresh_state)
    assert fresh_state.schema_version == CURRENT_SCHEMA_VERSION


def test_outline_scaffold_written(fresh_state):
    seed_starter_project(fresh_state)
    outline = fresh_state.project_path / "outputs" / "chapter_001_outline.md"
    assert outline.is_file()
    text = outline.read_text(encoding="utf-8")
    assert "Chapter 1" in text
    assert "Central conflict" in text


def test_placeholders_from_title_genre_only(fresh_state):
    seed_starter_project(fresh_state)
    char = fresh_state.characters["char_001"]
    assert "Drowned City" in char.full_name
    assert fresh_state.story_bible.get("logline", "").startswith("A Fantasy story")
    node = fresh_state.story_graph_nodes["graph_node_001"]
    assert "Fantasy" in node.description
    assert "Drowned City" in node.description
