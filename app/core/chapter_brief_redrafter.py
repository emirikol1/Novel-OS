"""
Redraft chapter prose from a saved chapter brief + reference text via the Scribe agent.

Writes a preview file only — apply saves to draft only (never revised/final).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

from chapter_brief_utils import brief_has_content
from chapter_prompt_builder import build_scribe_context_block
from chapter_regenerator import ChapterRegenerator, VALID_SOURCES, extract_chapter_prose
from llm_client import LLMClient, LLMError
from state_manager import StoryState


VALID_MODES = frozenset({"align", "preserve"})


def _mode_instructions(mode: str) -> str:
    if mode == "preserve":
        return (
            "**Preserve mode:** Keep the same events, scene order, and major story beats from "
            "the reference prose. Adjust wording, detail, and emphasis so the chapter **aligns "
            "with the chapter brief** without restructuring the narrative."
        )
    return (
        "**Align mode:** The chapter brief is **authoritative**. Rewrite the chapter as needed "
        "so it fulfills the brief — POV, required beats, continuity notes, and ending hook — "
        "even if that means reordering or replacing scenes from the reference prose."
    )


def _redraft_prompt(
    chapter_number: int,
    *,
    title: str,
    source_label: str,
    source_text: str,
    context_block: str,
    mode: str,
    instructions: str,
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    context = f"\n{context_block}\n" if context_block.strip() else ""
    return f"""# CHAPTER REDRAFT FROM BRIEF — Chapter {chapter_number}

Redraft the chapter below using the **chapter brief** and story context as your guide.
Output the **full chapter** — do not summarize.

- **Chapter title:** {title or "Untitled"}
- **Reference stage:** {source_label}
- **Redraft mode:** {mode}
- **Reference word count:** {len(source_text.split())}

{_mode_instructions(mode)}
{context}
## Reference prose ({source_label})

```markdown
{source_text}
```
{extra}

## Output contract

1. Optional brief note (2–3 sentences) on how the redraft follows the brief.
2. `[REVISED_CHAPTER]` … `[/REVISED_CHAPTER]` containing the **complete** redrafted chapter prose.
3. Do **not** emit chain-of-thought or reasoning blocks.

Redraft the chapter now.
"""


class ChapterBriefRedrafter:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm
        self._source_reader = ChapterRegenerator(str(self.project_path), llm=llm)

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def preview_path(self, number: int) -> Path:
        return self.manuscript_dir / f"chapter_{self._nnn(number)}_redraft_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_redraft_meta.json"

    def read_source(self, number: int, source: str) -> str:
        return self._source_reader.read_source(number, source)

    def redraft(
        self,
        number: int,
        *,
        source: str = "final",
        mode: str = "align",
        instructions: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        """Run Scribe redraft; save preview + meta. Returns (preview_text, report_path)."""
        log = on_progress or (lambda msg: None)

        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source {source!r}")
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode {mode!r}; use align or preserve")

        brief = self.state.get_chapter_brief(number)
        if not brief_has_content(brief):
            raise ValueError(f"Chapter {number} has no saved brief with content")

        source_text = self.read_source(number, source)

        chapter = self.state.get_chapter(number)
        if not chapter:
            chapter = self.state.create_chapter(number)

        self.manuscript_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        outline_path = self.outputs_dir / f"chapter_{self._nnn(number)}_outline.md"
        outline_text = outline_path.read_text(encoding="utf-8").strip() if outline_path.exists() else ""

        context_block = build_scribe_context_block(
            self.state,
            chapter,
            hint_text="\n".join(
                part for part in (instructions, source_text[:4000]) if (part or "").strip()
            ),
            outline_text=outline_text or None,
        )

        user_prompt = _redraft_prompt(
            number,
            title=chapter.title or "",
            source_label=source,
            source_text=source_text,
            context_block=context_block,
            mode=mode,
            instructions=instructions,
        )
        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_redraft_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        log(f"Redrafting chapter {number} from {source} ({mode} mode) via Scribe…")
        try:
            raw = self._get_llm().run_agent("scribe", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Chapter redraft failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_redraft_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = extract_chapter_prose(raw)
        if not preview:
            raise RuntimeError("Scribe returned no chapter prose ([REVISED_CHAPTER] block missing)")

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        meta = {
            "source": source,
            "mode": mode,
            "instructions": instructions.strip(),
            "original_word_count": len(source_text.split()),
            "preview_word_count": len(preview.split()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Redraft preview ready ({meta['preview_word_count']} words)")
        return preview, str(report_path)
