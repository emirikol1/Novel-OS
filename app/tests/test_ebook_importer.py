"""Tests for flexible ebook / manuscript import parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ebook_importer import import_ebook, parse_ebook
from import_pipeline import ImportPipeline
from state_manager import initialize_project


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTING_IMPORTS = REPO_ROOT / "testing-imports"


@pytest.fixture
def fresh_import_project(tmp_path):
    proj = tmp_path / "import-target"
    proj.mkdir()
    initialize_project(str(proj), "Import Test", "Literary Fiction")
    return proj


def test_parse_juliette_splits_six_parts():
    src = TESTING_IMPORTS / "marquis-de-sade" / "english" / "juliette.txt"
    if not src.is_file():
        pytest.skip("testing-imports corpus not available")

    parsed = parse_ebook(src)
    assert parsed.metadata.title
    assert parsed.metadata.split_strategy.startswith("word_parts_")
    assert len(parsed.chapters) == 6
    assert all(ch.text.strip() for ch in parsed.chapters)
    total_words = sum(len(ch.text.split()) for ch in parsed.chapters)
    assert total_words > 200_000
    for ch in parsed.chapters:
        assert len(ch.text.split()) > 10_000


def test_parse_juliette_strips_front_and_back_matter():
    src = TESTING_IMPORTS / "marquis-de-sade" / "english" / "juliette.txt"
    if not src.is_file():
        pytest.skip("testing-imports corpus not available")

    parsed = parse_ebook(src)
    assert "Foreword" in parsed.front_matter
    assert "Bibliography" in parsed.back_matter
    assert "Panthemont" in parsed.chapters[0].text


def test_parse_huckleberry_gutenberg_chapters():
    src = TESTING_IMPORTS / "_huckleberry-finn-full.txt"
    if not src.is_file():
        pytest.skip("testing-imports corpus not available")

    parsed = parse_ebook(src)
    assert parsed.metadata.title == "Adventures of Huckleberry Finn"
    assert "Twain" in parsed.metadata.author
    assert parsed.metadata.split_strategy == "gutenberg_chapter"
    assert len(parsed.chapters) == 42


def test_parse_huckleberry_chapters_directory():
    src = TESTING_IMPORTS / "huckleberry-finn" / "chapters"
    if not src.is_dir():
        pytest.skip("testing-imports corpus not available")

    parsed = parse_ebook(src)
    assert parsed.metadata.split_strategy == "directory"
    assert len(parsed.chapters) == 42


def test_import_ebook_no_extract_creates_drafts(fresh_import_project, tmp_path):
    sample = tmp_path / "mini.txt"
    sample.write_text(
        "Title: Mini Tale\nAuthor: Test Author\n\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK MINI ***\n\n"
        "CHAPTER I.\nShort toc line.\n\n"
        "CHAPTER II.\nShort toc line.\n\n"
        "CHAPTER I.\n\n"
        + " ".join(f"word{i}" for i in range(210))
        + ".\n\nCHAPTER II.\n\n"
        + " ".join(f"other{i}" for i in range(210))
        + ".\n\n*** END OF THE PROJECT GUTENBERG EBOOK MINI ***\n",
        encoding="utf-8",
    )

    summary = import_ebook(
        sample,
        fresh_import_project,
        title="Mini Tale",
        genre="Test",
        extract=False,
    )
    assert summary["chapters_imported"] == 2
    assert summary["total_words"] > 0

    pipe = ImportPipeline(str(fresh_import_project))
    assert pipe.state.get_chapter(1) is not None
    assert pipe.state.get_chapter(2) is not None
    draft1 = fresh_import_project / "outputs" / "manuscript" / "chapter_001_draft.md"
    assert draft1.is_file()
    assert "word0" in draft1.read_text(encoding="utf-8")

    state_path = fresh_import_project / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["metadata"].get("import_split_strategy")
    assert state["metadata"].get("imported") is True


def test_parse_only_parts_override(tmp_path):
    body = " ".join(f"word{i}" for i in range(600))
    sample = tmp_path / "flat.txt"
    sample.write_text(body, encoding="utf-8")

    parsed = parse_ebook(sample, split_strategy="parts", parts=3)
    assert len(parsed.chapters) == 3
    assert parsed.metadata.split_strategy == "word_parts_3"
