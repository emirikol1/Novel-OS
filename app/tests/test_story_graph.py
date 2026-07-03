"""Tests for story graph / chapter brief Phase 1 (synthetic projects only)."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from api.main import create_app
from state_manager import PlotThread, StoryState, initialize_project
from story_graph import migrate_plot_threads_to_graph


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed_plot_project(tmp_path, *, with_characters: bool = False):
    """Synthetic project with one main plot and two subplot strings."""
    initialize_project(str(tmp_path / "p"), "Synthetic Novel", "Drama")
    state = StoryState(str(tmp_path / "p"))
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="The Heist",
            description="Steal the vault key",
            thread_type="main",
            priority=5,
            subplots=["Vault alarm subplot", "Inside man betrayal"],
            related_characters=["char_a"] if with_characters else [],
        ),
    )
    if with_characters:
        from state_manager import Character

        state.add_character(
            Character(
                id="char_a",
                full_name="Alice",
                role="protagonist",
                relationships={"char_b": "rival"},
            ),
        )
        state.add_character(
            Character(id="char_b", full_name="Bob", role="antagonist", relationships={}),
        )
    state.save_state()
    return tmp_path


def test_migration_creates_nodes_and_edges(tmp_path):
    _seed_plot_project(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    assert len(state.plot_threads) == 1

    result = migrate_plot_threads_to_graph(state)
    assert result["skipped"] is False
    assert result["nodes_created"] == 3  # main + 2 subplots
    assert result["edges_created"] == 2  # contains edges

    kinds = {n.kind for n in state.story_graph_nodes.values()}
    assert "main" in kinds
    assert "subplot" in kinds
    contains = [e for e in state.story_graph_edges.values() if e.kind == "contains"]
    assert len(contains) == 2
    for node in state.story_graph_nodes.values():
        if node.kind == "main":
            assert node.created_from == "migration"
            assert node.legacy_plot_thread_id == "plot_main"

    # Legacy plot threads untouched
    assert state.plot_threads["plot_main"].name == "The Heist"
    assert len(state.plot_threads["plot_main"].subplots) == 2


def test_migration_reuses_same_subplot_under_multiple_plots(tmp_path):
    _seed_plot_project(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    state.add_plot_thread(
        PlotThread(
            id="plot_second",
            name="The Betrayal",
            description="Expose the insider",
            thread_type="subplot",
            priority=4,
            subplots=["inside man betrayal", "Escape route"],
            related_characters=["char_b"],
        ),
    )
    state.save_state()

    result = migrate_plot_threads_to_graph(state)
    assert result["skipped"] is False

    shared_nodes = [
        n for n in state.story_graph_nodes.values()
        if n.kind == "subplot" and n.title.lower() == "inside man betrayal"
    ]
    assert len(shared_nodes) == 1
    shared = shared_nodes[0]
    parent_edges = [
        e for e in state.story_graph_edges.values()
        if e.kind == "contains" and e.target_id == shared.id
    ]
    assert len(parent_edges) == 2
    assert {e.source_id for e in parent_edges} == {
        "graph_node_plot_main",
        "graph_node_plot_second",
    }


def test_migration_skips_when_graph_nonempty(tmp_path):
    _seed_plot_project(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    migrate_plot_threads_to_graph(state)
    again = migrate_plot_threads_to_graph(state)
    assert again["skipped"] is True
    assert again["nodes_created"] == 0


def test_migration_character_relationship_edge(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    state = StoryState(str(tmp_path / "p"))
    migrate_plot_threads_to_graph(state)
    rel_edges = [
        e for e in state.story_graph_edges.values()
        if e.kind == "character_relationship"
    ]
    assert len(rel_edges) == 1
    assert rel_edges[0].source_id == "char_a"
    assert rel_edges[0].target_id == "char_b"
    assert rel_edges[0].label == "rival"


def test_story_state_roundtrip_persists_graph(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    state = StoryState(str(tmp_path / "p"))
    migrate_plot_threads_to_graph(state)
    state.save_state()

    reloaded = StoryState(str(tmp_path / "p"))
    assert len(reloaded.story_graph_nodes) == 3
    assert len(reloaded.story_graph_edges) >= 3
    assert reloaded.plot_threads["plot_main"].name == "The Heist"


def test_story_graph_node_crud_api(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)

    created = c.post(
        "/api/projects/p/story-graph/nodes",
        json={
            "title": "Reveal the traitor",
            "kind": "beat",
            "priority": 4,
            "start_chapter": 2,
            "resolution_chapter": 8,
            "layout": {"x": 120.5, "y": 40.0},
            "act": 2,
        },
    )
    assert created.status_code == 201
    node_id = created.json()["id"]
    assert created.json()["created_from"] == "manual"
    assert created.json()["start_chapter"] == 2
    assert created.json()["resolution_chapter"] == 8
    assert created.json()["layout"] == {"x": 120.5, "y": 40.0}
    assert created.json()["act"] == 2

    listed = c.get("/api/projects/p/story-graph/nodes").json()
    assert any(n["id"] == node_id for n in listed)

    patched = c.patch(
        f"/api/projects/p/story-graph/nodes/{node_id}",
        json={"title": "Reveal traitor at dinner", "status": "foreshadowed"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Reveal traitor at dinner"

    assert c.delete(f"/api/projects/p/story-graph/nodes/{node_id}").status_code == 204
    assert not any(n["id"] == node_id for n in c.get("/api/projects/p/story-graph/nodes").json())


def test_story_graph_edge_crud_api(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    migrate = c.post("/api/projects/p/story-graph/migrate", json={"force": False})
    assert migrate.status_code == 200
    nodes = c.get("/api/projects/p/story-graph/nodes").json()
    main = next(n for n in nodes if n["kind"] == "main")
    sub = next(n for n in nodes if n["kind"] == "subplot")

    created = c.post(
        "/api/projects/p/story-graph/edges",
        json={"source_id": main["id"], "target_id": sub["id"], "kind": "advances", "label": "setup"},
    )
    assert created.status_code == 201
    edge_id = created.json()["id"]

    edges = c.get("/api/projects/p/story-graph/edges").json()
    assert any(e["id"] == edge_id for e in edges)

    assert c.delete(f"/api/projects/p/story-graph/edges/{edge_id}").status_code == 204


def test_story_graph_allows_nested_subplot_contains_edge(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    parent = c.post(
        "/api/projects/p/story-graph/nodes",
        json={"title": "Court intrigue", "kind": "subplot"},
    ).json()
    child = c.post(
        "/api/projects/p/story-graph/nodes",
        json={"title": "Poison rumor", "kind": "subplot"},
    ).json()

    created = c.post(
        "/api/projects/p/story-graph/edges",
        json={
            "source_id": parent["id"],
            "target_id": child["id"],
            "kind": "contains",
            "label": "nested subplot",
        },
    )
    assert created.status_code == 201
    assert created.json()["kind"] == "contains"
    assert created.json()["source_id"] == parent["id"]
    assert created.json()["target_id"] == child["id"]


def test_migrate_api_preserves_plot_threads(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    before = c.get("/api/projects/p/plot-threads").json()
    assert len(before) == 1
    assert before[0]["subplots"] == ["Vault alarm subplot", "Inside man betrayal"]

    result = c.post("/api/projects/p/story-graph/migrate", json={"force": False}).json()
    assert result["skipped"] is False
    assert result["nodes_created"] == 3

    after = c.get("/api/projects/p/plot-threads").json()
    assert after == before

    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    saved = json.loads(sf.read_text())
    assert "plot_main" in saved["plot_threads"]
    assert "story_graph_nodes" in saved
    assert len(saved["story_graph_nodes"]) == 3


def test_chapter_brief_save_load(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    c = _client(tmp_path)
    c.post("/api/projects/p/story-graph/migrate", json={"force": False})
    main_node = next(
        n for n in c.get("/api/projects/p/story-graph/nodes").json() if n["kind"] == "main"
    )

    saved = c.put(
        "/api/projects/p/chapters/3/brief",
        json={
            "pov_character_id": "char_a",
            "pov_mode": "first_person",
            "active_character_ids": ["char_a", "char_b"],
            "active_node_ids": [main_node["id"]],
            "required_beats": ["Alarm fails", "Bob confronts Alice"],
            "continuity_notes": "Alice still has the keycard.",
            "ending_hook": "The vault door opens.",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["chapter_number"] == 3
    assert body["pov_character_id"] == "char_a"
    assert body["pov_mode"] == "first_person"
    assert body["required_beats"] == ["Alarm fails", "Bob confronts Alice"]
    assert body["ending_hook"] == "The vault door opens."

    loaded = c.get("/api/projects/p/chapters/3/brief").json()
    assert loaded == body

    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    disk = json.loads(sf.read_text())
    assert "3" in disk["chapter_briefs"]
    assert disk["chapter_briefs"]["3"]["continuity_notes"] == "Alice still has the keycard."

    assert c.delete("/api/projects/p/chapters/3/brief").status_code == 204
    assert c.get("/api/projects/p/chapters/3/brief").status_code == 404


def test_chapter_brief_validation(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    assert c.put(
        "/api/projects/p/chapters/1/brief",
        json={"pov_character_id": "missing_char"},
    ).status_code == 404


def test_migrate_force_remigration(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    c.post("/api/projects/p/story-graph/migrate", json={"force": False})

    manual = c.post(
        "/api/projects/p/story-graph/nodes",
        json={"title": "Author beat", "kind": "beat"},
    ).json()

    c.post("/api/projects/p/story-graph/migrate", json={"force": True})
    nodes = c.get("/api/projects/p/story-graph/nodes").json()
    assert any(n["id"] == manual["id"] for n in nodes)
    assert sum(1 for n in nodes if n["created_from"] == "migration") == 3


def test_graph_duplicates_api_scan_and_merge(tmp_path):
    _seed_plot_project(tmp_path)
    c = _client(tmp_path)
    c.post("/api/projects/p/story-graph/nodes", json={"title": "The Heist", "kind": "main"})
    c.post("/api/projects/p/story-graph/nodes", json={"title": "the heist", "kind": "main"})

    dup = c.get("/api/projects/p/story-graph/duplicates")
    assert dup.status_code == 200
    groups = dup.json()["groups"]
    assert len(groups) >= 1

    group = groups[0]
    keep = group["suggested_keep_id"]
    merge_ids = [m["id"] for m in group["members"] if m["id"] != keep]
    merged = c.post("/api/projects/p/story-graph/duplicates/merge", json={
        "keep_id": keep,
        "merge_ids": merge_ids,
    })
    assert merged.status_code == 200
    assert merged.json()["merged"] == len(merge_ids)

    after = c.get("/api/projects/p/story-graph/duplicates").json()
    assert len(after["groups"]) == 0

    # Legacy plot duplicate search still available
    legacy = c.get("/api/projects/p/duplicates")
    assert legacy.status_code == 200
    assert "plot_threads" in legacy.json()


def _seed_context_preview_project(tmp_path):
    """Synthetic project with bible, graph, chapter, and brief for context preview."""
    from story_graph import ChapterBrief, StoryGraphNode

    _seed_plot_project(tmp_path, with_characters=True)
    state = StoryState(str(tmp_path / "p"))
    migrate_plot_threads_to_graph(state)
    state.update_story_bible("logline", "A thief races the clock in a flooded vault city.")
    state.update_story_bible("themes", ["betrayal", "identity", "grief", "memory", "trust"])
    state.update_story_bible("setting_summary", "Coastal Maine in late autumn.")
    state.update_story_bible("historical_context", "The town flooded fifty years ago.")
    state.update_story_bible("premise_beats", ["Hero arrives", "Vault discovered", "Ally vanishes"])
    state.update_story_bible("world_rules", ["Magic costs memory", "No resurrection"])
    state.update_story_bible("import_notes", ["Tone is noir", "Keep Alice skeptical"])
    for i in range(8):
        nid = f"extra_node_{i}"
        state.story_graph_nodes[nid] = StoryGraphNode(
            id=nid,
            kind="subplot",
            title=f"Side plot {i}",
            description=f"Vault alarm thread {i}",
            priority=i + 1,
            status="active",
            linked_character_ids=["char_a"],
        )
    main_node = next(nid for nid, n in state.story_graph_nodes.items() if n.kind == "main")
    state.create_chapter(3)
    state.set_chapter_brief(
        ChapterBrief(
            chapter_number=3,
            pov_character_id="char_a",
            pov_mode="third_limited",
            active_character_ids=["char_a", "char_b"],
            active_node_ids=[main_node, *[f"extra_node_{i}" for i in range(8)]],
            required_beats=["Vault alarm fails"],
            continuity_notes="Alice still has the keycard.",
            ending_hook="The vault door opens.",
        ),
    )
    state.save_state()
    proj = tmp_path / "p"
    outline = proj / "outputs" / "chapter_003_outline.md"
    outline.parent.mkdir(parents=True, exist_ok=True)
    outline.write_text("# Outline\nAlice enters the flooded vault antechamber.", encoding="utf-8")
    return tmp_path, main_node


def test_chapter_context_preview_get_shape_and_omissions(tmp_path):
    tmp_path, main_node = _seed_context_preview_project(tmp_path)
    c = _client(tmp_path)

    resp = c.get("/api/projects/p/chapters/3/context-preview?mode=outline")
    assert resp.status_code == 200
    body = resp.json()

    assert body["chapter_number"] == 3
    assert body["mode"] == "outline"
    assert isinstance(body["bible"]["items"], list)
    assert isinstance(body["graph"]["items"], list)
    assert body["bible"]["omitted_count"] >= 1
    assert body["graph"]["omitted_count"] >= 1
    assert body["bible"]["omitted_reason"] == "budget cap"
    assert body["graph"]["omitted_reason"] == "budget cap"

    bible_labels = [item["label"] for item in body["bible"]["items"]]
    assert any("Logline" in label or "Setting" in label for label in bible_labels)
    for item in body["bible"]["items"]:
        assert item["label"]
        assert item["body"]
        assert item["reason"]
        assert "score" in item

    graph_labels = [item["label"] for item in body["graph"]["items"]]
    assert any("Heist" in label for label in graph_labels)
    assert {c["id"] for c in body["active_characters"]} == {"char_a", "char_b"}
    assert "Alice" in {c["name"] for c in body["active_characters"]}
    assert isinstance(body["mentioned_characters"], list)
    assert isinstance(body["beats"], list)
    assert main_node in {item["key"].split(":", 1)[-1] for item in body["graph"]["items"]}


def test_chapter_context_preview_post_uses_brief_body(tmp_path):
    tmp_path, _ = _seed_context_preview_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/p/chapters/3/context-preview",
        json={
            "mode": "outline",
            "active_character_ids": ["char_a"],
            "active_node_ids": [],
            "required_beats": ["Vault alarm fails"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "outline"
    assert body["graph"]["items"] == []
    assert body["active_characters"] == [{"id": "char_a", "name": "Alice"}]
    assert body["mentioned_characters"] == [{"id": "char_a", "name": "Alice"}]
    assert len(body["beats"]) == 1
    assert body["beats"][0]["title"] == "Vault alarm fails"


def test_chapter_context_preview_invalid_mode(tmp_path):
    _seed_context_preview_project(tmp_path)
    c = _client(tmp_path)
    resp = c.get("/api/projects/p/chapters/3/context-preview?mode=unknown")
    assert resp.status_code == 400


def test_eligible_graph_nodes_api(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    c = _client(tmp_path)
    c.post("/api/projects/p/story-graph/migrate", json={"force": False})
    early = c.post(
        "/api/projects/p/story-graph/nodes",
        json={"title": "Prologue only", "kind": "beat", "start_chapter": 1, "resolution_chapter": 1},
    ).json()
    late = c.post(
        "/api/projects/p/story-graph/nodes",
        json={"title": "Epilogue", "kind": "beat", "start_chapter": 20, "resolution_chapter": None},
    ).json()

    resp = c.get("/api/projects/p/chapters/3/story-graph/eligible-nodes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapter_number"] == 3
    eligible_ids = {n["id"] for n in body["eligible"]}
    assert early["id"] not in eligible_ids
    assert late["id"] not in eligible_ids
    assert any(n["kind"] == "main" for n in body["eligible"])


def test_pin_story_graph_node_syncs_brief(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    c = _client(tmp_path)
    c.post("/api/projects/p/story-graph/migrate", json={"force": False})
    node = next(n for n in c.get("/api/projects/p/story-graph/nodes").json() if n["kind"] == "main")

    c.put(
        "/api/projects/p/chapters/3/brief",
        json={"mentioned_character_ids": ["char_a"], "active_character_ids": ["char_a"]},
    )

    pinned = c.post(
        f"/api/projects/p/story-graph/nodes/{node['id']}/pin",
        json={"chapter_number": 3, "pinned": True},
    )
    assert pinned.status_code == 200
    assert 3 in pinned.json()["chapter_pins"]

    brief = c.get("/api/projects/p/chapters/3/brief").json()
    assert node["id"] in brief["active_node_ids"]

    unpinned = c.post(
        f"/api/projects/p/story-graph/nodes/{node['id']}/pin",
        json={"chapter_number": 3, "pinned": False},
    )
    assert unpinned.status_code == 200
    assert 3 not in unpinned.json()["chapter_pins"]
    brief_after = c.get("/api/projects/p/chapters/3/brief").json()
    assert node["id"] not in brief_after["active_node_ids"]


def test_create_node_assign_to_brief(tmp_path):
    _seed_plot_project(tmp_path, with_characters=True)
    c = _client(tmp_path)
    created = c.post(
        "/api/projects/p/story-graph/nodes",
        json={
            "title": "New subplot from brief",
            "kind": "subplot",
            "chapter_number": 2,
            "assign_to_brief": True,
        },
    )
    assert created.status_code == 201
    node_id = created.json()["id"]
    assert created.json()["start_chapter"] == 2

    brief = c.get("/api/projects/p/chapters/2/brief").json()
    assert node_id in brief["active_node_ids"]
