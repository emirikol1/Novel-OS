# Demo Project: "The Last Algorithm"

This is a canned example Novel OS project demonstrating Structure V2 planning surfaces and the chapter pipeline. It is richer than the minimal seed created by **New project** in the Library.

## Project Overview

- **Title**: The Last Algorithm
- **Genre**: Science Fiction / Techno-Thriller
- **Target Length**: 80,000 words
- **Chapters**: 32 (Act 1 sample seeded in state)

## Premise

In a world where AI manages every aspect of human life, a rogue data archivist discovers that the central algorithm—the one governing global decisions—is not malfunctioning, but evolving with terrifying intent. She must race against time to expose the truth before the system locks humanity into an irreversible path.

## Key Characters

- **Dr. Maya Chen** (Protagonist): Data archivist, brilliant but socially isolated
- **Marcus Webb** (Ally): Former AI engineer with regrets
- **Director Sarah Holt** (Antagonist): Head of AI Security, believes in the system

## Using This Demo

### Web UI (recommended)

1. Copy or import this folder into your Novel OS projects library, or open it from the app bundle at `examples/demo_project/`.
2. Open the project in the Library.
3. Review **Story Graph**, **Cast**, and **Chapter 1** brief + beat board.
4. Follow the workflow in `/help` or `docs/WORKFLOWS.md`.

### CLI (optional)

```bash
cd novel-os/app
python core/orchestrator.py status --project /path/to/demo_project
python core/orchestrator.py plan chapter --number 1 --pov "Dr. Maya Chen" --summary "Maya discovers an anomaly in the archives"
```

## Project Structure

```
demo_project/
├── story_bible.md              # Complete world-building (author-facing)
├── characters/                 # Detailed character profile markdown
│   ├── maya_chen.md
│   └── the_collective.md
├── outline.json                # Full story outline metadata
└── outputs/
    ├── state/
    │   └── story_state.json    # Structure V2 machine-readable state
    ├── chapter_001_outline.md  # Chapter 1 planning scaffold
    ├── manuscript/             # Chapter drafts and revisions (as you write)
    └── feedback/               # Agent analysis and reports
```

## State File (Structure V2)

`outputs/state/story_state.json` includes:

- `schema_version: 2`
- Metadata (title, genre, progress)
- Character database with IDs aligned to `characters/*.md`
- Story graph nodes with lifespan (`start_chapter`, `resolution_chapter`) and layout samples
- Chapter 1 brief with `mentioned_character_ids`, `active_character_ids`, and `active_node_ids`
- `chapter_beats` for the beat board
- Style profile defaults

## Workflow Example

1. **Review** — `story_bible.md`, Cast, and Story Graph
2. **Plan** — Chapter 1 brief, beats, and outline notes
3. **Draft** — Generate Draft from outline
4. **Edit** — Revise, validate, approve
5. **Feed back** — Mine plots/characters; promote durable facts to Story Bible deliberately

## New project vs this demo

| | New project (`POST /api/projects`) | This demo |
|---|-----------------------------------|-----------|
| Characters | 1 placeholder protagonist | Full cast |
| Graph | 1 node | Multiple arcs with lifespan |
| Chapters | Chapter 1 only | Chapter 1 + planning metadata for 32 |
| Purpose | Start writing immediately | Reference a complete v2 project shape |

See in-app help: **Your first manuscript** at `/help/getting-started`.

## Notes

This demo is fully functional as a reference template. Replace names, graph nodes, and bible content with your own work when starting a real manuscript.
