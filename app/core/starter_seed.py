"""
Starter onboarding seed for new Novel OS projects (Structure V2).

Populates a freshly initialized project with minimal cast, chapter, graph, and brief
defaults derived from project title/genre only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_context import normalize_brief_for_storage
from state_migration import CURRENT_SCHEMA_VERSION
from story_graph import (
    ChapterBeat,
    ChapterBrief,
    StoryGraphLayout,
    StoryGraphNode,
    apply_brief_pov_to_chapter,
    new_chapter_beat_id,
    normalize_brief_characters,
    sync_chapter_pins_for_brief,
)

if TYPE_CHECKING:
    from state_manager import StoryState


_ARTICLES = frozenset({"a", "an", "the"})


def _title_subject(title: str) -> str:
    """Short subject phrase from a project title (no fixed character names)."""
    words = [w for w in re.split(r"\s+", (title or "").strip()) if w]
    meaningful = [w for w in words if w.lower() not in _ARTICLES]
    if not meaningful:
        meaningful = words
    if not meaningful:
        return "the protagonist"
    if len(meaningful) >= 2:
        return f"{meaningful[0]} {meaningful[1]}"
    return meaningful[0]


def _protagonist_name(title: str) -> str:
    subject = _title_subject(title)
    return f"{subject} Protagonist"


def _logline(title: str, genre: str) -> str:
    genre_text = (genre or "fiction").strip()
    title_text = (title or "this story").strip()
    return f"A {genre_text} story about {title_text}."


def _outline_scaffold(title: str, genre: str, graph_node_title: str) -> str:
    return f"""# Chapter 1 — Opening

## Intent
Introduce the protagonist and the central conflict for {title.strip() or "this project"}.

## Beats
- Establish POV and ordinary world ({genre.strip() or "fiction"})
- Hint at the central conflict ({graph_node_title})

## Ending hook
(TBD)
"""


def _write_outline_scaffold(state: "StoryState", content: str) -> None:
    outline_path = state.project_path / "outputs" / "chapter_001_outline.md"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    if not outline_path.exists():
        outline_path.write_text(content, encoding="utf-8")


def seed_starter_project(state: "StoryState") -> None:
    """Populate a freshly initialized project with minimal usable defaults."""
    if state.characters or state.chapters:
        return

    title = (state.metadata.get("title") or "").strip()
    genre = (state.metadata.get("genre") or "").strip()
    protagonist_id = "char_001"
    node_id = "graph_node_001"
    graph_node_title = "Central conflict"
    protagonist_name = _protagonist_name(title)

    from state_manager import Character, ChapterState  # noqa: WPS433

    state.schema_version = CURRENT_SCHEMA_VERSION
    state.update_story_bible("logline", _logline(title, genre))

    protagonist = Character(
        id=protagonist_id,
        full_name=protagonist_name,
        role="protagonist",
        internal_desire=f"Understand what { _title_subject(title) } truly means",
        external_goal=f"Resolve the central tension in {title or 'the story'}",
        arc_stage="beginning",
        arc_progress=0,
    )
    state.add_character(protagonist)

    chapter = ChapterState(number=1, title="Opening", status="planned")
    state.chapters[1] = chapter

    node = StoryGraphNode(
        id=node_id,
        kind="main",
        title=graph_node_title,
        description=(
            f"The primary {genre or 'story'} conflict driving {title or 'this project'}."
        ),
        status="active",
        priority=5,
        linked_character_ids=[protagonist_id],
        created_from="starter_seed",
        sort_order=0,
        start_chapter=1,
        resolution_chapter=None,
        layout=StoryGraphLayout(x=0.0, y=0.0),
        act=1,
        chapter_pins=[1],
    )
    state.add_story_graph_node(node)

    brief = ChapterBrief(
        chapter_number=1,
        pov_character_id=protagonist_id,
        mentioned_character_ids=[protagonist_id],
        active_character_ids=[protagonist_id],
        active_node_ids=[node_id],
    )
    normalize_brief_characters(brief)
    normalize_brief_for_storage(brief, state)
    state.set_chapter_brief(brief)
    sync_chapter_pins_for_brief(state, brief)
    apply_brief_pov_to_chapter(state, chapter, brief)

    beat_id = new_chapter_beat_id(state, 1)
    opening_beat = ChapterBeat(
        id=beat_id,
        title="Opening beat",
        summary="Establish protagonist and central tension",
        sort_order=0,
        status="planned",
        linked_node_ids=[node_id],
    )
    state.set_chapter_beats(1, [opening_beat])

    _write_outline_scaffold(state, _outline_scaffold(title, genre, graph_node_title))
