"""
Split an oversized chapter into sequential parts (1a, 1b, 1c, …).

Each part becomes its own chapter row and manuscript draft file, inserted
immediately after the parent slot so reading order is preserved.

Split is transactional: a pre-split backup is written first; prose files are
updated only after all chapter renames preflight cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from chapter_files import (
    apply_chapter_file_renames,
    chapter_file_rename_steps,
    preflight_chapter_file_renames,
)
from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from log_redaction import safe_log
from prompt_budget import DEFAULT_SPLIT_WORDS, part_label, split_text_chunks, word_count
from state_manager import StoryState, project_state_lock


@dataclass
class ChapterSplitResult:
    parent_number: int
    parts: List[dict]
    total_words: int
    recovered_from_backup: bool = False


class ChapterSplitError(RuntimeError):
    """Split failed; pre-split backup may exist under outputs/feedback/."""


class ChapterSplitter:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        self._reader = ChapterRegenerator(project_path)

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def _backup_path(self, number: int, source: str) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_pre_split_{source}.md"

    def _write_stage(self, number: int, source: str, text: str) -> None:
        path = self._reader.source_path(number, source)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _resolve_source_text(self, number: int, source: str) -> tuple[str, bool]:
        """Return prose to split; use pre-split backup when a prior attempt truncated the stage."""
        text = self._reader.read_source(number, source)
        backup = self._backup_path(number, source)
        if backup.exists():
            backup_text = backup.read_text(encoding="utf-8").strip()
            if backup_text and word_count(backup_text) > word_count(text):
                safe_log(
                    f"Chapter {number} split retry — using pre-split backup "
                    f"(~{word_count(backup_text):,} words vs current ~{word_count(text):,})."
                )
                return backup_text, True
        if word_count(text) < DEFAULT_SPLIT_WORDS:
            imported = self._import_source_text(number)
            if imported and word_count(imported) > word_count(text):
                safe_log(
                    f"Chapter {number} split retry — using imported source copy "
                    f"(~{word_count(imported):,} words)."
                )
                return imported, True
        return text, False

    def _import_source_text(self, number: int) -> str:
        """Best-effort original import copy when draft was truncated by a failed split."""
        nnn = self._nnn(number)
        sources = self.outputs_dir / "sources"
        if not sources.is_dir():
            return ""
        candidates = sorted(sources.glob(f"chapter_{nnn}*"))
        best = ""
        best_wc = 0
        for path in candidates:
            if not path.is_file():
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            wc = word_count(body)
            if wc > best_wc:
                best = body
                best_wc = wc
        return best

    def _shift_chapters_up(
        self,
        state: StoryState,
        *,
        after_number: int,
        shift: int,
    ) -> None:
        if shift <= 0:
            return
        to_shift = sorted((n for n in state.chapters if n > after_number), reverse=True)
        steps: list[tuple[Path, Path]] = []
        for old in to_shift:
            steps.extend(chapter_file_rename_steps(self.project_path, old, old + shift))
        if steps:
            preflight_chapter_file_renames(self.project_path, steps)
            apply_chapter_file_renames(steps)
        for old in reversed(to_shift):
            state.reassign_chapter(old, old + shift)

    def _title_for_part(self, base_title: str, parent: int, label: str) -> str:
        suffix = f"({parent}{label})"
        if not base_title:
            return f"Chapter {parent}{label}"
        if suffix in base_title or base_title.endswith(f"{parent}{label})"):
            return base_title
        return f"{base_title} {suffix}"

    def split_chapter(
        self,
        number: int,
        *,
        source: str = "draft",
        max_words: Optional[int] = None,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> ChapterSplitResult:
        log = on_progress or (lambda msg: None)
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source {source!r}")

        text, recovered = self._resolve_source_text(number, source)
        limit = max_words or DEFAULT_SPLIT_WORDS
        chunks = split_text_chunks(text, max_words=limit)
        if len(chunks) <= 1:
            wc = word_count(text)
            lock = project_state_lock(str(self.project_path))
            with lock:
                state = StoryState(str(self.project_path))
                chapter = state.get_chapter(number)
                part_label_set = chapter and (getattr(chapter, "part_label", "") or "").strip()
                backup = self._backup_path(number, source)
            if part_label_set and backup.exists():
                raise ChapterSplitError(
                    f"Chapter {number} looks partially split (label {part_label_set!r}) but only "
                    f"~{wc:,} words remain in {source}. A pre-split backup exists at "
                    f"{backup.name} — retry split to recover and finish, or restore that file manually."
                )
            safe_log(f"Chapter {number} is ~{wc} words — no split needed (limit {limit}).")
            return ChapterSplitResult(
                parent_number=number,
                parts=[{"number": number, "display_label": str(number), "word_count": wc}],
                total_words=wc,
                recovered_from_backup=recovered,
            )

        shift = len(chunks) - 1
        lock = project_state_lock(str(self.project_path))
        with lock:
            state = StoryState(str(self.project_path))
            chapter = state.get_chapter(number)
            if chapter is None:
                raise ValueError(f"Chapter {number} not found")

            base_title = (chapter.title or "").strip()
            parent = number
            part_rows: List[dict] = []

            if dry_run:
                for idx, chunk in enumerate(chunks):
                    label = part_label(idx)
                    part_rows.append({
                        "number": number + idx,
                        "display_label": f"{parent}{label}",
                        "word_count": word_count(chunk),
                    })
                log(
                    f"Dry-run — would split chapter {number} into {len(chunks)} parts "
                    f"({', '.join(r['display_label'] for r in part_rows)})"
                )
                return ChapterSplitResult(
                    parent_number=parent,
                    parts=part_rows,
                    total_words=word_count(text),
                    recovered_from_backup=recovered,
                )

            self.feedback_dir.mkdir(parents=True, exist_ok=True)
            self._backup_path(number, source).write_text(text, encoding="utf-8")

            try:
                self._shift_chapters_up(state, after_number=number, shift=shift)

                for idx, chunk in enumerate(chunks):
                    ch_num = number + idx
                    label = part_label(idx)
                    if idx == 0:
                        target = chapter
                    else:
                        target = state.create_chapter(
                            ch_num,
                            self._title_for_part(base_title, parent, label),
                        )
                    target.part_of = parent
                    target.part_label = label
                    target.status = "drafted"
                    target.word_count = word_count(chunk)
                    if idx == 0:
                        target.title = self._title_for_part(base_title, parent, label)
                    self._write_stage(ch_num, source, chunk)
                    part_rows.append({
                        "number": ch_num,
                        "display_label": f"{parent}{label}",
                        "word_count": target.word_count,
                    })
                    log(f"[{parent}{label}] saved {target.word_count} words at chapter {ch_num}")

                state.save_state()
            except (FileExistsError, FileNotFoundError, OSError) as exc:
                raise ChapterSplitError(
                    f"Chapter split failed before completing (nothing new was saved to story state). "
                    f"Pre-split backup preserved at {self._backup_path(number, source).name}. "
                    f"Resolve the file collision, then retry split. Detail: {exc}"
                ) from exc

        return ChapterSplitResult(
            parent_number=parent,
            parts=part_rows,
            total_words=word_count(text),
            recovered_from_backup=recovered,
        )
