# Dashboard Stats

The **Writing progress** section on the project dashboard (`ProjectDashboard`) summarizes manuscript health from chapter list data returned by the API.

Stats are computed client-side in `web/src/lib/writingStats.ts` from `ChapterSummary[]` — no separate stats endpoint.

---

## Data source

Each chapter in `GET /api/projects/{project_id}/chapters` includes:

| Field | Used for |
|---|---|
| `number` | Ordering, next-action links, health lists |
| `word_count` | Total words, zero-word detection |
| `status` | Fallback when `pipeline_step` is missing; `planned` treated like `none` for next action |
| `pipeline_step` | Pipeline bucket counts, completion %, missing-Final detection |

`pipeline_step` is set server-side in `ProjectService._chapter_pipeline_step` from stage files, DB Final artifact, and chapter `status`.

---

## Pipeline buckets

```mermaid
flowchart LR
    CS["ChapterSummary.pipeline_step"]
    Count["countPipeline"]
    UI["Dashboard pipeline chips"]

    CS --> Count --> UI
```

| `pipeline_step` | Meaning | How API derives it |
|---|---|---|
| `none` | No draft file; status not drafted | Default when no draft/revised/final content |
| `drafted` | Draft exists or status is `drafted` / `drafting` | `chapter_NNN_draft.md` present |
| `revised` | Revision exists or status is `edited` / `editing` | `chapter_NNN_revised.md` present |
| `validated` | Guardian passed; status `validated` | Status match |
| `approved` | Approved but no Final yet | Status `complete` without Final file/artifact |
| `final` | Human-reviewed Final on file | `chapter_NNN_final.md` or DB final artifact |

Counts are the number of chapters in each bucket. Unknown `pipeline_step` values fall into `none`.

---

## Completion percentage

```
completionPct = round((pipeline.final / chapterCount) * 100)
```

- **Numerator:** chapters with `pipeline_step === "final"`
- **Denominator:** `chapters.length` (0 chapters → 0%)
- Displayed as: `{completionPct}% complete — {final} of {chapterCount} chapters finalized`

This measures **Final** adoption, not orchestrator `complete` status alone.

---

## Next action

`computeNextAction` scans chapters sorted by `number` and returns the first applicable label:

| Condition | Label | Link target |
|---|---|---|
| First chapter with `pipeline_step === "none"` or `status === "planned"` | `Draft chapter {n}` | That chapter |
| First `pipeline_step === "drafted"` | `Revise chapter {n}` | That chapter |
| First `pipeline_step === "revised"` | `Validate chapter {n}` | That chapter |
| First `validated` or `approved` | `Promote or final review chapter {n}` | That chapter |
| All chapters `final` | `Export manuscript or plan next chapter` | No chapter link |
| Empty chapter list | `Plan chapter {nextChapterNumber}` | No chapter link |
| Otherwise | `Plan chapter {nextChapterNumber}` | No chapter link |

`nextChapterNumber` is `max(chapter.number) + 1`, or `1` if there are no chapters.

---

## Health signals

Shown when any signal is non-zero:

| Signal | Derivation |
|---|---|
| **Zero-word chapters** | `word_count === 0` → list of chapter numbers |
| **Chapters without Final** | `pipeline_step !== "final"` → list of chapter numbers |
| **Pending AI previews** | Chapters with unsaved regenerate/outline/expand previews (`projectChaptersWithPendingPreviews`) |

These are advisory — they do not block export or agent runs.

---

## Header stats (separate from Writing progress)

The dashboard header also shows:

| Stat | Source |
|---|---|
| Chapters | `project.chapter_count` |
| Written | chapters where `status !== "planned"` |
| Words | sum of `chapter.word_count` (same total as Writing progress **Total words**) |

---

## Source files

| File | Role |
|---|---|
| `web/src/lib/writingStats.ts` | `buildWritingStats`, `countPipeline`, `computeNextAction` |
| `web/src/routes/ProjectDashboard.tsx` | Renders progress section |
| `web/src/lib/chapterPipeline.ts` | `PIPELINE_LABELS`, step types |
| `api/services.py` | `_chapter_pipeline_step`, `_chapter_summary` |

See [WORKFLOWS.md](WORKFLOWS.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
