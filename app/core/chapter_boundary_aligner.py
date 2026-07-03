"""
Align chapter boundaries so splits fall between sentences, paragraphs, or thoughts.

Uses only a short context window around each boundary for the LLM. Text is moved
verbatim between adjacent chapters — no wording changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional, Tuple

from chapter_paragraph_formatter import prose_signature
from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from llm_client import LLMClient, LLMError
from state_manager import StoryState
from state_parser import extract_block

BOUNDARY_CONTEXT_PARAGRAPHS = 2
MoveDirection = Literal["to_previous", "to_next"]


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def tail_paragraphs(text: str, count: int = BOUNDARY_CONTEXT_PARAGRAPHS) -> str:
    paras = split_paragraphs(text)
    if not paras:
        return ""
    return "\n\n".join(paras[-count:])


def head_paragraphs(text: str, count: int = BOUNDARY_CONTEXT_PARAGRAPHS) -> str:
    paras = split_paragraphs(text)
    if not paras:
        return ""
    return "\n\n".join(paras[:count])


def pair_prose_signature(text_a: str, text_b: str) -> str:
    return prose_signature((text_a or "") + (text_b or ""))


def validate_pair_unchanged(original_a: str, original_b: str, new_a: str, new_b: str) -> None:
    if pair_prose_signature(original_a, original_b) != pair_prose_signature(new_a, new_b):
        raise ValueError(
            "Boundary alignment changed manuscript text — only relocation across the "
            "chapter boundary is allowed. No spelling fixes, word changes, or omissions."
        )


def _join_at_boundary(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    left_s = left.rstrip()
    right_s = right.lstrip()
    if left_s.endswith((".", "!", "?", "…", "”", '"')) and right_s[:1].isupper():
        return left_s + "\n\n" + right
    return left_s + right


def apply_boundary_move(
    chapter_a: str,
    chapter_b: str,
    *,
    direction: MoveDirection,
    move_text: str,
) -> tuple[str, str]:
    """Relocate move_text across the boundary between chapter_a and chapter_b."""
    move_text = move_text.replace("\r\n", "\n")
    if not move_text.strip():
        raise ValueError("move_text is empty")
    if direction == "to_previous":
        lead = len(chapter_b) - len(chapter_b.lstrip())
        rest = chapter_b[lead:]
        if not rest.startswith(move_text):
            raise ValueError("move_text does not match the start of the next chapter at the boundary")
        new_b = chapter_b[lead + len(move_text):].lstrip("\n")
        new_a = _join_at_boundary(chapter_a, move_text)
    else:
        trimmed_a = chapter_a.rstrip()
        if not trimmed_a.endswith(move_text):
            if trimmed_a.endswith(move_text.rstrip()):
                move_text = move_text.rstrip()
            else:
                raise ValueError("move_text does not match the end of the previous chapter at the boundary")
        new_a = trimmed_a[: len(trimmed_a) - len(move_text)].rstrip()
        new_b = _join_at_boundary(move_text, chapter_b)
    validate_pair_unchanged(chapter_a, chapter_b, new_a, new_b)
    return new_a, new_b


@dataclass
class BoundaryAlignmentResult:
    chapter_a: int
    chapter_b: int
    adjusted: bool
    direction: MoveDirection | None
    move_text: str
    text_a: str
    text_b: str
    original_a: str
    original_b: str


def parse_alignment_response(raw: str) -> tuple[str, MoveDirection | None, str]:
    block = extract_block(raw, "BOUNDARY_ALIGNMENT")
    if not block:
        cleaned = re.sub(r"\[/?BOUNDARY_ALIGNMENT\]", "", raw, flags=re.IGNORECASE).strip()
        block = cleaned
    status = "no_change"
    direction: MoveDirection | None = None
    move_text = ""
    in_move_text = False
    move_lines: list[str] = []
    for line in block.splitlines():
        low = line.strip().lower()
        if low.startswith("status:"):
            status = line.split(":", 1)[1].strip().lower()
        elif low.startswith("move_direction:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("to_previous", "to_next"):
                direction = val  # type: ignore[assignment]
        elif low.startswith("move_text:"):
            val = line.split(":", 1)[1].strip()
            if val == "|":
                in_move_text = True
                move_lines = []
            else:
                move_text = val
        elif in_move_text:
            if line.strip().startswith("[/") and "BOUNDARY_ALIGNMENT" in line.upper():
                break
            move_lines.append(line)
    if move_lines:
        move_text = "\n".join(move_lines).strip("\n")
    if status in ("no_change", "aligned", "none"):
        return "no_change", None, ""
    if status not in ("adjusted", "move"):
        return "no_change", None, ""
    if not direction or not move_text.strip():
        raise ValueError("Boundary alignment response missing move_direction or move_text")
    return "adjusted", direction, move_text


def _alignment_prompt(
    chapter_a: int,
    chapter_b: int,
    *,
    title_a: str,
    title_b: str,
    tail_a: str,
    head_b: str,
    source_label: str,
) -> str:
    return f"""# CHAPTER BOUNDARY ALIGNMENT — Chapters {chapter_a} and {chapter_b}

You are a **boundary editor only**. The author has already established paragraph breaks.
Your job is to decide whether the split **between** these two chapters cuts mid-sentence,
mid-paragraph, or mid-thought. If so, specify **exact text to relocate** across the boundary.

## Critical rules

- **Do NOT change, fix, or modernize any wording** — this may be an old manuscript.
- **Do NOT rewrite** — only move contiguous text from one chapter to the other.
- Copy `move_text` **character-for-character** from the context below.
- Prefer moving **whole sentences or paragraphs** when possible.
- If the boundary already falls at a natural break, return `status: no_change`.

## Chapter metadata

- **Previous chapter ({chapter_a}):** {title_a or "Untitled"}
- **Next chapter ({chapter_b}):** {title_b or "Untitled"}
- **Source stage:** {source_label}

## End of chapter {chapter_a} (context only)

```markdown
{tail_a}
```

## Start of chapter {chapter_b} (context only)

```markdown
{head_b}
```

## Output contract

Return **one** block:

```
[BOUNDARY_ALIGNMENT]
status: no_change
[/BOUNDARY_ALIGNMENT]
```

OR when text must move:

```
[BOUNDARY_ALIGNMENT]
status: adjusted
move_direction: to_previous
move_text: |
paste exact text to cut from the START of chapter {chapter_b} and append to chapter {chapter_a}
[/BOUNDARY_ALIGNMENT]
```

Use `move_direction: to_next` when text at the **end** of chapter {chapter_a} belongs in chapter {chapter_b} instead.

No commentary outside the block.
"""


class ChapterBoundaryAligner:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._reader = ChapterRegenerator(project_path)
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def meta_path(self, chapter_a: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(chapter_a)}_alignment_meta.json"

    def read_source(self, number: int, source: str) -> str:
        return self._reader.read_source(number, source)

    def write_source(self, number: int, source: str, text: str) -> None:
        path = self._reader.source_path(number, source)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def has_preview(self, chapter_a: int) -> bool:
        return self.meta_path(chapter_a).exists()

    def align_boundary(
        self,
        chapter_a: int,
        chapter_b: int | None = None,
        *,
        source: str = "draft",
        dry_run: bool = False,
        auto_apply: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> BoundaryAlignmentResult:
        log = on_progress or (lambda msg: None)
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source {source!r}")
        if chapter_b is None:
            chapter_b = chapter_a + 1
        if chapter_b <= chapter_a:
            raise ValueError("chapter_b must be greater than chapter_a")

        text_a = self.read_source(chapter_a, source)
        text_b = self.read_source(chapter_b, source)
        if not text_a.strip() or not text_b.strip():
            raise ValueError(
                f"Both chapters need {source} text to align the boundary "
                f"({chapter_a} ↔ {chapter_b})."
            )

        ch_a = self.state.get_chapter(chapter_a)
        ch_b = self.state.get_chapter(chapter_b)
        tail_a = tail_paragraphs(text_a)
        head_b = head_paragraphs(text_b)
        if not tail_a.strip() or not head_b.strip():
            raise ValueError("Chapters need paragraph breaks before boundary alignment.")

        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        user_prompt = _alignment_prompt(
            chapter_a,
            chapter_b,
            title_a=(ch_a.title if ch_a else "") or "",
            title_b=(ch_b.title if ch_b else "") or "",
            tail_a=tail_a,
            head_b=head_b,
            source_label=source,
        )
        prompt_path = self.feedback_dir / f"chapter_{self._nnn(chapter_a)}_alignment_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return BoundaryAlignmentResult(
                chapter_a=chapter_a,
                chapter_b=chapter_b,
                adjusted=False,
                direction=None,
                move_text="",
                text_a=text_a,
                text_b=text_b,
                original_a=text_a,
                original_b=text_b,
            )

        log(f"Aligning boundary {chapter_a}|{chapter_b} ({source})…")
        try:
            raw = self._get_llm().run_agent("editor", user_prompt)
        except LLMError as exc:
            raise RuntimeError(f"Boundary alignment failed: {exc}") from exc

        report_path = self.feedback_dir / f"chapter_{self._nnn(chapter_a)}_alignment_report.md"
        report_path.write_text(raw, encoding="utf-8")

        status, direction, move_text = parse_alignment_response(raw)
        new_a, new_b = text_a, text_b
        adjusted = False
        if status == "adjusted" and direction and move_text.strip():
            new_a, new_b = apply_boundary_move(
                text_a, text_b, direction=direction, move_text=move_text,
            )
            adjusted = new_a != text_a or new_b != text_b

        result = BoundaryAlignmentResult(
            chapter_a=chapter_a,
            chapter_b=chapter_b,
            adjusted=adjusted,
            direction=direction if adjusted else None,
            move_text=move_text if adjusted else "",
            text_a=new_a,
            text_b=new_b,
            original_a=text_a,
            original_b=text_b,
        )

        if auto_apply and adjusted:
            self._commit_pair(chapter_a, chapter_b, source, new_a, new_b)
            log(f"Boundary {chapter_a}|{chapter_b} aligned and saved")
            return result

        meta = {
            "chapter_a": chapter_a,
            "chapter_b": chapter_b,
            "source": source,
            "adjusted": adjusted,
            "direction": direction,
            "move_text": move_text if adjusted else "",
            "original_word_count_a": len(text_a.split()),
            "original_word_count_b": len(text_b.split()),
            "preview_word_count_a": len(new_a.split()),
            "preview_word_count_b": len(new_b.split()),
            "text_a": new_a,
            "text_b": new_b,
            "original_a": text_a,
            "original_b": text_b,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(chapter_a).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if adjusted:
            log(f"Boundary preview ready — text moved {direction}")
        else:
            log("Boundary already aligned — preview saved (no changes)")
        return result

    def _commit_pair(
        self,
        chapter_a: int,
        chapter_b: int,
        source: str,
        text_a: str,
        text_b: str,
    ) -> None:
        original_a = self.read_source(chapter_a, source)
        original_b = self.read_source(chapter_b, source)
        validate_pair_unchanged(original_a, original_b, text_a, text_b)
        self.write_source(chapter_a, source, text_a)
        self.write_source(chapter_b, source, text_b)
        for num, text in ((chapter_a, text_a), (chapter_b, text_b)):
            ch = self.state.get_chapter(num)
            if ch:
                ch.word_count = len(text.split())
        self.state.save_state()
        self.discard_preview(chapter_a)

    def discard_preview(self, chapter_a: int) -> None:
        path = self.meta_path(chapter_a)
        if path.exists():
            path.unlink()

    def apply_preview(self, chapter_a: int, *, text_a: str, text_b: str) -> None:
        meta_path = self.meta_path(chapter_a)
        if not meta_path.exists():
            raise ValueError("No boundary alignment preview to apply.")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        source = meta.get("source", "draft")
        chapter_b = int(meta["chapter_b"])
        original_a = meta.get("original_a") or self.read_source(chapter_a, source)
        original_b = meta.get("original_b") or self.read_source(chapter_b, source)
        validate_pair_unchanged(original_a, original_b, text_a, text_b)
        self._commit_pair(chapter_a, chapter_b, source, text_a, text_b)

    def align_boundaries_after_split(
        self,
        part_numbers: list[int],
        *,
        source: str = "draft",
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> int:
        """Align each internal boundary between consecutive part numbers. Returns count adjusted."""
        log = on_progress or (lambda msg: None)
        adjusted_count = 0
        for a, b in zip(part_numbers, part_numbers[1:]):
            try:
                result = self.align_boundary(
                    a, b, source=source, auto_apply=True, on_progress=log,
                )
                if result.adjusted:
                    adjusted_count += 1
            except (ValueError, RuntimeError) as exc:
                log(f"Boundary {a}|{b} alignment skipped: {exc}")
        return adjusted_count
