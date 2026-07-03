"""
Generate a short chapter title from prose via the Architect agent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from batch_extract import resolve_chapter_source
from chapter_regenerator import ChapterRegenerator
from llm_client import LLMClient, LLMError
from state_parser import _strip_model_reasoning, extract_block

BATCH_SOURCES = frozenset({"best", "draft", "revised", "final"})
_PLACEHOLDER = frozenset({"untitled", "tbd", "n/a", "none", ""})
_MAX_TITLE_LEN = 120


def _excerpt_for_title(text: str, max_words: int = 2400) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    head = (max_words * 2) // 3
    tail = max_words - head
    return (
        " ".join(words[:head])
        + "\n\n[… middle omitted for length …]\n\n"
        + " ".join(words[-tail:])
    )


def _title_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    book_title: str,
    genre: str,
) -> str:
    excerpt = _excerpt_for_title(source_text)
    meta = []
    if book_title.strip():
        meta.append(f"- **Book title:** {book_title.strip()}")
    if genre.strip():
        meta.append(f"- **Genre:** {genre.strip()}")
    meta_block = "\n".join(meta)
    if meta_block:
        meta_block = meta_block + "\n"
    return f"""# CHAPTER TITLE — Chapter {chapter_number}

You are the **Architect**. Read the chapter prose below and propose one **evocative chapter title**
(2–6 words, title case). Do not include the chapter number. Avoid spoilers; hint at mood or theme.

{meta_block}- **Source stage:** {source_label}
- **Prose word count:** {len(source_text.split())}

## Chapter prose ({source_label})

```markdown
{excerpt}
```

## Output contract

Return **only**:
```
[CHAPTER_TITLE]
<your title>
[/CHAPTER_TITLE]
```

No chain-of-thought, no alternate options, no quotation marks around the title.
"""


def parse_chapter_title(raw: str) -> str:
    block = extract_block(raw, "CHAPTER_TITLE")
    if not block:
        cleaned = _strip_model_reasoning(raw)
        cleaned = re.sub(r"\[/?CHAPTER_TITLE\]", "", cleaned, flags=re.IGNORECASE)
        block = cleaned.strip()
    title = re.sub(r"^#+\s*", "", block.strip())
    title = title.strip(" \"'“”‘’")
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > _MAX_TITLE_LEN:
        title = title[:_MAX_TITLE_LEN].rstrip()
    if not title or title.lower() in _PLACEHOLDER:
        raise ValueError("Model returned an empty or placeholder chapter title.")
    if re.fullmatch(r"chapter\s+\d+[a-z]?", title, flags=re.IGNORECASE):
        raise ValueError("Model returned a generic chapter number instead of a title.")
    return title


class ChapterTitleGenerator:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self._reader = ChapterRegenerator(str(self.project_path), llm=llm)
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def generate(
        self,
        number: int,
        *,
        source: str = "best",
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> str:
        if source not in BATCH_SOURCES:
            raise ValueError(f"Invalid source {source!r}; expected best, draft, revised, or final")
        found = resolve_chapter_source(self._reader, number, source)
        if found is None:
            raise FileNotFoundError(
                f"No {source if source != 'best' else 'final/revised/draft'} text found for chapter {number}."
            )
        stage_label, text = found
        if not text.strip():
            raise ValueError(f"Chapter {number} has no prose to title.")

        state = self._reader.state
        state._load_state()
        book_title = str(state.metadata.get("title", "") or "")
        genre = str(state.metadata.get("genre", "") or "")

        prompt = _title_prompt(
            number,
            stage_label,
            text,
            book_title=book_title,
            genre=genre,
        )
        log = on_progress or (lambda _msg: None)
        log(f"Generating title for chapter {number} ({stage_label})…")
        try:
            raw = self._get_llm().run_agent("architect", prompt)
        except LLMError as exc:
            raise RuntimeError(f"Chapter title generation failed: {exc}") from exc
        return parse_chapter_title(raw)
