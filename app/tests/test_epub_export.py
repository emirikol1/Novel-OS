"""Tests for EPUB export."""

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import BadRequest, ProjectService
from epub_exporter import build_epub, markdown_to_xhtml_body, strip_mentions


def _seed_project(root: Path, slug: str, title: str, genre: str,
                  chapters: dict | None = None) -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": title, "genre": genre, "author": "Test Author"},
        "characters": {},
        "plot_threads": {},
        "chapters": chapters or {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")


def _seed_chapter_files(root: Path, slug: str, number: int, **files) -> None:
    proj = root / slug / "outputs"
    nnn = f"{number:03d}"
    (proj / "manuscript").mkdir(parents=True, exist_ok=True)
    if "final" in files and files["final"] is not None:
        (proj / "manuscript" / f"chapter_{nnn}_final.md").write_text(
            files["final"], encoding="utf-8",
        )


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def test_strip_mentions():
    assert strip_mentions("Hello [[char:Full Name]] there") == "Hello Full Name there"
    assert strip_mentions("See [[lore:Label]] now") == "See Label now"
    assert strip_mentions("Ref [[lore:section:Label]] end") == "Ref Label end"


def test_markdown_to_xhtml_escapes_and_headings():
    body = markdown_to_xhtml_body("# Title\n\nPara with <tags>.\n\n---\n\n## Sub")
    assert "<h1>Title</h1>" in body
    assert "<h2>Sub</h2>" in body
    assert "&lt;tags&gt;" in body
    assert "<hr/>" in body


def test_build_epub_valid_zip_and_mimetype():
    data = build_epub("My Book", "Author", [
        (1, "Opening", "# Chapter One\n\nFirst paragraph."),
        (2, "Middle", "Second chapter prose."),
    ])
    assert data[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(data)) as zf:
        assert zf.read("mimetype") == b"application/epub+zip"
        info = zf.getinfo("mimetype")
        assert info.compress_type == zipfile.ZIP_STORED
        assert "OEBPS/content.opf" in zf.namelist()
        assert "OEBPS/nav.xhtml" in zf.namelist()
        assert "OEBPS/chapters/chapter-001.xhtml" in zf.namelist()
        assert "OEBPS/chapters/chapter-002.xhtml" in zf.namelist()
        ch1 = zf.read("OEBPS/chapters/chapter-001.xhtml").decode("utf-8")
        assert "Chapter One" in ch1
        assert "First paragraph." in ch1


def test_export_epub_skips_chapters_without_final(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "complete",
              "word_count": 2, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted",
              "word_count": 0, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "Tale", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, final="Only chapter one is final.")
    svc = ProjectService(tmp_path)
    filename, data = svc.export_epub("p")
    assert filename == "p.epub"
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert "OEBPS/chapters/chapter-001.xhtml" in names
        assert "OEBPS/chapters/chapter-002.xhtml" not in names


def test_export_epub_no_final_raises(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted",
              "word_count": 0, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "Tale", "Drama", chapters=chapters)
    svc = ProjectService(tmp_path)
    with pytest.raises(BadRequest, match="No chapters with Final"):
        svc.export_epub("p")


def test_export_epub_endpoint(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "complete",
              "word_count": 3, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "EPUB Tale", "Drama", chapters=chapters)
    _seed_chapter_files(
        tmp_path, "p", 1,
        final="Meet [[char:Jordan Lee]] at the [[lore:archive:Old Archive]].",
    )
    c = _client(tmp_path)
    resp = c.get("/api/projects/p/export.epub")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/epub+zip"
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.content[:2] == b"PK"
    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        ch1 = zf.read("OEBPS/chapters/chapter-001.xhtml").decode("utf-8")
        assert "Jordan Lee" in ch1
        assert "Old Archive" in ch1
        assert "[[char:" not in ch1


def test_export_epub_404_and_400(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/projects/missing/export.epub").status_code == 404
    _seed_project(tmp_path, "empty", "Empty", "Drama")
    assert c.get("/api/projects/empty/export.epub").status_code == 400
