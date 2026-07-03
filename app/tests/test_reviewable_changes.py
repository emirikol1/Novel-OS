"""Tests for generic reviewable changes using synthetic projects only."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from api.main import create_app
from reviewable_changes import ReviewableChange
from state_manager import Character, PlotThread, StoryState, initialize_project
from story_graph import ChapterBrief, StoryGraphEdge, StoryGraphNode


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed_review_project(tmp_path):
    project = tmp_path / "p"
    initialize_project(str(project), "Synthetic Novel", "Drama")
    state = StoryState(str(project))
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="Synthetic Thread",
            description="Synthetic plot description",
            thread_type="main",
            priority=5,
            related_characters=["char_a"],
        ),
    )
    state.add_character(
        Character(
            id="char_a",
            full_name="Alice Example",
            role="protagonist",
            relationships={"char_b": "ally"},
        ),
    )
    state.add_character(
        Character(id="char_b", full_name="Bob Example", role="supporting"),
    )
    state.add_story_graph_node(
        StoryGraphNode(
            id="graph_node_existing",
            kind="beat",
            title="Existing Synthetic Node",
            start_chapter=1,
        ),
    )
    state.set_chapter_brief(
        ChapterBrief(chapter_number=1, active_node_ids=["graph_node_existing"]),
    )
    state.save_state()
    return project


def _generate(c):
    resp = c.post("/api/projects/p/reviewable-changes/generate-graph-suggestions", json={})
    assert resp.status_code == 200
    return resp.json()["changes"]


def _change(changes, kind):
    return next(change for change in changes if change["kind"] == kind)


def test_story_state_roundtrip_persists_reviewable_changes(tmp_path):
    project = tmp_path / "p"
    initialize_project(str(project), "Synthetic Novel", "Drama")
    state = StoryState(str(project))
    assert state.reviewable_changes == {}

    state.reviewable_changes["rc_test"] = ReviewableChange(
        id="rc_test",
        kind="story_graph_node",
        title="Synthetic change",
        source="test",
    )
    state.save_state()

    reloaded = StoryState(str(project))
    assert "rc_test" in reloaded.reviewable_changes
    assert reloaded.reviewable_changes["rc_test"].status == "pending"


def test_generate_graph_suggestions_is_preview_first(tmp_path):
    project = _seed_review_project(tmp_path)
    c = _client(tmp_path)

    changes = _generate(c)
    kinds = {change["kind"] for change in changes}

    assert {"story_graph_node", "story_graph_edge", "story_graph_chapter_pin"} <= kinds
    assert all(change["status"] == "pending" for change in changes)
    assert all("Synthetic Thread" not in change["reason"] for change in changes)

    state = StoryState(str(project))
    assert "graph_node_plot_main" not in state.story_graph_nodes
    assert not any(edge.kind == "character_relationship" for edge in state.story_graph_edges.values())
    assert state.story_graph_nodes["graph_node_existing"].chapter_pins == []

    filtered = c.get("/api/projects/p/reviewable-changes?type=story_graph_edge")
    assert filtered.status_code == 200
    assert [change["kind"] for change in filtered.json()] == ["story_graph_edge"]


def test_apply_and_mark_reviewed_reviewable_change(tmp_path):
    project = _seed_review_project(tmp_path)
    c = _client(tmp_path)
    node_change = _change(_generate(c), "story_graph_node")

    applied = c.post(f"/api/projects/p/reviewable-changes/{node_change['id']}/apply")
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied_needs_review"
    assert applied.json()["revert_available"] is True

    state = StoryState(str(project))
    assert "graph_node_plot_main" in state.story_graph_nodes

    reviewed = c.post(f"/api/projects/p/reviewable-changes/{node_change['id']}/mark-reviewed")
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["reviewed_at"]


def test_revert_reviewable_edge_change(tmp_path):
    project = _seed_review_project(tmp_path)
    c = _client(tmp_path)
    edge_change = _change(_generate(c), "story_graph_edge")

    applied = c.post(f"/api/projects/p/reviewable-changes/{edge_change['id']}/apply")
    assert applied.status_code == 200
    edge_id = applied.json()["target"]["id"]
    assert edge_id in StoryState(str(project)).story_graph_edges

    reverted = c.post(f"/api/projects/p/reviewable-changes/{edge_change['id']}/revert")
    assert reverted.status_code == 200
    assert reverted.json()["status"] == "reverted"
    assert edge_id not in StoryState(str(project)).story_graph_edges


def test_revert_blocks_when_node_has_new_edge_reference(tmp_path):
    project = _seed_review_project(tmp_path)
    c = _client(tmp_path)
    node_change = _change(_generate(c), "story_graph_node")

    applied = c.post(f"/api/projects/p/reviewable-changes/{node_change['id']}/apply")
    assert applied.status_code == 200
    node_id = applied.json()["target"]["id"]

    state = StoryState(str(project))
    state.add_story_graph_edge(
        StoryGraphEdge(
            id="graph_edge_manual",
            source_id=node_id,
            target_id="graph_node_existing",
            kind="relates",
        ),
    )
    state.save_state()

    blocked = c.post(f"/api/projects/p/reviewable-changes/{node_change['id']}/revert")
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["conflicts"]
    assert node_id in StoryState(str(project)).story_graph_nodes
