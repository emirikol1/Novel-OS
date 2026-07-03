"""Tests for budgeted bible and graph context resolution."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from context_resolver import (  # noqa: E402
    BUDGET_OUTLINE,
    ContextBudget,
    format_bible_context_block,
    format_graph_nodes_block,
    resolve_bible_context,
    resolve_graph_nodes,
)
from state_manager import StoryState, initialize_project  # noqa: E402
from story_graph import StoryGraphEdge, StoryGraphNode  # noqa: E402


def _seed_bible(state: StoryState) -> None:
    state.update_story_bible("logline", "A thief races the clock in a flooded city.")
    state.update_story_bible("themes", ["betrayal", "identity", "grief", "memory"])
    state.update_story_bible("setting_summary", "Coastal Maine in late autumn.")
    state.update_story_bible("historical_context", "The town flooded fifty years ago.")
    state.update_story_bible("premise_beats", ["Hero arrives", "Vault discovered", "Ally vanishes"])
    state.update_story_bible("world_rules", ["Magic costs memory", "No resurrection"])
    state.update_story_bible("import_notes", ["Tone is noir", "Keep Jordan skeptical"])


def test_resolve_bible_context_ranks_text_match(tmp_path):
    initialize_project(str(tmp_path), "Rank", "Fiction")
    state = StoryState(str(tmp_path))
    _seed_bible(state)

    resolved = resolve_bible_context(
        state,
        budget=ContextBudget(max_items=3, max_chars=5000),
        hint_text="Jordan is skeptical about the flooded vault",
    )

    labels = [item.label for item in resolved.items]
    assert "Logline" in labels
    assert any("Premise" in lbl or "Setting" in lbl for lbl in labels)


def test_resolve_bible_context_budget_caps_items_and_chars(tmp_path):
    initialize_project(str(tmp_path), "Cap", "Fiction")
    state = StoryState(str(tmp_path))
    _seed_bible(state)

    resolved = resolve_bible_context(
        state,
        budget=ContextBudget(max_items=2, max_chars=120),
    )

    assert len(resolved.items) <= 2
    assert resolved.omitted_count >= 1
    block = format_bible_context_block(resolved)
    assert "Omitted" in block


def test_resolve_graph_nodes_caps_selected_and_related(tmp_path):
    initialize_project(str(tmp_path), "Graph", "Thriller")
    state = StoryState(str(tmp_path))

    for i in range(10):
        nid = f"node_{i}"
        state.story_graph_nodes[nid] = StoryGraphNode(
            id=nid,
            kind="subplot",
            title=f"Plot thread {i}",
            description=f"Event chain {i} with vault alarm",
            priority=i + 1,
            status="active",
        )

    for i in range(9):
        state.story_graph_edges[f"edge_{i}"] = StoryGraphEdge(
            id=f"edge_{i}",
            source_id=f"node_{i}",
            target_id=f"node_{i + 1}",
            kind="advances",
        )

    selected = [f"node_{i}" for i in range(10)]
    resolved = resolve_graph_nodes(
        state,
        selected_node_ids=selected,
        budget=ContextBudget(max_items=20, max_chars=8000, max_selected_nodes=3, max_related_nodes=2),
        hint_text="vault alarm",
    )

    assert len(resolved.items) <= 5
    assert resolved.omitted_count >= 5
    block = format_graph_nodes_block(resolved)
    assert "Omitted" in block
    assert "Plot thread" in block


def test_format_graph_nodes_marks_related_neighbors(tmp_path):
    initialize_project(str(tmp_path), "Rel", "Thriller")
    state = StoryState(str(tmp_path))
    state.story_graph_nodes["main"] = StoryGraphNode(
        id="main",
        kind="main",
        title="The Heist",
        description="Steal the vault key",
        priority=5,
    )
    state.story_graph_nodes["child"] = StoryGraphNode(
        id="child",
        kind="beat",
        title="Alarm trip",
        description="Vault alarm fails",
        priority=4,
    )
    state.story_graph_edges["e1"] = StoryGraphEdge(
        id="e1",
        source_id="main",
        target_id="child",
        kind="contains",
    )

    resolved = resolve_graph_nodes(
        state,
        selected_node_ids=["main"],
        budget=ContextBudget(max_selected_nodes=4, max_related_nodes=4, max_items=8, max_chars=4000),
    )
    block = format_graph_nodes_block(resolved)

    assert "The Heist" in block
    assert "Alarm trip" in block
    assert "related" in block


def test_bible_excludes_tone(tmp_path):
    initialize_project(str(tmp_path), "Tone", "Fiction")
    state = StoryState(str(tmp_path))
    state.update_story_bible("logline", "A quiet story.")
    state.style_profile.tone = "noir"

    block = format_bible_context_block(resolve_bible_context(state, budget=BUDGET_OUTLINE))
    assert "Tone" not in block
