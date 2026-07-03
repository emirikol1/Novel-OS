"""Phase 2: chapter brief prompt integration (synthetic projects only)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_outline_generator import ChapterOutlineGenerator  # noqa: E402
from orchestrator import NovelOrchestrator  # noqa: E402
from api.services import ProjectService  # noqa: E402
from state_manager import Character, PlotThread, StoryState, initialize_project  # noqa: E402
from story_graph import (  # noqa: E402
    ChapterBrief,
    StoryGraphEdge,
    StoryGraphNode,
    character_display_name,
    format_chapter_brief_prompt_context,
    migrate_plot_threads_to_graph,
)


def _seed_brief_project(tmp_path):
    """Synthetic project with characters, plot thread, graph node, and chapter brief."""
    proj = tmp_path / "brief_novel"
    initialize_project(str(proj), "Brief Test Novel", "Thriller")
    state = StoryState(str(proj))
    state.add_character(
        Character(
            id="char_a",
            full_name="Alice",
            role="protagonist",
            current_location="Vault antechamber",
            emotional_state="anxious",
            arc_stage="middle",
            arc_progress=40,
        ),
    )
    state.add_character(
        Character(
            id="char_b",
            full_name="Bob",
            role="antagonist",
            current_location="Security office",
            emotional_state="suspicious",
        ),
    )
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="The Heist",
            description="Steal the vault key",
            thread_type="main",
            status="active",
            priority=5,
            related_characters=["char_a", "char_b"],
        ),
    )
    migrate_plot_threads_to_graph(state)
    main_node_id = next(
        nid for nid, n in state.story_graph_nodes.items() if n.kind == "main"
    )
    state.set_chapter_brief(
        ChapterBrief(
            chapter_number=3,
            pov_character_id="char_a",
            pov_mode="third_limited",
            active_character_ids=["char_a", "char_b"],
            active_node_ids=[main_node_id],
            required_beats=["Alarm fails", "Bob confronts Alice"],
            continuity_notes="Alice still has the keycard.",
            ending_hook="The vault door opens.",
        ),
    )
    state.create_chapter(3)
    state.save_state()
    return proj, main_node_id


def test_format_chapter_brief_prompt_context_includes_selections(tmp_path):
    proj, main_node_id = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None

    ctx = format_chapter_brief_prompt_context(state, brief)

    assert "## Chapter Brief" in ctx
    assert "### Writing Style" in ctx
    assert "Third person limited" in ctx
    assert "**Alice**" in ctx
    assert "**Bob**" in ctx
    assert "Vault antechamber" in ctx
    assert "The Heist" in ctx
    assert main_node_id in ctx or "Steal the vault key" in ctx
    assert "Alarm fails" in ctx
    assert "Bob confronts Alice" in ctx
    assert "keycard" in ctx
    assert "vault door opens" in ctx.lower()


def test_format_chapter_brief_prompt_context_includes_landed_beats(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.landed_beats = ["Vault alarm triggered", "Bob reveals betrayal"]
    state.set_chapter_brief(brief)
    state.save_state()

    ctx = format_chapter_brief_prompt_context(state, brief)

    assert "### Chapter Beats" in ctx
    assert "**[landed]** Vault alarm triggered" in ctx
    assert "**[landed]** Bob reveals betrayal" in ctx
    assert "**[planned]** Alarm fails" in ctx
    assert "### Required Beats" not in ctx
    assert "### Landed Beats From Existing Text" not in ctx


def test_format_chapter_brief_prompt_context_mentioned_compact(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.mentioned_character_ids = ["char_a", "char_b"]
    state.set_chapter_brief(brief)
    state.save_state()

    ctx = format_chapter_brief_prompt_context(state, brief)

    assert "### Mentioned Characters" in ctx
    assert "**Alice** (protagonist)" in ctx
    assert "**Bob** (antagonist)" in ctx


def test_format_chapter_brief_prompt_context_chapter_beats_replaces_legacy(tmp_path):
    from story_graph import ChapterBeat

    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    state.set_chapter_beats(
        3,
        [
            ChapterBeat(id="beat_3_001", title="Alarm fails", status="planned", sort_order=0),
            ChapterBeat(id="beat_3_002", title="Vault alarm triggered", status="landed", sort_order=1),
        ],
    )
    state.save_state()

    ctx = format_chapter_brief_prompt_context(state, brief)

    assert "### Chapter Beats" in ctx
    assert "**[planned]** Alarm fails" in ctx
    assert "**[landed]** Vault alarm triggered" in ctx
    assert "### Required Beats" not in ctx
    assert "### Landed Beats From Existing Text" not in ctx


def test_format_chapter_brief_warns_on_missing_ids(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = ChapterBrief(
        chapter_number=3,
        pov_character_id="missing_pov",
        active_character_ids=["char_a", "ghost_char"],
        active_node_ids=["ghost_node"],
        required_beats=["One beat"],
    )

    ctx = format_chapter_brief_prompt_context(state, brief)

    assert "[unknown character id: ghost_char]" in ctx
    assert "[unknown character id: missing_pov]" in ctx
    assert "[unknown story node id: ghost_node]" in ctx
    assert "One beat" in ctx


def test_generate_chapter_brief_from_sample_outline(tmp_path):
    proj, main_node_id = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    chapter = state.get_chapter(3)
    chapter.pov_character = "Alice"
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault to advance The Heist.\n"
        "- Bob reveals the keycard was switched.\n"
        "- Alice decides to open the vault anyway.",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert brief.pov_character_id == "char_a"
    assert brief.pov_mode == "third_limited"
    assert "char_a" in brief.mentioned_character_ids
    assert "char_b" in brief.mentioned_character_ids
    assert "char_a" in brief.active_character_ids
    assert main_node_id in brief.active_node_ids
    assert brief.required_beats == []
    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert saved_beats
    assert "Alice enters the vault" in saved_beats[0].title
    assert "Generated from chapter 3" in brief.continuity_notes


def test_generate_chapter_brief_skips_pov_metadata_beats(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "**POV:** Alice | **Source:** reverse-engineered from draft\n"
        "- Point of view: third person limited\n"
        "- POV: Alice\n"
        "- Alice enters the vault to advance The Heist.\n"
        "- Bob reveals the keycard was switched.\n",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert brief.pov_character_id == "char_a"
    assert all("pov" not in beat.lower() or "vault" in beat.lower() for beat in brief.required_beats)
    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert saved_beats
    assert "Alice enters the vault" in saved_beats[0].title
    assert not any(beat.lower().startswith("pov:") for beat in [b.title for b in saved_beats])
    assert not any(beat.lower().startswith("point of view:") for beat in [b.title for b in saved_beats])


def test_generate_chapter_brief_preserves_landed_beats(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.landed_beats = ["Vault alarm triggered", "Bob reveals betrayal"]
    state.set_chapter_brief(brief)
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault to advance The Heist.\n"
        "- Bob reveals the keycard was switched.\n"
        "- Alice decides to open the vault anyway.",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert generated.landed_beats == ["Vault alarm triggered", "Bob reveals betrayal"]
    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert any(b.status == "landed" and "Vault alarm triggered" in b.title for b in saved_beats)
    assert any("Alice enters the vault" in b.title for b in saved_beats)


def test_generate_chapter_briefs_bulk_saves_missing_only(tmp_path):
    proj, main_node_id = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    state.create_chapter(4)
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice advances The Heist with Bob.\n- The vault opens on a new danger.",
        encoding="utf-8",
    )

    result = ProjectService(tmp_path).generate_chapter_briefs("brief_novel")

    assert [b.chapter_number for b in result.generated] == [3]
    assert main_node_id in result.generated[0].active_node_ids
    assert result.skipped[0]["chapter"] == 4
    saved = StoryState(str(proj)).get_chapter_brief(3)
    assert saved is not None
    assert main_node_id in saved.active_node_ids


def test_plan_chapter_without_brief_keeps_plot_threads(tmp_path):
    proj = tmp_path / "plain"
    initialize_project(str(proj), "Plain Novel", "Drama")
    state = StoryState(str(proj))
    state.add_plot_thread(
        PlotThread(
            id="plot_a",
            name="Rescue Mission",
            description="Extract the hostages",
            thread_type="main",
            status="active",
        ),
    )
    state.save_state()

    orch = NovelOrchestrator(str(proj))
    orch.plan_chapter(1, dry_run=True)

    prompt_path = proj / "outputs" / "chapter_001_prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8")

    assert "ARCHITECT TASK" in prompt
    assert "### Active Plot Threads" in prompt
    assert "Rescue Mission" in prompt
    assert "## Chapter Brief" not in prompt


def test_plan_chapter_with_brief_includes_brief_context(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)

    orch = NovelOrchestrator(str(proj))
    orch.plan_chapter(3, dry_run=True)

    prompt = (proj / "outputs" / "chapter_003_prompt.md").read_text(encoding="utf-8")

    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "### Active Plot Threads" in prompt
    assert "The Heist" in prompt


def test_plan_chapter_applies_brief_pov_when_unset(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.pov_character = ""
    state.save_state()

    orch = NovelOrchestrator(str(proj))
    orch.plan_chapter(3, dry_run=True)

    assert orch.state.get_chapter(3).pov_character == "Alice"


def test_explicit_pov_beats_brief_pov_in_plan_chapter(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)

    orch = NovelOrchestrator(str(proj))
    orch.plan_chapter(3, pov="Bob", dry_run=True)

    chapter = orch.state.get_chapter(3)
    assert chapter is not None
    assert chapter.pov_character == "Bob"

    prompt = (proj / "outputs" / "chapter_003_prompt.md").read_text(encoding="utf-8")
    assert "do **not** include POV or" in prompt
    assert "## Chapter Brief" in prompt


def test_notes_outline_prompt_includes_brief_context(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)

    gen = ChapterOutlineGenerator(str(proj))
    _, path = gen.generate(
        3,
        source="notes",
        instructions="Focus on the alarm sequence and Bob's suspicion.",
        dry_run=True,
    )

    prompt = Path(path).read_text(encoding="utf-8")

    assert "OUTLINE FROM AUTHOR NOTES" in prompt
    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "keycard" in prompt
    assert "alarm sequence" in prompt


def test_notes_outline_applies_brief_pov_when_unset(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.pov_character = ""
    state.save_state()

    gen = ChapterOutlineGenerator(str(proj))
    gen.generate(3, source="notes", instructions="Open on Alice in the antechamber.", dry_run=True)

    reloaded = StoryState(str(proj))
    ch = reloaded.get_chapter(3)
    assert ch is not None
    assert ch.pov_character == "Alice"


def test_scribe_fallback_includes_brief_when_no_outline(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)

    orch = NovelOrchestrator(str(proj))
    orch.write_chapter(3, dry_run=True)

    prompt = (proj / "outputs" / "chapter_003_scribe_prompt.md").read_text(encoding="utf-8")

    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "SCRIBE PROMPT" in prompt


def test_scribe_includes_brief_when_outline_exists(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    outline = proj / "outputs" / "chapter_003_outline.md"
    outline.write_text(
        "# Chapter 3: The Vault\n\n## Beats\n1. Alice enters\n2. Alarm\n",
        encoding="utf-8",
    )

    orch = NovelOrchestrator(str(proj))
    orch.write_chapter(3, dry_run=True)

    prompt = (proj / "outputs" / "chapter_003_scribe_prompt.md").read_text(encoding="utf-8")

    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "## Beat sheet" in prompt
    assert "Alice enters" in prompt
    assert "SCRIBE PROMPT" in prompt


def test_character_display_name_fallback(tmp_path):
    proj = tmp_path / "empty"
    initialize_project(str(proj), "Empty", "Drama")
    state = StoryState(str(proj))
    assert character_display_name(state, "nope").startswith("[unknown")


def test_format_chapter_brief_caps_graph_nodes(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    for i in range(12):
        nid = f"extra_node_{i}"
        state.story_graph_nodes[nid] = StoryGraphNode(
            id=nid,
            kind="subplot",
            title=f"Side plot {i}",
            description=f"Thread {i}",
            priority=i,
        )
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.active_node_ids = list(state.story_graph_nodes.keys())
    state.set_chapter_brief(brief)
    state.save_state()

    from context_resolver import ContextBudget

    ctx = format_chapter_brief_prompt_context(
        state,
        brief,
        budget=ContextBudget(max_selected_nodes=3, max_related_nodes=1, max_items=4, max_chars=500),
    )

    assert "### Active Story Nodes" in ctx
    assert "Omitted" in ctx
    graph_section = ctx.split("### Active Story Nodes", 1)[1].split("###", 1)[0]
    assert graph_section.count("- **") <= 4


def test_generate_chapter_brief_preserves_hand_edited_cast(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.mentioned_character_ids = ["char_a"]
    brief.active_character_ids = ["char_a"]
    state.set_chapter_brief(brief)
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault.\n- Bob reveals the keycard was switched.\n",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert "char_a" in generated.mentioned_character_ids
    assert "char_b" in generated.mentioned_character_ids
    assert "char_a" in generated.active_character_ids


def test_guardian_validation_prompt_includes_brief_context(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.status = "edited"
    state.save_state()
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_003_revised.md").write_text("Alice crept toward the vault.", encoding="utf-8")

    orch = NovelOrchestrator(str(proj))
    orch.validate_chapter(3, dry_run=True)

    prompt = (proj / "outputs" / "feedback" / "chapter_003_validation_prompt.md").read_text(
        encoding="utf-8",
    )
    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt


def test_edit_prompt_includes_brief_context(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.status = "drafted"
    chapter.word_count = 120
    state.save_state()
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True, exist_ok=True)
    (ms / "chapter_003_draft.md").write_text("Alice crept toward the vault.", encoding="utf-8")

    orch = NovelOrchestrator(str(proj))
    orch.edit_chapter(3, dry_run=True)

    prompt = (proj / "outputs" / "feedback" / "chapter_003_edit_prompt.md").read_text(encoding="utf-8")
    assert "## Chapter Brief" in prompt
    assert "Alarm fails" in prompt
    assert "Alice crept" in prompt


def test_save_brief_normalizes_active_subset_mentioned(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app

    proj, _ = _seed_brief_project(tmp_path)
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    c = TestClient(create_app(projects_root=tmp_path, db_url=db_url))

    saved = c.put(
        "/api/projects/brief_novel/chapters/3/brief",
        json={
            "active_character_ids": ["char_a", "char_b"],
            "mentioned_character_ids": ["char_a"],
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert set(body["active_character_ids"]) == {"char_a", "char_b"}
    assert set(body["mentioned_character_ids"]) == {"char_a", "char_b"}


def test_save_brief_rejects_out_of_range_active_nodes(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app

    proj, main_node_id = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.story_graph_nodes[main_node_id].start_chapter = 10
    state.story_graph_nodes[main_node_id].resolution_chapter = 12
    state.save_state()

    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    c = TestClient(create_app(projects_root=tmp_path, db_url=db_url))

    resp = c.put(
        "/api/projects/brief_novel/chapters/3/brief",
        json={
            "mentioned_character_ids": ["char_a"],
            "active_character_ids": ["char_a"],
            "active_node_ids": [main_node_id],
        },
    )
    assert resp.status_code == 400
    assert "not eligible" in resp.json()["detail"].lower()


def test_save_brief_syncs_chapter_pins(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app

    proj, main_node_id = _seed_brief_project(tmp_path)
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    c = TestClient(create_app(projects_root=tmp_path, db_url=db_url))

    saved = c.put(
        "/api/projects/brief_novel/chapters/3/brief",
        json={
            "mentioned_character_ids": ["char_a"],
            "active_character_ids": ["char_a"],
            "active_node_ids": [main_node_id],
        },
    )
    assert saved.status_code == 200

    node = next(
        n for n in c.get("/api/projects/brief_novel/story-graph/nodes").json()
        if n["id"] == main_node_id
    )
    assert 3 in node["chapter_pins"]

