"""
Novel OS — Import existing manuscript chapters (.txt) and extract story state.

Workflow per chapter:
  1. Copy source text to outputs/sources/
  2. Save as manuscript draft
  3. Run Archivist LLM → parse IMPORT_STATE_UPDATE + SCRIBE_STATE_UPDATE
  4. Optionally run Guardian validate for continuity pass

After all chapters:
  5. Optional synthesize → outline.json + story bible summary
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from llm_client import LLMClient, LLMError
from state_manager import StoryState, project_state_lock
from state_parser import ingest_agent_output


TEXT_EXTENSIONS = {".txt", ".text"}

from prompt_budget import DEFAULT_CHUNK_WORDS, split_text_chunks  # noqa: E402

IMPORT_CHUNK_WORDS = int(os.environ.get("NOVEL_OS_IMPORT_CHUNK_WORDS", str(DEFAULT_CHUNK_WORDS)))


def split_import_chunks(text: str, max_words: int | None = None) -> List[str]:
    """Split long chapter text into LLM-sized chunks (paragraph-aware when possible)."""
    return split_text_chunks(text, max_words=max_words or IMPORT_CHUNK_WORDS)


def natural_sort_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


@dataclass
class ChapterFile:
    path: Path
    number: int


def discover_chapters(
    chapters_dir: Path,
    *,
    start: int = 1,
    extensions: Optional[set] = None,
) -> List[ChapterFile]:
    """Find chapter text files sorted naturally; assign sequential chapter numbers from `start`."""
    chapters_dir = Path(chapters_dir)
    if not chapters_dir.is_dir():
        raise FileNotFoundError(f"Chapters directory not found: {chapters_dir}")

    ext = extensions or TEXT_EXTENSIONS
    files = sorted(
        [p for p in chapters_dir.iterdir() if p.is_file() and p.suffix.lower() in ext],
        key=natural_sort_key,
    )
    if not files:
        raise FileNotFoundError(
            f"No chapter files ({', '.join(sorted(ext))}) found in {chapters_dir}"
        )
    return [ChapterFile(path=f, number=start + i) for i, f in enumerate(files)]


def _archivist_user_prompt(
    chapter_number: int,
    chapter_text: str,
    filename: str,
    *,
    chunk_index: int = 1,
    chunk_total: int = 1,
) -> str:
    chunk_note = ""
    if chunk_total > 1:
        chunk_note = (
            f"\n- **Segment:** {chunk_index} of {chunk_total} "
            f"(extract only facts present in this segment; state merges across segments)"
        )
    return f"""# IMPORT TASK — Existing Manuscript Chapter

Analyze the following **existing chapter** (do not rewrite it). Extract all structured metadata per your OUTPUT CONTRACT.

- **Chapter number:** {chapter_number}
- **Source file:** {filename}{chunk_note}
- **Word count:** {len(chapter_text.split())}

---

## CHAPTER TEXT

{chapter_text}

---

Emit your brief summary, then `[SCRIBE_STATE_UPDATE]`, then `[IMPORT_STATE_UPDATE]` as your final block.
"""


def _synthesize_user_prompt(state: StoryState) -> str:
    chars = [
        f"- {c.full_name} ({c.role}): {c.notes or c.internal_desire or '—'}"
        for c in state.get_all_characters()
    ]
    threads = [
        f"- {t.name} [{t.thread_type}]: {t.description}"
        for t in state.plot_threads.values()
    ]
    events = []
    for ch in sorted(state.chapters.values(), key=lambda c: c.number):
        for ev in ch.plot_advances:
            events.append(f"Ch{ch.number}: {ev}")

    return f"""# STORY SYNTHESIS — From Imported Manuscript

You have analyzed {len(state.chapters)} imported chapters. Produce a high-level story structure JSON.

## Characters ({len(chars)})
{chr(10).join(chars) or '- (none yet)'}

## Plot threads ({len(threads)})
{chr(10).join(threads) or '- (none yet)'}

## Key events (sample)
{chr(10).join(events[:40]) or '- (none yet)'}

---

Return **only** valid JSON (no markdown fences) with this shape:

{{
  "title": "...",
  "genre_hint": "...",
  "logline": "one sentence",
  "themes": ["..."],
  "acts": [
    {{"act": 1, "chapters": "1-N", "summary": "..."}}
  ],
  "chapter_summaries": [
    {{"number": 1, "title": "...", "summary": "..."}}
  ],
  "open_threads": ["..."],
  "notes": "..."
}}
"""


class ImportPipeline:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.sources_dir = self.outputs_dir / "sources"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _ensure_dirs(self) -> None:
        for d in (self.manuscript_dir, self.sources_dir, self.feedback_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _persist_chapter_draft_metadata(
        self,
        number: int,
        *,
        title: str = "",
        word_count: int,
    ) -> None:
        """Reload story state under lock, then record draft metadata before a long LLM call."""
        lock = project_state_lock(str(self.project_path))
        with lock:
            self.state._load_state()
            ch = self.state.get_chapter(number) or self.state.create_chapter(number)
            if title.strip():
                ch.title = title.strip()
            ch.status = "drafted"
            ch.word_count = word_count
            ch.last_modified = __import__("datetime").datetime.now().isoformat()
            self.state.save_state()

    def import_chapter_file(
        self,
        chapter: ChapterFile,
        *,
        extract: bool = True,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[int, List[str]]:
        """Import one chapter file. Returns (word_count, change_log)."""
        self._ensure_dirs()
        log_fn = on_progress or (lambda msg: None)
        n = chapter.number
        text = chapter.path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            raise ValueError(f"Empty chapter file: {chapter.path}")

        # Preserve original
        src_copy = self.sources_dir / f"chapter_{n:03d}{chapter.path.suffix.lower()}"
        shutil.copy2(chapter.path, src_copy)

        return self.import_chapter_text(
            n, text,
            source_label=chapter.path.name,
            extract=extract,
            dry_run=dry_run,
            on_progress=log_fn,
        )

    def import_chapter_text(
        self,
        number: int,
        text: str,
        *,
        title: str = "",
        source_label: str = "paste",
        extract: bool = True,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[int, List[str]]:
        """Import prose pasted or typed in the UI. Returns (word_count, change_log)."""
        self._ensure_dirs()
        log_fn = on_progress or (lambda msg: None)
        text = text.strip()
        if not text:
            raise ValueError("Empty chapter text")

        n = number
        src_copy = self.sources_dir / f"chapter_{n:03d}_paste.txt"
        src_copy.write_text(text, encoding="utf-8")

        word_count = len(text.split())
        draft_path = self.manuscript_dir / f"chapter_{n:03d}_draft.md"
        draft_path.write_text(text, encoding="utf-8")
        self._persist_chapter_draft_metadata(n, title=title, word_count=word_count)
        lock = project_state_lock(str(self.project_path))
        with lock:
            self.state._load_state()
            self.state.set_metadata("imported", True)
            self.state.save_state()
        log_fn(f"[{n}] saved draft ({word_count} words)")

        if not extract:
            return word_count, []

        return self._extract_chapter(n, text, source_label=source_label, dry_run=dry_run, on_progress=log_fn)

    def _extract_chapter(
        self,
        number: int,
        text: str,
        *,
        source_label: str,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[int, List[str]]:
        log_fn = on_progress or (lambda msg: None)
        n = number
        lock = project_state_lock(str(self.project_path))
        with lock:
            self.state._load_state()
            ch = self.state.get_chapter(n)
            if ch is None:
                raise ValueError(f"Chapter {n} not found")
            word_count = ch.word_count

        chunks = split_import_chunks(text)
        all_changes: List[str] = []

        for ci, chunk in enumerate(chunks, start=1):
            from job_control import check_job_cancelled  # noqa: WPS433

            check_job_cancelled()
            chunk_label = source_label
            if len(chunks) > 1:
                chunk_label = f"{source_label} §{ci}/{len(chunks)}"
                log_fn(f"[{n}] extracting chunk {ci}/{len(chunks)} via Archivist...")

            user_prompt = _archivist_user_prompt(
                n, chunk, chunk_label, chunk_index=ci, chunk_total=len(chunks),
            )
            suffix = f"_chunk{ci:02d}" if len(chunks) > 1 else ""
            prompt_path = self.feedback_dir / f"chapter_{n:03d}_import_prompt{suffix}.md"
            prompt_path.write_text(user_prompt, encoding="utf-8")

            if dry_run:
                if ci == len(chunks):
                    log_fn(f"[{n}] dry-run — prompts saved under {self.feedback_dir}")
                continue

            if len(chunks) == 1:
                log_fn(f"[{n}] extracting characters/plot via Archivist...")
            try:
                result = self._get_llm().run_agent("archivist", user_prompt)
            except LLMError as e:
                raise RuntimeError(f"Chapter {n} extraction failed: {e}") from e

            report_path = self.feedback_dir / f"chapter_{n:03d}_import_report{suffix}.md"
            report_path.write_text(result, encoding="utf-8")

            with lock:
                self.state._load_state()
                ch = self.state.get_chapter(n)
                if ch is None:
                    raise ValueError(f"Chapter {n} not found")
                changes = ingest_agent_output(self.state, n, "archivist", result)
                for line in changes:
                    log_fn(f"    • {line}")
                all_changes.extend(changes)
                self.state.set_metadata("imported", True)
                self.state.save_state()

        if dry_run:
            return word_count, []

        return word_count, all_changes

    def extract_chapter_from_draft(self, number: int, on_progress: Optional[Callable[[str], None]] = None) -> Tuple[int, List[str]]:
        """Run Archivist on the saved draft file for an existing chapter."""
        draft_path = self.manuscript_dir / f"chapter_{number:03d}_draft.md"
        if not draft_path.exists():
            raise ValueError(f"No draft text for chapter {number}")
        text = draft_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Draft is empty for chapter {number}")
        return self._extract_chapter(number, text, source_label="draft", on_progress=on_progress)

    def import_directory(
        self,
        chapters_dir: Path,
        *,
        chapter_from: Optional[int] = None,
        chapter_to: Optional[int] = None,
        extract: bool = True,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Import all chapter files from a directory."""
        files = discover_chapters(chapters_dir)
        if chapter_from is not None:
            files = [f for f in files if f.number >= chapter_from]
        if chapter_to is not None:
            files = [f for f in files if f.number <= chapter_to]
        if not files:
            raise ValueError("No chapters in selected range")

        log_fn = on_progress or print
        total_words = 0
        all_changes = 0
        for cf in files:
            from job_control import check_job_cancelled  # noqa: WPS433

            check_job_cancelled()
            wc, changes = self.import_chapter_file(
                cf, extract=extract, dry_run=dry_run, on_progress=log_fn
            )
            total_words += wc
            all_changes += len(changes)

        summary = {
            "chapters_imported": len(files),
            "total_words": total_words,
            "state_updates": all_changes,
            "characters": len(self.state.characters),
            "plot_threads": len(self.state.plot_threads),
        }
        log_fn(
            f"=== IMPORT DONE: {summary['chapters_imported']} chapters, "
            f"{summary['total_words']} words, {summary['characters']} characters, "
            f"{summary['plot_threads']} plot threads ==="
        )
        from job_control import check_job_cancelled  # noqa: WPS433

        check_job_cancelled()
        return summary

    def synthesize_structure(
        self,
        *,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Path:
        """After import, build outline.json from accumulated state via LLM."""
        log_fn = on_progress or print
        prompt = _synthesize_user_prompt(self.state)
        prompt_path = self.outputs_dir / "import_synthesize_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if dry_run:
            log_fn(f"Dry-run — synthesis prompt saved to {prompt_path}")
            return prompt_path

        log_fn("Synthesizing story structure...")
        try:
            raw = self._get_llm().complete(
                "You output only valid JSON. No commentary.",
                prompt,
            )
        except LLMError as e:
            raise RuntimeError(f"Synthesis failed: {e}") from e

        # Strip accidental fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        outline_path = self.outputs_dir / "outline.json"
        data = json.loads(raw)
        outline_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        if "logline" in data:
            self.state.story_bible["logline"] = data["logline"]
        if "themes" in data:
            self.state.story_bible["themes"] = data["themes"]
        self.state.set_metadata("structure_synthesized", True)
        self.state.save_state()
        log_fn(f"Wrote {outline_path}")
        return outline_path

    def write_character_profiles(self) -> int:
        """Export character database to outputs/characters/*.md for human review."""
        out_dir = self.outputs_dir / "characters"
        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for char in self.state.get_all_characters():
            slug = re.sub(r"[^a-z0-9]+", "_", char.full_name.lower()).strip("_")
            path = out_dir / f"{slug}.md"
            lines = [
                f"# {char.full_name}",
                "",
                f"- **Role:** {char.role}",
                f"- **Location:** {char.current_location or '—'}",
                f"- **Emotional state:** {char.emotional_state or '—'}",
                f"- **Desire:** {char.internal_desire or '—'}",
                f"- **Goal:** {char.external_goal or '—'}",
                f"- **Fear:** {char.fear or '—'}",
                f"- **Last appearance:** chapter {char.last_appearance_chapter or '—'}",
                "",
                "## Notes",
                char.notes or "—",
                "",
            ]
            path.write_text("\n".join(lines), encoding="utf-8")
            count += 1
        return count
