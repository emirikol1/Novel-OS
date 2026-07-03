"""Tests for story graph node deduplication (synthetic projects only)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from graph_dedup import (
    find_graph_duplicate_groups,
    graph_node_match_score,
    merge_graph_nodes,
    scan_graph_duplicates,
)
from state_manager import StoryState, initialize_project
from story_graph import ChapterBrief, StoryGraphEdge, StoryGraphNode


def _add_node(state: StoryState, nid: str, title: str, **kwargs) -> None:
    state.add_story_graph_node(
        StoryGraphNode(
            id=nid,
            kind=kwargs.get("kind", "beat"),
            title=title,
            description=kwargs.get("description", ""),
            legacy_plot_thread_id=kwargs.get("legacy_plot_thread_id", ""),
        ),
    )


def test_graph_node_match_score_exact_title():
    assert graph_node_match_score("Vault Alarm", "Vault Alarm") >= 0.99
    assert graph_node_match_score("The Heist", "Heist") >= 0.78


def test_find_graph_duplicate_groups(tmp_path):
    initialize_project(str(tmp_path), "Synthetic", "Drama")
    state = StoryState(str(tmp_path))
    _add_node(state, "graph_node_001", "Vault alarm", kind="beat")
    _add_node(state, "graph_node_002", "Vault Alarm", kind="beat")
    _add_node(state, "graph_node_003", "Unrelated theme", kind="theme")

    groups = find_graph_duplicate_groups(state)
    assert len(groups) == 1
    assert len(groups[0].members) == 2
    assert groups[0].kind == "story_graph_node"


def test_merge_graph_nodes_rewires_edges_and_briefs(tmp_path):
    initialize_project(str(tmp_path), "Synthetic", "Drama")
    state = StoryState(str(tmp_path))
    _add_node(state, "graph_node_001", "Main arc", kind="main")
    _add_node(state, "graph_node_002", "Main Arc", kind="main")
    _add_node(state, "graph_node_003", "Side beat", kind="beat")
    state.add_story_graph_edge(
        StoryGraphEdge(
            id="edge_001",
            source_id="graph_node_002",
            target_id="graph_node_003",
            kind="relates",
        ),
    )
    state.set_chapter_brief(
        ChapterBrief(chapter_number=1, active_node_ids=["graph_node_002"]),
    )

    log = merge_graph_nodes(state, "graph_node_001", ["graph_node_002"])
    assert log
    assert "graph_node_002" not in state.story_graph_nodes
    assert len(state.story_graph_nodes) == 2

    edge = state.story_graph_edges["edge_001"]
    assert edge.source_id == "graph_node_001"
    assert edge.target_id == "graph_node_003"

    brief = state.get_chapter_brief(1)
    assert brief is not None
    assert brief.active_node_ids == ["graph_node_001"]


def test_scan_graph_duplicates_shape(tmp_path):
    initialize_project(str(tmp_path), "Synthetic", "Drama")
    state = StoryState(str(tmp_path))
    _add_node(state, "a", "Alpha", kind="beat")
    _add_node(state, "b", "Alpha", kind="beat")
    report = scan_graph_duplicates(state)
    assert "groups" in report
    assert len(report["groups"]) >= 1


def test_legacy_plot_thread_id_links_duplicates(tmp_path):
    initialize_project(str(tmp_path), "Synthetic", "Drama")
    state = StoryState(str(tmp_path))
    _add_node(state, "n1", "Different titles", legacy_plot_thread_id="plot_x")
    _add_node(state, "n2", "Other label", legacy_plot_thread_id="plot_x")
    groups = find_graph_duplicate_groups(state)
    assert len(groups) == 1
