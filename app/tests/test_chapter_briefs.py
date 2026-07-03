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
    ChapterBeat,
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
            relationships={"char_b": "teacher(mentor)"},
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
            continuity_notes="Alice still has the keycard.",
            ending_hook="The vault door opens.",
        ),
    )
    state.set_chapter_beats(
        3,
        [
            ChapterBeat(id="beat_3_001", title="Alarm fails", status="planned", sort_order=0),
            ChapterBeat(id="beat_3_002", title="Bob confronts Alice", status="planned", sort_order=1),
        ],
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
    assert "Bob: mentor" in ctx
    assert "teacher(mentor)" not in ctx
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
    state.set_chapter_beats(
        3,
        [
            ChapterBeat(id="beat_3_001", title="Alarm fails", status="planned", sort_order=0),
            ChapterBeat(id="beat_3_002", title="Vault alarm triggered", status="landed", sort_order=1),
            ChapterBeat(id="beat_3_003", title="Bob reveals betrayal", status="landed", sort_order=2),
        ],
    )
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


def test_scribe_prompt_omits_placeholder_context_sections(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    orch = NovelOrchestrator(str(proj))
    chapter = orch.state.get_chapter(3)
    assert chapter is not None

    prompt = orch._build_scribe_user_prompt(chapter)

    assert "### Previous Chapter Recap" not in prompt
    assert "[Summary of Chapter" not in prompt
    assert "## Chapter Goals" not in prompt
    assert "[Primary plot advancement]" not in prompt
    assert "## Scene Outline" not in prompt
    assert "### Chapter Beats" in prompt


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
    assert "char_a" in brief.active_character_ids
    assert not (set(brief.mentioned_character_ids) & set(brief.active_character_ids))
    assert main_node_id in brief.active_node_ids
    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert saved_beats
    assert any("Alice enters the vault" in beat.title for beat in saved_beats)
    assert "Generated from chapter 3" in brief.continuity_notes


def test_generate_chapter_brief_keeps_more_than_five_beats_by_default(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.set_chapter_beats(3, [])
    state.save_state()
    beat_lines = "\n".join(
        f"{i}. 4 | Alice resolves consequential turn {i}."
        for i in range(1, 8)
    )
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        f"# Chapter 3: Extended Beat List\n\n## Beats\n{beat_lines}\n",
        encoding="utf-8",
    )

    ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    generated_titles = [beat.title for beat in saved_beats]
    assert generated_titles == [
        f"Alice resolves consequential turn {i}."
        for i in range(1, 8)
    ]


def test_chapter_brief_ai_prompt_defaults_to_important_beats_not_fixed_count():
    prompt = ProjectService._ai_chapter_brief_prompt(
        3,
        title="Extended Beat List",
        source_label="draft",
        source_text="Alice decides to open the vault. Bob reveals the alarm is armed.",
        existing_outline="",
        max_beats=None,
    )

    assert "List every beat that meets the importance threshold" in prompt
    assert "arbitrary count" in prompt
    assert "importance score >= 4" in prompt
    assert "Return exactly one `[CHAPTER_BRIEF]` block" in prompt
    assert "The `## Beats` section is mandatory" in prompt
    assert "Every beat line must match `N. S | summary`" in prompt
    assert "5 = chapter-defining turn" in prompt
    assert "4 = consequential scene-level beat" in prompt
    assert "0 = not a beat" in prompt
    assert "`max_beats`/count is a cap, not a target" in prompt
    assert "List up to 5" not in prompt
    assert "turning points" in prompt
    assert "repeated micro-actions" in prompt


def test_chapter_brief_ai_prompt_describes_explicit_cap_not_target():
    prompt = ProjectService._ai_chapter_brief_prompt(
        3,
        title="Extended Beat List",
        source_label="draft",
        source_text="Alice decides to open the vault. Bob reveals the alarm is armed.",
        existing_outline="",
        max_beats=2,
        beat_importance_threshold=5,
    )

    assert "importance score >= 5" in prompt
    assert "list at most 2 beats" in prompt
    assert "`max_beats`/count is a cap, not a target" in prompt
    assert "do not add lower-importance beats to reach it" in prompt


def test_chapter_brief_scored_parser_filters_and_strips_metadata():
    beats = ProjectService._brief_beats_from_text(
        """## Beats
1. 5 | Alice follows the rabbit.
2. 3 | Alice notices a minor clock detail.
3. Alice opens the hidden door. | importance_score=4
4. Alice repeats the same hallway search. | importance_score=2
5. Alice studies the broken lock. | importance_score=high
6. Alice hears a distant footstep.
""",
        max_beats=None,
        beat_importance_threshold=4,
        require_scored_beats=True,
    )

    assert beats == [
        "Alice follows the rabbit.",
        "Alice opens the hidden door.",
    ]


def test_chapter_brief_public_domain_alice_scores_filter_and_strip_metadata():
    beats = ProjectService._brief_beats_from_text(
        """[CHAPTER_BRIEF]
POV Character: Alice
## Beats
1. 5 | Alice follows the White Rabbit and tumbles down the rabbit-hole.
2. 4 | Alice unlocks the tiny door and sees the garden beyond.
3. 3 | Alice wonders whether cats eat bats during the fall.
4. 2 | Alice notices jars and cupboards lining the well.
## Continuity Notes
- Public-domain Alice's Adventures in Wonderland Chapter 1 style example.
[/CHAPTER_BRIEF]""",
        max_beats=None,
        beat_importance_threshold=4,
        require_scored_beats=True,
    )

    assert beats == [
        "Alice follows the White Rabbit and tumbles down the rabbit-hole.",
        "Alice unlocks the tiny door and sees the garden beyond.",
    ]
    assert all("|" not in beat and "importance_score" not in beat for beat in beats)


def test_chapter_brief_scored_parser_applies_threshold_before_cap():
    beats = ProjectService._brief_beats_from_text(
        """## Beats
1. 2 | Alice studies a minor footprint.
2. 3 | Bob repeats the warning again.
3. 5 | Alice burns the escape map.
4. 4 | Bob reveals the door code.
5. 5 | Alice chooses the dangerous exit.
""",
        max_beats=2,
        beat_importance_threshold=4,
        require_scored_beats=True,
    )

    assert beats == [
        "Alice burns the escape map.",
        "Bob reveals the door code.",
    ]


def test_chapter_brief_unscored_outline_beats_still_work():
    beats = ProjectService._brief_beats_from_text(
        """## Beats
1. Alice follows the rabbit into the tunnel.
2. Bob reveals the hidden door code.
""",
        max_beats=None,
        beat_importance_threshold=4,
        require_scored_beats=False,
    )

    assert beats == [
        "Alice follows the rabbit into the tunnel.",
        "Bob reveals the hidden door code.",
    ]


def test_chapter_brief_background_job_uses_ai_without_outline(tmp_path, monkeypatch):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    state.set_chapter_beats(3, [])
    state.save_state()
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_003_draft.md").write_text(
        "Alice opens the vault while Bob watches from the security office. "
        "The siren starts before Alice can remove the keycard.",
        encoding="utf-8",
    )

    class FakeLLM:
        def run_agent(self, agent_name, prompt):
            assert agent_name == "archivist"
            assert "Chapter material (draft)" in prompt
            assert "Existing outline or notes" not in prompt
            assert "reusable prose style fingerprint" in prompt
            assert "sentence cadence" in prompt
            return """[CHAPTER_BRIEF]
POV Character: Alice
POV Mode: First person
Tone: dread
Tense: present
Prose Style: clipped suspense
Vocabulary Level: moderate
Style Notes: Keep sentences clipped around the alarm.
Target Word Count: 3200
Characters_Present:
- Alice
Characters_Mentioned:
- Bob
## Beats
1. 5 | Alice opens the vault.
2. 3 | Bob watches from the security office.
3. The siren starts before Alice can remove the keycard. | importance_score=4
4. Alice studies the blinking alarm light. | importance_score=2
5. Alice checks the vault keypad again. | importance_score=high
6. Alice hears a distant footstep.
## Continuity Notes
- The vault alarm is active.
## Ending Hook
The siren starts.
[/CHAPTER_BRIEF]"""

    monkeypatch.setattr("llm_client.LLMClient", lambda: FakeLLM())

    job = ProjectService(tmp_path).make_chapter_brief_job("brief_novel", 3, source="best")
    job()

    reloaded = StoryState(str(proj))
    saved = reloaded.get_chapter_brief(3)
    assert saved is not None
    assert saved.pov_character_id == "char_a"
    assert saved.pov_mode == "first_person"
    assert saved.tone == "dread"
    assert saved.tense == "present"
    assert saved.style_notes == "Keep sentences clipped around the alarm."
    assert "vault alarm is active" in saved.continuity_notes
    assert saved.ending_hook == "The siren starts."
    beats = reloaded.get_chapter_beats(3)
    assert [beat.title for beat in beats] == [
        "Alice opens the vault.",
        "The siren starts before Alice can remove the keycard.",
    ]


def test_chapter_brief_ai_cast_matching_dedupes_accent_variants(tmp_path, monkeypatch):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    state.add_character(Character(id="char_accented", full_name="Countess Renée", role="supporting"))
    state.add_character(Character(id="char_unaccented", full_name="Countess Renee", role="supporting"))
    state.save_state()
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_003_draft.md").write_text(
        "The countess opens the locked cabinet.",
        encoding="utf-8",
    )

    class FakeLLM:
        def run_agent(self, agent_name, prompt):
            assert agent_name == "archivist"
            return """[CHAPTER_BRIEF]
POV Character:
POV Mode:
Tone:
Tense:
Prose Style:
Vocabulary Level:
Style Notes:
Target Word Count:
Characters_Present:
- Countess Renée
Characters_Mentioned:
- Countess Renee
## Beats
1. 5 | The countess opens the locked cabinet.
## Continuity Notes
- The cabinet is open.
## Ending Hook
The cabinet is open.
[/CHAPTER_BRIEF]"""

    monkeypatch.setattr("llm_client.LLMClient", lambda: FakeLLM())

    ProjectService(tmp_path).make_chapter_brief_job("brief_novel", 3, source="best")()

    saved = StoryState(str(proj)).get_chapter_brief(3)
    assert saved is not None
    assert saved.active_character_ids == ["char_accented"]
    assert saved.mentioned_character_ids == []


def test_brief_character_name_matching_allows_minor_typos(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.add_character(Character(id="char_renee", full_name="Renee Moreau", role="supporting"))

    assert ProjectService._brief_character_id_by_name(state, "Renee Morreau") == "char_renee"


def test_generate_chapter_brief_detects_aliases_and_scene_verbs_active(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    state.add_character(
        Character(
            id="char_clara",
            full_name="Clara West",
            role="supporting",
            aliases=["Clara"],
        ),
    )
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.pov_character = "Alice"
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault.\n"
        "- Bob reveals the keycard was switched.\n"
        "- Clara reaches the alarm console.\n",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert "char_a" in brief.active_character_ids
    assert "char_b" in brief.active_character_ids
    assert "char_clara" in brief.active_character_ids
    assert not (set(brief.mentioned_character_ids) & set(brief.active_character_ids))


def test_generate_chapter_brief_extracts_full_metadata_from_outline(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.pov_character = ""
    state.style_profile.description = "Default style note should be replaced."
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "# Chapter 3: Vault Turn\n\n"
        "**POV Character:** Bob | **POV Mode:** Third person omniscient\n"
        "**Target word count:** 3,400 words\n"
        "**Tone:** dread\n"
        "**Tense:** present\n"
        "**Prose style:** lyrical suspense\n"
        "**Vocabulary level:** elevated\n"
        "**Vocabulary description:** Precise ritual language.\n"
        "**Style notes:** Use clipped fragments around alarms.\n\n"
        "## Beats\n"
        "1. Alice enters the vault to advance The Heist.\n"
        "2. Bob reveals the keycard was switched.\n\n"
        "## Continuity Notes\n"
        "- Alice still has the keycard.\n\n"
        "## Ending Hook\n"
        "The vault door opens.\n",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert brief.pov_character_id == "char_b"
    assert brief.pov_mode == "third_omniscient"
    assert brief.target_word_count == 3400
    assert brief.tone == "dread"
    assert brief.tense == "present"
    assert brief.prose_style == "lyrical suspense"
    assert brief.vocabulary_level == "elevated"
    assert "Use clipped fragments around alarms." in brief.style_notes
    assert "Precise ritual language." in brief.style_notes
    assert "Alice still has the keycard." in brief.continuity_notes
    assert brief.ending_hook == "The vault door opens."


def test_generate_chapter_brief_source_metadata_overrides_existing_style_fields(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    brief.pov_mode = "third_limited"
    brief.target_word_count = 1900
    brief.vocabulary_level = "moderate"
    brief.style_notes = "Old saved note."
    state.set_chapter_brief(brief)
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "# Chapter 3: Metadata Override\n\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        "| Narrative Perspective | First person |\n"
        "| Word Count | 2.8k words |\n"
        "| Vocabulary Level | spare |\n\n"
        "## Vocabulary Description\n"
        "- Use clipped, tactile language.\n\n"
        "## Style Notes\n"
        "- Keep the scene close and breathless.\n\n"
        "## Beats\n"
        "1. Alice enters the vault.\n",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert generated.pov_mode == "first_person"
    assert generated.target_word_count == 2800
    assert generated.vocabulary_level == "spare"
    assert "Use clipped, tactile language." in generated.style_notes
    assert "Keep the scene close and breathless." in generated.style_notes
    assert "Old saved note." not in generated.style_notes


def test_generate_chapter_brief_prefers_current_fields_and_source_word_count(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_003_draft.md").write_text(
        "Alice tests the lock.",
        encoding="utf-8",
    )
    (manuscript / "chapter_003_revised.md").write_text(
        "Alice tests the lock while Bob watches nearby.",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief(
        "brief_novel",
        3,
        current_brief={
            "tense": "present",
            "style_notes": "Keep sentences clipped around the alarm.",
            "target_word_count": 0,
        },
    )

    assert generated.tense == "present"
    assert generated.style_notes == "Keep sentences clipped around the alarm."
    assert generated.target_word_count == 8


def test_chapter_brief_background_job_preserves_current_style_notes(tmp_path, monkeypatch):
    proj, _ = _seed_brief_project(tmp_path)
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_003_draft.md").write_text(
        "Alice tests the lock while Bob watches nearby.",
        encoding="utf-8",
    )

    class FakeLLM:
        def run_agent(self, agent_name, prompt):
            assert agent_name == "archivist"
            assert "Style Notes:" in prompt
            return """[CHAPTER_BRIEF]
POV Character: Alice
POV Mode: First person
Tone: dread
Tense: past
Prose Style: clipped suspense
Vocabulary Level: moderate
Target Word Count:
Characters_Present:
- Alice
Characters_Mentioned:
- Bob
## Beats
1. Alice tests the lock.
## Continuity Notes
- Bob watches nearby.
## Ending Hook
Alice tests the lock.
[/CHAPTER_BRIEF]"""

    monkeypatch.setattr("llm_client.LLMClient", lambda: FakeLLM())

    job = ProjectService(tmp_path).make_chapter_brief_job(
        "brief_novel",
        3,
        source="best",
        current_brief={
            "tense": "present",
            "style_notes": "Keep sentences clipped around the alarm.",
            "target_word_count": 0,
        },
    )
    job()

    saved = StoryState(str(proj)).get_chapter_brief(3)
    assert saved is not None
    assert saved.tense == "present"
    assert saved.style_notes == "Keep sentences clipped around the alarm."
    assert saved.target_word_count == 8


def test_chapter_brief_background_job_falls_back_to_style_fingerprint(tmp_path, monkeypatch):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    state.save_state()
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "chapter_003_draft.md").write_text(
        "Alice moved fast. Bob waited. The alarm blinked red. Alice did not look back.",
        encoding="utf-8",
    )

    class FakeLLM:
        def run_agent(self, agent_name, prompt):
            assert agent_name == "archivist"
            return """[CHAPTER_BRIEF]
POV Character: Alice
POV Mode:
Tone:
Tense:
Prose Style:
Vocabulary Level:
Target Word Count:
Characters_Present:
- Alice
Characters_Mentioned:
- Bob
## Beats
1. Alice moves fast.
## Continuity Notes
- The alarm is active.
## Ending Hook
Alice does not look back.
[/CHAPTER_BRIEF]"""

    monkeypatch.setattr("llm_client.LLMClient", lambda: FakeLLM())

    ProjectService(tmp_path).make_chapter_brief_job("brief_novel", 3, source="best")()

    saved = StoryState(str(proj)).get_chapter_brief(3)
    assert saved is not None
    assert saved.style_notes.startswith("Style fingerprint:")
    assert "sentence cadence" in saved.style_notes
    assert "paragraphing" in saved.style_notes


def test_generate_chapter_brief_creates_missing_explicit_pov_character(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.delete_chapter_brief(3)
    chapter = state.get_chapter(3)
    assert chapter is not None
    chapter.pov_character = ""
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "# Chapter 3: New Viewpoint\n\n"
        "**POV Character:** Clara West | **POV Mode:** First person\n\n"
        "## Beats\n"
        "1. Clara West discovers the vault is already open.\n"
        "2. Alice decides to trust Clara with the next key.\n",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert brief.pov_character_id == "char_clara_west"
    assert brief.pov_mode == "first_person"
    assert "char_clara_west" in brief.active_character_ids
    assert "char_clara_west" not in brief.mentioned_character_ids
    reloaded = StoryState(str(proj))
    created = reloaded.get_character("char_clara_west")
    assert created is not None
    assert created.full_name == "Clara West"
    assert created.role == "supporting"


def test_generate_chapter_brief_dedupes_planned_beats_and_keeps_continuity_notes(tmp_path):
    from story_graph import ChapterBeat

    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.set_chapter_beats(
        3,
        [
            ChapterBeat(
                id="beat_3_001",
                title="Alice enters the vault.",
                summary="",
                sort_order=0,
                status="planned",
            ),
            ChapterBeat(
                id="beat_3_002",
                title="Old stale scan beat.",
                summary="",
                sort_order=1,
                status="planned",
            ),
        ],
    )
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "# Chapter 3: Dedupe Case\n\n"
        "## Beats\n"
        "1. Alice enters the vault.\n"
        "2. Alice enters the vault.\n"
        "3. Bob checks the alarm panel.\n"
        "4. Bob checks alarm panel.\n\n"
        "## Continuity Notes\n"
        "- Alice still has the keycard.\n\n"
        "## Ending Hook\n"
        "The alarm goes silent.\n",
        encoding="utf-8",
    )

    brief = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    planned_titles = [b.title for b in saved_beats if b.status == "planned"]
    assert planned_titles.count("Alice enters the vault.") == 1
    assert planned_titles.count("Bob checks the alarm panel.") == 1
    assert "Old stale scan beat." not in planned_titles
    assert not any("Alice still has the keycard" in title for title in planned_titles)
    assert "Alice still has the keycard." in brief.continuity_notes
    assert brief.ending_hook == "The alarm goes silent."


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
    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert saved_beats
    assert any("Alice enters the vault" in beat.title for beat in saved_beats)
    assert not any(beat.lower().startswith("pov:") for beat in [b.title for b in saved_beats])
    assert not any(beat.lower().startswith("point of view:") for beat in [b.title for b in saved_beats])


def test_generate_chapter_brief_preserves_landed_beats(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    state.set_chapter_beats(
        3,
        [
            *state.get_chapter_beats(3),
            ChapterBeat(id="beat_3_003", title="Vault alarm triggered", status="landed", sort_order=2),
            ChapterBeat(id="beat_3_004", title="Bob reveals betrayal", status="landed", sort_order=3),
        ],
    )
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault to advance The Heist.\n"
        "- Bob reveals the keycard was switched.\n"
        "- Alice decides to open the vault anyway.",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert any(b.status == "landed" and "Vault alarm triggered" in b.title for b in saved_beats)
    assert any(b.status == "landed" and "Bob reveals betrayal" in b.title for b in saved_beats)
    assert any("Alice enters the vault" in b.title for b in saved_beats)


def test_generate_chapter_brief_does_not_duplicate_landed_as_planned(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.set_chapter_beats(
        3,
        [
            ChapterBeat(
                id="beat_3_001",
                title="Vault alarm triggered.",
                status="landed",
                sort_order=0,
            ),
        ],
    )
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "## Beats\n"
        "1. The vault alarm is triggered.\n"
        "2. Alice opens the vault.\n",
        encoding="utf-8",
    )

    ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    saved_beats = StoryState(str(proj)).get_chapter_beats(3)
    assert sum("alarm" in b.title.lower() for b in saved_beats) == 1
    assert any(b.status == "planned" and "Alice opens the vault" in b.title for b in saved_beats)


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
    assert "### Active Plot Threads" not in prompt
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


def test_generate_chapter_brief_fuzzy_dedupes_active_story_nodes(tmp_path):
    proj, main_node_id = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    state.story_graph_nodes["graph_node_duplicate_heist"] = StoryGraphNode(
        id="graph_node_duplicate_heist",
        kind="main",
        title="The Hiest",
        description="Steal the vault key",
        priority=10,
        linked_character_ids=["char_a", "char_b"],
    )
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault to advance The Heist.\n"
        "- Bob checks the alarm panel.\n",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    heist_ids = {main_node_id, "graph_node_duplicate_heist"}
    assert len(heist_ids & set(generated.active_node_ids)) == 1


def test_generate_chapter_brief_replaces_previous_scan_cast(tmp_path):
    proj, _ = _seed_brief_project(tmp_path)
    state = StoryState(str(proj))
    brief = state.get_chapter_brief(3)
    assert brief is not None
    state.add_character(Character(id="char_stale", full_name="Stale Cast", role="supporting"))
    brief.mentioned_character_ids = ["char_stale"]
    brief.active_character_ids = ["char_stale"]
    state.set_chapter_brief(brief)
    state.save_state()
    (proj / "outputs" / "chapter_003_outline.md").write_text(
        "- Alice enters the vault.\n- Bob reveals the keycard was switched.\n",
        encoding="utf-8",
    )

    generated = ProjectService(tmp_path).generate_chapter_brief("brief_novel", 3)

    assert "char_a" in generated.active_character_ids
    assert "char_b" in generated.active_character_ids
    assert "char_stale" not in generated.active_character_ids
    assert "char_stale" not in generated.mentioned_character_ids
    assert not (set(generated.mentioned_character_ids) & set(generated.active_character_ids))


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


def test_save_brief_keeps_active_and_mentioned_exclusive(tmp_path):
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
    assert body["mentioned_character_ids"] == []


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

