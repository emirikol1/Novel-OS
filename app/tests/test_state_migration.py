"""P0/P2 tests for schema_version detection and v1→v2 migration."""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from api.services import ProjectService  # noqa: E402
from project_portable import build_package_bytes, import_package_bytes  # noqa: E402
from state_manager import PlotThread, StoryState, initialize_project  # noqa: E402
from state_migration import (  # noqa: E402
    CURRENT_SCHEMA_VERSION,
    LEGACY_SCHEMA_VERSION,
    detect_schema_version,
    migrate_raw_story_state_json,
    migrate_story_state,
)


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


def _write_legacy_state(project_dir: Path, *, schema_version=None, extra=None) -> Path:
    state_dir = project_dir / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"title": "Legacy Tale", "genre": "Fantasy"},
        "characters": {
            "char_a": {
                "id": "char_a",
                "full_name": "Alice",
                "role": "protagonist",
                "aliases": [],
            },
            "char_b": {
                "id": "char_b",
                "full_name": "Bob",
                "role": "supporting",
                "aliases": [],
            },
        },
        "plot_threads": {
            "plot_main": {
                "id": "plot_main",
                "name": "Main Quest",
                "description": "Save the realm",
                "thread_type": "main",
                "status": "active",
                "priority": 5,
                "sort_order": 0,
                "subplots": ["Side path"],
                "start_chapter": 2,
                "target_resolution_chapter": 10,
                "related_characters": ["char_a"],
                "related_threads": [],
                "milestones": [],
                "foreshadowing_planted": [],
                "last_updated_chapter": 0,
            },
        },
        "chapters": {
            "1": {"number": 1, "title": "One", "status": "planned"},
            "2": {"number": 2, "title": "Two", "status": "planned"},
        },
        "timeline": [],
        "style_profile": {},
        "story_graph_nodes": {},
        "story_graph_edges": {},
        "chapter_briefs": {
            "1": {
                "chapter_number": 1,
                "active_character_ids": ["char_a"],
                "mentioned_character_ids": [],
                "active_node_ids": [],
                "required_beats": ["Open the gate"],
                "landed_beats": ["Hero arrives"],
            },
            "2": {
                "chapter_number": 2,
                "active_character_ids": ["char_a", "char_b"],
                "mentioned_character_ids": [],
                "active_node_ids": [],
                "required_beats": [],
                "landed_beats": [],
            },
        },
        "chapter_beats": {},
        "session_log": [],
    }
    if extra:
        payload.update(extra)
    if schema_version is not None:
        payload["schema_version"] = schema_version
    state_file = state_dir / "story_state.json"
    state_file.write_text(json.dumps(payload), encoding="utf-8")
    return state_file


def test_detect_schema_version_missing():
    assert detect_schema_version({}) == LEGACY_SCHEMA_VERSION
    assert detect_schema_version({"metadata": {}}) == LEGACY_SCHEMA_VERSION


def test_detect_schema_version_explicit_v2():
    assert detect_schema_version({"schema_version": 2}) == CURRENT_SCHEMA_VERSION


def test_new_project_initialize_is_v2(tmp_path):
    initialize_project(str(tmp_path / "fresh"), "Fresh Novel", "Sci-Fi")
    raw = json.loads(
        (tmp_path / "fresh" / "outputs" / "state" / "story_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_persists_when_requested(tmp_path):
    project_dir = tmp_path / "legacy"
    state_file = _write_legacy_state(project_dir)
    assert "schema_version" not in json.loads(state_file.read_text(encoding="utf-8"))

    state = StoryState(str(project_dir), persist_migration=True)
    assert state.schema_version == CURRENT_SCHEMA_VERSION

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_idempotent_double_load(tmp_path):
    project_dir = tmp_path / "legacy-twice"
    _write_legacy_state(project_dir)

    first = StoryState(str(project_dir), persist_migration=True)
    assert first.schema_version == CURRENT_SCHEMA_VERSION
    mtime_after_first = (project_dir / "outputs" / "state" / "story_state.json").stat().st_mtime

    second = StoryState(str(project_dir), persist_migration=True)
    assert second.schema_version == CURRENT_SCHEMA_VERSION
    mtime_after_second = (project_dir / "outputs" / "state" / "story_state.json").stat().st_mtime
    assert mtime_after_second == mtime_after_first


def test_list_projects_does_not_persist_migration(tmp_path):
    legacy_dir = tmp_path / "listed-legacy"
    state_file = _write_legacy_state(legacy_dir)
    before = state_file.read_text(encoding="utf-8")
    assert "schema_version" not in json.loads(before)

    summaries = ProjectService(tmp_path).list_projects()
    assert len(summaries) == 1
    assert summaries[0].id == "listed-legacy"
    assert summaries[0].title == "Legacy Tale"
    assert summaries[0].chapter_count == 2

    after = state_file.read_text(encoding="utf-8")
    assert after == before
    assert "schema_version" not in json.loads(after)


def test_migrate_raw_story_state_json_legacy_to_v2():
    raw, result = migrate_raw_story_state_json({"metadata": {"title": "X"}})
    assert result.changed is True
    assert result.source_version == LEGACY_SCHEMA_VERSION
    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_raw_story_state_json_idempotent():
    raw, result = migrate_raw_story_state_json({"schema_version": 2, "metadata": {}})
    assert result.changed is False
    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION


def test_full_v1_fixture_end_to_end(tmp_path):
    project_dir = tmp_path / "v1-full"
    _write_legacy_state(project_dir)

    state = StoryState(str(project_dir), persist_migration=True, auto_migrate=False)
    result = migrate_story_state(state)
    assert result.changed is True
    assert "migrate_graph_from_plot_threads" in result.steps_applied
    assert "backfill_node_lifespan" in result.steps_applied
    assert "sync_brief_mentioned_characters" in result.steps_applied
    assert "migrate_brief_beats_to_chapter_beats" in result.steps_applied
    assert state.schema_version == CURRENT_SCHEMA_VERSION

    assert len(state.story_graph_nodes) >= 2
    main_node = state.story_graph_nodes.get("graph_node_plot_main")
    assert main_node is not None
    assert main_node.start_chapter == 2
    assert main_node.resolution_chapter == 10
    assert main_node.legacy_plot_thread_id == "plot_main"

    brief1 = state.chapter_briefs[1]
    assert "char_a" in brief1.mentioned_character_ids
    assert "char_a" in brief1.active_character_ids

    brief2 = state.chapter_briefs[2]
    assert set(brief2.mentioned_character_ids) == {"char_a", "char_b"}

    beats1 = state.chapter_beats[1]
    assert len(beats1) == 2
    assert beats1[0].title == "Open the gate"
    assert beats1[0].status == "planned"
    assert beats1[1].title == "Hero arrives"
    assert beats1[1].status == "landed"

    state.save_state()
    again = StoryState(str(project_dir), persist_migration=True)
    assert again.schema_version == CURRENT_SCHEMA_VERSION
    assert len(again.story_graph_nodes) == len(state.story_graph_nodes)
    assert len(again.chapter_beats.get(1, [])) == 2


def test_migrate_idempotent_double_run_in_memory(tmp_path):
    project_dir = tmp_path / "v1-idempotent"
    _write_legacy_state(project_dir)
    state = StoryState(str(project_dir), auto_migrate=False)
    first = migrate_story_state(state)
    assert first.changed is True
    node_count = len(state.story_graph_nodes)
    beat_count = len(state.chapter_beats.get(1, []))
    second = migrate_story_state(state)
    assert second.changed is False
    assert len(state.story_graph_nodes) == node_count
    assert len(state.chapter_beats.get(1, [])) == beat_count


def test_migrate_skips_beats_when_chapter_beats_populated(tmp_path):
    project_dir = tmp_path / "v1-beats-skip"
    _write_legacy_state(
        project_dir,
        extra={
            "chapter_beats": {
                "1": [
                    {
                        "id": "beat_1_001",
                        "title": "Existing beat",
                        "summary": "",
                        "sort_order": 0,
                        "status": "planned",
                        "linked_node_ids": [],
                    }
                ]
            }
        },
    )
    state = StoryState(str(project_dir), auto_migrate=False)
    migrate_story_state(state)
    assert len(state.chapter_beats[1]) == 1
    assert state.chapter_beats[1][0].title == "Existing beat"


def test_sync_chapter_pins_additive_from_briefs(tmp_path):
    project_dir = tmp_path / "v1-pins"
    state_file = _write_legacy_state(project_dir)
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    raw["chapter_briefs"]["2"]["active_node_ids"] = ["graph_node_plot_main"]
    state_file.write_text(json.dumps(raw), encoding="utf-8")

    state = StoryState(str(project_dir), auto_migrate=False)
    migrate_story_state(state)
    node = state.story_graph_nodes["graph_node_plot_main"]
    assert 2 in node.chapter_pins


def test_renumber_updates_node_lifespan_and_pins(tmp_path):
    initialize_project(str(tmp_path / "p"), "Renumber", "Drama")
    state = StoryState(str(tmp_path / "p"), auto_migrate=False)
    from story_graph import StoryGraphNode

    state.add_story_graph_node(
        StoryGraphNode(
            id="node_a",
            kind="plot_thread",
            title="Thread A",
            start_chapter=3,
            resolution_chapter=5,
            chapter_pins=[3, 4],
        )
    )
    state.create_chapter(3, "Three")
    state.create_chapter(4, "Four")
    state.create_chapter(5, "Five")
    state.save_state()

    state.reassign_chapter(3, 2)
    node = state.story_graph_nodes["node_a"]
    assert node.start_chapter == 2
    assert node.resolution_chapter == 5
    assert node.chapter_pins == [2, 4]

    state.reassign_chapter(5, 6)
    node = state.story_graph_nodes["node_a"]
    assert node.resolution_chapter == 6


def test_renumber_sequential_updates_chapter_beats_keys(tmp_path):
    initialize_project(str(tmp_path / "p"), "Beats Renumber", "Drama")
    state = StoryState(str(tmp_path / "p"), auto_migrate=False)
    from story_graph import ChapterBeat

    state.create_chapter(1, "One")
    state.create_chapter(3, "Three")
    state.create_chapter(5, "Five")
    state.set_chapter_beats(
        5,
        [ChapterBeat(id="beat_5_001", title="Climax", sort_order=0, status="planned")],
    )
    state.save_state()

    state.reassign_chapter(5, 3)
    assert 3 in state.chapter_beats
    assert 5 not in state.chapter_beats
    assert state.chapter_beats[3][0].title == "Climax"


def test_delete_chapter_scrubs_v2_structure(tmp_path):
    initialize_project(str(tmp_path / "p"), "Delete", "Drama")
    state = StoryState(str(tmp_path / "p"), auto_migrate=False)
    from story_graph import ChapterBeat, ChapterBrief, StoryGraphNode

    state.create_chapter(2, "Two")
    state.add_story_graph_node(
        StoryGraphNode(
            id="node_x",
            kind="plot_thread",
            title="X",
            start_chapter=2,
            resolution_chapter=2,
            chapter_pins=[2],
        )
    )
    state.set_chapter_brief(ChapterBrief(chapter_number=2, active_character_ids=["char_a"]))
    state.set_chapter_beats(
        2,
        [ChapterBeat(id="beat_2_001", title="Mid", sort_order=0, status="planned")],
    )
    state.save_state()

    assert state.delete_chapter(2) is True
    node = state.story_graph_nodes["node_x"]
    assert node.start_chapter == 0
    assert node.resolution_chapter is None
    assert node.chapter_pins == []
    assert 2 not in state.chapter_briefs
    assert 2 not in state.chapter_beats


def test_portable_import_triggers_migration(tmp_path):
    legacy_dir = tmp_path / "export-src"
    _write_legacy_state(legacy_dir)
    db_export = {
        "version": 1,
        "project_id": "export-src",
        "project": {"id": "export-src", "title": "Legacy Tale", "genre": "Fantasy",
                    "author": "", "status": "in_progress", "updated_at": ""},
        "chapters": [],
        "artifacts": [],
        "snapshots": [],
        "comments": [],
    }
    blob = build_package_bytes(
        legacy_dir, db_export, project_id="export-src", title="Legacy Tale",
    )
    assert blob[:2] == b"PK"

    dest = tmp_path / "library"
    imported: list[str] = []

    def import_db(new_id: str, data: dict) -> None:
        imported.append(new_id)

    new_id, title = import_package_bytes(
        dest,
        blob,
        import_db=import_db,
        sync_artifacts=lambda _nid: None,
        slugify=_slugify,
    )
    assert title == "Legacy Tale"
    assert new_id == "legacy-tale"
    assert imported == ["legacy-tale"]

    state_file = dest / new_id / "outputs" / "state" / "story_state.json"
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION
    assert raw["story_graph_nodes"]
    assert raw["chapter_beats"]["1"]
    assert "char_a" in raw["chapter_briefs"]["1"]["mentioned_character_ids"]
