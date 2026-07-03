"""Tests for oversized chapter splitting."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_splitter import ChapterSplitError, ChapterSplitter  # noqa: E402
from state_manager import StoryState, initialize_project  # noqa: E402


def _seed_project(tmp_path, number: int, words: int):
    proj = tmp_path / "split_novel"
    initialize_project(str(proj), "Split Test", "Fiction")
    text = " ".join(f"word{i}" for i in range(words))
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / f"chapter_{number:03d}_draft.md").write_text(text, encoding="utf-8")
    state = StoryState(str(proj))
    ch = state.get_chapter(number) or state.create_chapter(number, "Long")
    ch.status = "drafted"
    ch.word_count = words
    state.save_state()
    return proj


def test_split_creates_parts_with_labels(tmp_path):
    proj = _seed_project(tmp_path, 1, 150)
    result = ChapterSplitter(str(proj)).split_chapter(1, source="draft", max_words=60)
    assert len(result.parts) == 3
    assert result.parts[0]["display_label"] == "1a"
    assert result.parts[1]["display_label"] == "1b"
    assert result.parts[2]["display_label"] == "1c"

    state = StoryState(str(proj))
    assert state.get_chapter(1).part_label == "a"
    assert state.get_chapter(1).part_of == 1
    assert state.get_chapter(2).part_label == "b"
    assert state.get_chapter(3).part_label == "c"


def test_split_noop_when_short(tmp_path):
    proj = _seed_project(tmp_path, 1, 40)
    result = ChapterSplitter(str(proj)).split_chapter(1, source="draft", max_words=60)
    assert len(result.parts) == 1
    assert result.parts[0]["number"] == 1


def test_split_recovers_from_backup_after_truncated_draft(tmp_path):
    proj = _seed_project(tmp_path, 1, 150)
    splitter = ChapterSplitter(str(proj))
    backup = proj / "outputs" / "feedback" / "chapter_001_pre_split_draft.md"
    backup.parent.mkdir(parents=True, exist_ok=True)
    full = " ".join(f"word{i}" for i in range(150))
    backup.write_text(full, encoding="utf-8")
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text(
        " ".join(f"word{i}" for i in range(60)),
        encoding="utf-8",
    )
    state = StoryState(str(proj))
    ch = state.get_chapter(1)
    assert ch is not None
    ch.part_label = "a"
    ch.part_of = 1
    state.save_state()

    result = splitter.split_chapter(1, source="draft", max_words=60)
    assert result.recovered_from_backup
    assert len(result.parts) == 3


def test_partial_split_without_backup_raises(tmp_path):
    proj = _seed_project(tmp_path, 1, 40)
    state = StoryState(str(proj))
    ch = state.get_chapter(1)
    assert ch is not None
    ch.part_label = "a"
    ch.part_of = 1
    state.save_state()
    backup = proj / "outputs" / "feedback" / "chapter_001_pre_split_draft.md"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(" ".join(f"word{i}" for i in range(40)), encoding="utf-8")

    with pytest.raises(ChapterSplitError, match="partially split"):
        ChapterSplitter(str(proj)).split_chapter(1, source="draft", max_words=60)
