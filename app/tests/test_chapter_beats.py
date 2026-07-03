"""Structure V2 P1: chapter_beats CRUD and helpers (synthetic projects only)."""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from api.main import create_app
from state_manager import Character, StoryState, initialize_project
from story_graph import (
    ChapterBeat,
    ChapterBrief,
    StoryGraphNode,
    new_chapter_beat_id,
    node_eligible_at_chapter,
    normalize_start_chapter,
)


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed(tmp_path):
    initialize_project(str(tmp_path / "p"), "Beat Novel", "Drama")
    state = StoryState(str(tmp_path / "p"))
    state.add_character(Character(id="char_a", full_name="Alice", role="protagonist"))
    state.story_graph_nodes["graph_node_001"] = StoryGraphNode(
        id="graph_node_001",
        kind="main",
        title="Central conflict",
        start_chapter=1,
        resolution_chapter=10,
    )
    state.create_chapter(3)
    state.save_state()
    return tmp_path


def test_normalize_start_chapter():
    assert normalize_start_chapter(0) == 1
    assert normalize_start_chapter(-1) == 1
    assert normalize_start_chapter(5) == 5


def test_node_eligible_at_chapter():
    node = StoryGraphNode(id="n1", kind="beat", title="T", start_chapter=0, resolution_chapter=5)
    assert node_eligible_at_chapter(node, 1)
    assert node_eligible_at_chapter(node, 5)
    assert not node_eligible_at_chapter(node, 6)
    open_ended = StoryGraphNode(id="n2", kind="beat", title="T", start_chapter=3, resolution_chapter=None)
    assert not node_eligible_at_chapter(open_ended, 2)
    assert node_eligible_at_chapter(open_ended, 99)


def test_chapter_beat_state_crud(tmp_path):
    _seed(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    beat_id = new_chapter_beat_id(state, 3)
    beat = ChapterBeat(id=beat_id, title="Alarm fails", status="planned", sort_order=0)
    state.add_chapter_beat(3, beat)
    state.save_state()

    reloaded = StoryState(str(tmp_path / "p"))
    beats = reloaded.get_chapter_beats(3)
    assert len(beats) == 1
    assert beats[0].title == "Alarm fails"
    assert beats[0].status == "planned"

    reloaded.update_chapter_beat(3, beat_id, {"status": "landed", "summary": "Done"})
    reloaded.save_state()

    again = StoryState(str(tmp_path / "p"))
    updated = again.get_chapter_beats(3)[0]
    assert updated.status == "landed"
    assert updated.summary == "Done"

    assert again.delete_chapter_beat(3, beat_id)
    again.save_state()
    assert StoryState(str(tmp_path / "p")).get_chapter_beats(3) == []


def test_chapter_beat_reorder(tmp_path):
    _seed(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    b1 = ChapterBeat(id="beat_3_001", title="First", sort_order=0)
    b2 = ChapterBeat(id="beat_3_002", title="Second", sort_order=1)
    state.set_chapter_beats(3, [b1, b2])
    state.reorder_chapter_beats(3, ["beat_3_002", "beat_3_001"])
    state.save_state()

    beats = StoryState(str(tmp_path / "p")).get_chapter_beats(3)
    assert [b.id for b in beats] == ["beat_3_002", "beat_3_001"]
    assert beats[0].sort_order == 0


def test_chapter_beat_api_crud(tmp_path):
    _seed(tmp_path)
    c = _client(tmp_path)

    created = c.post(
        "/api/projects/p/chapters/3/beats",
        json={"title": "Vault opens", "status": "planned", "linked_node_ids": ["graph_node_001"]},
    )
    assert created.status_code == 201
    beat_id = created.json()["id"]
    assert created.json()["title"] == "Vault opens"

    listed = c.get("/api/projects/p/chapters/3/beats").json()
    assert len(listed) == 1

    patched = c.patch(
        f"/api/projects/p/chapters/3/beats/{beat_id}",
        json={"status": "landed", "summary": "Door swings open"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "landed"

    bulk = c.put(
        "/api/projects/p/chapters/3/beats",
        json={
            "beats": [
                {
                    "id": beat_id,
                    "title": "Vault opens",
                    "summary": "Bulk updated",
                    "sort_order": 0,
                    "status": "landed",
                    "linked_node_ids": ["graph_node_001"],
                },
                {
                    "title": "Escape",
                    "summary": "",
                    "sort_order": 1,
                    "status": "planned",
                    "linked_node_ids": [],
                },
            ],
        },
    )
    assert bulk.status_code == 200
    assert len(bulk.json()) == 2

    second_id = next(b["id"] for b in bulk.json() if b["title"] == "Escape")
    reordered = c.put(
        "/api/projects/p/chapters/3/beats/reorder",
        json={"ordered_ids": [second_id, beat_id]},
    )
    assert reordered.status_code == 200
    assert reordered.json()[0]["id"] == second_id

    assert c.delete(f"/api/projects/p/chapters/3/beats/{beat_id}").status_code == 204
    assert len(c.get("/api/projects/p/chapters/3/beats").json()) == 1


def test_list_chapter_beats_lazy_migrates_legacy_brief_beats(tmp_path):
    _seed(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    state.set_chapter_brief(
        ChapterBrief(
            chapter_number=3,
            required_beats=["Reach the vault", "Disable alarm"],
            landed_beats=["Alarm already triggered"],
        )
    )
    state.save_state()
    c = _client(tmp_path)

    listed = c.get("/api/projects/p/chapters/3/beats")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 3
    assert body[0]["status"] == "planned"
    assert body[0]["title"] == "Reach the vault"
    assert body[2]["status"] == "landed"
    assert body[2]["title"] == "Alarm already triggered"

    disk = json.loads((tmp_path / "p" / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"))
    assert "3" in disk["chapter_beats"]
    assert len(disk["chapter_beats"]["3"]) == 3

    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    disk = json.loads(sf.read_text())
    assert "chapter_beats" in disk
    assert "3" in disk["chapter_beats"]


def test_delete_node_scrubs_beat_links(tmp_path):
    _seed(tmp_path)
    state = StoryState(str(tmp_path / "p"))
    state.add_chapter_beat(
        3,
        ChapterBeat(id="beat_3_001", title="Linked", linked_node_ids=["graph_node_001"]),
    )
    state.save_state()

    state.delete_story_graph_node("graph_node_001")
    state.save_state()

    beat = StoryState(str(tmp_path / "p")).get_chapter_beats(3)[0]
    assert beat.linked_node_ids == []
