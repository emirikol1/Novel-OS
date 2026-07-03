"""Tests for mention parsing, context, continuity warnings, and reviewed apply."""

import json
from pathlib import Path

import pytest

from mentions import (
    build_mention_targets,
    parse_mentions,
    resolve_mention,
    resolve_mentions_in_text,
    strip_mentions,
    text_has_mentions,
)
from mention_context import build_mention_context_block, mention_context_for_prompts
from mention_updates import (
    ALLOWED_CHARACTER_FIELDS,
    MentionSuggestionsStore,
    apply_reviewed_edits,
    suggest_conservative_updates,
)
from continuity_engine import (
    check_mention_state_conflicts,
    check_unresolved_mentions,
    run_all,
)
from state_manager import StoryState, Character, initialize_project


@pytest.fixture
def project(tmp_path):
    initialize_project(str(tmp_path), "Mention Test", "Fantasy")
    state = StoryState(str(tmp_path))
    state.add_character(Character(
        id="char_001",
        full_name="Lena Voss",
        role="protagonist",
        current_location="Harbor District",
        emotional_state="anxious",
        knowledge=["the signal exists"],
        notes="",
        last_appearance_chapter=2,
        aliases=["Lena"],
    ))
    state.add_character(Character(
        id="char_002",
        full_name="Marcus Hale",
        role="antagonist",
        emotional_state="dead",
        notes="killed in ch3",
        last_appearance_chapter=3,
    ))
    state.update_story_bible("world_rules", "No faster-than-light travel.")
    state.create_chapter(4, "The Market")
    state.chapters[4].pov_character = "Lena Voss"
    state.save_state()
    return tmp_path, state


def test_parse_and_resolve_character(project):
    _, state = project
    text = "[[char:Lena]] entered the square. [[char:Unknown Person]] waved."
    targets = build_mention_targets(state)
    parsed = parse_mentions(text)
    assert len(parsed) == 2
    assert parsed[0].kind == "char"
    resolved = resolve_mentions_in_text(text, targets)
    assert resolved[0].broken is False
    assert resolved[0].target.id == "char_001"
    assert resolved[1].broken is True


def test_strip_mentions():
    text = "Meet [[char:Lena Voss]] at [[lore:world_rules:No FTL]]."
    assert strip_mentions(text) == "Meet Lena Voss at No FTL."


def test_build_mention_context_block(project):
    _, state = project
    text = "[[char:Lena Voss]] worried about [[lore:world_rules:No faster-than-light travel.]]."
    block = build_mention_context_block(text, state)
    assert "Lena Voss" in block
    assert "Harbor District" in block
    assert "signals only" in block.lower()
    assert mention_context_for_prompts("", state) == ""


def test_unresolved_mention_warning(project):
    _, state = project
    text = "[[char:Ghost Name]] appeared."
    findings = check_unresolved_mentions(state, text, chapter_number=4)
    assert len(findings) == 1
    assert findings[0].category == "unresolved_mention"
    assert findings[0].severity == "warning"


def test_dead_character_mention_conflict(project):
    _, state = project
    text = "[[char:Marcus Hale]] stood in the doorway."
    findings = check_mention_state_conflicts(state, text, chapter_number=4)
    cats = {f.category for f in findings}
    assert "mention_dead_conflict" in cats


def test_run_all_includes_mention_checks(project):
    _, state = project
    text = "[[char:Ghost]] and [[char:Marcus Hale]] in scene."
    findings = run_all(state, as_of_chapter=4, chapter_text=text)
    categories = {f.category for f in findings}
    assert "unresolved_mention" in categories
    assert "mention_dead_conflict" in categories


def test_conservative_last_appearance_suggestion(project):
    _, state = project
    text = (
        "[[char:Lena Voss]] walked through the market.\n"
        "Lena Voss said, \"We need to move.\""
    )
    bundle = suggest_conservative_updates(state, 4, text, source="revised")
    assert len(bundle.suggestions) == 1
    s = bundle.suggestions[0]
    assert s.field == "last_appearance_chapter"
    assert s.suggested_value == 4
    assert s.explicit_presence is True


def test_conservative_last_appearance_suggestion_uses_alias_presence(project):
    _, state = project
    text = "[[char:Lena]] reaches the market gate."
    bundle = suggest_conservative_updates(state, 4, text, source="revised")

    assert len(bundle.suggestions) == 1
    assert bundle.suggestions[0].character_id == "char_001"


def test_no_last_appearance_for_bare_mention(project):
    _, state = project
    text = "They whispered about [[char:Lena Voss]] in the tavern."
    bundle = suggest_conservative_updates(state, 4, text, source="revised")
    assert bundle.suggestions == []


def test_apply_reviewed_edits(project):
    _, state = project
    edits = [
        {
            "character_id": "char_001",
            "field": "current_location",
            "value": "Market Square",
        },
        {
            "character_id": "char_001",
            "field": "last_appearance_chapter",
            "value": 4,
            "explicit_presence": True,
        },
    ]
    log = apply_reviewed_edits(state, 4, edits)
    state.save_state()
    assert len(log) == 2
    char = state.get_character("char_001")
    assert char.current_location == "Market Square"
    assert char.last_appearance_chapter == 4


def test_apply_rejects_last_appearance_without_explicit_presence(project):
    _, state = project
    with pytest.raises(ValueError, match="explicit_presence"):
        apply_reviewed_edits(state, 4, [{
            "character_id": "char_001",
            "field": "last_appearance_chapter",
            "value": 4,
            "explicit_presence": False,
        }])


def test_suggestions_store_roundtrip(project):
    path, state = project
    text = "Lena Voss said hello.\n[[char:Lena Voss]]"
    bundle = suggest_conservative_updates(state, 4, text, source="draft")
    store = MentionSuggestionsStore(path)
    store.save(bundle)
    loaded = store.load(4)
    assert loaded is not None
    assert loaded.chapter_number == 4
    assert len(loaded.suggestions) >= 1


def test_allowed_fields_set():
    assert "knowledge" in ALLOWED_CHARACTER_FIELDS
    assert "notes" in ALLOWED_CHARACTER_FIELDS
    assert "physical_description" not in ALLOWED_CHARACTER_FIELDS


def test_text_has_mentions():
    assert text_has_mentions("[[char:A]]")
    assert not text_has_mentions("plain prose")


def test_mention_api_apply(tmp_path):
    """API round-trip: analysis, suggest, apply."""
    from api.main import create_app
    from fastapi.testclient import TestClient

    initialize_project(str(tmp_path / "p"), "API Test", "Fantasy")
    state = StoryState(str(tmp_path / "p"))
    state.add_character(Character(
        id="char_001", full_name="Lena", role="protagonist", last_appearance_chapter=1,
    ))
    state.create_chapter(1, "Ch1")
    state.save_state()
    ms = tmp_path / "p" / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    text = "[[char:Lena]] walked in.\nLena said, \"Hello.\""
    (ms / "chapter_001_revised.md").write_text(text, encoding="utf-8")

    db_url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    c = TestClient(create_app(projects_root=tmp_path, db_url=db_url))

    analysis = c.get("/api/projects/p/chapters/1/mentions/analysis?source=revised")
    assert analysis.status_code == 200
    body = analysis.json()
    assert body["chapter_number"] == 1
    assert isinstance(body["warnings"], list)

    suggest = c.post("/api/projects/p/chapters/1/mentions/suggest", json={"source": "revised"})
    assert suggest.status_code == 200

    applied = c.post(
        "/api/projects/p/chapters/1/mentions/apply",
        json={
            "edits": [{
                "character_id": "char_001",
                "field": "current_location",
                "value": "Town Square",
            }],
        },
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] == 1

