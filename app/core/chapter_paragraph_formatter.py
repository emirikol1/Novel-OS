"""
Insert paragraph breaks and scene-break markers without changing manuscript wording.

Preview → keep / discard. Output is rejected when any character of the prose changes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

from llm_client import LLMClient, LLMError
from state_manager import StoryState
from state_parser import extract_block

from chapter_regenerator import VALID_SOURCES

SCENE_BREAK_MARKER = "..."
SCENE_BREAK_LINE_RE = re.compile(r"^\s*\.\.\.\s*$", re.MULTILINE)


def strip_scene_break_lines(text: str) -> str:
    return SCENE_BREAK_LINE_RE.sub("", text)


def prose_signature(text: str) -> str:
    """Manuscript characters in order, ignoring all whitespace and scene-break lines."""
    return re.sub(r"\s+", "", strip_scene_break_lines(text))


def count_scene_breaks(text: str) -> int:
    return len(SCENE_BREAK_LINE_RE.findall(text))


def validate_formatting_only(original: str, formatted: str) -> None:
    if prose_signature(original) != prose_signature(formatted):
        raise ValueError(
            "Formatted text changed the manuscript — only paragraph breaks and "
            "scene breaks (... on their own line) are allowed. "
            "No spelling fixes, word changes, or omissions."
        )


def extract_formatted_chapter(text: str) -> str:
    block = extract_block(text, "FORMATTED_CHAPTER")
    if block:
        return block.strip()
    cleaned = re.sub(r"\[/?FORMATTED_CHAPTER\]", "", text, flags=re.IGNORECASE)
    return cleaned.strip()


def _paragraph_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    title: str,
) -> str:
    return f"""# PARAGRAPH & SCENE-BREAK FORMATTING — Chapter {chapter_number}

You are a **manuscript formatter only**. You must **not** edit, correct, modernize, or reword any text.
This may be a very old manuscript with archaic spelling, typos, or unfamiliar words — **leave every character as-is**.

## Your ONLY allowed changes

1. **Paragraph breaks** — insert blank lines between logical paragraphs.
2. **Scene breaks** — when POV, location, or time clearly shifts between paragraphs, insert a scene break:
   a single line containing exactly three periods:

```
...
```

Place the scene break **between** paragraphs, never mid-sentence.

## Forbidden (will cause rejection)

- Fixing spelling, grammar, or punctuation
- Adding, removing, or changing any words
- Summarizing, truncating, or reordering prose
- Adding titles, headers, or commentary outside the chapter body

## Chapter metadata

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- **Character count (approx.):** {len(source_text)}

## Source text (format this — do not rewrite)

```markdown
{source_text}
```

## Output contract

Return the **complete** chapter with formatting applied:

```
[FORMATTED_CHAPTER]
...full chapter text with new paragraph breaks and optional scene breaks...
[/FORMATTED_CHAPTER]
```

No chain-of-thought. No notes before or after the block.
"""


class ChapterParagraphFormatter:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def preview_path(self, number: int) -> Path:
        return self.manuscript_dir / f"chapter_{self._nnn(number)}_paragraphs_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_paragraphs_meta.json"

    def read_source(self, number: int, source: str) -> str:
        from chapter_regenerator import ChapterRegenerator
        return ChapterRegenerator(str(self.project_path)).read_source(number, source)

    def format_paragraphs(
        self,
        number: int,
        *,
        source: str = "draft",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        log = on_progress or (lambda msg: None)
        source = source if source in VALID_SOURCES else "draft"
        source_text = self.read_source(number, source)
        if not source_text.strip():
            raise ValueError(f"No {source} text found for chapter {number}.")

        chapter = self.state.get_chapter(number) or self.state.create_chapter(number)
        self.manuscript_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        user_prompt = _paragraph_prompt(
            number,
            source,
            source_text,
            title=chapter.title or "",
        )
        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_paragraphs_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        log(f"Formatting paragraphs for chapter {number} ({source})…")
        try:
            raw = self._get_llm().run_agent("editor", user_prompt)
        except LLMError as exc:
            raise RuntimeError(f"Paragraph formatting failed: {exc}") from exc

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_paragraphs_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = extract_formatted_chapter(raw)
        if not preview:
            raise RuntimeError("Editor returned no formatted chapter ([FORMATTED_CHAPTER] block missing)")

        validate_formatting_only(source_text, preview)

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        scene_breaks = count_scene_breaks(preview)
        meta = {
            "source": source,
            "original_word_count": len(source_text.split()),
            "preview_word_count": len(preview.split()),
            "scene_break_count": scene_breaks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Paragraph preview ready ({scene_breaks} scene break(s))")
        return preview, str(report_path)
