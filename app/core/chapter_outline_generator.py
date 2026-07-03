"""
Generate a structured chapter outline (beat sheet).

Modes:
- **notes** — forward-plan from author direction (no prose required)
- **draft / revised / final** — reverse-engineer outline from existing chapter text

Uses the Architect agent. Preview → keep / discard before writing chapter_NNN_outline.md.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from llm_client import LLMClient, LLMError
from context_resolver import BUDGET_OUTLINE, format_bible_context_for_prompt
from prompt_budget import check_prompt_budget, split_text_chunks, word_count
from mention_context import mention_context_for_prompts
from prompt_context import strip_outline_pov_metadata
from state_parser import _KNOWN_TAGS, _strip_model_reasoning, extract_block

_OUTLINE_POV_NOTE = (
    "POV (viewpoint character and narrative perspective) is defined in the **Chapter Brief** when "
    "present. Do **not** include POV metadata in the outline output."
)

OUTLINE_SOURCES = frozenset(VALID_SOURCES | {"notes"})


def extract_chapter_outline(text: str) -> str:
    """Pull beat-sheet markdown from an Architect response."""
    block = extract_block(text, "CHAPTER_OUTLINE")
    if block:
        return block.strip()

    cleaned = _strip_model_reasoning(text)
    for tag in _KNOWN_TAGS:
        cleaned = re.sub(
            rf"\[{re.escape(tag)}\].*?\[/{re.escape(tag)}\]",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
    cleaned = re.sub(r"\[/?[A-Z_]+\]", "", cleaned)
    # Drop leading conversational preamble before first markdown heading
    lines = cleaned.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            return "\n".join(lines[i:]).strip()
    return cleaned.strip()


def _outline_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    title: str,
    instructions: str,
    plot_context: str = "",
    brief_context: str = "",
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""
    brief_block = f"\n{brief_context}\n" if brief_context.strip() else ""
    return f"""# OUTLINE FROM PROSE — Chapter {chapter_number}

You are the **Architect**. Read the chapter prose below and produce a **beat-sheet outline**
that captures what actually happens — not what was planned. This reverse-engineers structure
from finished (or draft) text so the outline can guide revisions or later chapters.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- {_OUTLINE_POV_NOTE}
- **Prose word count:** {len(source_text.split())}
{brief_block}{plot_block}
## Chapter prose ({source_label})

```markdown
{source_text}
```
{extra}

## Output contract

Return:
1. Optional brief note (2–3 sentences) on structure you inferred.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` containing the **complete** beat-sheet in Markdown:

```
# Chapter {chapter_number}: <title>

## Chapter Goal
<what changes by end of chapter>

## Beats
1. **<beat name>** — <what happens>
2. …
(4–10 beats matching the prose)

## Characters & threads
- <who appears, plot threads advanced>

## Continuity Notes
- <facts to preserve>

## Ending Hook
<how the chapter ends>
```

3. Do **not** emit chain-of-thought or reasoning blocks.
4. Outline only — **no new prose**, dialogue, or narrative paragraphs.

Write the beat-sheet now.
"""


def _outline_segment_prompt(
    chapter_number: int,
    source_label: str,
    segment_text: str,
    *,
    segment_index: int,
    segment_total: int,
    title: str,
    instructions: str = "",
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    return f"""# OUTLINE FROM PROSE — Chapter {chapter_number} (segment {segment_index}/{segment_total})

You are the **Architect**. Read **only this prose segment** and extract beats for what happens
in this portion of the chapter. Do not invent events from other segments.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- **Segment:** {segment_index} of {segment_total}
- **Segment word count:** {word_count(segment_text)}
{extra}

## Prose segment

```markdown
{segment_text}
```

## Output contract

Return:
1. Optional brief note (1–2 sentences) on structure in this segment.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` with **segment beats only**:

```
## Beats (segment {segment_index})
1. **<beat name>** — <what happens in this segment>
2. …

## Continuity Notes (segment)
- <facts established in this segment>
```

3. Outline only — no new prose. No chain-of-thought blocks.

Extract segment beats now.
"""


def _outline_merge_prompt(
    chapter_number: int,
    source_label: str,
    segment_outlines: list[str],
    *,
    title: str,
    instructions: str,
    plot_context: str = "",
    brief_context: str = "",
    total_word_count: int,
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""
    brief_block = f"\n{brief_context}\n" if brief_context.strip() else ""
    joined = "\n\n---\n\n".join(
        f"### Segment outline {idx}\n{outline.strip()}"
        for idx, outline in enumerate(segment_outlines, start=1)
    )
    return f"""# MERGE OUTLINE SEGMENTS — Chapter {chapter_number}

You are the **Architect**. Combine the partial beat sheets below into **one** chapter outline
that covers the full chapter in reading order. Deduplicate repeated beats; preserve every major turn.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- **Total prose word count:** {total_word_count:,}
- **Segments merged:** {len(segment_outlines)}
{brief_block}{plot_block}
## Partial outlines (in order)

{joined}
{extra}

## Output contract

Return:
1. Optional brief note (2–3 sentences) on overall chapter structure.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` containing the **complete unified** beat-sheet:

```
# Chapter {chapter_number}: <title>

## Chapter Goal
<what changes by end of chapter>

## Beats
1. **<beat name>** — <what happens>
2. …
(4–12 beats covering the full chapter)

## Characters & threads
- <who appears, plot threads advanced>

## Continuity Notes
- <facts to preserve>

## Ending Hook
<how the chapter ends>
```

3. Outline only — no prose. No chain-of-thought blocks.

Write the merged beat-sheet now.
"""


def _notes_outline_prompt(
    chapter_number: int,
    *,
    title: str,
    target_words: int,
    instructions: str,
    plot_context: str,
    character_context: str,
    bible_context: str,
    existing_outline: str,
    brief_context: str = "",
) -> str:
    existing_block = ""
    if existing_outline.strip():
        existing_block = f"""
## Current outline (revise or replace using author notes)

```markdown
{existing_outline.strip()}
```
"""
    bible_block = f"\n## Story bible\n{bible_context}\n" if bible_context.strip() else ""
    brief_block = f"\n{brief_context}\n" if brief_context.strip() else ""
    char_block = ""
    if not brief_context.strip() and character_context.strip():
        char_block = f"\n## Relevant characters\n{character_context}\n"
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""

    return f"""# OUTLINE FROM AUTHOR NOTES — Chapter {chapter_number}

You are the **Architect**. The author has provided direction for this chapter's beat-sheet.
Produce a structured **outline** the Scribe will later expand into prose. **No dialogue or narrative paragraphs.**

- **Chapter title:** {title or "Propose a fitting title"}
- **Target word count:** {target_words}
- {_OUTLINE_POV_NOTE}
{bible_block}{brief_block}{char_block}{plot_block}{existing_block}
## Author direction (required)

{instructions.strip()}

## Output contract

Return:
1. Optional brief note (2–3 sentences) on how you interpreted the author's direction.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` containing the **complete** beat-sheet in Markdown:

```
# Chapter {chapter_number}: <title>

## Chapter Goal
<what must change by end of chapter>

## Beats
1. **<beat name>** — <1-2 sentence summary; conflict/turn>
2. …
(4–7 beats)

## Continuity Notes
- <facts the Scribe must honor>

## Ending Hook
<pull into next chapter>
```

3. Do **not** emit chain-of-thought or reasoning blocks.
4. Outline only — honor the author's notes; use story context to fill gaps.

Write the beat-sheet now.
"""


class ChapterOutlineGenerator:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.feedback_dir = self.outputs_dir / "feedback"
        self._reader = ChapterRegenerator(project_path, llm=llm)
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def preview_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_outline_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_outline_preview_meta.json"

    def _read_existing_outline(self, number: int) -> str:
        path = self.outputs_dir / f"chapter_{self._nnn(number)}_outline.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def generate(
        self,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        log = on_progress or (lambda msg: None)
        if source not in OUTLINE_SOURCES:
            source = "draft"

        state = self._reader.state
        chapter = state.get_chapter(number)
        if not chapter:
            chapter = state.create_chapter(number)

        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        from plot_prompts import format_plot_threads_block  # noqa: WPS433
        from story_graph import (  # noqa: WPS433
            ChapterBrief,
            apply_brief_pov_to_chapter,
            format_chapter_brief_prompt_context,
        )

        plot_context = format_plot_threads_block(
            state.get_active_plot_threads(), max_threads=8,
        )
        brief = state.get_chapter_brief(number)
        prev_pov = chapter.pov_character
        apply_brief_pov_to_chapter(state, chapter, brief)
        if chapter.pov_character != prev_pov:
            state.save_state()
        from prompt_context import effective_target_word_count  # noqa: WPS433
        from story_graph import ChapterBrief, format_chapter_brief_prompt_context  # noqa: WPS433

        target_words = effective_target_word_count(brief, state, chapter)
        brief_context = (
            format_chapter_brief_prompt_context(state, brief) if brief is not None else ""
        )
        if not brief_context.strip() and chapter is not None:
            brief_context = format_chapter_brief_prompt_context(
                state,
                ChapterBrief(chapter_number=number),
            )

        from chapter_brief_utils import format_chapter_beats_for_outline_prompt  # noqa: WPS433

        beats_context = format_chapter_beats_for_outline_prompt(state, number, brief)
        if beats_context.strip():
            brief_context = f"{brief_context.rstrip()}\n\n{beats_context}\n" if brief_context.strip() else f"{beats_context}\n"

        if source == "notes":
            if not instructions.strip():
                raise ValueError("Outline notes / direction are required for notes-based generation.")
            char_lines: list[str] = []
            if not brief_context.strip():
                for char in state.get_all_characters():
                    if char.last_appearance_chapter >= number - 3 or char.last_appearance_chapter == 0:
                        char_lines.append(
                            f"- **{char.full_name}** ({char.role}) — "
                            f"{char.current_location or 'unknown location'}, "
                            f"{char.emotional_state or 'unknown mood'}"
                        )
            user_prompt = _notes_outline_prompt(
                number,
                title=chapter.title or "",
                target_words=target_words,
                instructions=instructions,
                plot_context=plot_context,
                character_context="\n".join(char_lines[:12]),
                bible_context=format_bible_context_for_prompt(
                    state,
                    budget=BUDGET_OUTLINE,
                    hint_text=instructions,
                ),
                existing_outline=self._read_existing_outline(number),
                brief_context=brief_context,
            )
            mention_block = mention_context_for_prompts(instructions, state)
            if mention_block:
                user_prompt = mention_block + user_prompt
            source_text = ""
            original_wc = 0
            chunks: list[str] = []
        else:
            source_text = self._reader.read_source(number, source)
            original_wc = word_count(source_text)
            chunks = split_text_chunks(source_text)
            mention_block = mention_context_for_prompts(source_text, state)
            title = chapter.title or ""

            if len(chunks) == 1:
                user_prompt = _outline_prompt(
                    number,
                    source,
                    source_text,
                    title=title,
                    instructions=instructions,
                    plot_context=plot_context,
                    brief_context=brief_context,
                )
                if mention_block:
                    user_prompt = mention_block + user_prompt
            else:
                user_prompt = ""
                log(
                    f"Long chapter (~{original_wc:,} words) — "
                    f"outline-from-text will run in {len(chunks)} segments plus a merge pass."
                )

        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_generate_prompt.md"

        if source != "notes" and len(chunks) > 1:
            if dry_run:
                seg_prompt = mention_block + _outline_segment_prompt(
                    number,
                    source,
                    chunks[0],
                    segment_index=1,
                    segment_total=len(chunks),
                    title=title,
                    instructions=instructions,
                )
                prompt_path.write_text(seg_prompt, encoding="utf-8")
                log(
                    f"Dry-run — segment prompts will be saved under {self.feedback_dir} "
                    f"({len(chunks)} segments + merge)"
                )
                return "", str(prompt_path)

            segment_outlines: list[str] = []
            for ci, chunk in enumerate(chunks, start=1):
                from job_control import check_job_cancelled  # noqa: WPS433

                check_job_cancelled()
                seg_prompt = mention_block + _outline_segment_prompt(
                    number,
                    source,
                    chunk,
                    segment_index=ci,
                    segment_total=len(chunks),
                    title=title,
                    instructions=instructions,
                )
                seg_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_segment_{ci:02d}_prompt.md"
                seg_path.write_text(seg_prompt, encoding="utf-8")
                check_prompt_budget(seg_prompt, label=f"outline segment {ci}/{len(chunks)}")
                log(f"Outlining segment {ci}/{len(chunks)} (~{word_count(chunk):,} words)…")
                try:
                    raw_seg = self._get_llm().run_agent("architect", seg_prompt)
                except LLMError as e:
                    raise RuntimeError(f"Outline segment {ci}/{len(chunks)} failed: {e}") from e
                seg_report = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_segment_{ci:02d}_report.md"
                seg_report.write_text(raw_seg, encoding="utf-8")
                seg_outline = extract_chapter_outline(raw_seg)
                if not seg_outline:
                    raise RuntimeError(
                        f"Architect returned no outline for segment {ci}/{len(chunks)} "
                        "([CHAPTER_OUTLINE] block missing)"
                    )
                segment_outlines.append(seg_outline)

            user_prompt = mention_block + _outline_merge_prompt(
                number,
                source,
                segment_outlines,
                title=title,
                instructions=instructions,
                plot_context=plot_context,
                brief_context=brief_context,
                total_word_count=original_wc,
            )
            prompt_path.write_text(user_prompt, encoding="utf-8")
            check_prompt_budget(user_prompt, label="outline merge")
            log(f"Merging {len(segment_outlines)} segment outlines…")
            try:
                raw = self._get_llm().run_agent("architect", user_prompt)
            except LLMError as e:
                raise RuntimeError(f"Outline merge failed: {e}") from e
            report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_generate_report.md"
            report_path.write_text(raw, encoding="utf-8")
            preview = strip_outline_pov_metadata(extract_chapter_outline(raw))
            if not preview:
                raise RuntimeError("Architect returned no merged outline ([CHAPTER_OUTLINE] block missing)")
            preview_path = self.preview_path(number)
            preview_path.write_text(preview, encoding="utf-8")
            meta = {
                "source": source,
                "instructions": instructions.strip(),
                "original_word_count": original_wc,
                "preview_word_count": len(preview.split()),
                "segment_count": len(chunks),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
            log(f"Outline preview ready ({len(preview.split())} words, {len(chunks)} segments merged)")
            return preview, str(report_path)

        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        label = "author notes" if source == "notes" else source
        log(f"Generating outline for chapter {number} from {label} via Architect…")
        check_prompt_budget(user_prompt, label=f"outline-from-{label}")
        try:
            raw = self._get_llm().run_agent("architect", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Outline generation failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_generate_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = strip_outline_pov_metadata(extract_chapter_outline(raw))
        if not preview:
            raise RuntimeError("Architect returned no outline ([CHAPTER_OUTLINE] block missing)")

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        meta = {
            "source": source,
            "instructions": instructions.strip(),
            "original_word_count": original_wc,
            "preview_word_count": len(preview.split()),
            "segment_count": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Outline preview ready ({len(preview.split())} words)")
        return preview, str(report_path)
