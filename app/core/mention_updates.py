"""
Conservative mention-based memory update suggestions and reviewed apply.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from mentions import build_mention_targets, resolve_mentions_in_text, strip_mentions
from llm_client import LLMClient, LLMError
from log_redaction import size_ref

if TYPE_CHECKING:
    from state_manager import StoryState

ALLOWED_CHARACTER_FIELDS = frozenset({
    "current_location",
    "emotional_state",
    "knowledge",
    "notes",
    "last_appearance_chapter",
})

def _presence_patterns(char_name: str) -> tuple[str, ...]:
    escaped = re.escape(char_name)
    return (
        rf"\b{escaped}\b\s+(?:said|asked|replied|whispered|shouted|muttered|growled|sighed)",
        rf"\b{escaped}\b\s+(?:walked|ran|entered|left|stood|sat|looked|turned)",
        rf"\b{escaped}\b\s+(?:was|is)\s+(?:in|at|on)\b",
    )


@dataclass
class MentionFieldEdit:
    character_id: str
    character_name: str
    field: str
    current_value: Any
    suggested_value: Any
    reason: str
    explicit_presence: bool = False
    mention_label: str = ""
    mention_raw: str = ""


@dataclass
class MentionSuggestionsBundle:
    chapter_number: int
    source: str
    suggestions: List[MentionFieldEdit] = field(default_factory=list)
    generated_at: str = ""
    source_text_word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "chapter_number": self.chapter_number,
            "source": self.source,
            "generated_at": self.generated_at,
            "source_text_word_count": self.source_text_word_count,
            "suggestions": [asdict(s) for s in self.suggestions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MentionSuggestionsBundle":
        suggestions = [MentionFieldEdit(**s) for s in data.get("suggestions", [])]
        return cls(
            chapter_number=int(data.get("chapter_number", 0)),
            source=data.get("source", "draft"),
            suggestions=suggestions,
            generated_at=data.get("generated_at", ""),
            source_text_word_count=int(data.get("source_text_word_count", 0)),
        )


def _char_by_name(state: "StoryState", name: str):
    want = name.strip().lower()
    for char in state.get_all_characters():
        if char.full_name.strip().lower() == want:
            return char
        if any(a.strip().lower() == want for a in char.aliases):
            return char
    return None


def _detect_explicit_presence(char_name: str, chapter_text: str, pov: str) -> bool:
    plain = strip_mentions(chapter_text)
    if pov and pov.strip().lower() == char_name.strip().lower():
        if re.search(rf"\b{re.escape(char_name)}\b", plain, re.I):
            return any(re.search(p, plain, re.I) for p in _presence_patterns(char_name))
    return any(re.search(p, plain, re.I) for p in _presence_patterns(char_name))


def suggest_conservative_updates(
    state: "StoryState",
    chapter_number: int,
    text: str,
    *,
    source: str = "draft",
) -> MentionSuggestionsBundle:
    """Heuristic suggestions — only last_appearance when explicit on-page presence is detected."""
    targets = build_mention_targets(state)
    resolved = resolve_mentions_in_text(text, targets)
    chapter = state.get_chapter(chapter_number)
    pov = chapter.pov_character if chapter else ""
    suggestions: List[MentionFieldEdit] = []
    seen: set[tuple[str, str]] = set()

    for rm in resolved:
        if rm.broken or rm.kind != "char" or not rm.target or not rm.target.id:
            continue
        char = state.get_character(rm.target.id)
        if not char:
            continue
        key = (char.id, "last_appearance_chapter")
        if key in seen:
            continue
        if not _detect_explicit_presence(char.full_name, text, pov):
            continue
        seen.add(key)
        if char.last_appearance_chapter >= chapter_number:
            continue
        suggestions.append(MentionFieldEdit(
            character_id=char.id,
            character_name=char.full_name,
            field="last_appearance_chapter",
            current_value=char.last_appearance_chapter,
            suggested_value=chapter_number,
            reason="Character appears to be directly present in scene (POV or action/dialogue cues).",
            explicit_presence=True,
            mention_label=rm.label,
            mention_raw=rm.raw,
        ))

    return MentionSuggestionsBundle(
        chapter_number=chapter_number,
        source=source,
        suggestions=suggestions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_text_word_count=len(text.split()),
    )


def _llm_suggest_prompt(chapter_number: int, text: str, state: "StoryState") -> str:
    char_lines = []
    for char in state.get_all_characters():
        char_lines.append(
            f"- {char.id}: {char.full_name} | loc={char.current_location or '?'} | "
            f"emotion={char.emotional_state or '?'} | last_ch={char.last_appearance_chapter}"
        )
    return f"""# MENTION MEMORY SUGGESTIONS — Chapter {chapter_number}

Read the chapter prose and any resolved [[char:...]] mentions. Suggest **conservative** updates
to character memory fields ONLY when the text clearly supports them.

Allowed fields per character: current_location, emotional_state, knowledge (list), notes, last_appearance_chapter.

Rules:
- A mere mention, rumor, flashback, or hypothetical does NOT justify last_appearance_chapter.
- Only set last_appearance_chapter when the character is directly present in the scene.
- Do not invent facts not supported by the prose.
- Omit characters with no justified changes.

## Current cast
{chr(10).join(char_lines[:40])}

## Chapter text
{text[:12000]}

---

Emit a final block:

[MENTION_MEMORY_SUGGESTIONS]
Character_ID: char_001
Field: current_location
Suggested: Market Square
Reason: Scene opens with her standing in the market.
Explicit_Presence: no

Character_ID: char_001
Field: last_appearance_chapter
Suggested: {chapter_number}
Reason: POV and on-page dialogue throughout the chapter.
Explicit_Presence: yes
"""


def _parse_llm_suggestions(raw: str, state: "StoryState", chapter_number: int) -> List[MentionFieldEdit]:
    if "[MENTION_MEMORY_SUGGESTIONS]" not in raw:
        return []
    block = raw.split("[MENTION_MEMORY_SUGGESTIONS]", 1)[1]
    if "[" in block:
        block = block.split("[", 1)[0]
    entries: List[MentionFieldEdit] = []
    current: Dict[str, str] = {}

    def flush() -> None:
        nonlocal current
        if not current.get("Character_ID") or not current.get("Field"):
            current = {}
            return
        cid = current["Character_ID"].strip()
        field_name = current["Field"].strip()
        if field_name not in ALLOWED_CHARACTER_FIELDS:
            current = {}
            return
        char = state.get_character(cid)
        if not char:
            current = {}
            return
        suggested_raw = current.get("Suggested", "").strip()
        if field_name == "last_appearance_chapter":
            explicit = current.get("Explicit_Presence", "").strip().lower() in ("yes", "true", "1")
            if not explicit:
                current = {}
                return
            try:
                suggested_val = int(suggested_raw)
            except ValueError:
                current = {}
                return
        elif field_name == "knowledge":
            suggested_val = [s.strip() for s in suggested_raw.split(";") if s.strip()]
        else:
            suggested_val = suggested_raw
        current_val = getattr(char, field_name, "")
        entries.append(MentionFieldEdit(
            character_id=cid,
            character_name=char.full_name,
            field=field_name,
            current_value=current_val,
            suggested_value=suggested_val,
            reason=current.get("Reason", "LLM suggestion").strip(),
            explicit_presence=field_name == "last_appearance_chapter",
            mention_label=char.full_name,
            mention_raw="",
        ))
        current = {}

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if ":" not in stripped:
            continue
        k, v = stripped.split(":", 1)
        current[k.strip()] = v.strip()
    flush()
    return entries


def suggest_with_llm(
    state: "StoryState",
    chapter_number: int,
    text: str,
    *,
    source: str = "draft",
    llm: Optional[LLMClient] = None,
) -> MentionSuggestionsBundle:
    client = llm or LLMClient()
    prompt = _llm_suggest_prompt(chapter_number, text, state)
    try:
        raw = client.run_agent("archivist", prompt)
    except LLMError as e:
        raise RuntimeError(f"Mention suggestion LLM failed: {e}") from e
    llm_suggestions = _parse_llm_suggestions(raw, state, chapter_number)
    base = suggest_conservative_updates(state, chapter_number, text, source=source)
    merged: Dict[tuple[str, str], MentionFieldEdit] = {
        (s.character_id, s.field): s for s in base.suggestions
    }
    for s in llm_suggestions:
        merged[(s.character_id, s.field)] = s
    return MentionSuggestionsBundle(
        chapter_number=chapter_number,
        source=source,
        suggestions=list(merged.values()),
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_text_word_count=len(text.split()),
    )


def apply_reviewed_edits(
    state: "StoryState",
    chapter_number: int,
    edits: List[Dict[str, Any]],
) -> List[str]:
    """Apply author-approved field values. Never runs without explicit edits list."""
    log: List[str] = []
    for edit in edits:
        cid = str(edit.get("character_id", "")).strip()
        field_name = str(edit.get("field", "")).strip()
        if not cid or field_name not in ALLOWED_CHARACTER_FIELDS:
            raise ValueError(f"Invalid edit: character_id={cid!r} field={field_name!r}")
        char = state.get_character(cid)
        if not char:
            raise ValueError(f"Unknown character: {cid}")
        value = edit.get("value")
        if field_name == "last_appearance_chapter":
            if not edit.get("explicit_presence"):
                raise ValueError(
                    f"last_appearance_chapter for {cid} requires explicit_presence approval"
                )
            try:
                value = int(value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid last_appearance_chapter: {value!r}") from e
        elif field_name == "knowledge":
            if not isinstance(value, list):
                raise ValueError("knowledge must be a list of strings")
            value = [str(v).strip() for v in value if str(v).strip()]
        else:
            value = str(value) if value is not None else ""
        old = getattr(char, field_name)
        if old == value:
            continue
        state.update_character(cid, {field_name: value})
        log.append(f"{cid}.{field_name} updated ({size_ref(str(old))} -> {size_ref(str(value))})")
    if log:
        state._log_action("mention_memory_apply", {"chapter": chapter_number, "edits": len(edits)})
    return log


class MentionSuggestionsStore:
    """Persist suggestion bundles under outputs/feedback/."""

    def __init__(self, project_path: str | Path):
        self.feedback_dir = Path(project_path) / "outputs" / "feedback"

    def _path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{number:03d}_mention_suggestions.json"

    def save(self, bundle: MentionSuggestionsBundle) -> Path:
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(bundle.chapter_number)
        path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
        return path

    def load(self, number: int) -> Optional[MentionSuggestionsBundle]:
        path = self._path(number)
        if not path.exists():
            return None
        return MentionSuggestionsBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def discard(self, number: int) -> None:
        path = self._path(number)
        if path.exists():
            path.unlink()
