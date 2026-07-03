"""Deterministic timeline extraction from chapter prose.

This intentionally avoids requiring an LLM server. It produces reviewable
candidate events from manuscript text; callers decide what to save.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable


EVENT_TYPES = frozenset({"scene", "backstory", "flashback", "summary"})
SIGNIFICANCE = frozenset({"minor", "major", "turning_point", "climax"})

_SCENE_BREAK_RE = re.compile(r"\n\s*(?:\*\s*\*\s*\*|---+|#{1,3}\s+.+)\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_DAY_RE = re.compile(r"\bday\s+(\d{1,3})\b", re.IGNORECASE)
_TIME_RE = re.compile(
    r"\b(?:at\s+)?((?:dawn|noon|midnight|dusk|morning|afternoon|evening|night)|\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:at|inside|outside|in|on|near)\s+(?:the\s+)?([A-Z][A-Za-z0-9' -]{2,40}?)(?=\s+(?:on|at|before|after|during|when|where|with|and)\b|[,.!?;]|$)",
    re.IGNORECASE,
)
_FLASHBACK_HINTS = ("remembered", "years ago", "when she was", "when he was", "flashback")
_TURNING_HINTS = ("revealed", "betrayed", "decided", "discovered", "confessed", "escaped")
_CLIMAX_HINTS = ("confronted", "killed", "died", "exploded", "finally", "last chance")


@dataclass
class TimelineCandidate:
    description: str
    chapter: int
    day: int | None = None
    time: str | None = None
    location: str = ""
    characters_present: list[str] | None = None
    event_type: str = "scene"
    significance: str = "minor"
    source: str = "best"
    excerpt: str = ""
    score: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["characters_present"] = data["characters_present"] or []
        return data


def extract_timeline_candidates(
    chapters: Iterable[tuple[int, str, str]],
    characters: dict[str, list[str]],
    *,
    max_events_per_chapter: int = 5,
) -> list[TimelineCandidate]:
    """Extract reviewable timeline events from ``(chapter, source, text)`` rows."""
    candidates: list[TimelineCandidate] = []
    for chapter, source, text in chapters:
        chapter_candidates: list[TimelineCandidate] = []
        for excerpt in _event_excerpts(text):
            candidate = _candidate_from_excerpt(chapter, source, excerpt, characters)
            if candidate.description:
                chapter_candidates.append(candidate)
        chapter_candidates.sort(key=lambda c: (-c.score, c.description))
        candidates.extend(chapter_candidates[:max(1, max_events_per_chapter)])
    return candidates


def _event_excerpts(text: str) -> list[str]:
    chunks: list[str] = []
    for scene in _SCENE_BREAK_RE.split(text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", scene) if p.strip()]
        if not paragraphs and scene.strip():
            paragraphs = [scene.strip()]
        for paragraph in paragraphs:
            normalized = re.sub(r"\s+", " ", paragraph).strip()
            if len(normalized.split()) < 12:
                continue
            chunks.append(normalized)
    if chunks:
        return chunks
    normalized = re.sub(r"\s+", " ", text).strip()
    return [normalized] if normalized else []


def _candidate_from_excerpt(
    chapter: int,
    source: str,
    excerpt: str,
    characters: dict[str, list[str]],
) -> TimelineCandidate:
    lowered = excerpt.lower()
    description = _description(excerpt)
    day = _extract_day(excerpt)
    time = _extract_time(excerpt)
    location = _extract_location(excerpt)
    present = _characters_present(excerpt, characters)
    score, reason = _score_candidate(lowered, day, time, location, present)
    return TimelineCandidate(
        description=description,
        chapter=chapter,
        day=day,
        time=time,
        location=location,
        characters_present=present,
        event_type=_event_type(lowered),
        significance=_significance(lowered),
        source=source,
        excerpt=excerpt[:320],
        score=score,
        reason=reason,
    )


def _description(excerpt: str) -> str:
    sentence = _SENTENCE_RE.split(excerpt, maxsplit=1)[0].strip()
    sentence = re.sub(r"^#+\s*", "", sentence)
    if len(sentence) <= 180:
        return sentence
    return sentence[:177].rstrip() + "..."


def _extract_day(excerpt: str) -> int | None:
    match = _DAY_RE.search(excerpt)
    return int(match.group(1)) if match else None


def _extract_time(excerpt: str) -> str | None:
    match = _TIME_RE.search(excerpt)
    return match.group(1).strip() if match else None


def _extract_location(excerpt: str) -> str:
    for match in _LOCATION_RE.finditer(excerpt):
        candidate = match.group(1).strip(" .,;:!?")
        lowered = candidate.lower()
        if lowered.startswith("day ") or lowered in {"morning", "afternoon", "evening", "night"}:
            continue
        return candidate
    return ""


def _characters_present(excerpt: str, characters: dict[str, list[str]]) -> list[str]:
    found: list[str] = []
    lowered = excerpt.lower()
    for character_id, names in characters.items():
        if any(_name_in_text(name, lowered) for name in names if name.strip()):
            found.append(character_id)
    return found


def _name_in_text(name: str, lowered_text: str) -> bool:
    escaped = re.escape(name.lower())
    return re.search(rf"\b{escaped}\b", lowered_text) is not None


def _event_type(lowered: str) -> str:
    if any(hint in lowered for hint in _FLASHBACK_HINTS):
        return "flashback"
    if "summarized" in lowered or "over the next" in lowered:
        return "summary"
    return "scene"


def _significance(lowered: str) -> str:
    if any(hint in lowered for hint in _CLIMAX_HINTS):
        return "climax"
    if any(hint in lowered for hint in _TURNING_HINTS):
        return "turning_point"
    return "major" if len(lowered.split()) >= 55 else "minor"


def _score_candidate(
    lowered: str,
    day: int | None,
    time: str | None,
    location: str,
    characters_present: list[str],
) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    if any(hint in lowered for hint in _CLIMAX_HINTS):
        score += 8
        reasons.append("climax/action cue")
    if any(hint in lowered for hint in _TURNING_HINTS):
        score += 7
        reasons.append("turning-point cue")
    if characters_present:
        score += min(5, len(characters_present) * 2)
        reasons.append("named character present")
    if location:
        score += 2
        reasons.append("location found")
    if day is not None or time:
        score += 2
        reasons.append("time marker found")
    if any(hint in lowered for hint in _FLASHBACK_HINTS):
        score += 2
        reasons.append("flashback/backstory cue")
    word_count = len(lowered.split())
    if 18 <= word_count <= 90:
        score += 1
        reasons.append("scene-sized passage")
    return score, ", ".join(reasons) or "substantial chapter passage"
