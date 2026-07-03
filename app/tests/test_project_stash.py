"""Tests for stashed project archive/restore."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from api import db as dbmod  # noqa: E402
from api.main import create_app  # noqa: E402
from project_portable import build_package_bytes, import_package_bytes  # noqa: E402
from project_stash import delete_stashed, list_stashed, restore_stashed, stash_project  # noqa: E402
from state_manager import StoryState, initialize_project  # noqa: E402


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


def _seed_project(root: Path, slug: str, title: str, genre: str) -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": title, "genre": genre, "author": "Test Author", "status": "in_progress"},
        "characters": {},
        "plot_threads": {},
        "chapters": {"1": {"number": 1, "title": "One", "status": "drafted"}},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / slug / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)


def _client(projects_root: Path, stashed_root: Path | None = None) -> TestClient:
    db_url = f"sqlite:///{(projects_root / 'novel_os_test.db').as_posix()}"
    app = create_app(projects_root=projects_root, db_url=db_url)
    if stashed_root is not None:
        import os

        os.environ["NOVEL_OS_STASHED_DIR"] = str(stashed_root)
    return TestClient(app)


def _db_export(project_id: str, title: str, genre: str) -> dict:
    return {
        "version": 1,
        "project_id": project_id,
        "project": {
            "id": project_id,
            "title": title,
            "genre": genre,
            "author": "",
            "status": "in_progress",
            "updated_at": "",
        },
        "chapters": [],
        "artifacts": [],
        "snapshots": [],
        "comments": [],
    }


@pytest.fixture
def library(tmp_path):
    project_dir = tmp_path / "projects"
    stashed_dir = tmp_path / "stashed"
    _seed_project(project_dir, "alpha-novel", "Alpha Novel", "Fantasy")
    return project_dir, stashed_dir


def test_stash_removes_project_from_active_list(library):
    projects_root, stashed_dir = library
    c = _client(projects_root, stashed_dir)

    listed = c.get("/api/projects").json()
    assert any(p["id"] == "alpha-novel" for p in listed)

    resp = c.post("/api/projects/alpha-novel/stash")
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "alpha-novel"
    assert body["title"] == "Alpha Novel"
    assert body["genre"] == "Fantasy"
    assert body["chapter_count"] == 1
    assert body["filename"] == "alpha-novel.novel-os.zip"

    assert c.get("/api/projects").json() == []
    stashed = c.get("/api/stashed").json()
    assert len(stashed) == 1
    assert stashed[0]["id"] == "alpha-novel"
    assert not (projects_root / "alpha-novel").exists()
    assert (stashed_dir / "alpha-novel.novel-os.zip").exists()
    assert (stashed_dir / "manifest.json").exists()


def test_restore_uses_preferred_project_id(library):
    projects_root, stashed_dir = library
    c = _client(projects_root, stashed_dir)
    assert c.post("/api/projects/alpha-novel/stash").status_code == 201

    restored = c.post("/api/stashed/alpha-novel/restore")
    assert restored.status_code == 201
    body = restored.json()
    assert body["id"] == "alpha-novel"
    assert body["title"] == "Alpha Novel"
    assert (projects_root / "alpha-novel" / "outputs" / "state" / "story_state.json").exists()
    assert c.get("/api/stashed").json() == []
    assert not (stashed_dir / "alpha-novel.novel-os.zip").exists()


def test_restore_id_collision_falls_back_to_allocated_folder(library):
    projects_root, stashed_dir = library
    c = _client(projects_root, stashed_dir)
    assert c.post("/api/projects/alpha-novel/stash").status_code == 201

    _seed_project(projects_root, "alpha-novel", "Blocker", "Drama")

    restored = c.post("/api/stashed/alpha-novel/restore")
    assert restored.status_code == 201
    body = restored.json()
    assert body["id"] == "alpha-novel-2"
    assert body["title"] == "Alpha Novel"
    assert (projects_root / "alpha-novel").exists()
    assert (projects_root / "alpha-novel-2").exists()


def test_import_package_bytes_preferred_project_id(tmp_path):
    initialize_project(str(tmp_path / "src"), "Preferred Tale", "Sci-Fi")
    db_export = _db_export("src-id", "Preferred Tale", "Sci-Fi")
    blob = build_package_bytes(
        tmp_path / "src", db_export, project_id="src-id", title="Preferred Tale",
    )
    dest = tmp_path / "library"

    new_id, title = import_package_bytes(
        dest,
        blob,
        import_db=lambda _nid, _data: None,
        sync_artifacts=lambda _nid: None,
        slugify=_slugify,
        preferred_project_id="my-slot",
    )
    assert new_id == "my-slot"
    assert title == "Preferred Tale"
    assert (dest / "my-slot").is_dir()


def test_core_stash_list_restore_delete(tmp_path):
    project_dir = tmp_path / "live" / "beta"
    initialize_project(str(project_dir), "Beta Book", "Mystery")
    state = StoryState(str(project_dir))
    assert len(state.chapters) >= 0
    state.save_state()

    stashed_dir = tmp_path / "stashed"
    db_export = _db_export("beta", "Beta Book", "Mystery")
    blob = build_package_bytes(project_dir, db_export, project_id="beta", title="Beta Book")
    entry = stash_project(
        project_dir,
        stashed_dir,
        blob,
        {"id": "beta", "title": "Beta Book", "genre": "Mystery", "chapter_count": 0},
    )
    assert entry["filename"] == "beta.novel-os.zip"

    listed = list_stashed(stashed_dir)
    assert len(listed) == 1
    assert listed[0]["title"] == "Beta Book"

    projects_root = tmp_path / "library"
    projects_root.mkdir()

    def import_fn(zip_bytes: bytes) -> tuple[str, str]:
        return import_package_bytes(
            projects_root,
            zip_bytes,
            import_db=lambda _nid, _data: None,
            sync_artifacts=lambda _nid: None,
            slugify=_slugify,
            preferred_project_id="beta",
        )

    project_id, title = restore_stashed(stashed_dir, projects_root, "beta", import_fn)
    assert project_id == "beta"
    assert title == "Beta Book"
    assert list_stashed(stashed_dir) == []
    assert not (stashed_dir / "beta.novel-os.zip").exists()



def test_list_stashed_scans_zip_without_manifest(tmp_path):
    project_dir = tmp_path / "gamma"
    initialize_project(str(project_dir), "Gamma Story", "Horror")
    stashed_dir = tmp_path / "stashed"
    stashed_dir.mkdir()
    db_export = _db_export("gamma", "Gamma Story", "Horror")
    blob = build_package_bytes(project_dir, db_export, project_id="gamma", title="Gamma Story")
    (stashed_dir / "gamma.novel-os.zip").write_bytes(blob)

    listed = list_stashed(stashed_dir)
    assert len(listed) == 1
    assert listed[0]["id"] == "gamma"
    assert listed[0]["title"] == "Gamma Story"


def test_list_projects_skips_non_directories(tmp_path):
    _seed_project(tmp_path, "real-project", "Real", "Drama")
    (tmp_path / "stray-file.txt").write_text("not a project", encoding="utf-8")
    from api.services import ProjectService

    projects = ProjectService(tmp_path).list_projects()
    assert [p.id for p in projects] == ["real-project"]


def test_delete_stashed_core(tmp_path):
    stashed_dir = tmp_path / "stashed"
    stashed_dir.mkdir()
    (stashed_dir / "gone.novel-os.zip").write_bytes(b"PK\x03\x04")
    manifest = {
        "version": 1,
        "entries": [{
            "id": "gone",
            "title": "Gone",
            "genre": "",
            "chapter_count": 0,
            "stashed_at": "2020-01-01T00:00:00+00:00",
            "filename": "gone.novel-os.zip",
        }],
    }
    (stashed_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert delete_stashed(stashed_dir, "gone") is True
    assert not (stashed_dir / "gone.novel-os.zip").exists()
    assert json.loads((stashed_dir / "manifest.json").read_text())["entries"] == []
