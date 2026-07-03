"""Tests for chapter artifact path matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_files import chapter_artifact_paths, chapter_file_rename_steps  # noqa: E402


def test_chapter_artifact_paths_do_not_match_longer_numbers(tmp_path):
    out = tmp_path / "outputs" / "manuscript"
    out.mkdir(parents=True)
    (out / "chapter_002_draft.md").write_text("two", encoding="utf-8")
    (out / "chapter_020_draft.md").write_text("twenty", encoding="utf-8")

    two = chapter_artifact_paths(tmp_path, 2)
    twenty = chapter_artifact_paths(tmp_path, 20)

    assert [p.name for p in two] == ["chapter_002_draft.md"]
    assert [p.name for p in twenty] == ["chapter_020_draft.md"]


def test_chapter_file_rename_steps_only_touch_target_number(tmp_path):
    out = tmp_path / "outputs" / "manuscript"
    out.mkdir(parents=True)
    (out / "chapter_002_draft.md").write_text("two", encoding="utf-8")
    (out / "chapter_020_draft.md").write_text("twenty", encoding="utf-8")

    steps = chapter_file_rename_steps(tmp_path, 2, 3)
    assert len(steps) == 1
    assert steps[0][0].name == "chapter_002_draft.md"
    assert steps[0][1].name == "chapter_003_draft.md"
