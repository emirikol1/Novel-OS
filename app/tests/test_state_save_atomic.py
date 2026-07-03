"""story_state.json must stay present during save_state (no load-during-gap data loss)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from state_manager import StoryState, initialize_project


def test_save_state_never_removes_story_state_file(tmp_path):
    initialize_project(str(tmp_path), "Race Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    state_file = tmp_path / "outputs" / "state" / "story_state.json"
    seen_missing = threading.Event()

    def reader() -> None:
        for _ in range(200):
            if not state_file.exists():
                seen_missing.set()
                return
            time.sleep(0.001)

    def writer() -> None:
        for i in range(50):
            s = StoryState(str(tmp_path))
            s.chapters[1].word_count = 100 + i
            s.save_state()

    threads = [threading.Thread(target=reader) for _ in range(4)]
    threads.append(threading.Thread(target=writer))
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not seen_missing.is_set()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert sorted(data["chapters"].keys()) == ["1", "2"]


def test_concurrent_load_during_save_does_not_persist_empty_chapters(tmp_path):
    """Simulate API _load with persist_migration while another thread saves."""
    initialize_project(str(tmp_path), "Race Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    barrier = threading.Barrier(2)
    state_file = tmp_path / "outputs" / "state" / "story_state.json"

    def saver() -> None:
        barrier.wait()
        for _ in range(30):
            s = StoryState(str(tmp_path))
            s.chapters[1].word_count += 1
            s.save_state()

    def loader() -> None:
        barrier.wait()
        for _ in range(30):
            if not state_file.exists():
                pytest.fail("story_state.json disappeared during save_state")
            loaded = StoryState(str(tmp_path), persist_migration=True)
            if loaded.chapters:
                loaded.chapters[1].title = "One"
                loaded.save_state()

    t1 = threading.Thread(target=saver)
    t2 = threading.Thread(target=loader)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["chapters"], "chapters dict must not be wiped by concurrent load/save"


def test_persist_migration_skipped_when_state_file_missing(tmp_path):
    """API _load must not write an empty project if story_state.json is absent."""
    initialize_project(str(tmp_path), "Race Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()

    state_file = tmp_path / "outputs" / "state" / "story_state.json"
    state_file.unlink()

    StoryState(str(tmp_path), persist_migration=True)

    assert not state_file.exists()


def test_save_state_refuses_empty_chapter_wipe(tmp_path):
    initialize_project(str(tmp_path), "Race Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    state_file = tmp_path / "outputs" / "state" / "story_state.json"
    empty = StoryState(str(tmp_path), auto_migrate=False)
    empty.chapters.clear()
    empty.characters.clear()
    empty.plot_threads.clear()
    empty.save_state()

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert sorted(data["chapters"].keys()) == ["1", "2"]


def test_load_state_recovers_from_backup_on_corrupt_primary(tmp_path):
    initialize_project(str(tmp_path), "Race Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()
    state.create_chapter(2, "Two")
    state.save_state()

    state_file = tmp_path / "outputs" / "state" / "story_state.json"
    state_file.write_text("{not valid json", encoding="utf-8")

    reloaded = StoryState(str(tmp_path), auto_migrate=False)
    assert 1 in reloaded.chapters
    assert 2 in reloaded.chapters
