# Story Graph & Chapter Briefs

The **Story Graph** is Novel OS’s primary planning layer for arcs, subplots, plot beats, and structural links. **Chapter briefs** bind a chapter to POV, active characters, active graph nodes, and chapter-local landed beats before outlining and drafting.

The **Story Bible** remains the durable canon store: one-fact-per-line worldbuilding, setting facts, world rules, themes, and stable facts that future chapters must obey. Writing tone lives in **Story Style / Tone**. Do not use the graph as a replacement for durable worldbuilding canon.

Legacy **plot threads** remain in `story_state.json` for backward compatibility, mining, and duplicate search. They are not deleted when you migrate.

## Design Intent

The graph exists to reduce author bookkeeping, not to create a second outline the author must maintain by hand. It should answer practical drafting questions quickly:

- What story arcs, subplots, mysteries, themes, and beats matter now?
- Which characters are attached to those story elements?
- Which chapter or act should carry each element?
- What dependencies, foreshadowing, or resolution links should the agents consider?
- What context will be injected into planning, drafting, revision, and validation?

The ideal workflow is **author writes or plans normally → Novel OS suggests graph updates → author reviews or auto-accepts small, understandable changes → the graph drives briefs and context**. Manual graph editing remains available for intentional structure, but the app should do as much extraction, linking, pinning, and duplicate detection as possible.

## Product Principles

- **Review first:** AI-generated or mined graph changes should be previewed before they modify canonical state.
- **Post-apply review:** If the author chooses auto-accept, applied changes should remain in the Review queue until marked reviewed or safely reverted.
- **Preserve author edits:** Sync and migration must not overwrite manually curated titles, descriptions, layout, act placement, chapter pins, or relationships without explicit approval.
- **Incremental over rebuild:** Prefer adding or patching missing graph facts to forcing users to rebuild the map.
- **Map as control surface:** A selected graph node should make it easy to inspect/edit lifespan, act, chapter pins, linked characters, parent/child structure, and prompt relevance.
- **Context clarity:** If a node affects prompts, the UI should make that visible through chapter brief selection, blueprint placement, or context preview.
- **Low workload:** The user’s main job should be approving, dismissing, or lightly editing suggestions, not redrawing diagrams after every chapter.

## Recommended workflow

1. **Migrate (optional)** — Story Graph tab → **Build graph from plots**. Copies plot threads and subplot lines into graph nodes and `contains` edges. Repeated subplot labels become one shared subplot node that can belong to multiple plots. Original plot threads stay intact.
2. **Arrange** — Add or edit nodes, link beats, set priorities. Use `contains` links for plot → subplot and subplot → nested subplot relationships. Run **Find duplicates** if migration created overlapping titles.
3. **Chapter brief** — On a chapter page, set POV, active characters, and **active graph nodes** for that chapter.
4. **Outline** — Write or generate the chapter outline (Architect reads brief + outline when present).
5. **Draft** — Generate Draft; Scribe uses outline and brief-scoped graph context.
6. **Review landed beats** — After prose exists, extract landed beats into the chapter brief. These are chapter-local events, not Story Bible canon.
7. **Mine & sync** — Mine Plots still updates legacy plot threads; Mine Bible extracts durable canon. Review applies, then sync or edit the graph without replacing manual structure.

## Sync Model

Today, migration copies legacy plot threads and subplot lines into graph nodes, and chapter briefs mirror active node selections into chapter pins. This is intentionally non-destructive.

The long-term model should be an incremental graph-sync layer:

- Plot mining can propose new graph nodes, status changes, character links, and lifespan updates.
- Character mining can propose relationship edges and character-to-plot involvement.
- Chapter briefs can propose chapter pins and landed-beat links.
- Duplicate scans can propose merges without collapsing unrelated author intent.

Sync should be treated as suggestion review, not automatic truth. Apply only the changes the author accepts, and preserve existing manual layout.

## Review Queue

Graph suggestions are stored as generic reviewable changes in project state. The Review tab is the central queue for:

- Pending graph suggestions waiting for Apply or Dismiss.
- Auto-applied graph suggestions waiting for Mark reviewed or Revert.
- Blocked reverts with conflict reasons and manual resolution guidance.

Side-by-side review shows the current/proposed structured graph fields. Revert is conservative: created nodes can be removed only if no edges, chapter brief selections, beat links, or newer edits depend on them. Relationship edges and chapter pins are also reverted only when their current state still matches the applied change.

## Prompt behavior

| Surface | Affects agents? | Notes |
|--------|-----------------|-------|
| Chapter brief (POV, active nodes) | Yes (with saved outline) | Scoped graph lines injected into planning/draft prompts |
| Chapter brief landed beats | Yes (when saved) | Chapter-local events from existing prose; not Story Bible canon by default |
| Story Graph (full map) | Indirect | Full graph is not dumped into every prompt; brief selects scope |
| Story Bible | Yes, when prompt builders include bible context | Durable canon facts, world rules, setting, themes |
| Story Style / Tone | Yes, when prompt builders include style context | Authoritative tone, POV default, tense, prose style |
| Legacy plot threads | Fallback | Used when graph is empty or as broad arc context |
| Blueprint | No | Read-only review |

If no saved outline exists, brief fields alone may not fully drive generation — still write outline notes.

## Duplicate detection

| Tool | Location | What it scans |
|------|----------|----------------|
| Plot-thread duplicates | Plot Threads → Resolve Duplicates | Legacy `plot_threads` (characters too on Cast) |
| Graph duplicates | Story Graph → Find duplicates | `story_graph_nodes` by title/kind/description similarity |
| Bible duplicates | Story Bible → Deduplicate | List entries within bible sections |

These systems are independent. After migration you may have similar titles in both layers until you merge graph duplicates and/or legacy plot duplicates.

## Canon Boundaries

- **Story Bible:** durable canon facts and rules future chapters must obey.
- **Story Graph:** story structure, arcs, subplots, dependencies, and character-to-plot links.
- **Landed beats:** events that actually happened in one chapter; promote only reusable facts through a reviewed Story Bible flow.
- **Timeline:** chronological ordering of events, not a substitute for bible rules or graph structure.

## Shared And Nested Subplots

- A single subplot node can have multiple parent plots through multiple incoming `contains` edges.
- Subplots can also contain other subplots, which lets you model nested arcs without duplicating nodes.
- Chapter briefs select the subplot node once; prompt context will use that selected node regardless of how many parent plots reference it.

## API (graph dedup)

```
GET  /api/projects/{id}/story-graph/duplicates
POST /api/projects/{id}/story-graph/duplicates/merge
POST /api/projects/{id}/story-graph/duplicates/auto-resolve
```

See [API.md](API.md) for request bodies.

## Testing guidance

Automated tests must use **synthetic projects** (`tmp_path`, `initialize_project`, mocked state JSON). Do not point tests at real author project directories or production `projects/` trees.
