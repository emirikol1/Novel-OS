import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import ProjectService


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


@pytest.fixture
def projects_root(tmp_path):
    _seed_project(tmp_path, "the-last-signal", "The Last Signal", "Sci-Fi Thriller")
    return tmp_path


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_project_detail_includes_storage_paths(projects_root):
    c = _client(projects_root)
    data = c.get("/api/projects/the-last-signal").json()
    root = projects_root / "the-last-signal"
    assert data["project_path"] == str(root)
    assert data["story_state_path"] == str(root / "outputs" / "state" / "story_state.json")
    assert data["manuscript_path"] == str(root / "outputs" / "manuscript")


def test_system_prompt_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    c = TestClient(create_app())
    assert c.get("/api/settings/system-prompt").json()["prefix"] == ""
    c.put("/api/settings/system-prompt", json={"prefix": "Be concise.", "agents_dir": ""})
    assert c.get("/api/settings/system-prompt").json()["prefix"] == "Be concise."


def test_agent_prompt_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    c = TestClient(create_app())
    listing = c.get("/api/settings/agent-prompts")
    assert listing.status_code == 200
    prompts = listing.json()["prompts"]
    assert any(p["agent"] == "scribe" for p in prompts)

    updated = c.put(
        "/api/settings/agent-prompts/scribe",
        json={"selected_variant": "custom", "custom_prompt": "Write with warmer scene texture."},
    )
    assert updated.status_code == 200
    scribe = next(p for p in updated.json()["prompts"] if p["agent"] == "scribe")
    assert scribe["selected_variant"] == "custom"
    assert scribe["custom_prompt"] == "Write with warmer scene texture."

    bad = c.put(
        "/api/settings/agent-prompts/scribe",
        json={"selected_variant": "broken", "custom_prompt": ""},
    )
    assert bad.status_code == 400


def test_llm_queue_settings_and_flush(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    import llm_queue as lq

    lq._queue = None
    c = TestClient(create_app())

    default = c.get("/api/settings/llm-queue")
    assert default.status_code == 200
    assert default.json()["max_concurrent"] == 2
    assert default.json()["active"] == 0

    updated = c.put("/api/settings/llm-queue", json={"max_concurrent": 3})
    assert updated.status_code == 200
    assert updated.json()["max_concurrent"] == 3

    flushed = c.post("/api/settings/llm-queue/flush")
    assert flushed.status_code == 200
    assert flushed.json()["queue"]["flushed"] is True
    lq._queue = None


def test_list_projects(projects_root):
    svc = ProjectService(projects_root)
    projects = svc.list_projects()
    assert len(projects) == 1
    assert projects[0].id == "the-last-signal"
    assert projects[0].title == "The Last Signal"
    assert projects[0].chapter_count == 0


def _client(projects_root):
    db_url = f"sqlite:///{(Path(projects_root) / 'novel_os_test.db').as_posix()}"
    app = create_app(projects_root=projects_root, db_url=db_url)
    return TestClient(app)


def test_get_projects_endpoint(projects_root):
    resp = _client(projects_root).get("/api/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == "the-last-signal"


def test_project_detail(projects_root):
    resp = _client(projects_root).get("/api/projects/the-last-signal")
    assert resp.status_code == 200
    assert resp.json()["author"] == "Test Author"


def test_project_detail_404(projects_root):
    resp = _client(projects_root).get("/api/projects/nope")
    assert resp.status_code == 404


def test_chapters_list(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 2300, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    resp = _client(tmp_path).get("/api/projects/p/chapters")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["number"] == 1
    assert rows[0]["title"] == "Opening"
    assert rows[0]["pipeline_step"] == "drafted"


def test_chapter_pipeline_step_from_files(tmp_path):
    chapters = {"1": {"number": 1, "title": "Ch1", "status": "complete",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    (ms / "chapter_001_final.md").write_text("Final prose here.", encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "final"


def test_chapter_pipeline_step_validated(tmp_path):
    chapters = {"1": {"number": 1, "title": "Ch1", "status": "validated",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    ms = tmp_path / "p" / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    (ms / "chapter_001_revised.md").write_text("Revised.", encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "validated"


def test_update_chapter_title(tmp_path):
    chapters = {"1": {"number": 1, "title": "", "status": "drafted",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    c = _client(tmp_path)
    resp = c.patch("/api/projects/p/chapters/1", json={"title": "The Archive"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "The Archive"
    assert resp.json()["title_source"] == "manual"
    detail = c.get("/api/projects/p/chapters/1").json()
    assert detail["title"] == "The Archive"
    list_row = c.get("/api/projects/p/chapters").json()[0]
    assert list_row["title"] == "The Archive"


def test_chapter_detail_with_files(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 5, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "chapter_001_outline.md").write_text("# Beat sheet", encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("Prose here", encoding="utf-8")
    resp = _client(tmp_path).get("/api/projects/p/chapters/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["outline"] == "# Beat sheet"
    assert body["draft"] == "Prose here"


def test_chapter_detail_missing_files(tmp_path):
    chapters = {"2": {"number": 2, "title": "", "status": "planned",
                      "word_count": 0, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    body = _client(tmp_path).get("/api/projects/p/chapters/2").json()
    assert body["outline"] is None
    assert body["draft"] is None


def test_chapter_404(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    resp = _client(tmp_path).get("/api/projects/p/chapters/9")
    assert resp.status_code == 404


def test_characters_endpoint(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {"char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"}}
    sf.write_text(json.dumps(data), encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/characters").json()
    assert rows[0]["full_name"] == "Lena"


# --- M2: chapter stages + editable Final -------------------------------------

def _seed_chapter_files(root: Path, slug: str, number: int,
                        outline=None, draft=None, revised=None, final=None) -> None:
    proj = root / slug / "outputs"
    nnn = f"{number:03d}"
    (proj / "manuscript").mkdir(parents=True, exist_ok=True)
    if outline is not None:
        (proj / f"chapter_{nnn}_outline.md").write_text(outline, encoding="utf-8")
    if draft is not None:
        (proj / "manuscript" / f"chapter_{nnn}_draft.md").write_text(draft, encoding="utf-8")
    if revised is not None:
        (proj / "manuscript" / f"chapter_{nnn}_revised.md").write_text(revised, encoding="utf-8")
    if final is not None:
        (proj / "manuscript" / f"chapter_{nnn}_final.md").write_text(final, encoding="utf-8")


def _seed_with_chapter(tmp_path, number=1, status="drafted", **files):
    chapters = {str(number): {"number": number, "title": "Opening", "status": status,
                              "word_count": 0, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", number, **files)


def test_stages_returns_all_present_artifacts(tmp_path):
    _seed_with_chapter(tmp_path, outline="# Beats", draft="Draft text", revised="Revised text")
    body = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert body["outline"] == "# Beats"
    assert body["draft"] == "Draft text"
    assert body["revised"] == "Revised text"
    assert body["final"] is None


def test_stages_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).get("/api/projects/p/chapters/9/stages").status_code == 404


def test_promote_final_prefers_revised(tmp_path):
    _seed_with_chapter(tmp_path, draft="Draft text", revised="Revised text")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.status_code == 200
    assert resp.json()["final"] == "Revised text"
    # now present in stages
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["final"] == "Revised text"


def test_promote_final_falls_back_to_draft(tmp_path):
    _seed_with_chapter(tmp_path, draft="Only draft")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.json()["final"] == "Only draft"


def test_approve_promotes_draft_when_no_revised(tmp_path):
    _seed_with_chapter(tmp_path, status="validated", draft="Imported chapter prose")
    ProjectService(tmp_path).approve_chapter("p", 1)
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["final"] == "Imported chapter prose"
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "final"
    assert rows[0]["status"] == "complete"


def test_approve_does_not_auto_promote_when_revised_exists(tmp_path):
    _seed_with_chapter(tmp_path, status="validated", draft="Draft", revised="Revised")
    ProjectService(tmp_path).approve_chapter("p", 1)
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["final"] is None
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "approved"


def test_promote_final_conflict_when_no_source(tmp_path):
    _seed_with_chapter(tmp_path)  # no artifacts at all
    assert _client(tmp_path).post("/api/projects/p/chapters/1/final/promote").status_code == 409


def test_promote_is_idempotent_without_force(tmp_path):
    _seed_with_chapter(tmp_path, revised="Revised", final="Hand-edited final")
    # already has a final — promote without force must not clobber the human edit
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.json()["final"] == "Hand-edited final"


def test_save_final_writes_and_updates_word_count(tmp_path):
    _seed_with_chapter(tmp_path, draft="x")
    resp = _client(tmp_path).put("/api/projects/p/chapters/1/final", json={"text": "one two three"})
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 3
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["final"] == "one two three"


def test_save_revised_writes_and_updates_status(tmp_path):
    _seed_with_chapter(tmp_path, draft="draft", revised="old revised")
    resp = _client(tmp_path).put("/api/projects/p/chapters/1/revised", json={"text": "new revised text"})
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 3
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["revised"] == "new revised text"


def test_save_final_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).put("/api/projects/p/chapters/9/final",
                                 json={"text": "x"}).status_code == 404


def test_unfinalize_copies_final_to_draft_and_revised(tmp_path):
    _seed_with_chapter(
        tmp_path, status="complete",
        draft="Old draft", revised="Old revised", final="Canonical final prose here",
    )
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["final"] is None
    assert body["draft"] == "Canonical final prose here"
    assert body["revised"] == "Canonical final prose here"
    assert body["status"] == "edited"
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["final"] is None
    assert stages["draft"] == "Canonical final prose here"
    assert stages["continuity"] is None
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_reopens_complete_without_final(tmp_path):
    _seed_with_chapter(tmp_path, status="complete", draft="Draft", revised="Revised")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    assert resp.json()["status"] == "edited"
    assert resp.json()["draft"] == "Draft"
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_clears_validated_and_final(tmp_path):
    chapters = {
        "1": {
            "number": 1, "title": "Ch", "status": "validated",
            "word_count": 10, "pov_character": "",
            "continuity_checks": {"status": "PASS", "validated_at": "2026-01-01"},
        },
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, revised="Revised text", final="Final canon")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "edited"
    assert body["final"] is None
    assert body["revised"] == "Final canon"
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["continuity"] is None
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_conflict_when_nothing_to_reopen(tmp_path):
    _seed_with_chapter(tmp_path, status="drafted", draft="Only draft")
    assert _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize").status_code == 409


# --- Tier 0: create / run / export -------------------------------------------

import api.services as services


def test_create_project_then_lists(tmp_path):
    c = _client(tmp_path)
    resp = c.post("/api/projects", json={"title": "The Drowned City", "genre": "Fantasy"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "the-drowned-city"
    assert body["chapter_count"] == 1
    ids = [p["id"] for p in c.get("/api/projects").json()]
    assert "the-drowned-city" in ids

    detail = c.get("/api/projects/the-drowned-city").json()
    assert detail["chapter_count"] == 1

    chars = c.get("/api/projects/the-drowned-city/characters").json()
    assert len(chars) == 1
    assert chars[0]["role"] == "protagonist"

    nodes = c.get("/api/projects/the-drowned-city/story-graph/nodes").json()
    assert len(nodes) == 1
    assert nodes[0]["title"] == "Central conflict"
    assert nodes[0]["start_chapter"] == 1

    brief = c.get("/api/projects/the-drowned-city/chapters/1/brief").json()
    assert brief["pov_character_id"] == chars[0]["id"]
    assert brief["active_node_ids"] == [nodes[0]["id"]]
    assert brief["mentioned_character_ids"]
    assert set(brief["active_character_ids"]) <= set(brief["mentioned_character_ids"])


def test_create_project_seeded_brief_v2_fields(tmp_path):
    c = _client(tmp_path)
    resp = c.post("/api/projects", json={"title": "Signal Fire", "genre": "Sci-Fi"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    brief = c.get(f"/api/projects/{project_id}/chapters/1/brief").json()
    assert brief["mentioned_character_ids"]
    assert brief["active_character_ids"]
    assert brief["active_node_ids"]

    beats = c.get(f"/api/projects/{project_id}/chapters/1/beats").json()
    assert len(beats) == 1
    assert beats[0]["linked_node_ids"] == brief["active_node_ids"]


def test_create_project_requires_title(tmp_path):
    assert _client(tmp_path).post("/api/projects", json={"title": "  "}).status_code == 400


def test_add_character(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    resp = _client(tmp_path).post("/api/projects/p/characters",
                                  json={"name": "Mara Vale", "role": "protagonist"})
    assert resp.status_code == 201
    assert any(c["full_name"] == "Mara Vale" for c in resp.json())


def _wait_job(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.03)
    return client.get(f"/api/jobs/{job_id}").json()


class _FakeOrch:
    calls: list = []

    def __init__(self, _dir):
        pass

    def write_chapter(self, n):
        _FakeOrch.calls.append(("write", n))


def test_run_phase_job_lifecycle(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama")
    _FakeOrch.calls = []
    monkeypatch.setattr(services, "build_orchestrator", lambda d: _FakeOrch(d))
    c = _client(tmp_path)
    resp = c.post("/api/projects/p/run", json={"stage": "write", "params": {"number": 1}})
    assert resp.status_code == 202
    job = _wait_job(c, resp.json()["job_id"])
    assert job["status"] == "done"
    assert _FakeOrch.calls == [("write", 1)]


def test_cancel_job_api(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama")
    hold = threading.Event()
    released = threading.Event()

    class SlowOrch:
        def write_chapter(self, n):
            hold.set()
            released.wait(timeout=3)

    monkeypatch.setattr(services, "build_orchestrator", lambda d: SlowOrch())
    c = _client(tmp_path)
    job_id = c.post("/api/projects/p/run", json={"stage": "write", "params": {"number": 1}}).json()["job_id"]
    hold.wait(timeout=2)
    resp = c.post(f"/api/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    assert resp.json()["error"] == "Cancelled"
    released.set()


def test_run_unknown_stage_400(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).post("/api/projects/p/run",
                                  json={"stage": "nope", "params": {}}).status_code == 400


def test_run_job_captures_error(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama")

    def boom(_dir):
        class O:
            def write_chapter(self, n):
                raise RuntimeError("LLM exploded")
        return O()

    monkeypatch.setattr(services, "build_orchestrator", boom)
    c = _client(tmp_path)
    job_id = c.post("/api/projects/p/run", json={"stage": "write", "params": {"number": 1}}).json()["job_id"]
    job = _wait_job(c, job_id)
    assert job["status"] == "error"
    assert "LLM exploded" in job["error"]


def test_export_prefers_final(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "complete",
                      "word_count": 2, "pov_character": ""}}
    _seed_project(tmp_path, "p", "Compiled Tale", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, draft="DRAFT body", final="FINAL body")
    text = _client(tmp_path).get("/api/projects/p/export").text
    assert "Compiled Tale" in text
    assert "FINAL body" in text
    assert "DRAFT body" not in text


def test_export_import_project_package(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "drafted",
                      "word_count": 3, "pov_character": ""}}
    _seed_project(tmp_path, "source", "Shared Novel", "Sci-Fi", chapters=chapters)
    _seed_chapter_files(tmp_path, "source", 1, draft="chapter one")
    c = _client(tmp_path)
    dbmod.ingest_project(tmp_path, "source")

    export = c.get("/api/projects/source/export-package")
    assert export.status_code == 200
    assert export.headers["content-type"] == "application/zip"
    assert export.content[:2] == b"PK"

    imported = c.post(
        "/api/projects/import-package",
        content=export.content,
        headers={"Content-Type": "application/zip"},
    )
    assert imported.status_code == 201
    body = imported.json()
    assert body["id"] == "shared-novel"
    assert body["title"] == "Shared Novel"
    assert body["chapter_count"] == 1
    assert (tmp_path / "shared-novel" / "outputs" / "state" / "story_state.json").exists()
    assert c.get("/api/projects/shared-novel").status_code == 200


_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_export_import_package_includes_features_14_16(tmp_path):
    _seed_project(tmp_path, "source", "Rich Novel", "Fantasy")
    sf = tmp_path / "source" / "outputs" / "state" / "story_state.json"
    state = json.loads(sf.read_text(encoding="utf-8"))
    state["characters"] = {
        "char_a": {
            "id": "char_a",
            "full_name": "Alice",
            "role": "protagonist",
            "aliases": [],
            "portrait_filename": "",
        },
    }
    sf.write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)
    dbmod.ingest_project(tmp_path, "source")

    spark = c.post(
        "/api/projects/source/research",
        json={"title": "Spark", "body": "notes", "kind": "note", "tags": ["x"]},
    )
    assert spark.status_code == 201
    created_map = c.post("/api/projects/source/maps", json={"name": "Realm"})
    assert created_map.status_code == 201
    map_id = created_map.json()["id"]
    assert c.post(
        f"/api/projects/source/maps/{map_id}/image",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    ).status_code == 200
    assert c.post(
        f"/api/projects/source/maps/{map_id}/pins",
        json={"label": "Capital", "x": 0.5, "y": 0.5},
    ).status_code == 201
    assert c.post(
        "/api/projects/source/characters/char_a/portrait",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    ).status_code == 200

    export = c.get("/api/projects/source/export-package")
    assert export.status_code == 200
    import zipfile
    import io
    with zipfile.ZipFile(io.BytesIO(export.content), "r") as zf:
        names = set(zf.namelist())
        db_data = json.loads(zf.read("db_export.json"))
    assert len(db_data.get("research_sparks", [])) == 1
    assert len(db_data.get("project_maps", [])) == 1
    assert len(db_data.get("map_pins", [])) == 1
    assert any(n.startswith("assets/portraits/char_a/") for n in names)
    assert any(n.startswith(f"assets/maps/{map_id}/") for n in names)

    imported = c.post(
        "/api/projects/import-package",
        content=export.content,
        headers={"Content-Type": "application/zip"},
    )
    assert imported.status_code == 201
    new_id = imported.json()["id"]
    sparks = c.get(f"/api/projects/{new_id}/research").json()
    assert len(sparks) == 1 and sparks[0]["title"] == "Spark"
    maps = c.get(f"/api/projects/{new_id}/maps").json()
    assert len(maps) == 1 and maps[0]["name"] == "Realm"
    new_map_id = maps[0]["id"]
    pins = c.get(f"/api/projects/{new_id}/maps/{new_map_id}/pins").json()
    assert len(pins) == 1 and pins[0]["label"] == "Capital"
    portrait = c.get(f"/api/projects/{new_id}/characters/char_a/portrait")
    assert portrait.status_code == 200


def test_import_package_rejects_invalid_zip(tmp_path):
    c = _client(tmp_path)
    resp = c.post(
        "/api/projects/import-package",
        content=b"not a zip",
        headers={"Content-Type": "application/zip"},
    )
    assert resp.status_code == 400


# --- Tier 1: snapshots + comments + DB ingest ---------------------------------

import api.db as dbmod


def test_snapshot_lifecycle(tmp_path):
    _seed_with_chapter(tmp_path, draft="draft body")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    r = c.post("/api/projects/p/chapters/1/snapshots", json={"label": "v1"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert any(s["id"] == sid for s in c.get("/api/projects/p/chapters/1/snapshots").json())
    got = c.get(f"/api/projects/p/chapters/1/snapshots/{sid}").json()
    assert got["text"] == "draft body" and got["label"] == "v1"


def test_snapshot_409_without_final(tmp_path):
    _seed_with_chapter(tmp_path)
    assert _client(tmp_path).post("/api/projects/p/chapters/1/snapshots", json={}).status_code == 409


def test_snapshot_restore_makes_backup(tmp_path):
    _seed_with_chapter(tmp_path, draft="orig")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    sid = c.post("/api/projects/p/chapters/1/snapshots", json={"label": "v1"}).json()["id"]
    c.put("/api/projects/p/chapters/1/final", json={"text": "changed"})
    r = c.post(f"/api/projects/p/chapters/1/snapshots/{sid}/restore")
    assert r.status_code == 200 and r.json()["final"] == "orig"
    assert c.get("/api/projects/p/chapters/1/stages").json()["final"] == "orig"
    labels = [s["label"] for s in c.get("/api/projects/p/chapters/1/snapshots").json()]
    assert "Before restore" in labels


def test_snapshot_delete(tmp_path):
    _seed_with_chapter(tmp_path, draft="x")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    sid = c.post("/api/projects/p/chapters/1/snapshots", json={}).json()["id"]
    assert c.delete(f"/api/projects/p/chapters/1/snapshots/{sid}").status_code == 204
    assert c.get("/api/projects/p/chapters/1/snapshots").json() == []


def test_comment_crud(tmp_path):
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/comments", json={"body": "tighten this", "quote": "the pipe"})
    assert r.status_code == 201
    cid = r.json()["id"]
    rows = c.get("/api/projects/p/chapters/1/comments").json()
    assert rows[0]["body"] == "tighten this" and rows[0]["quote"] == "the pipe"
    up = c.patch(f"/api/projects/p/chapters/1/comments/{cid}", json={"resolved": True})
    assert up.json()["resolved"] is True
    assert c.delete(f"/api/projects/p/chapters/1/comments/{cid}").status_code == 204
    assert c.get("/api/projects/p/chapters/1/comments").json() == []


def test_comment_requires_body(tmp_path):
    _seed_with_chapter(tmp_path)
    assert _client(tmp_path).post("/api/projects/p/chapters/1/comments", json={"body": "  "}).status_code == 400


def test_legacy_comment_defaults_stage(tmp_path):
    """Older callers sending only body + quote get stage=comment."""
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/comments", json={"body": "note", "quote": "snippet"})
    assert r.status_code == 201
    row = r.json()
    assert row["stage"] == "comment"
    assert row["start_offset"] is None
    assert row["end_offset"] is None
    assert row["paragraph_hash"]  # auto-derived from quote


def test_annotation_crud_with_metadata(tmp_path):
    _seed_with_chapter(tmp_path, draft="First paragraph.\n\nSecond paragraph.")
    c = _client(tmp_path)
    payload = {
        "body": "tighten opening",
        "quote": "First paragraph.",
        "stage": "draft",
        "start_offset": 0,
        "end_offset": 16,
        "paragraph_hash": "abc123deadbeef",
    }
    r = c.post("/api/projects/p/chapters/1/comments", json=payload)
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["stage"] == "draft"
    assert r.json()["start_offset"] == 0
    assert r.json()["end_offset"] == 16
    assert r.json()["paragraph_hash"] == "abc123deadbeef"

    rows = c.get("/api/projects/p/chapters/1/comments").json()
    assert len(rows) == 1
    assert rows[0]["stage"] == "draft"

    up = c.patch(
        f"/api/projects/p/chapters/1/comments/{cid}",
        json={"resolved": True, "stage": "revised", "start_offset": 5, "end_offset": 20},
    )
    assert up.status_code == 200
    assert up.json()["resolved"] is True
    assert up.json()["stage"] == "revised"
    assert up.json()["start_offset"] == 5
    assert up.json()["end_offset"] == 20

    assert c.delete(f"/api/projects/p/chapters/1/comments/{cid}").status_code == 204
    assert c.get("/api/projects/p/chapters/1/comments").json() == []


def test_annotation_invalid_stage(tmp_path):
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post(
        "/api/projects/p/chapters/1/comments",
        json={"body": "x", "stage": "outline"},
    )
    assert r.status_code == 400


def test_annotation_metadata_survives_db_reload(tmp_path):
    _seed_with_chapter(tmp_path)
    db_url = f"sqlite:///{(tmp_path / 'novel_os_test.db').as_posix()}"
    c = _client(tmp_path)
    r = c.post(
        "/api/projects/p/chapters/1/comments",
        json={
            "body": "final polish",
            "quote": "the ending",
            "stage": "final",
            "start_offset": 42,
            "end_offset": 52,
        },
    )
    cid = r.json()["id"]

    dbmod.configure(db_url)
    row = dbmod.comment_update("p", 1, cid, resolved=True)
    assert row is not None
    assert row.stage == "final"
    assert row.start_offset == 42
    assert row.end_offset == 52
    assert row.paragraph_hash

    listed = c.get("/api/projects/p/chapters/1/comments").json()
    assert listed[0]["stage"] == "final"
    assert listed[0]["start_offset"] == 42
    assert listed[0]["resolved"] is True


def test_comment_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    assert c.get("/api/projects/p/chapters/1/comments").status_code == 404
    assert c.post("/api/projects/p/chapters/1/comments", json={"body": "x"}).status_code == 404


def test_paragraph_anchor_hash_stable():
    h1 = dbmod.paragraph_anchor_hash("  First   paragraph.  ")
    h2 = dbmod.paragraph_anchor_hash("First paragraph.")
    assert h1 == h2
    assert len(h1) == 16


def test_ingest_mirrors_content_to_db(tmp_path):
    _seed_with_chapter(tmp_path, outline="# Beats", draft="draft body")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")  # dual-writes final to DB
    assert dbmod.get_artifact_text("p", 1, "final") == "draft body"
    c.get("/api/projects/p/chapters/1/stages")  # triggers ingest of outline/draft
    assert dbmod.get_artifact_text("p", 1, "outline") == "# Beats"
    assert dbmod.get_artifact_text("p", 1, "draft") == "draft body"


def test_save_outline_and_title_after_final(tmp_path):
    _seed_with_chapter(tmp_path, outline="# Original beats", draft="draft body")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    r = c.put("/api/projects/p/chapters/1/outline", json={"text": "# Updated beats\n\n- New beat"})
    assert r.status_code == 200
    assert r.json()["word_count"] == 6
    outline_path = tmp_path / "p" / "outputs" / "chapter_001_outline.md"
    assert "Updated beats" in outline_path.read_text(encoding="utf-8")
    title = c.patch("/api/projects/p/chapters/1", json={"title": "Renamed chapter"}).json()
    assert title["title"] == "Renamed chapter"
    state = json.loads((tmp_path / "p" / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"))
    assert state["chapters"]["1"]["title"] == "Renamed chapter"


# --- Delete operations --------------------------------------------------------

def test_delete_character(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {"char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"}}
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p/characters/char_001").status_code == 204
    assert c.get("/api/projects/p/characters").json() == []


def test_character_aliases_round_trip(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_jordan": {
            "id": "char_jordan", "full_name": "Jordan Lee", "role": "protagonist",
            "aliases": ["Nickname"],
        }
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    listed = c.get("/api/projects/p/characters").json()
    assert listed[0]["aliases"] == ["Nickname"]
    detail = c.get("/api/projects/p/characters/char_jordan").json()
    assert detail["aliases"] == ["Nickname"]
    patched = c.patch(
        "/api/projects/p/characters/char_jordan",
        json={"aliases": ["Nickname", "Ms. Lee", "Mrs Quinn"]},
    )
    assert patched.status_code == 200
    assert patched.json()["aliases"] == ["Nickname", "Ms. Lee", "Mrs Quinn"]


def test_delete_plot_thread(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_main": {
            "id": "plot_main", "name": "The Quest", "description": "Find it",
            "thread_type": "main", "status": "active", "priority": 5,
            "sort_order": 0, "subplots": ["Side quest"],
        },
        "plot_b": {
            "id": "plot_b", "name": "Romance", "description": "",
            "thread_type": "subplot", "status": "active", "priority": 3,
            "sort_order": 1, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    rows = c.get("/api/projects/p/plot-threads").json()
    assert rows[0]["name"] == "The Quest"
    assert rows[0]["subplots"] == ["Side quest"]
    assert c.delete("/api/projects/p/plot-threads/plot_main").status_code == 204
    assert len(c.get("/api/projects/p/plot-threads").json()) == 1


def test_timeline_crud(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_001": {
            "id": "char_001", "full_name": "Alice", "role": "protagonist",
            "aliases": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    assert c.get("/api/projects/p/timeline").json() == []

    created = c.post(
        "/api/projects/p/timeline",
        json={
            "description": "Alice arrives at the station",
            "chapter": 2,
            "day": 3,
            "time": "dawn",
            "location": "Central Station",
            "characters_present": ["char_001"],
            "event_type": "scene",
            "significance": "major",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["description"] == "Alice arrives at the station"
    assert body["chapter"] == 2
    assert body["day"] == 3
    assert body["characters_present"] == ["char_001"]
    event_id = body["id"]

    listed = c.get("/api/projects/p/timeline").json()
    assert len(listed) == 1
    assert listed[0]["id"] == event_id

    patched = c.patch(
        f"/api/projects/p/timeline/{event_id}",
        json={"description": "Alice boards the train", "significance": "turning_point"},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Alice boards the train"
    assert patched.json()["significance"] == "turning_point"

    assert c.delete(f"/api/projects/p/timeline/{event_id}").status_code == 204
    assert c.get("/api/projects/p/timeline").json() == []

    saved = json.loads(sf.read_text())
    assert saved["timeline"] == []


def test_timeline_create_validation(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    assert c.post("/api/projects/p/timeline", json={"description": "", "chapter": 1}).status_code == 400
    assert c.post(
        "/api/projects/p/timeline",
        json={"description": "Beat", "chapter": 1, "event_type": "invalid"},
    ).status_code == 400
    assert c.post(
        "/api/projects/p/timeline",
        json={"description": "Beat", "chapter": 1, "characters_present": ["missing"]},
    ).status_code == 404


def test_research_sparks_crud(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_001": {
            "id": "char_001", "full_name": "Alice", "role": "protagonist",
            "aliases": [],
        },
    }
    data["plot_threads"] = {
        "plot_main": {
            "id": "plot_main", "name": "Main arc", "description": "",
            "thread_type": "main", "status": "active", "priority": 1,
            "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    assert c.get("/api/projects/p/research").json() == []

    created = c.post(
        "/api/projects/p/research",
        json={
            "title": "Station architecture",
            "body": "Victorian ironwork references",
            "source_url": "https://example.com/station",
            "tags": ["architecture", "mood"],
            "kind": "link",
            "attachment_ref": "photo-notes.txt",
            "link_character_id": "char_001",
            "link_chapter": 2,
            "link_plot_thread_id": "plot_main",
            "link_bible_section": "world_building",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Station architecture"
    assert body["tags"] == ["architecture", "mood"]
    assert body["kind"] == "link"
    assert body["source_url"] == "https://example.com/station"
    spark_id = body["id"]

    listed = c.get("/api/projects/p/research").json()
    assert len(listed) == 1
    assert listed[0]["id"] == spark_id

    filtered = c.get("/api/projects/p/research", params={"tag": "mood"}).json()
    assert len(filtered) == 1
    assert c.get("/api/projects/p/research", params={"tag": "missing"}).json() == []

    search = c.get("/api/projects/p/research", params={"q": "ironwork"}).json()
    assert len(search) == 1

    patched = c.patch(
        f"/api/projects/p/research/{spark_id}",
        json={"title": "Updated station notes", "kind": "note"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Updated station notes"
    assert patched.json()["kind"] == "note"

    assert c.delete(f"/api/projects/p/research/{spark_id}").status_code == 204
    assert c.get("/api/projects/p/research").json() == []

    saved = json.loads(sf.read_text())
    assert "research" not in saved


def test_research_sparks_validation(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    assert c.post("/api/projects/p/research", json={"title": ""}).status_code == 400
    assert c.post(
        "/api/projects/p/research",
        json={"title": "X", "kind": "invalid"},
    ).status_code == 400
    assert c.post(
        "/api/projects/p/research",
        json={"title": "X", "link_character_id": "missing"},
    ).status_code == 404


def test_reorder_plot_threads(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_a": {
            "id": "plot_a", "name": "First", "description": "", "thread_type": "main",
            "status": "active", "priority": 5, "sort_order": 0, "subplots": [],
        },
        "plot_b": {
            "id": "plot_b", "name": "Second", "description": "", "thread_type": "main",
            "status": "active", "priority": 3, "sort_order": 1, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    resp = c.put(
        "/api/projects/p/plot-threads/reorder",
        json={"ordered_ids": ["plot_b", "plot_a"]},
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert names == ["Second", "First"]
    assert names == [r["name"] for r in c.get("/api/projects/p/plot-threads").json()]


def test_update_plot_thread_subplots(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_x": {
            "id": "plot_x", "name": "Arc", "description": "Main arc", "thread_type": "main",
            "status": "active", "priority": 4, "sort_order": 0, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    resp = c.patch(
        "/api/projects/p/plot-threads/plot_x",
        json={"subplots": ["Beat one", "Beat two"]},
    )
    assert resp.status_code == 200
    assert resp.json()["subplots"] == ["Beat one", "Beat two"]


def test_delete_chapter(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "drafted",
                      "word_count": 5, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, draft="hello world")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p/chapters/1").status_code == 204
    assert c.get("/api/projects/p/chapters").json() == []
    proj = tmp_path / "p"
    assert not (proj / "outputs" / "manuscript" / "chapter_001_draft.md").exists()


def test_delete_project(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p").status_code == 204
    assert c.get("/api/projects").json() == []
    assert not (tmp_path / "p").exists()


def test_delete_chapter_removes_all_chapter_assets(tmp_path):
    chapters = {
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    files = [
        proj / "outputs" / "chapter_002_prompt.md",
        proj / "outputs" / "chapter_002_scribe_prompt.md",
        proj / "outputs" / "manuscript" / "chapter_002_draft.md",
        proj / "outputs" / "sources" / "chapter_002_paste.txt",
        proj / "outputs" / "feedback" / "chapter_002_report.md",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("asset", encoding="utf-8")

    c = _client(tmp_path)
    assert c.delete("/api/projects/p/chapters/2").status_code == 204
    for path in files:
        assert not path.exists()
    state = json.loads((proj / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"))
    assert "2" not in state["chapters"]


def test_reassign_chapter_move(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 5, "pov_character": ""},
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 3, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_briefs"] = {
        "1": {"chapter_number": 1, "required_beats": ["open"], "landed_beats": ["arrived"]}
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("chapter one", encoding="utf-8")
    (proj / "outputs" / "feedback").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "feedback" / "chapter_001_regenerate_meta.json").write_text("{}", encoding="utf-8")
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/reassign", json={"to_number": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "moved"
    assert body["to_number"] == 2
    rows = c.get("/api/projects/p/chapters").json()
    nums = sorted(ch["number"] for ch in rows)
    assert nums == [2, 3]
    assert (proj / "outputs" / "manuscript" / "chapter_002_draft.md").exists()
    assert not (proj / "outputs" / "manuscript" / "chapter_001_draft.md").exists()
    assert (proj / "outputs" / "feedback" / "chapter_002_regenerate_meta.json").exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "1" not in state["chapter_briefs"]
    assert state["chapter_briefs"]["2"]["chapter_number"] == 2
    assert state["chapter_briefs"]["2"]["landed_beats"] == ["arrived"]


def test_reassign_chapter_swap(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_briefs"] = {
        "1": {"chapter_number": 1, "required_beats": ["one"]},
        "2": {"chapter_number": 2, "required_beats": ["two"]},
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/reassign", json={"to_number": 2})
    assert r.status_code == 200
    assert r.json()["action"] == "swapped"
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows[1] == "Two"
    assert rows[2] == "One"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["chapter_briefs"]["1"]["chapter_number"] == 1
    assert state["chapter_briefs"]["1"]["required_beats"] == ["two"]
    assert state["chapter_briefs"]["2"]["chapter_number"] == 2
    assert state["chapter_briefs"]["2"]["required_beats"] == ["one"]


def test_reassign_chapter_collision_cancels_before_moving(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 3, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    source = proj / "outputs" / "manuscript" / "chapter_001_draft.md"
    collision = proj / "outputs" / "manuscript" / "chapter_002_draft.md"
    source.write_text("chapter one", encoding="utf-8")
    collision.write_text("existing chapter two artifact", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/reassign", json={"to_number": 2})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Chapter file collision detected" in detail
    assert "no files were moved" in detail
    assert str(source) in detail
    assert str(collision) in detail
    assert source.exists()
    assert collision.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sorted(state["chapters"]) == ["1", "3"]
    assert state["chapters"]["1"]["title"] == "One"


def test_insert_chapter_shifts_existing_numbers(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_briefs"] = {
        "2": {"chapter_number": 2, "required_beats": ["two"]},
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_002_draft.md").write_text("chapter two", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/insert", json={"number": 2, "title": "Inserted"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "inserted"
    assert body["inserted_number"] == 2
    assert body["mapping"] == [{"from_number": 2, "to_number": 3}]
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows == {1: "One", 2: "Inserted", 3: "Two"}
    assert (proj / "outputs" / "manuscript" / "chapter_003_draft.md").exists()
    assert not (proj / "outputs" / "manuscript" / "chapter_002_draft.md").exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["chapter_briefs"]["3"]["chapter_number"] == 3
    assert state["chapter_briefs"]["3"]["required_beats"] == ["two"]


def test_insert_chapter_collision_cancels_before_shifting(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    source = proj / "outputs" / "manuscript" / "chapter_002_draft.md"
    collision = proj / "outputs" / "manuscript" / "chapter_003_draft.md"
    source.write_text("chapter two", encoding="utf-8")
    collision.write_text("orphan chapter three artifact", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/insert", json={"number": 2, "title": "Inserted"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Chapter file collision detected" in detail
    assert "no files were moved" in detail
    assert str(source) in detail
    assert str(collision) in detail
    assert source.exists()
    assert collision.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sorted(state["chapters"]) == ["1", "2"]
    assert state["chapters"]["2"]["title"] == "Two"


def test_duplicate_chapter_copies_assets_and_shifts_later(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 2, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("chapter one", encoding="utf-8")
    (proj / "outputs" / "manuscript" / "chapter_002_draft.md").write_text("chapter two", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/duplicate", json={})
    assert r.status_code == 200
    assert r.json()["action"] == "duplicated"
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows == {1: "One", 2: "One (copy)", 3: "Two"}
    assert (proj / "outputs" / "manuscript" / "chapter_002_draft.md").read_text(encoding="utf-8") == "chapter one"
    assert (proj / "outputs" / "manuscript" / "chapter_003_draft.md").read_text(encoding="utf-8") == "chapter two"


def test_merge_next_chapter_combines_text_and_compacts(tmp_path):
    chapters = {
        "1": {
            "number": 1,
            "title": "One",
            "status": "drafted",
            "word_count": 2,
            "pov_character": "keep-pov",
            "location": "Keep room",
            "time": "Morning",
            "target_word_count": 1000,
            "scenes": [{"summary": "keep scene"}],
            "plot_advances": ["keep plot"],
            "character_development": {"A": "keep dev"},
            "emotional_beats": ["keep emotion"],
            "new_information": ["keep info"],
            "foreshadowing_planted": ["keep plant"],
            "foreshadowing_resolved": ["keep resolve"],
            "hooks_start": ["keep start"],
            "hooks_end": ["keep end"],
            "continuity_checks": {"shared": "keep continuity"},
            "quality_scores": {"pacing": 0.5},
        },
        "2": {
            "number": 2,
            "title": "Two",
            "status": "complete",
            "word_count": 2,
            "pov_character": "source-pov",
            "location": "Source room",
            "time": "Night",
            "target_word_count": 1500,
            "scenes": [{"summary": "source scene"}],
            "plot_advances": ["source plot"],
            "character_development": {"A": "source dev", "B": "source dev"},
            "emotional_beats": ["source emotion"],
            "new_information": ["source info"],
            "foreshadowing_planted": ["source plant"],
            "foreshadowing_resolved": ["source resolve"],
            "hooks_start": ["source start"],
            "hooks_end": ["source end"],
            "continuity_checks": {"shared": "source continuity", "source": "source continuity"},
            "quality_scores": {"pacing": 0.8, "voice": 0.7},
        },
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["timeline"] = [
        {"id": "t1", "description": "source event", "chapter": 2},
    ]
    state["plot_threads"] = {
        "thread": {
            "id": "thread",
            "name": "Thread",
            "description": "",
            "thread_type": "main",
            "start_chapter": 2,
            "last_updated_chapter": 2,
            "target_resolution_chapter": 2,
            "foreshadowing_planted": [2],
            "milestones": [{"chapter": 2, "description": "source milestone"}],
        }
    }
    state["chapter_briefs"] = {
        "1": {
            "chapter_number": 1,
            "pov_character_id": "keep-pov",
            "pov_mode": "third_limited",
            "active_character_ids": ["a"],
            "active_node_ids": ["node-a"],
            "required_beats": ["keep required"],
            "landed_beats": ["keep landed"],
            "continuity_notes": "keep note",
            "ending_hook": "keep hook",
        },
        "2": {
            "chapter_number": 2,
            "pov_character_id": "source-pov",
            "pov_mode": "first_person",
            "active_character_ids": ["b"],
            "active_node_ids": ["node-b"],
            "required_beats": ["source required"],
            "landed_beats": ["source landed"],
            "continuity_notes": "source note",
            "ending_hook": "source hook",
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("one", encoding="utf-8")
    (proj / "outputs" / "manuscript" / "chapter_002_draft.md").write_text("two", encoding="utf-8")
    (proj / "outputs" / "manuscript" / "chapter_003_draft.md").write_text("three", encoding="utf-8")
    (proj / "outputs" / "feedback").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "feedback" / "chapter_002_report.md").write_text("source report", encoding="utf-8")

    c = _client(tmp_path)
    c.put("/api/projects/p/chapters/1/final", json={"text": "one final"})
    c.put("/api/projects/p/chapters/2/final", json={"text": "two final"})
    c.post("/api/projects/p/chapters/1/snapshots", json={"label": "keep snap"})
    snap_id = c.post("/api/projects/p/chapters/2/snapshots", json={"label": "source snap"}).json()["id"]
    comment_id = c.post(
        "/api/projects/p/chapters/2/comments",
        json={"body": "source comment", "quote": "two", "stage": "draft"},
    ).json()["id"]
    r = c.post("/api/projects/p/chapters/1/merge", json={"source_number": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "merged"
    assert body["removed_snapshot_count"] == 2
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows == {1: "One / Two", 3: "Three"}
    merged = (proj / "outputs" / "manuscript" / "chapter_001_draft.md").read_text(encoding="utf-8")
    assert "one" in merged
    assert "two" in merged
    assert not (proj / "outputs" / "manuscript" / "chapter_002_draft.md").exists()
    assert not (proj / "outputs" / "manuscript" / "chapter_002_final.md").exists()
    assert (proj / "outputs" / "manuscript" / "chapter_001_final.md").read_text(encoding="utf-8") == (
        "one final\n\n---\n\ntwo final"
    )
    assert (proj / "outputs" / "manuscript" / "chapter_003_draft.md").read_text(encoding="utf-8") == "three"
    assert (proj / "outputs" / "feedback" / "chapter_001_merged_from_002_report.md").exists()
    comments = c.get("/api/projects/p/chapters/1/comments").json()
    assert any(row["id"] == comment_id and row["body"] == "source comment" for row in comments)
    snapshots = c.get("/api/projects/p/chapters/1/snapshots").json()
    assert snapshots == []
    assert not any(row["id"] == snap_id for row in snapshots)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    merged_chapter = state["chapters"]["1"]
    assert merged_chapter["pov_character"] == "keep-pov"
    assert merged_chapter["location"] == "Keep room"
    assert merged_chapter["time"] == "Morning"
    assert merged_chapter["target_word_count"] == 2500
    assert merged_chapter["scenes"] == [{"summary": "keep scene"}, {"summary": "source scene"}]
    assert merged_chapter["plot_advances"] == ["keep plot", "source plot"]
    assert merged_chapter["character_development"]["A"] == "keep dev"
    assert merged_chapter["character_development"]["A (merged from chapter 2)"] == "source dev"
    assert merged_chapter["character_development"]["B"] == "source dev"
    assert merged_chapter["emotional_beats"] == ["keep emotion", "source emotion"]
    assert merged_chapter["new_information"] == ["keep info", "source info"]
    assert merged_chapter["foreshadowing_planted"] == ["keep plant", "source plant"]
    assert merged_chapter["foreshadowing_resolved"] == ["keep resolve", "source resolve"]
    assert merged_chapter["hooks_start"] == ["keep start", "source start"]
    assert merged_chapter["hooks_end"] == ["keep end", "source end"]
    assert merged_chapter["continuity_checks"]["shared"] == "keep continuity"
    assert merged_chapter["continuity_checks"]["shared (merged from chapter 2)"] == "source continuity"
    assert merged_chapter["continuity_checks"]["source"] == "source continuity"
    assert merged_chapter["continuity_checks"]["merged_from_chapter_2"]["pov_character"] == "source-pov"
    assert merged_chapter["quality_scores"]["pacing"] == 0.5
    assert merged_chapter["quality_scores"]["pacing (merged from chapter 2)"] == 0.8
    assert merged_chapter["quality_scores"]["voice"] == 0.7
    assert state["timeline"][0]["chapter"] == 1
    thread = state["plot_threads"]["thread"]
    assert thread["start_chapter"] == 1
    assert thread["last_updated_chapter"] == 1
    assert thread["target_resolution_chapter"] == 1
    assert thread["foreshadowing_planted"] == [1]
    assert thread["milestones"][0]["chapter"] == 1
    brief = state["chapter_briefs"]["1"]
    assert "2" not in state["chapter_briefs"]
    assert brief["pov_character_id"] == "keep-pov"
    assert brief["pov_mode"] == "third_limited"
    assert brief["ending_hook"] == "keep hook"
    assert brief["active_character_ids"] == ["a", "b"]
    assert brief["active_node_ids"] == ["node-a", "node-b"]
    assert brief["required_beats"] == ["keep required", "source required"]
    assert brief["landed_beats"] == ["keep landed", "source landed"]
    assert "keep note" in brief["continuity_notes"]
    assert "source note" in brief["continuity_notes"]


def test_renumber_chapters_sequential_removes_gaps(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 3, "pov_character": ""},
        "5": {"number": 5, "title": "Five", "status": "drafted", "word_count": 5, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_briefs"] = {
        "5": {"chapter_number": 5, "required_beats": ["five"]},
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (proj / "outputs" / "feedback").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "feedback" / "chapter_003_report.md").write_text("three", encoding="utf-8")
    (proj / "outputs" / "feedback" / "chapter_005_report.md").write_text("five", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/renumber-sequential")
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "renumbered"
    assert body["mapping"] == [
        {"from_number": 3, "to_number": 2},
        {"from_number": 5, "to_number": 3},
    ]
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows == {1: "One", 2: "Three", 3: "Five"}
    assert (proj / "outputs" / "feedback" / "chapter_002_report.md").exists()
    assert (proj / "outputs" / "feedback" / "chapter_003_report.md").exists()
    assert not (proj / "outputs" / "feedback" / "chapter_005_report.md").exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["chapter_briefs"]["3"]["chapter_number"] == 3
    assert state["chapter_briefs"]["3"]["required_beats"] == ["five"]


def test_renumber_chapters_sequential_collision_cancels_before_moving(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 3, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    state_path = proj / "outputs" / "state" / "story_state.json"
    (proj / "outputs" / "feedback").mkdir(parents=True, exist_ok=True)
    source = proj / "outputs" / "feedback" / "chapter_003_report.md"
    collision = proj / "outputs" / "feedback" / "chapter_002_report.md"
    source.write_text("chapter three", encoding="utf-8")
    collision.write_text("orphan chapter two artifact", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/renumber-sequential")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Chapter file collision detected" in detail
    assert "no files were moved" in detail
    assert str(source) in detail
    assert str(collision) in detail
    assert source.exists()
    assert collision.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sorted(state["chapters"]) == ["1", "3"]
    assert state["chapters"]["3"]["title"] == "Three"


def test_validate_chapter_structure_reports_orphan_assets(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "planned", "word_count": 0, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "feedback").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "feedback" / "chapter_005_report.md").write_text("orphan", encoding="utf-8")

    c = _client(tmp_path)
    r = c.get("/api/projects/p/chapter-structure")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_count"] == 1
    assert body["project_path"] == str(proj)
    assert any(
        issue["component"] == "assets"
        and issue["chapter"] == 5
        and "missing chapter 5" in issue["message"]
        for issue in body["issues"]
    )
    assert body["chapters"][0]["number"] == 1


def test_validate_chapter_structure_ignores_orphan_source_paste(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "planned", "word_count": 0, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "sources").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "sources" / "chapter_006_paste.txt").write_text("scratch", encoding="utf-8")

    c = _client(tmp_path)
    r = c.get("/api/projects/p/chapter-structure")
    assert r.status_code == 200
    body = r.json()
    assert not any(
        issue["component"] == "assets"
        and issue["chapter"] == 6
        for issue in body["issues"]
    )


def test_extract_background_no_llm(tmp_path, monkeypatch):
    """Endpoint accepts job; we mock extractor to avoid LLM."""
    _seed_project(tmp_path, "p", "P", "Drama")
    from background_extractor import BackgroundExtractor

    def fake_extract(self, text, *, label="Background", dry_run=False, on_progress=None):
        parsed = {
            "block_summary": "Test block",
            "logline": "A test logline",
            "new_characters": ["Jane Doe | protagonist | A hero"],
            "story_bible_notes": ["The world is round"],
        }
        from state_parser import apply_background_to_state
        changes = apply_background_to_state(self.state, parsed, source="lorekeeper", label=label)
        self.state.save_state()
        return changes, "/tmp/report.md"

    monkeypatch.setattr(BackgroundExtractor, "extract", fake_extract)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/extract-background", json={
        "text": "Jane Doe is the hero of this world.",
        "label": "Character bios",
    })
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"
    bible = c.get("/api/projects/p/story-bible").json()["data"]
    assert bible.get("logline") == "A test logline"
    chars = c.get("/api/projects/p/characters").json()
    assert any(ch["full_name"] == "Jane Doe" for ch in chars)


def test_regenerate_preview_apply_discard(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama", chapters={
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 3, "pov_character": ""},
    })
    proj = tmp_path / "p"
    draft = proj / "outputs" / "manuscript" / "chapter_001_draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("Original chapter prose here.", encoding="utf-8")

    from chapter_regenerator import ChapterRegenerator

    def fake_regenerate(self, number, *, source="draft", instructions="", dry_run=False, on_progress=None):
        preview = "Regenerated chapter prose with more polish."
        self.preview_path(number).write_text(preview, encoding="utf-8")
        self.meta_path(number).parent.mkdir(parents=True, exist_ok=True)
        self.meta_path(number).write_text(
            '{"source":"draft","original_word_count":4,"preview_word_count":6,"generated_at":"now"}',
            encoding="utf-8",
        )
        return preview, "/tmp/report.md"

    monkeypatch.setattr(ChapterRegenerator, "regenerate", fake_regenerate)
    c = _client(tmp_path)

    r = c.post("/api/projects/p/chapters/1/regenerate", json={"source": "draft"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"

    prev = c.get("/api/projects/p/chapters/1/regenerate/preview")
    assert prev.status_code == 200
    assert "Regenerated" in prev.json()["text"]

    applied = c.post("/api/projects/p/chapters/1/regenerate/apply", json={
        "text": prev.json()["text"],
    })
    assert applied.status_code == 200
    assert applied.json()["target"] == "draft"
    assert draft.read_text(encoding="utf-8") == prev.json()["text"]
    assert c.get("/api/projects/p/chapters/1/regenerate/preview").status_code == 404

    # discard path
    r2 = c.post("/api/projects/p/chapters/1/regenerate", json={"source": "draft"})
    job_id2 = r2.json()["job_id"]
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id2}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert c.delete("/api/projects/p/chapters/1/regenerate/preview").status_code == 204
    assert c.get("/api/projects/p/chapters/1/regenerate/preview").status_code == 404


def test_redraft_from_brief_preview_apply_discard(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama", chapters={
        "1": {"number": 1, "title": "One", "status": "complete", "word_count": 10, "pov_character": ""},
    })
    proj = tmp_path / "p"
    state_dir = proj / "outputs" / "state"
    state = json.loads((state_dir / "story_state.json").read_text(encoding="utf-8"))
    state["chapter_briefs"] = {
        "1": {
            "chapter_number": 1,
            "pov_character_id": "char_x",
            "pov_mode": "third_limited",
            "active_character_ids": [],
            "active_node_ids": [],
            "required_beats": ["Open on the vault"],
            "landed_beats": [],
            "continuity_notes": "",
            "ending_hook": "",
        },
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")

    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    draft = ms / "chapter_001_draft.md"
    revised = ms / "chapter_001_revised.md"
    final = ms / "chapter_001_final.md"
    draft.write_text("Original draft prose.", encoding="utf-8")
    revised.write_text("Original revised prose.", encoding="utf-8")
    final.write_text("Original final prose.", encoding="utf-8")

    from chapter_brief_redrafter import ChapterBriefRedrafter

    def fake_redraft(self, number, *, source="final", mode="align", instructions="", dry_run=False, on_progress=None):
        preview = "Redrafted chapter aligned to brief."
        self.preview_path(number).write_text(preview, encoding="utf-8")
        self.meta_path(number).parent.mkdir(parents=True, exist_ok=True)
        self.meta_path(number).write_text(
            json.dumps({
                "source": source,
                "mode": mode,
                "original_word_count": 3,
                "preview_word_count": 6,
                "generated_at": "now",
                "instructions": instructions,
            }),
            encoding="utf-8",
        )
        return preview, "/tmp/redraft_report.md"

    monkeypatch.setattr(ChapterBriefRedrafter, "redraft", fake_redraft)
    c = _client(tmp_path)

    r = c.post("/api/projects/p/chapters/1/redraft-from-brief", json={"source": "final", "mode": "align"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"

    prev = c.get("/api/projects/p/chapters/1/redraft-from-brief/preview")
    assert prev.status_code == 200
    body = prev.json()
    assert "Redrafted" in body["text"]
    assert body["mode"] == "align"
    assert body["source"] == "final"

    applied = c.post("/api/projects/p/chapters/1/redraft-from-brief/apply", json={
        "text": body["text"],
    })
    assert applied.status_code == 200
    assert applied.json()["target"] == "draft"
    assert draft.read_text(encoding="utf-8") == body["text"]
    assert revised.read_text(encoding="utf-8") == "Original revised prose."
    assert final.read_text(encoding="utf-8") == "Original final prose."
    assert c.get("/api/projects/p/chapters/1/redraft-from-brief/preview").status_code == 404

    r2 = c.post("/api/projects/p/chapters/1/redraft-from-brief", json={"source": "final"})
    job_id2 = r2.json()["job_id"]
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id2}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert c.delete("/api/projects/p/chapters/1/redraft-from-brief/preview").status_code == 204
    assert c.get("/api/projects/p/chapters/1/redraft-from-brief/preview").status_code == 404


def test_redraft_from_brief_requires_brief(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama", chapters={
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 3, "pov_character": ""},
    })
    proj = tmp_path / "p"
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_001_final.md").write_text("Final prose here.", encoding="utf-8")

    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/redraft-from-brief", json={"source": "final"})
    assert r.status_code == 400
    assert "brief" in r.json()["detail"].lower()


def test_manual_merge_unrelated_names(tmp_path):
    """Manual merge API works when heuristic scan finds no group (different surnames)."""
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_sam_rivera": {
                "id": "char_sam_rivera", "full_name": "Sam Rivera", "role": "minor",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
            "char_sam_ortiz": {
                "id": "char_sam_ortiz", "full_name": "Sam Ortiz (deceased)", "role": "minor",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
        },
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)
    assert c.get("/api/projects/p/duplicates").json()["characters"] == []

    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "character",
        "keep_id": "char_sam_rivera",
        "merge_ids": ["char_sam_ortiz"],
    })
    assert r.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1
    detail = c.get("/api/projects/p/characters/char_sam_rivera").json()
    assert detail["full_name"] == "Sam Ortiz (deceased)"
    assert "Sam Rivera" in detail["aliases"]


def test_duplicates_scan_and_merge(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_nora_blake": {
                "id": "char_nora_blake", "full_name": "Nora Blake", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [],
            },
            "char_nora": {
                "id": "char_nora", "full_name": "Nora", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [],
            },
        },
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)

    dup = c.get("/api/projects/p/duplicates")
    assert dup.status_code == 200
    body = dup.json()
    assert len(body["characters"]) >= 1

    group = body["characters"][0]
    keep = group["suggested_keep_id"]
    merge_ids = [m["id"] for m in group["members"] if m["id"] != keep]
    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "character",
        "keep_id": keep,
        "merge_ids": merge_ids,
    })
    assert r.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1

    auto = c.post("/api/projects/p/duplicates/auto-resolve")
    assert auto.status_code == 200


def test_merge_with_label_override_and_ai_prune(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_a": {
                "id": "char_a", "full_name": "Nora Blake", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
            "char_b": {
                "id": "char_b", "full_name": "Maya", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
        },
        "plot_threads": {
            "plot_a": {
                "id": "plot_a", "name": "Main Quest", "description": "", "thread_type": "main",
                "status": "active", "priority": 5, "sort_order": 0, "subplots": [],
            },
            "plot_b": {
                "id": "plot_b", "name": "The Quest", "description": "", "thread_type": "main",
                "status": "active", "priority": 3, "sort_order": 1, "subplots": [],
            },
        },
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True, exist_ok=True)
    suggestions = {
        "characters": [{
            "kind": "character",
            "confidence": 0.9,
            "reason": "AI",
            "suggested_keep_id": "char_a",
            "members": [
                {"id": "char_a", "label": "Nora Blake", "role": "supporting"},
                {"id": "char_b", "label": "Maya", "role": "supporting"},
            ],
        }],
        "plot_threads": [{
            "kind": "plot_thread",
            "confidence": 0.88,
            "reason": "AI",
            "suggested_keep_id": "plot_a",
            "members": [
                {"id": "plot_a", "label": "Main Quest", "thread_type": "main"},
                {"id": "plot_b", "label": "The Quest", "thread_type": "main"},
            ],
        }],
    }
    (dedup_dir / "suggestions.json").write_text(json.dumps(suggestions), encoding="utf-8")
    c = _client(tmp_path)

    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "plot_thread",
        "keep_id": "plot_a",
        "merge_ids": ["plot_b"],
        "label_override": "The Main Quest Arc",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["keep_label"] == "The Main Quest Arc"

    ai = c.get("/api/projects/p/duplicates?ai=true")
    assert ai.status_code == 200
    assert ai.json()["plot_threads"] == []
    assert len(ai.json()["characters"]) == 1

    plots = c.get("/api/projects/p/plot-threads").json()
    assert len(plots) == 1
    assert plots[0]["name"] == "The Main Quest Arc"


def test_bible_merge_prunes_ai_suggestions(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {},
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {
            "setting_summary": [
                "Harbor Tower is a four-story brick-facade building with an elevator.",
                "Building has four floors above lobby, accessed by elevator.",
            ],
        },
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True, exist_ok=True)
    ai_group = {
        "section": "setting_summary",
        "confidence": 0.95,
        "reason": "Same building description",
        "suggested_keep_index": 0,
        "members": [
            {
                "id": "setting_summary:0",
                "section": "setting_summary",
                "index": 0,
                "label": state["story_bible"]["setting_summary"][0],
            },
            {
                "id": "setting_summary:1",
                "section": "setting_summary",
                "index": 1,
                "label": state["story_bible"]["setting_summary"][1],
            },
        ],
    }
    (dedup_dir / "bible_suggestions.json").write_text(
        json.dumps({"groups": [ai_group]}), encoding="utf-8",
    )
    c = _client(tmp_path)

    before = c.get("/api/projects/p/story-bible/duplicates?ai=true")
    assert before.status_code == 200
    assert len(before.json()["groups"]) == 1

    merged = c.post("/api/projects/p/story-bible/duplicates/merge", json={
        "keep_section": "setting_summary",
        "keep_index": 0,
        "members": ai_group["members"],
        "text_override": "Harbor Tower: four stories, elevator, mirrored lobby.",
    })
    assert merged.status_code == 200
    assert merged.json()["removed"] >= 1
    assert "Harbor Tower" in merged.json()["keep_text"]

    after = c.get("/api/projects/p/story-bible/duplicates?ai=true")
    assert after.status_code == 200
    assert after.json()["groups"] == []

    bible = c.get("/api/projects/p/story-bible").json()["data"]["setting_summary"]
    assert len(bible) == 1
    assert "mirrored lobby" in bible[0]


def test_dedup_status_endpoints(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)

    empty_bible = c.get("/api/projects/p/story-bible/duplicates/status")
    assert empty_bible.status_code == 200
    assert empty_bible.json() == {"ai_suggestions_ready": False, "ai_group_count": 0}

    empty_entity = c.get("/api/projects/p/duplicates/status")
    assert empty_entity.status_code == 200
    body = empty_entity.json()
    assert body["ai_suggestions_ready"] is False
    assert body["ai_group_count"] == 0
    assert body["has_ai_file"] is False
    assert body["ai_scan_completed"] is False

    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "bible_suggestions.json").write_text(
        json.dumps({"groups": [{"section": "themes", "members": []}, {"section": "themes", "members": []}]}),
        encoding="utf-8",
    )
    (dedup_dir / "suggestions.json").write_text(
        json.dumps({"characters": [{"kind": "character", "members": []}], "plot_threads": []}),
        encoding="utf-8",
    )

    bible_status = c.get("/api/projects/p/story-bible/duplicates/status")
    assert bible_status.json()["ai_suggestions_ready"] is True
    assert bible_status.json()["ai_group_count"] == 2

    entity_status = c.get("/api/projects/p/duplicates/status")
    assert entity_status.json()["ai_suggestions_ready"] is True
    assert entity_status.json()["ai_group_count"] == 1
    assert entity_status.json()["has_ai_file"] is True


def test_entity_ai_scan_empty_results_load_as_ai(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "suggestions.json").write_text(
        json.dumps({
            "scanned_at": "2026-06-29T12:00:00+00:00",
            "characters": [],
            "plot_threads": [],
        }),
        encoding="utf-8",
    )
    c = _client(tmp_path)

    status = c.get("/api/projects/p/duplicates/status").json()
    assert status["has_ai_file"] is True
    assert status["ai_scan_completed"] is True
    assert status["ai_suggestions_ready"] is False

    report = c.get("/api/projects/p/duplicates?ai=true").json()
    assert report["source"] == "ai"
    assert report["ai_scan_completed"] is True
    assert report["characters"] == []
    assert report["plot_threads"] == []


def test_project_backup_lifecycle(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_a": {
            "id": "char_a", "full_name": "Alice", "role": "protagonist",
            "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
        }
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    assert c.get("/api/projects/p/backups").status_code == 200
    assert c.post("/api/projects/p/backups/quick-save").status_code == 200

    data["characters"]["char_b"] = {
        "id": "char_b", "full_name": "Bob", "role": "supporting",
        "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
    }
    sf.write_text(json.dumps(data), encoding="utf-8")

    r = c.post("/api/projects/p/backups", json={"label": "With Alice only"})
    assert r.status_code == 201
    backup_id = r.json()["id"]

    listed = c.get("/api/projects/p/backups").json()
    assert any(b["id"] == backup_id for b in listed["named"])
    assert listed["quick"]["current"] is not None

    restore = c.post("/api/projects/p/backups/quick-restore")
    assert restore.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1
    assert chars[0]["full_name"] == "Alice"

    undo = c.post("/api/projects/p/backups/undo-restore")
    assert undo.status_code == 200
    chars2 = c.get("/api/projects/p/characters").json()
    assert len(chars2) == 2

    assert c.delete(f"/api/projects/p/backups/{backup_id}").status_code == 204
    assert c.get("/api/projects/p/backups").json()["named"] == []


def test_generate_outline_lifecycle(tmp_path, monkeypatch):
    from chapter_outline_generator import ChapterOutlineGenerator

    _seed_with_chapter(tmp_path, draft="Chapter prose about Jordan and the archive.")
    proj = tmp_path / "p" / "outputs"
    outline = proj / "chapter_001_outline.md"

    def fake_generate(self, number, *, source="draft", instructions="", dry_run=False, on_progress=None):
        preview = "# Chapter 1: The Archive\n\n## Beats\n1. **Opening** — Jordan enters."
        self.preview_path(number).parent.mkdir(parents=True, exist_ok=True)
        self.preview_path(number).write_text(preview, encoding="utf-8")
        self.meta_path(number).write_text(
            '{"source":"draft","original_word_count":6,"preview_word_count":8,"generated_at":"now"}',
            encoding="utf-8",
        )
        return preview, "/tmp/report.md"

    monkeypatch.setattr(ChapterOutlineGenerator, "generate", fake_generate)
    c = _client(tmp_path)

    r = c.post("/api/projects/p/chapters/1/generate-outline", json={"source": "draft"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"

    prev = c.get("/api/projects/p/chapters/1/generate-outline/preview")
    assert prev.status_code == 200
    assert "Beats" in prev.json()["text"]

    applied = c.post("/api/projects/p/chapters/1/generate-outline/apply", json={
        "text": prev.json()["text"],
    })
    assert applied.status_code == 200
    assert applied.json()["target"] == "outline"
    assert outline.exists()
    assert "Jordan" in outline.read_text(encoding="utf-8")
    assert c.get("/api/projects/p/chapters/1/generate-outline/preview").status_code == 404


def test_generate_outline_from_notes_requires_instructions(tmp_path):
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/generate-outline", json={"source": "notes"})
    assert r.status_code == 400


def test_batch_extract_outlines_api(tmp_path, monkeypatch):
    _seed_with_chapter(tmp_path, draft="Chapter prose about Jordan and the archive.")
    import batch_extract as batch_mod

    def fake_batch(project_path, **kwargs):
        from chapter_outline_generator import ChapterOutlineGenerator

        gen = ChapterOutlineGenerator(project_path)
        gen.preview_path(1).parent.mkdir(parents=True, exist_ok=True)
        gen.preview_path(1).write_text("# Outline preview", encoding="utf-8")

    monkeypatch.setattr(batch_mod, "batch_extract_outlines", fake_batch)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/batch/extract-outlines", json={"source": "best"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"


def test_plot_panel_issues_api(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_a": {
            "id": "plot_a", "name": "Main arc", "description": "", "thread_type": "main",
            "status": "active", "priority": 5, "sort_order": 0,
            "subplots": ["Heist planning: crew meets"],
        },
        "plot_b": {
            "id": "plot_b", "name": "B plot", "description": "", "thread_type": "main",
            "status": "active", "priority": 3, "sort_order": 1,
            "subplots": ["Heist planning: the crew gathers"],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    report = c.get("/api/projects/p/plot-threads/panel-issues")
    assert report.status_code == 200
    issues = report.json()["issues"]
    assert len(issues) >= 1
    issue_id = issues[0]["issue_id"]
    resolved = c.post(
        "/api/projects/p/plot-threads/panel-issues/resolve",
        json={"issue_id": issue_id},
    )
    assert resolved.status_code == 200
    assert resolved.json()["log"]
