"""Landed beat extraction — parser, service, and API (synthetic data only)."""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from api.main import create_app  # noqa: E402
from chapter_beat_extractor import (  # noqa: E402
    ChapterBeatExtractor,
    parse_chapter_beat_candidates,
)
from state_manager import Character, StoryState, initialize_project  # noqa: E402
from story_graph import ChapterBrief  # noqa: E402


SAMPLE_ARCHIVIST_RESPONSE = """
Brief note: the chapter escalates from setup to confrontation.

[CHAPTER_BEAT_CANDIDATES]
1. setup | Alex enters the warehouse | Establishes the scene and stakes | Alex | Advances the rescue thread
2. confrontation | Guard blocks the exit | Raises immediate danger | Alex, Guard | Forces a decision
3. revelation | Hidden map falls from the crate | Reveals the next location | Alex | Sets up chapter four
[/CHAPTER_BEAT_CANDIDATES]
"""


def _client(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed_beat_project(tmp_path):
    proj = tmp_path / "beat_novel"
    initialize_project(str(proj), "Beat Test Novel", "Thriller")
    state = StoryState(str(proj))
    state.add_character(
        Character(id="char_a", full_name="Alex", role="protagonist"),
    )
    state.set_chapter_brief(
        ChapterBrief(
            chapter_number=2,
            required_beats=["Reach the warehouse", "Find the map"],
            landed_beats=["Old landed beat"],
        ),
    )
    state.create_chapter(2)
    state.save_state()
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_002_draft.md").write_text(
        "Alex slipped into the warehouse before dawn. A guard appeared at the exit. "
        "A hidden map fell from an open crate.",
        encoding="utf-8",
    )
    return proj


def test_chapter_brief_from_dict_defaults_landed_beats():
    brief = ChapterBrief.from_dict({"chapter_number": 1, "required_beats": ["Plan the heist"]})
    assert brief.landed_beats == []
    assert brief.required_beats == ["Plan the heist"]


def test_parse_chapter_beat_candidates_full_format():
    candidates = parse_chapter_beat_candidates(SAMPLE_ARCHIVIST_RESPONSE)
    assert len(candidates) == 3
    assert candidates[0].rank == 1
    assert candidates[0].category == "setup"
    assert candidates[0].beat == "Alex enters the warehouse"
    assert candidates[0].significance == "Establishes the scene and stakes"
    assert candidates[0].involved_characters == ["Alex"]
    assert candidates[0].story_relevance == "Advances the rescue thread"


def test_parse_chapter_beat_candidates_defensive_minimal_lines():
    text = """
[CHAPTER_BEAT_CANDIDATES]
- Alex finds the map
2. beat only | second field
turning_point | major event | it changes everything
[/CHAPTER_BEAT_CANDIDATES]
"""
    candidates = parse_chapter_beat_candidates(text)
    assert len(candidates) == 3
    assert candidates[0].beat == "Alex finds the map"
    assert candidates[1].rank == 2
    assert candidates[1].beat == "beat only"
    assert candidates[2].category == "turning_point"


def test_parse_chapter_beat_candidates_missing_block():
    assert parse_chapter_beat_candidates("No structured block here.") == []


def test_resolve_source_best_prefers_final(tmp_path):
    proj = _seed_beat_project(tmp_path)
    ms = proj / "outputs" / "manuscript"
    (ms / "chapter_002_final.md").write_text("Final prose only.", encoding="utf-8")

    extractor = ChapterBeatExtractor(str(proj))
    source, text = extractor.resolve_source_text(2, "best")
    assert source == "final"
    assert text == "Final prose only."


def test_resolve_source_explicit_requires_stage(tmp_path):
    proj = _seed_beat_project(tmp_path)
    extractor = ChapterBeatExtractor(str(proj))

    _, text = extractor.resolve_source_text(2, "draft")
    assert "warehouse" in text

    with pytest.raises(FileNotFoundError):
        extractor.resolve_source_text(2, "final")


@patch("chapter_beat_extractor.LLMClient.run_agent")
def test_generate_beat_candidates_api(mock_run, tmp_path):
    mock_run.return_value = SAMPLE_ARCHIVIST_RESPONSE
    _seed_beat_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates",
        json={"source": "draft", "count": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapter_number"] == 2
    assert body["source_used"] == "draft"
    assert len(body["candidates"]) == 3
    assert body["candidates"][0]["beat"] == "Alex enters the warehouse"


@patch("chapter_beat_extractor.LLMClient.run_agent")
def test_generate_beat_candidates_async_saves_preview(mock_run, tmp_path):
    mock_run.return_value = SAMPLE_ARCHIVIST_RESPONSE
    _seed_beat_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates/async",
        json={"source": "draft", "count": 3},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    for _ in range(20):
        status = c.get(f"/api/jobs/{job_id}").json()
        if status["status"] != "running":
            break
        time.sleep(0.05)
    assert status["status"] == "done"

    preview = c.get("/api/projects/beat_novel/chapters/2/brief/beat-candidates/preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["source_used"] == "draft"
    assert body["candidates"][0]["beat"] == "Alex enters the warehouse"


def test_apply_beat_candidates_preserves_required_beats(tmp_path):
    _seed_beat_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates/apply",
        json={
            "selected_beats": ["Alex enters the warehouse", "Guard blocks the exit"],
            "mode": "append",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["required_beats"] == ["Reach the warehouse", "Find the map"]
    assert "Alex enters the warehouse" in body["landed_beats"]
    assert "Guard blocks the exit" in body["landed_beats"]
    assert "Old landed beat" in body["landed_beats"]

    sf = tmp_path / "beat_novel" / "outputs" / "state" / "story_state.json"
    disk = json.loads(sf.read_text(encoding="utf-8"))
    brief = disk["chapter_briefs"]["2"]
    assert brief["required_beats"] == ["Reach the warehouse", "Find the map"]
    assert "Alex enters the warehouse" in brief["landed_beats"]
    assert "2" in disk["chapter_beats"]
    landed_rows = [b for b in disk["chapter_beats"]["2"] if b["status"] == "landed"]
    assert any("Alex enters the warehouse" in b["title"] for b in landed_rows)


def test_apply_beat_candidates_dual_writes_landed_beats(tmp_path):
    _seed_beat_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates/apply",
        json={"selected_beats": ["New landed beat"], "mode": "append"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "New landed beat" in body["landed_beats"]
    disk = json.loads(
        (tmp_path / "beat_novel" / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8"),
    )
    assert any(
        b["status"] == "landed" and b["title"] == "New landed beat"
        for b in disk["chapter_beats"]["2"]
    )


def test_apply_beat_candidates_preserves_planned_beats(tmp_path):
    proj = _seed_beat_project(tmp_path)
    state = StoryState(str(proj))
    from story_graph import ChapterBeat

    state.set_chapter_beats(
        2,
        [
            ChapterBeat(id="beat_2_001", title="Reach the warehouse", status="planned"),
            ChapterBeat(id="beat_2_002", title="Old landed beat", status="landed"),
        ],
    )
    state.save_state()
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates/apply",
        json={"selected_beats": ["Alex enters the warehouse"], "mode": "append"},
    )
    assert resp.status_code == 200
    reloaded = StoryState(str(proj))
    beats = reloaded.get_chapter_beats(2)
    assert any(b.status == "planned" and b.title == "Reach the warehouse" for b in beats)
    assert any(b.status == "landed" and "Alex enters the warehouse" in b.title for b in beats)


def test_apply_beat_candidates_replace_mode(tmp_path):
    _seed_beat_project(tmp_path)
    c = _client(tmp_path)

    resp = c.post(
        "/api/projects/beat_novel/chapters/2/brief/beat-candidates/apply",
        json={"selected_beats": ["Only this beat"], "mode": "replace"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["landed_beats"] == ["Only this beat"]
    assert body["required_beats"] == ["Reach the warehouse", "Find the map"]
