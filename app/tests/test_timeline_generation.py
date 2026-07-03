"""Timeline generation tests using synthetic chapter text only."""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from api.main import create_app
from state_manager import Character, StoryState, initialize_project
from timeline_extractor import extract_timeline_candidates


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed_project(tmp_path: Path) -> Path:
    project = tmp_path / "p"
    initialize_project(str(project), "Synthetic Timeline", "Mystery")
    state = StoryState(str(project))
    state.create_chapter(1)
    state.create_chapter(2)
    state.add_character(Character(id="char_lena", full_name="Lena Vale", role="protagonist"))
    state.add_character(Character(id="char_maro", full_name="Maro", role="supporting"))
    state.save_state()
    manuscript = project / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_001_revised.md").write_text(
        "At the Glass Archive on Day 2, Lena Vale discovered the missing ledger before dawn.\n\n"
        "Maro confessed that the map was false and led Lena through the locked stacks.",
        encoding="utf-8",
    )
    return project


def test_extract_timeline_candidates_from_sample_text():
    candidates = extract_timeline_candidates(
        [(
            1,
            "revised",
            "At the Glass Archive on Day 2, Lena Vale discovered the missing ledger before dawn.",
        )],
        {"char_lena": ["Lena Vale", "Lena"]},
    )
    assert len(candidates) == 1
    event = candidates[0]
    assert event.chapter == 1
    assert event.day == 2
    assert event.time == "dawn"
    assert event.location == "Glass Archive"
    assert event.characters_present == ["char_lena"]
    assert event.significance == "turning_point"
    assert event.score > 0
    assert "turning-point" in event.reason


def test_generate_timeline_preview_and_skips_empty_chapters(tmp_path):
    _seed_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post("/api/projects/p/timeline/generate", json={"source": "best"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapters_scanned"] == [1]
    assert body["skipped_chapters"][0]["chapter"] == 2
    assert len(body["candidates"]) >= 1
    assert body["candidates"][0]["chapter"] == 1
    assert "Lena" in body["candidates"][0]["description"]
    assert "score" in body["candidates"][0]
    assert "reason" in body["candidates"][0]


def test_generate_timeline_can_scan_specific_chapters(tmp_path):
    _seed_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post("/api/projects/p/timeline/generate", json={"chapters": [1], "source": "best"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapters_scanned"] == [1]
    assert body["skipped_chapters"] == []


def test_generate_timeline_returns_ranked_alternates(tmp_path):
    project = _seed_project(tmp_path)
    (project / "outputs" / "manuscript" / "chapter_001_revised.md").write_text(
        "Lena Vale packed a satchel and waited by the door.\n\n"
        "At the Glass Archive on Day 2, Lena Vale discovered the missing ledger before dawn.\n\n"
        "Maro studied the false map in silence while rain tapped the windows.\n\n"
        "Lena confronted Maro after he confessed that the map was false.",
        encoding="utf-8",
    )
    c = _client(tmp_path)

    body = c.post(
        "/api/projects/p/timeline/generate",
        json={"chapters": [1], "source": "best", "max_events_per_chapter": 1},
    ).json()
    assert body["recommended_per_chapter"] == 1
    assert len(body["candidates"]) > 1
    scores = [candidate["score"] for candidate in body["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_apply_generated_timeline_events_creates_reviewed_events(tmp_path):
    _seed_project(tmp_path)
    c = _client(tmp_path)
    generated = c.post("/api/projects/p/timeline/generate", json={"source": "best"}).json()
    first = generated["candidates"][0]

    applied = c.post("/api/projects/p/timeline/generated-events", json={"events": [first]})
    assert applied.status_code == 200
    assert len(applied.json()["created"]) == 1

    listed = c.get("/api/projects/p/timeline").json()
    assert len(listed) == 1
    assert listed[0]["description"] == first["description"]
    assert listed[0]["characters_present"] == first["characters_present"]


def test_delete_all_timeline_events(tmp_path):
    _seed_project(tmp_path)
    c = _client(tmp_path)
    generated = c.post("/api/projects/p/timeline/generate", json={"source": "best"}).json()
    c.post("/api/projects/p/timeline/generated-events", json={"events": generated["candidates"][:2]})
    assert len(c.get("/api/projects/p/timeline").json()) == 2

    deleted = c.delete("/api/projects/p/timeline")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2
    assert c.get("/api/projects/p/timeline").json() == []


def test_generate_timeline_rejects_bad_source(tmp_path):
    _seed_project(tmp_path)
    resp = _client(tmp_path).post("/api/projects/p/timeline/generate", json={"source": "notes"})
    assert resp.status_code == 400
