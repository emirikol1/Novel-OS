"""
Extract ranked landed beat candidates from chapter prose via the Archivist.

Review-first: returns candidates for author selection; apply writes landed_beats
on the chapter brief without touching required_beats.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from llm_client import LLMClient, LLMError
from state_parser import extract_block

BEAT_SOURCES = frozenset(VALID_SOURCES | {"best"})
BEST_SOURCE_ORDER = ("final", "revised", "draft")


@dataclass
class ParsedBeatCandidate:
    rank: int
    beat: str
    significance: str
    involved_characters: List[str] = field(default_factory=list)
    story_relevance: str = ""
    category: str = ""


def _split_fields(line: str) -> list[str]:
    if "|" in line:
        return [part.strip() for part in line.split("|")]
    parts = re.split(r"\s{2,}|\t", line)
    return [part.strip() for part in parts if part.strip()]


def _parse_characters(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw or raw.lower() in {"none", "n/a", "-", "[none]"}:
        return []
    return [name.strip() for name in re.split(r"[,;]", raw) if name.strip()]


def _parse_candidate_line(line: str, default_rank: int) -> Optional[ParsedBeatCandidate]:
    stripped = (line or "").strip()
    if not stripped or stripped.startswith("#"):
        return None

    stripped = re.sub(r"^[-*•]\s*", "", stripped)
    rank = default_rank
    match = re.match(r"^(\d+)\.\s*", stripped)
    if match:
        rank = int(match.group(1))
        stripped = stripped[match.end():]

    parts = _split_fields(stripped)
    if not parts:
        return None

    if len(parts) == 1:
        return ParsedBeatCandidate(rank=rank, beat=parts[0], significance="")
    if len(parts) == 2:
        return ParsedBeatCandidate(rank=rank, beat=parts[0], significance=parts[1])
    if len(parts) == 3:
        return ParsedBeatCandidate(
            rank=rank,
            category=parts[0],
            beat=parts[1],
            significance=parts[2],
        )

    return ParsedBeatCandidate(
        rank=rank,
        category=parts[0],
        beat=parts[1],
        significance=parts[2],
        involved_characters=_parse_characters(parts[3]),
        story_relevance=parts[4] if len(parts) > 4 else "",
    )


def parse_chapter_beat_candidates(text: str) -> List[ParsedBeatCandidate]:
    """Parse `[CHAPTER_BEAT_CANDIDATES]` block into ranked beat candidates."""
    block = extract_block(text, "CHAPTER_BEAT_CANDIDATES")
    if not block:
        return []

    candidates: list[ParsedBeatCandidate] = []
    for index, line in enumerate(block.splitlines(), start=1):
        parsed = _parse_candidate_line(line, index)
        if parsed and parsed.beat.strip():
            candidates.append(parsed)

    candidates.sort(key=lambda item: item.rank)
    return candidates


def _beat_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    title: str,
    count: int,
) -> str:
    return f"""# CHAPTER LANDED BEAT EXTRACTION — Chapter {chapter_number}

You are the **Archivist**. Read the chapter prose below and identify the **{count} most significant events that actually landed** in the text — concrete story beats that happened on the page, not planned beats or speculation.

Boundary rules:
- Landed beats are **chapter-local events** for review in the Chapter Brief.
- Do **not** promote landed beats into Story Bible canon.
- If a beat implies a durable world rule, setting fact, or canon relationship, mention that only in `story relevance`; Story Bible promotion is a separate reviewed Lorekeeper flow.
- Plot arcs, subplots, and structural relationships belong in the Story Graph / plot-mining workflow, not in landed beats.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- **Word count:** {len(source_text.split())}

## Chapter text

{source_text}

---

1. Optional brief note (2–3 sentences) on the chapter's structural movement.
2. Emit `[CHAPTER_BEAT_CANDIDATES]` … `[/CHAPTER_BEAT_CANDIDATES]` as your **final** block.

Inside the block, list **exactly up to {count}** ranked candidates, one per line:

```
1. category | beat summary | why it matters | involved characters (comma-separated) | story relevance
2. ...
```

Rules:
- Rank from most to least significant (1 = most significant).
- **category** examples: turning_point, revelation, confrontation, decision, setup, payoff, relationship_shift, local_world_detail
- **beat summary** — one sentence describing what happened.
- **why it matters** — one sentence on narrative significance.
- Extract only what the prose supports; do not invent events.
- Use full character names when known.
- Do not wrap the block in code fences.

Write the ranked candidates now.
"""


class ChapterBeatExtractor:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = self._reader_state(project_path)
        self._reader = ChapterRegenerator(project_path, llm=llm)
        self._llm = llm

    @staticmethod
    def _reader_state(project_path: str):
        from state_manager import StoryState  # noqa: WPS433

        return StoryState(str(project_path))

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    @staticmethod
    def _nnn(number: int) -> str:
        return f"{number:03d}"

    def resolve_source_text(self, number: int, source: str) -> Tuple[str, str]:
        if source not in BEAT_SOURCES:
            raise ValueError(f"Invalid source {source!r}; expected best, draft, revised, or final")
        if source == "best":
            for stage in BEST_SOURCE_ORDER:
                try:
                    return stage, self._reader.read_source(number, stage)
                except (FileNotFoundError, ValueError):
                    continue
            raise FileNotFoundError(
                f"No final, revised, or draft text found for chapter {number}",
            )
        return source, self._reader.read_source(number, source)

    def extract(
        self,
        number: int,
        *,
        source: str = "best",
        count: int = 10,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[ParsedBeatCandidate], str, str]:
        log = on_progress or (lambda msg: None)
        if count < 1 or count > 20:
            raise ValueError("count must be between 1 and 20")

        source_label, source_text = self.resolve_source_text(number, source)
        chapter = self.state.get_chapter(number) or self.state.create_chapter(number)
        title = chapter.title or ""

        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        nnn = self._nnn(number)
        prompt = _beat_prompt(number, source_label, source_text, title=title, count=count)
        prompt_path = self.feedback_dir / f"chapter_{nnn}_beat_candidates_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return [], source_label, str(prompt_path)

        log(f"Extracting landed beat candidates from chapter {number} ({source_label})…")
        try:
            raw = self._get_llm().run_agent("archivist", prompt)
        except LLMError as exc:
            raise RuntimeError(f"Beat candidate extraction failed: {exc}") from exc

        report_path = self.feedback_dir / f"chapter_{nnn}_beat_candidates_report.md"
        report_path.write_text(raw, encoding="utf-8")

        candidates = parse_chapter_beat_candidates(raw)
        if not candidates:
            raise RuntimeError(
                "Archivist returned no beat candidates ([CHAPTER_BEAT_CANDIDATES] block missing or empty)",
            )

        meta_path = self.feedback_dir / f"chapter_{nnn}_beat_candidates_meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "source": source,
                    "source_used": source_label,
                    "count_requested": count,
                    "candidates_found": len(candidates),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log(f"Found {len(candidates)} beat candidate(s)")
        return candidates[:count], source_label, str(report_path)
