"""Chapter registry must survive stale saves, plot mining, and corrupt state files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from state_integrity import discover_chapter_numbers_from_artifacts, reconcile_chapters_from_artifacts
from state_manager import StoryState, initialize_project
from state_parser import apply_chapter_plot_mine


def test_stale_empty_save_cannot_wipe_chapters(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    stale = StoryState(str(tmp_path), auto_migrate=False)
    stale.chapters.clear()
    stale.characters.clear()
    stale.plot_threads.clear()
    stale.save_state()

    disk = json.loads(
        (tmp_path / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"),
    )
    assert sorted(disk["chapters"].keys()) == ["1", "2"]
    assert stale.chapters[1].title == "One"


def test_manuscript_files_restore_missing_registry_rows(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    ms = tmp_path / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_draft.md").write_text("Once upon a time.", encoding="utf-8")
    (ms / "chapter_002_final.md").write_text("The end.", encoding="utf-8")

    state_file = tmp_path / "outputs" / "state" / "story_state.json"
    state_file.write_text(
        json.dumps({"schema_version": 2, "chapters": {}, "characters": {}, "plot_threads": {}}),
        encoding="utf-8",
    )

    state = StoryState(str(tmp_path), auto_migrate=False)
    assert sorted(state.chapters.keys()) == [1, 2]
    assert state.chapters[2].status == "drafted"
    assert state.chapters[2].word_count == 2


def test_plot_mine_apply_cannot_wipe_other_chapters(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    ms = tmp_path / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_draft.md").write_text("Chapter one prose.", encoding="utf-8")
    (ms / "chapter_002_draft.md").write_text("Chapter two prose.", encoding="utf-8")

    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    stale = StoryState(str(tmp_path), auto_migrate=False)
    stale.chapters = {2: stale.chapters[2]}
    apply_chapter_plot_mine(
        stale,
        2,
        {
            "plot_threads": ["Arc | main | Description | Hero"],
            "subplot_threads": [],
            "subplot_beats": [],
            "resolved_subplots": [],
            "plot_events": ["Beat"],
        },
        source="mine_plots",
    )
    stale.save_state()

    disk = json.loads(
        (tmp_path / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"),
    )
    assert "1" in disk["chapters"]
    assert "2" in disk["chapters"]
    assert disk["plot_threads"]


def test_explicit_delete_chapter_after_files_removed(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    ms = tmp_path / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    draft = ms / "chapter_001_draft.md"
    draft.write_text("Chapter one.", encoding="utf-8")

    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()

    draft.unlink()
    state.delete_chapter(1)
    state.save_state()

    disk = json.loads(
        (tmp_path / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"),
    )
    assert "1" not in disk.get("chapters", {})


def test_save_appends_history_snapshot(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()

    history = tmp_path / "outputs" / "state" / "history"
    assert history.is_dir()
    assert list(history.glob("story_state_*.json"))


def test_orphan_manuscript_file_not_adopted_on_save(tmp_path):
    """A stray chapter_003 file must not join the registry when only 1–2 are registered."""
    initialize_project(str(tmp_path), "Novel", "Drama")
    ms = tmp_path / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_draft.md").write_text("One.", encoding="utf-8")
    (ms / "chapter_002_draft.md").write_text("Two.", encoding="utf-8")
    (ms / "chapter_003_draft.md").write_text("Orphan three.", encoding="utf-8")

    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    disk = json.loads(
        (tmp_path / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"),
    )
    assert sorted(disk["chapters"].keys()) == ["1", "2"]


def test_renumber_style_merge_drops_absent_numbers(tmp_path):
    """After 1,3,5 -> 1,2,3 reassign, chapter 5 must not reappear from stale on_disk."""
    from state_integrity import merge_chapters_for_save

    incoming = {
        "1": {"number": 1, "title": "One"},
        "2": {"number": 2, "title": "Three"},
        "3": {"number": 3, "title": "Five"},
    }
    on_disk = {
        "1": {"number": 1, "title": "One"},
        "3": {"number": 3, "title": "Three"},
        "5": {"number": 5, "title": "Five"},
    }
    merged = merge_chapters_for_save(incoming, on_disk, tmp_path)
    assert sorted(int(k) for k in merged) == [1, 2, 3]

    ms = tmp_path / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_003_final.md").write_text("Final text here.", encoding="utf-8")
    found = discover_chapter_numbers_from_artifacts(tmp_path)
    assert found == {3}

    state = StoryState(str(tmp_path), auto_migrate=False)
    state.chapters.clear()
    restored = reconcile_chapters_from_artifacts(state, registry_numbers=set())
    assert restored == [3]
