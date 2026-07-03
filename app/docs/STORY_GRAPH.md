# Story Graph & Chapter Briefs

The **Story Graph** is Novel OS’s primary planning layer for arcs, subplots, plot beats, and structural links. **Chapter briefs** bind a chapter to POV, active characters, active graph nodes, and chapter-local landed beats before outlining and drafting.

The **Story Bible** remains the durable canon store: one-fact-per-line worldbuilding, setting facts, world rules, themes, and stable facts that future chapters must obey. Writing tone lives in **Story Style / Tone**. Do not use the graph as a replacement for durable worldbuilding canon.

Legacy **plot threads** remain in `story_state.json` for backward compatibility, mining, and duplicate search. They are not deleted when you migrate.

## Recommended workflow

1. **Migrate (optional)** — Story Graph tab → **Build graph from plots**. Copies plot threads and subplot lines into graph nodes and `contains` edges. Repeated subplot labels become one shared subplot node that can belong to multiple plots. Original plot threads stay intact.
2. **Arrange** — Add or edit nodes, link beats, set priorities. Use `contains` links for plot → subplot and subplot → nested subplot relationships. Run **Find duplicates** if migration created overlapping titles.
3. **Chapter brief** — On a chapter page, set POV, active characters, and **active graph nodes** for that chapter.
4. **Outline** — Write or generate the chapter outline (Architect reads brief + outline when present).
5. **Draft** — Generate Draft; Scribe uses outline and brief-scoped graph context.
6. **Review landed beats** — After prose exists, extract landed beats into the chapter brief. These are chapter-local events, not Story Bible canon.
7. **Mine & sync** — Mine Plots still updates legacy plot threads; Mine Bible extracts durable canon. Review applies, then re-run migration or edit the graph manually.

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
