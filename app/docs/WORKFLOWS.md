# Writing Workflows

Practical paths through Novel OS. In-app help mirrors this at `/help`.

## New project defaults (onboarding)

When you create a project via **Library → New project** (`POST /api/projects`), Novel OS seeds a minimal Structure V2 workspace:

| Asset | What you get |
|-------|----------------|
| **Character** | One protagonist (placeholder name derived from your title) |
| **Chapter** | Chapter 1 — *Opening*, status `planned` |
| **Story Graph** | One main node — *Central conflict*, lifespan starting at chapter 1 |
| **Chapter brief** | POV = protagonist; protagonist mentioned + active; graph node in effect |
| **Beats** | One planned opening beat linked to the graph node |
| **Outline scaffold** | `outputs/chapter_001_outline.md` with intent + beat bullets |

**First-session checklist:** open Chapter 1 → review brief → add beats or outline notes → **Outline from notes** → **Generate Draft**.

**Starter seed vs demo:** new projects use the minimal seed above. The richer canned example lives in `examples/demo_project/` (full cast, graph, and v2 `story_state.json`).

Brief v2 fields on seeded Chapter 1: `mentioned_character_ids`, `active_character_ids`, `active_node_ids`. Graph nodes carry lifespan (`start_chapter`, `resolution_chapter`) and `chapter_pins` synced when a node is active on a brief.

## Story Graph-first chapter (recommended)

0. **New project** — Chapter 1, brief, and one graph node already exist; refine rather than create from zero.
1. **Canon** — Story Bible for durable facts/rules/setting, Story Style / Tone for writing tone, Cast for character memory, optional Timeline for chronology.
2. **Graph** — Story Graph for arcs, subplots, structural links, and character-to-plot relationships; build from plots (non-destructive) or create nodes manually; fix duplicates with **Find duplicates**.
3. **Chapter brief** — POV + active graph nodes (+ active characters if needed).
4. **Outline** — Plan Chapter or Outline from notes; edit and keep outline.
5. **Draft pipeline** — Generate Draft → Revise → Validate → Approve → Final.
6. **Feedback loop** — Extract landed beats for chapter-local events; mine plots/characters/bible; review applies; re-sync graph after plot mining; promote only durable facts to Story Bible.

## Reviewable AI Work

Reviewable generation and extraction jobs should offer two modes:

- **Queue for review:** generated changes appear in the **Review** tab before they modify trusted project state.
- **Auto-accept:** generated changes are applied when ready, then remain in the **Review** tab as **Applied** until the author marks them reviewed or reverts them.

Review cards show side-by-side before/after data. Revert is allowed only when the backend can prove the inverse operation is safe. If reverting would orphan graph links, invalidate references, or overwrite newer edits, Novel OS blocks the revert and explains what the author must resolve manually.

Long prose changes should use preview/snapshot artifacts for side-by-side review rather than duplicating full manuscript text into operational logs.

## Mine All

The dashboard **Mine All** action runs project-level generation/extraction in the approved order:

1. Extract or generate outlines.
2. Mine characters.
3. Mine plots.
4. Mine bible facts.
5. Generate graph suggestions and mapping.
6. Generate chapter briefs only when auto-accept is selected; review-mode briefs need the reviewable brief wrapper before they can be queued safely.
7. Refresh project indexes.

Modes:

- **Missing outlines:** only chapters without outlines are targeted.
- **Missing chapter briefs:** runs prerequisite extraction/mapping, then fills missing briefs only when auto-accept is selected.
- **Everything:** regenerates reviewable replacements or auto-accepted updates where supported.

Findings appear in the Review tab as phases complete. Running status appears through the standard background job/LLM queue surfaces.

## Memory Surfaces

| Surface | Use For | Do Not Use For |
|---------|---------|----------------|
| **Story Bible** | Durable canon: world rules, setting facts, themes, stable relationship facts, technology/magic constraints | Ordinary one-chapter events, plot-arc structure, or writing tone |
| **Story Style / Tone** | Authoritative writing tone, POV defaults, tense, prose style, vocabulary | Worldbuilding canon or plot structure |
| **Story Graph** | Arcs, subplots, mysteries, dependencies, and character-to-plot links | One-fact-per-line worldbuilding canon |
| **Chapter Brief / Landed Beats** | Per-chapter prompt focus and events that actually happened in that chapter | Automatic Story Bible updates |
| **Timeline** | Chronological event ordering | Durable world rules or graph structure |

If a landed beat establishes a reusable fact, promote it through a reviewed Story Bible/bible-mining flow instead of treating every beat as canon.

## Legacy plot-thread workflow (still supported)

New projects skip legacy plot threads unless you add them manually. When working on older imports:

1. Maintain arcs on the **Plot Threads** tab.
2. Use **Resolve Duplicates** and **Check subplot issues** for hygiene.
3. Migrate to Story Graph when ready (does not delete threads).
4. Continue mining plots — updates still land on plot threads until you adopt briefs + graph.

## Duplicate search (preserve both)

- **Entity dedup** (`/duplicates`) — characters and plot threads.
- **Graph dedup** (`/story-graph/duplicates`) — story graph nodes after migration or manual entry.
- **Bible dedup** (`/story-bible/duplicates`) — story bible list lines.

Run the tool that matches the data layer you are cleaning.

## Chapter brief + POV

Chapter briefs live per chapter in `story_state.json`:

- `pov_character_id` — drives POV when outline generation does not override.
- `mentioned_character_ids` — cast referenced this chapter (v2).
- `active_character_ids` — cast directly present/included whose state should drive prompts (exclusive with mentioned cast).
- `active_node_ids` — graph nodes that should advance this chapter (in effect, not just eligible).
- `chapter_beats` — chapter-local beat board rows. Use `planned` for beats the chapter should hit and `landed` for events already present in manuscript text.
- `continuity_notes`, `ending_hook` — author-facing planning text.

See [STORY_GRAPH.md](STORY_GRAPH.md) for eligible vs in-effect nodes and prompt fallbacks when outline is missing.

## Sample-only testing

Integration tests create isolated directories under `tmp_path`. Never wire CI or local test runs to a real novel project folder. Seeded-project shape is covered by `tests/test_starter_seed.py` and create-project API tests. See also `tests/test_story_graph.py` and `tests/test_graph_dedup.py`.
