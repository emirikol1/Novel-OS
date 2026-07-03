"""Tests for chapter title generation and title_source tracking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services import ProjectService
from chapter_title_generator import ChapterTitleGenerator, parse_chapter_title
from state_manager import StoryState, initialize_project


def _seed_titled_project(tmp_path: Path, *, chapters: dict | None = None) -> Path:
    proj = tmp_path / "title_novel"
    initialize_project(str(proj), "Title Novel", "Drama")
    if chapters:
        state = StoryState(str(proj))
        for key, data in chapters.items():
            num = int(key)
            if num not in state.chapters:
                state.create_chapter(num)
            state.update_chapter(num, data)
        state.save_state()
    return proj


def test_parse_chapter_title_strips_block():
    raw = "Note\n[CHAPTER_TITLE]\nThe Weight of Silence\n[/CHAPTER_TITLE]"
    assert parse_chapter_title(raw) == "The Weight of Silence"


def test_parse_chapter_title_rejects_generic_number():
    with pytest.raises(ValueError, match="generic chapter number"):
        parse_chapter_title("[CHAPTER_TITLE]\nChapter 3\n[/CHAPTER_TITLE]")


def test_update_chapter_title_marks_manual(tmp_path):
    proj = _seed_titled_project(
        tmp_path,
        chapters={"1": {"number": 1, "title": "", "status": "drafted", "word_count": 120, "title_source": "auto"}},
    )
    svc = ProjectService(tmp_path)
    updated = svc.update_chapter("title_novel", 1, {"title": "Handwritten"})
    assert updated.title == "Handwritten"
    assert updated.title_source == "manual"
    state = StoryState(str(proj))
    assert state.chapters[1].title_source == "manual"


def test_auto_title_chapter_stats(tmp_path):
    proj = _seed_titled_project(
        tmp_path,
        chapters={
            "1": {"number": 1, "title": "Manual One", "status": "drafted", "word_count": 100, "title_source": "manual"},
            "2": {"number": 2, "title": "Auto Two", "status": "drafted", "word_count": 200, "title_source": "auto"},
            "3": {"number": 3, "title": "", "status": "drafted", "word_count": 150, "title_source": ""},
            "4": {"number": 4, "title": "", "status": "planned", "word_count": 0, "title_source": ""},
        },
    )
    stats = ProjectService(tmp_path).auto_title_chapter_stats("title_novel")
    assert stats.total_with_prose == 3
    assert stats.missing_count == 2
    assert stats.missing_chapters == [2, 3]
    assert stats.secondary_count == 1
    assert stats.secondary_chapters == [2]


def test_generate_chapter_titles_eligible_scope(tmp_path, monkeypatch):
    proj = _seed_titled_project(
        tmp_path,
        chapters={
            "1": {"number": 1, "title": "", "status": "drafted", "word_count": 80, "title_source": ""},
            "2": {"number": 2, "title": "Old Auto", "status": "drafted", "word_count": 90, "title_source": "auto"},
        },
    )
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_draft.md").write_text("Alice opened the vault under moonlight.", encoding="utf-8")
    (ms / "chapter_002_draft.md").write_text("Bob revealed the switched keycard.", encoding="utf-8")

    titles = iter(["Moonlit Vault", "Switched Keycard"])

    def fake_generate(self, number, *, source="best", on_progress=None):
        return next(titles)

    monkeypatch.setattr(ChapterTitleGenerator, "generate", fake_generate)

    result = ProjectService(tmp_path).generate_chapter_titles("title_novel", scope="eligible")
    assert [row.chapter for row in result.generated] == [1, 2]
    state = StoryState(str(proj))
    assert state.chapters[1].title == "Moonlit Vault"
    assert state.chapters[1].title_source == "auto"


def test_generate_chapter_titles_auto_only_scope(tmp_path, monkeypatch):
    proj = _seed_titled_project(
        tmp_path,
        chapters={
            "2": {"number": 2, "title": "Old Auto", "status": "drafted", "word_count": 90, "title_source": "auto"},
        },
    )
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_002_draft.md").write_text("Bob revealed the switched keycard.", encoding="utf-8")

    monkeypatch.setattr(
        ChapterTitleGenerator,
        "generate",
        lambda self, number, *, source="best", on_progress=None: "Switched Keycard",
    )

    result = ProjectService(tmp_path).generate_chapter_titles("title_novel", scope="auto_only")
    assert [row.chapter for row in result.generated] == [2]
    assert result.generated[0].title == "Switched Keycard"


def test_generate_chapter_titles_skips_manual(tmp_path, monkeypatch):
    proj = _seed_titled_project(
        tmp_path,
        chapters={
            "1": {"number": 1, "title": "Mine", "status": "drafted", "word_count": 80, "title_source": "manual"},
        },
    )
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_draft.md").write_text("Prose.", encoding="utf-8")

    monkeypatch.setattr(
        ChapterTitleGenerator,
        "generate",
        lambda self, number, *, source="best", on_progress=None: "Should Not Run",
    )

    result = ProjectService(tmp_path).generate_chapter_titles("title_novel", scope="eligible")
    assert result.generated == []
    assert result.skipped == []
    stats = ProjectService(tmp_path).auto_title_chapter_stats("title_novel")
    assert stats.missing_chapters == []
