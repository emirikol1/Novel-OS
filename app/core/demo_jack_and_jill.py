"""
Complete demo project: Jack and Jill (children's nursery rhyme).

One finished chapter with cast, story graph, brief, beats, bible, timeline,
and full pipeline artifacts (outline → draft → revised → final).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_context import normalize_brief_for_storage
from state_manager import Character, ChapterState, StyleProfile, TimelineEvent
from story_graph import (
    ChapterBeat,
    ChapterBrief,
    StoryGraphEdge,
    StoryGraphLayout,
    StoryGraphNode,
    apply_brief_pov_to_chapter,
    new_chapter_beat_id,
    normalize_brief_characters,
    sync_chapter_pins_for_brief,
)

if TYPE_CHECKING:
    from state_manager import StoryState

DEMO_TITLE = "Jack and Jill"
DEMO_GENRE = "Children's Nursery Rhyme"
DEMO_AUTHOR = "Public Domain (demo)"
DEMO_SLUG = "jack-and-jill"

CHAPTER_NUMBER = 1
CHAPTER_TITLE = "Up the Hill"

OUTLINE = """# Chapter 1 — Up the Hill

## Intent
Retell the classic nursery rhyme as a complete picture-book chapter: ordinary morning,
shared errand, small disaster, and a bruised but affectionate return home.

## Beats
- Mother sends Jack and Jill to fetch water from the hilltop spring
- The siblings climb, banter, and fill the pail together
- Jack slips on wet stone; Jill follows in a tumble
- They limp home with the pail (mostly) intact and a story for Mother

## Ending hook
Mother bandages Jack's brow while Jill boasts she "caught" the pail — setting up tomorrow's caution.
"""

DRAFT = """Mother handed them the pail at first light. "Up the hill," she said, "and mind the wet stones."

Jack took the handle first. Jill walked beside him, humming. The lane narrowed into grass, then into the steep path everyone in the village called the Hill.

"The spring is always coldest before breakfast," Jack said.

"Then we should hurry," Jill answered.

They climbed. The pail knocked against Jack's knee. Wind pulled at Jill's hair. Halfway up, Jack swapped hands so Jill could lead on the steeper bend.

At the top, water slid clear from a cut in the rock. They filled the pail together, both gripping the handle because it was heavy when full.

On the way down, Jack's foot found a slick patch. He sat down hard. The crown of his head struck a stone. Jill reached for him, lost her balance, and rolled after.

They lay in the clover, breathless, the pail on its side but not empty.

"Are you broken?" Jill whispered.

"Only my pride," Jack said, touching his forehead. "And maybe my crown."

They righted the pail and walked home slowly, bruised and laughing when it hurt too much to do otherwise.
"""

REVISED = """Mother met them at the cottage door with the empty wooden pail and a stern kind of love.

"Up the hill," she said, tying Jill's apron strings. "Fetch water from the spring. Mind the wet stones, both of you."

Jack took the handle first. Jill fell in beside him, humming a tune Mother hummed when bread was in the oven. The lane narrowed to grass, then to the steep path the whole village called the Hill — not grand, only tall enough to make small legs honest.

"The spring is coldest before breakfast," Jack said, as if he had measured it himself.

"Then we should hurry," Jill answered, though she never hurried on a path she liked.

They climbed. The pail knocked Jack's knee in a steady rhythm. Wind combed Jill's hair across her cheeks. Where the path bent steeper, they traded hands so Jill could lead on the inside, closer to the wall of earth and roots.

At the top, water slid clear from a notch in the rock. They knelt together and filled the pail, four hands on the handle because full water pulls downward like a promise.

The descent was quicker and less careful. Jack's heel found a slick of moss. His feet went forward; he sat down hard. The crown of his head struck stone with a sound Jill would remember on quiet nights. She grabbed for his sleeve, missed, and came tumbling after in a tangle of elbows and laughter that turned into a wince.

They lay in the clover, breathless, the pail on its side but not empty — a small mercy.

"Are you broken?" Jill whispered, fingers hovering above the red line on his forehead.

"Only my pride," Jack said. "And perhaps my crown."

They righted the pail and walked home slowly, bruised, loyal, and pleased to have a story worth telling at breakfast.
"""

FINAL = REVISED

CONTINUITY_PASS = {
    "status": "PASS",
    "summary": "Demo validation — continuity checks satisfied for a closed one-chapter arc.",
    "critical_issues": [],
    "warnings": [],
    "validated_at": datetime.now(timezone.utc).isoformat(),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def populate_jack_and_jill_demo(state: "StoryState") -> None:
    """Fill an initialized project with the Jack and Jill demo (clears existing cast/chapters)."""
    state.characters.clear()
    state.chapters.clear()
    state.plot_threads.clear()
    state.story_graph_nodes.clear()
    state.story_graph_edges.clear()
    state.chapter_briefs.clear()
    state.chapter_beats.clear()
    state.timeline.clear()

    state.set_metadata("title", DEMO_TITLE)
    state.set_metadata("genre", DEMO_GENRE)
    state.set_metadata("author", DEMO_AUTHOR)
    state.set_metadata("status", "in_progress")
    state.set_metadata("demo", True)

    state.update_story_bible(
        "logline",
        "When a brother and sister climb the village hill for water, a slip and a tumble "
        "teach them that errands finished together matter more than pride.",
    )
    state.update_story_bible(
        "themes",
        [
            "Shared responsibility",
            "Sibling loyalty",
            "Consequences of haste",
            "Ordinary courage",
        ],
    )
    state.update_story_bible(
        "setting_summary",
        [
            "A small English countryside village at the foot of a modest hill",
            "A cottage home with a kitchen spring errand tradition",
            "A hilltop rock spring where villagers fetch water",
        ],
    )
    state.update_story_bible(
        "historical_context",
        [
            "Based on the traditional nursery rhyme 'Jack and Jill' (public domain)",
            "Demo project for Novel OS Structure V2 — not a commercial manuscript",
        ],
    )
    state.update_story_bible(
        "premise_beats",
        [
            "Jack and Jill go up the hill to fetch a pail of water",
            "Jack falls down and breaks his crown",
            "Jill comes tumbling after",
            "They return home bruised but together",
        ],
    )
    state.update_story_bible(
        "world_rules",
        "Realistic nursery-world setting: no magic, no modern technology, gentle stakes suitable "
        "for children's fiction. Injuries are painful but not graphic; adults provide care off-page.",
    )
    state.update_story_bible(
        "import_notes",
        "Novel OS demo manuscript — every major workspace surface is populated for onboarding.",
    )

    state.set_style_profile(
        StyleProfile(
            name="picture_book",
            description="Warm third-limited prose for a classic nursery tale",
            tone="light",
            point_of_view="third_limited",
            tense="past",
            prose_style="intimate",
            vocabulary_level="simple",
            dialogue_ratio=0.25,
            description_ratio=0.4,
            chapter_target_words=800,
            genre_conventions=["nursery_rhyme_adaptation", "sibling_story"],
        ),
    )

    jack = Character(
        id="char_jack",
        full_name="Jack",
        role="protagonist",
        age=8,
        physical_description="Brown hair, scraped knees, proud grin even when embarrassed",
        internal_desire="Prove he can handle grown-up errands",
        external_goal="Bring home a full pail without spilling",
        fear="Disappointing Mother or looking foolish in front of Jill",
        weakness="Overconfidence on steep paths",
        strength="Steady hands and stubborn cheer",
        arc_stage="resolution",
        arc_progress=100,
        relationships={"char_jill": "younger sister", "char_mother": "mother"},
        current_location="Cottage lane",
        emotional_state="Sheepish but relieved",
        last_appearance_chapter=CHAPTER_NUMBER,
        notes="POV character for the demo chapter.",
        aliases=["Jacky"],
    )
    jill = Character(
        id="char_jill",
        full_name="Jill",
        role="supporting",
        age=6,
        physical_description="Dark curls, quick eyes, grass stains on her hem",
        internal_desire="Keep pace with Jack and be trusted on the hill",
        external_goal="Help carry the pail safely home",
        fear="Being left behind on the path",
        weakness="Impulsive grabs when Jack stumbles",
        strength="Quick reflexes and blunt honesty",
        arc_stage="resolution",
        arc_progress=100,
        relationships={"char_jack": "older brother", "char_mother": "mother"},
        current_location="Cottage lane",
        emotional_state="Fiercely loyal",
        last_appearance_chapter=CHAPTER_NUMBER,
    )
    mother = Character(
        id="char_mother",
        full_name="Mother",
        role="minor",
        age=34,
        physical_description="Apron, firm voice, gentle hands",
        internal_desire="Raise children who help one another",
        external_goal="Keep the household supplied with spring water",
        relationships={"char_jack": "son", "char_jill": "daughter"},
        last_appearance_chapter=CHAPTER_NUMBER,
        notes="Framing presence — sends the errand and receives them home.",
    )
    state.add_character(jack)
    state.add_character(jill)
    state.add_character(mother)

    main_node = StoryGraphNode(
        id="graph_main_fetch",
        kind="main",
        title="Fetch a Pail of Water",
        description="The village errand that frames the rhyme: climb the hill, fill the pail, return home.",
        status="resolved",
        priority=5,
        linked_character_ids=["char_jack", "char_jill", "char_mother"],
        created_from="demo_seed",
        sort_order=0,
        start_chapter=1,
        resolution_chapter=1,
        layout=StoryGraphLayout(x=0.0, y=0.0),
        act=1,
        chapter_pins=[1],
    )
    fall_node = StoryGraphNode(
        id="graph_jack_fall",
        kind="subplot",
        title="Jack's Fall",
        description="Jack slips on wet stone and strikes his head — the rhyme's 'broke his crown' moment.",
        status="resolved",
        priority=4,
        linked_character_ids=["char_jack"],
        created_from="demo_seed",
        sort_order=1,
        start_chapter=1,
        resolution_chapter=1,
        layout=StoryGraphLayout(x=220.0, y=80.0),
        act=1,
        chapter_pins=[1],
    )
    tumble_node = StoryGraphNode(
        id="graph_jill_tumble",
        kind="subplot",
        title="Jill Comes Tumbling After",
        description="Jill loses her balance reaching for Jack and rolls down beside him.",
        status="resolved",
        priority=4,
        linked_character_ids=["char_jill", "char_jack"],
        created_from="demo_seed",
        sort_order=2,
        start_chapter=1,
        resolution_chapter=1,
        layout=StoryGraphLayout(x=220.0, y=200.0),
        act=1,
        chapter_pins=[1],
    )
    state.add_story_graph_node(main_node)
    state.add_story_graph_node(fall_node)
    state.add_story_graph_node(tumble_node)

    state.add_story_graph_edge(
        StoryGraphEdge(
            id="edge_main_fall",
            source_id="graph_main_fetch",
            target_id="graph_jack_fall",
            kind="contains",
            label="complication",
        ),
    )
    state.add_story_graph_edge(
        StoryGraphEdge(
            id="edge_main_tumble",
            source_id="graph_main_fetch",
            target_id="graph_jill_tumble",
            kind="contains",
            label="complication",
        ),
    )
    state.add_story_graph_edge(
        StoryGraphEdge(
            id="edge_fall_tumble",
            source_id="graph_jack_fall",
            target_id="graph_jill_tumble",
            kind="advances",
            label="cause",
        ),
    )
    state.add_story_graph_edge(
        StoryGraphEdge(
            id="edge_jack_jill",
            source_id="char_jack",
            target_id="char_jill",
            kind="character_relationship",
            label="siblings",
        ),
    )

    chapter = ChapterState(
        number=CHAPTER_NUMBER,
        title=CHAPTER_TITLE,
        status="complete",
        pov_character="Jack",
        location="Village hill and cottage lane",
        time="Early morning",
        word_count=len(FINAL.split()),
        target_word_count=800,
        plot_advances=[
            "Jack and Jill complete the water errand despite a fall.",
            "Sibling loyalty is tested and affirmed on the descent.",
        ],
        character_development={
            "char_jack": "Learns to accept help and laugh at a bruised pride.",
            "char_jill": "Proves she can steady the mission when Jack falters.",
        },
        emotional_beats=[
            "Anticipation leaving the cottage",
            "Comic tenderness after the tumble",
            "Quiet relief walking home",
        ],
        new_information=[
            "The hill path is slickest on the descent after moss gathers overnight.",
        ],
        foreshadowing_planted=[
            "Mother's warning about wet stones pays off on the way down.",
        ],
        hooks_start=["Mother's errand sets a simple goal with clear stakes."],
        hooks_end=["Jill vows to hold the pail tomorrow — a gentle sequel hook."],
        continuity_checks=CONTINUITY_PASS,
        quality_scores={"overall": 4.6, "voice": 4.5, "pacing": 4.7},
        last_modified=_utc_now(),
    )
    state.chapters[CHAPTER_NUMBER] = chapter

    brief = ChapterBrief(
        chapter_number=CHAPTER_NUMBER,
        pov_character_id="char_jack",
        pov_mode="third_limited",
        tone="light",
        tense="past",
        prose_style="intimate",
        vocabulary_level="simple",
        style_notes="Picture-book clarity; sensory hill details; rhyme beats land naturally.",
        target_word_count=800,
        mentioned_character_ids=["char_jack", "char_jill", "char_mother"],
        active_character_ids=["char_jack", "char_jill"],
        active_node_ids=["graph_main_fetch", "graph_jack_fall", "graph_jill_tumble"],
        continuity_notes="Keep injuries mild; Mother frames the errand and receives them home.",
        ending_hook="Jill claims she 'caught' the pail — pride recovered, sequel teased.",
    )
    normalize_brief_characters(brief)
    normalize_brief_for_storage(brief, state)
    state.set_chapter_brief(brief)
    sync_chapter_pins_for_brief(state, brief)
    apply_brief_pov_to_chapter(state, chapter, brief)

    beat_specs = [
        ("Mother sends them up the hill", "Establish errand, pail, and warning about wet stones.", "landed"),
        ("Fill the pail at the spring", "Sibling cooperation at the hilltop.", "landed"),
        ("Jack falls and strikes his head", "Rhyme beat: broke his crown.", "landed"),
        ("Jill tumbles after", "Rhyme beat: came tumbling after.", "landed"),
        ("Walk home bruised but together", "Return with water and a story.", "landed"),
    ]
    beats: list[ChapterBeat] = []
    for idx, (title, summary, status) in enumerate(beat_specs):
        node_ids = ["graph_main_fetch"]
        if "Jack falls" in title:
            node_ids = ["graph_jack_fall"]
        elif "Jill tumbles" in title:
            node_ids = ["graph_jill_tumble"]
        beats.append(
            ChapterBeat(
                id=new_chapter_beat_id(state, CHAPTER_NUMBER) if idx == 0 else f"beat_{CHAPTER_NUMBER}_{idx + 1:03d}",
                title=title,
                summary=summary,
                sort_order=idx,
                status=status,
                linked_node_ids=node_ids,
            ),
        )
    state.set_chapter_beats(CHAPTER_NUMBER, beats)

    state.add_timeline_event(
        TimelineEvent(
            id="timeline_001",
            description="Mother sends Jack and Jill up the hill with the pail.",
            chapter=1,
            day=1,
            time="dawn",
            location="Cottage door",
            characters_present=["char_jack", "char_jill", "char_mother"],
            event_type="scene",
            significance="major",
        ),
    )
    state.add_timeline_event(
        TimelineEvent(
            id="timeline_002",
            description="Jack slips on the descent; Jill tumbles after him.",
            chapter=1,
            day=1,
            time="morning",
            location="Hill path",
            characters_present=["char_jack", "char_jill"],
            event_type="scene",
            significance="turning_point",
        ),
    )
    state.add_timeline_event(
        TimelineEvent(
            id="timeline_003",
            description="Siblings limp home with the pail mostly full.",
            chapter=1,
            day=1,
            time="late morning",
            location="Cottage lane",
            characters_present=["char_jack", "char_jill"],
            event_type="scene",
            significance="major",
        ),
    )


def write_jack_and_jill_artifacts(project_path: Path) -> None:
    """Write on-disk pipeline files for chapter 1."""
    outputs = project_path / "outputs"
    manuscript = outputs / "manuscript"
    manuscript.mkdir(parents=True, exist_ok=True)
    nnn = f"{CHAPTER_NUMBER:03d}"
    (outputs / f"chapter_{nnn}_outline.md").write_text(OUTLINE, encoding="utf-8")
    (manuscript / f"chapter_{nnn}_draft.md").write_text(DRAFT, encoding="utf-8")
    (manuscript / f"chapter_{nnn}_revised.md").write_text(REVISED, encoding="utf-8")
    (manuscript / f"chapter_{nnn}_final.md").write_text(FINAL, encoding="utf-8")
