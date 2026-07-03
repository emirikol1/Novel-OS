"""Tests for sequential batch outline / codex extraction."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from batch_extract import (  # noqa: E402
    batch_extract_codex,
    batch_extract_outlines,
    batch_outline_extract_stats,
    chapter_has_outline,
    resolve_chapter_source,
)
from chapter_regenerator import ChapterRegenerator  # noqa: E402
from chapter_outline_generator import ChapterOutlineGenerator  # noqa: E402


def _seed_project(tmp_path: Path, chapter_numbers: list[int]) -> Path:
    proj = tmp_path / "novel"
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    chapters = {
        str(n): {"number": n, "title": f"Ch{n}", "status": "draft", "word_count": 100}
        for n in chapter_numbers
    }
    (proj / "outputs" / "state").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(
        json.dumps({
            "metadata": {"title": "T"},
            "chapters": chapters,
            "characters": {},
            "plot_threads": {},
            "story_bible": {"logline": "Test"},
        }),
        encoding="utf-8",
    )
    for n in chapter_numbers:
        (ms / f"chapter_{n:03d}_draft.md").write_text(
            f"Chapter {n} prose with enough words for mining.",
            encoding="utf-8",
        )
    return proj


def test_resolve_chapter_source_best(tmp_path):
    proj = _seed_project(tmp_path, [1])
    reader = ChapterRegenerator(str(proj))
    label, text = resolve_chapter_source(reader, 1, "best")
    assert label == "draft"
    assert "Chapter 1" in text


def test_batch_extract_outlines_skips_existing_preview(tmp_path, monkeypatch):
    proj = _seed_project(tmp_path, [1, 2])
    preview = proj / "outputs" / "feedback" / "chapter_001_outline_preview.md"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text("# Existing outline", encoding="utf-8")

    calls: list[int] = []

    def fake_generate(self, number, **kwargs):
        calls.append(number)
        return "outline", "report.md"

    monkeypatch.setattr(
        "chapter_outline_generator.ChapterOutlineGenerator.generate",
        fake_generate,
    )

    result = batch_extract_outlines(str(proj), skip_existing=True)
    assert result["generated"] == [2]
    assert result["skipped"] == [{"chapter": 1, "reason": "Outline already exists (saved or preview pending)."}]
    assert calls == [2]


def test_batch_extract_outlines_continues_on_failure(tmp_path, monkeypatch):
    proj = _seed_project(tmp_path, [1, 2])

    def fake_generate(self, number, **kwargs):
        if number == 1:
            raise RuntimeError("LLM unavailable")
        return "outline", "report.md"

    monkeypatch.setattr(
        "chapter_outline_generator.ChapterOutlineGenerator.generate",
        fake_generate,
    )

    result = batch_extract_outlines(str(proj), skip_existing=False)
    assert result["generated"] == [2]
    assert len(result["failed"]) == 1
    assert result["failed"][0]["chapter"] == 1


def test_batch_extract_codex_runs_three_passes_per_chapter(tmp_path, monkeypatch):
    proj = _seed_project(tmp_path, [1])
    calls: list[tuple[int, str]] = []

    def fake_mine(self, number, kind, **kwargs):
        calls.append((number, kind))
        return [], "report.md"

    monkeypatch.setattr("chapter_miner.ChapterMiner.mine", fake_mine)

    result = batch_extract_codex(str(proj), skip_existing=False)
    assert result["generated"] == [
        {"chapter": 1, "kind": "plots"},
        {"chapter": 1, "kind": "characters"},
        {"chapter": 1, "kind": "bible"},
    ]
    assert calls == [(1, "plots"), (1, "characters"), (1, "bible")]


def test_batch_extract_outlines_skips_saved_outline(tmp_path, monkeypatch):
    proj = _seed_project(tmp_path, [1])
    (proj / "outputs" / "chapter_001_outline.md").write_text("# Saved outline", encoding="utf-8")

    def fake_generate(self, number, **kwargs):
        raise AssertionError("should not run when saved outline exists")

    monkeypatch.setattr(
        "chapter_outline_generator.ChapterOutlineGenerator.generate",
        fake_generate,
    )

    result = batch_extract_outlines(str(proj), skip_existing=True)
    assert result["generated"] == []
    assert result["skipped"][0]["chapter"] == 1


def test_batch_outline_extract_stats(tmp_path):
    proj = _seed_project(tmp_path, [1, 2])
    preview = proj / "outputs" / "feedback" / "chapter_001_outline_preview.md"
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text("# Preview", encoding="utf-8")

    stats = batch_outline_extract_stats(str(proj))
    assert stats["total_with_prose"] == 2
    assert stats["missing_count"] == 1
    assert stats["missing_chapters"] == [2]
    assert chapter_has_outline(str(proj), 1)
    assert not chapter_has_outline(str(proj), 2)


def test_batch_codex_extract_stats(tmp_path):
    from batch_extract import batch_codex_extract_stats, chapter_has_complete_codex  # noqa: E402

    proj = _seed_project(tmp_path, [1, 2])
    feedback = proj / "outputs" / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    for kind in ("plots", "characters", "bible"):
        (feedback / f"chapter_001_mine_{kind}_preview.json").write_text(
            json.dumps({"parsed": {}}),
            encoding="utf-8",
        )

    stats = batch_codex_extract_stats(str(proj))
    assert stats["total_with_prose"] == 2
    assert stats["missing_count"] == 1
    assert stats["missing_chapters"] == [2]
    assert chapter_has_complete_codex(str(proj), 1)
    assert not chapter_has_complete_codex(str(proj), 2)


def test_batch_extract_outlines_auto_accept(tmp_path, monkeypatch):
    proj = _seed_project(tmp_path, [1])

    def fake_generate(self, number, **kwargs):
        preview = self.preview_path(number)
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text("# Generated outline", encoding="utf-8")
        return "# Generated outline", "report.md"

    monkeypatch.setattr(
        "chapter_outline_generator.ChapterOutlineGenerator.generate",
        fake_generate,
    )

    result = batch_extract_outlines(str(proj), skip_existing=False, auto_accept=True)
    assert result["generated"] == [1]
    saved = proj / "outputs" / "chapter_001_outline.md"
    assert saved.exists()
    assert "Generated outline" in saved.read_text(encoding="utf-8")
    gen = ChapterOutlineGenerator(str(proj))
    assert not gen.preview_path(1).exists()


def test_batch_extract_outlines_requires_chapters(tmp_path):
    proj = tmp_path / "empty"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(
        '{"metadata":{"title":"T"},"chapters":{},"characters":{},"plot_threads":{},"story_bible":{}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No chapters"):
        batch_extract_outlines(str(proj))
