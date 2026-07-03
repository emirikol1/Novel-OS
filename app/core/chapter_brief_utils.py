"""Helpers for chapter brief validation, cast inference, and beat prompt assembly."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, List, Tuple

from story_graph import ChapterBeat, ChapterBrief

if TYPE_CHECKING:
    from state_manager import StoryState


def brief_has_content(brief: ChapterBrief | None) -> bool:
    """True when the brief has at least one author-selected planning field."""
    if brief is None:
        return False
    return bool(
        (brief.pov_character_id or "").strip()
        or (brief.pov_mode or "").strip()
        or (getattr(brief, "tone", "") or "").strip()
        or (getattr(brief, "tense", "") or "").strip()
        or (getattr(brief, "prose_style", "") or "").strip()
        or (getattr(brief, "vocabulary_level", "") or "").strip()
        or (getattr(brief, "style_notes", "") or "").strip()
        or (getattr(brief, "target_word_count", 0) or 0) > 0
        or brief.mentioned_character_ids
        or brief.active_character_ids
        or brief.active_node_ids
        or any((b or "").strip() for b in (brief.required_beats or []))
        or any((b or "").strip() for b in (brief.landed_beats or []))
        or (brief.continuity_notes or "").strip()
        or (brief.ending_hook or "").strip()
    )


def infer_cast_from_text(
    state: "StoryState",
    text: str,
    pov_name: str = "",
) -> Tuple[List[str], List[str]]:
    """Return (mentioned_character_ids, active_character_ids) from prose/outline text."""
    from mention_updates import _detect_explicit_presence  # noqa: WPS433
    from mentions import build_mention_targets, resolve_mentions_in_text  # noqa: WPS433

    mentioned_ids: List[str] = []
    seen: set[str] = set()
    lowered = (text or "").lower()

    for cid, char in state.characters.items():
        names = [char.full_name, *getattr(char, "aliases", [])]
        if any(
            re.search(rf"\b{re.escape(name.lower())}\b", lowered)
            for name in names
            if (name or "").strip()
        ):
            if cid not in seen:
                mentioned_ids.append(cid)
                seen.add(cid)

    targets = build_mention_targets(state)
    for rm in resolve_mentions_in_text(text or "", targets):
        if rm.broken or rm.kind != "char" or not rm.target or not rm.target.id:
            continue
        cid = rm.target.id
        if cid not in seen:
            mentioned_ids.append(cid)
            seen.add(cid)

    pov = (pov_name or "").strip()
    if pov:
        for cid, char in state.characters.items():
            names = [char.full_name, *getattr(char, "aliases", [])]
            if any((n or "").strip().lower() == pov.lower() for n in names):
                if cid not in seen:
                    mentioned_ids.append(cid)
                    seen.add(cid)
                break

    active_ids: List[str] = []
    for cid in mentioned_ids:
        char = state.characters.get(cid)
        if not char:
            continue
        names = char.all_names() if hasattr(char, "all_names") else [char.full_name]
        if _detect_explicit_presence(names, text or "", pov):
            active_ids.append(cid)

    active_set = set(active_ids)
    mentioned_ids = [cid for cid in mentioned_ids if cid not in active_set]
    return mentioned_ids, active_ids


def beats_for_prompt(
    state: "StoryState",
    chapter_number: int,
    brief: ChapterBrief,
) -> List[ChapterBeat]:
    """Prefer persisted chapter_beats; synthesize from legacy brief strings when empty."""
    existing = list(state.get_chapter_beats(chapter_number))
    if existing:
        return existing

    beats: List[ChapterBeat] = []
    sort_order = 0
    for title in [b.strip() for b in (brief.required_beats or []) if (b or "").strip()]:
        beats.append(
            ChapterBeat(
                id=f"legacy_planned_{chapter_number}_{sort_order}",
                title=title,
                sort_order=sort_order,
                status="planned",
            )
        )
        sort_order += 1
    for title in [b.strip() for b in (brief.landed_beats or []) if (b or "").strip()]:
        beats.append(
            ChapterBeat(
                id=f"legacy_landed_{chapter_number}_{sort_order}",
                title=title,
                sort_order=sort_order,
                status="landed",
            )
        )
        sort_order += 1
    return beats


def migrate_legacy_brief_beats_to_chapter_beats(
    state: "StoryState",
    chapter_number: int,
    brief: ChapterBrief,
) -> List[ChapterBeat]:
    """Move old brief beat string lists into the chapter beat board and clear them."""
    legacy: List[Tuple[str, str]] = []
    legacy.extend(
        (title, "planned")
        for title in [b.strip() for b in (brief.required_beats or []) if (b or "").strip()]
    )
    legacy.extend(
        (title, "landed")
        for title in [b.strip() for b in (brief.landed_beats or []) if (b or "").strip()]
    )
    existing = list(state.get_chapter_beats(chapter_number))
    if not legacy:
        return existing

    beats = list(existing)
    known_keys = {_beat_key(b.title or b.summary) for b in beats if _beat_key(b.title or b.summary)}
    known_ids = {b.id for b in beats}
    sort_order = max((b.sort_order for b in beats), default=-1) + 1
    added = False
    for title, status in legacy:
        key = _beat_key(title)
        if not key or key in known_keys:
            continue
        beats.append(
            ChapterBeat(
                id=_next_beat_id(chapter_number, known_ids),
                title=title,
                summary=title,
                sort_order=sort_order,
                status=status,
            )
        )
        known_keys.add(key)
        sort_order += 1
        added = True

    brief.required_beats = []
    brief.landed_beats = []
    if added:
        return state.set_chapter_beats(chapter_number, beats)
    return existing


def format_chapter_beats_for_outline_prompt(
    state: "StoryState",
    chapter_number: int,
    brief: ChapterBrief | None = None,
) -> str:
    """Structured beat block for Architect outline prompts."""
    if brief is None:
        brief = state.get_chapter_brief(chapter_number)
        if brief is None:
            brief = ChapterBrief(chapter_number=chapter_number)
    beats = beats_for_prompt(state, chapter_number, brief)
    if not beats:
        return ""

    lines = [
        "## Chapter beats (authoritative — honor order and status)",
        "",
    ]
    ordered = sorted(beats, key=lambda b: (b.sort_order, b.id))
    for index, beat in enumerate(ordered, start=1):
        status = (beat.status or "planned").strip()
        title = (beat.title or "").strip()
        summary = (beat.summary or "").strip()
        if title and summary and summary.lower() != title.lower():
            text = f"**{title}** — {summary}"
        elif title:
            text = f"**{title}**"
        else:
            text = summary
        lines.append(f"{index}. [{status}] {text}")
    return "\n".join(lines)


def format_chapter_beats_section(
    beats: List[ChapterBeat],
    *,
    include_status: bool = True,
    state: "StoryState | None" = None,
) -> str:
    """Markdown block for canonical chapter beats in agent prompts."""
    if not beats:
        return ""

    lines = [
        "### Chapter Beats",
        "Canonical beat list for this chapter. Honor `planned` beats in draft/revise; "
        "treat `landed` as events already on the page.",
        "",
    ]
    ordered = sorted(beats, key=lambda b: (b.sort_order, b.id))
    for beat in ordered:
        title = (beat.title or "").strip()
        summary = (beat.summary or "").strip()
        text = title
        if summary and summary.lower() != title.lower():
            text = f"{title} — {summary}"
        node_bits: List[str] = []
        if state is not None:
            for nid in beat.linked_node_ids or []:
                node = state.story_graph_nodes.get((nid or "").strip())
                if node and (node.title or "").strip():
                    node_bits.append(node.title.strip())
        if node_bits:
            text = f"{text} (plot: {', '.join(node_bits)})"
        status = (beat.status or "planned").strip()
        if include_status:
            lines.append(f"- **[{status}]** {text}")
        else:
            lines.append(f"- {text}")
    return "\n".join(lines)


def merge_cast_ids(existing: List[str], inferred: List[str]) -> List[str]:
    """Union cast id lists, preserving existing order then appending new ids."""
    merged = [cid for cid in (existing or []) if (cid or "").strip()]
    seen = set(merged)
    for cid in inferred or []:
        cid = (cid or "").strip()
        if cid and cid not in seen:
            merged.append(cid)
            seen.add(cid)
    return merged


def _beat_key(text: str) -> str:
    text = re.sub(r"\*\*", "", text or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .!?:;—-")


def _beat_keys_similar(left: str, right: str) -> bool:
    left = _beat_key(left)
    right = _beat_key(right)
    if not left or not right:
        return False
    left_numbers = set(re.findall(r"\d+", left))
    right_numbers = set(re.findall(r"\d+", right))
    if left_numbers or right_numbers:
        if left_numbers != right_numbers:
            return False
    if left == right:
        return True
    stopwords = {"a", "an", "the", "is", "are", "was", "were", "to", "of"}
    left_core = " ".join(token for token in left.split() if token not in stopwords)
    right_core = " ".join(token for token in right.split() if token not in stopwords)
    if left_core and right_core and left_core == right_core:
        return True
    if min(len(left_core), len(right_core)) >= 20 and (left_core in right_core or right_core in left_core):
        return True
    return SequenceMatcher(None, left_core or left, right_core or right).ratio() >= 0.88


def _append_unique_beat_title(titles: List[str], title: str) -> bool:
    title = (title or "").strip()
    if not title:
        return False
    if any(_beat_keys_similar(title, existing) for existing in titles):
        return False
    titles.append(title)
    return True


def _next_beat_id(chapter_number: int, known_ids: set[str]) -> str:
    n = len(known_ids) + 1
    beat_id = f"beat_{chapter_number}_{n:03d}"
    while beat_id in known_ids:
        n += 1
        beat_id = f"beat_{chapter_number}_{n:03d}"
    known_ids.add(beat_id)
    return beat_id


def merge_planned_beats(
    state: "StoryState",
    chapter_number: int,
    new_titles: List[str],
) -> List[ChapterBeat]:
    """Merge imported planned beats without clobbering landed or hand-edited planned rows."""
    existing = list(state.get_chapter_beats(chapter_number))
    landed = [b for b in existing if (b.status or "").strip() == "landed"]
    planned = [b for b in existing if (b.status or "").strip() != "landed"]
    known_ids = {b.id for b in existing}
    incoming: List[str] = []
    for title in new_titles:
        title = (title or "").strip()
        _append_unique_beat_title(incoming, title)
    if planned:
        known_titles = [b.title or b.summary for b in planned if _beat_key(b.title or b.summary)]
        sort_order = max((b.sort_order for b in existing), default=-1) + 1
        for title in incoming:
            if any(_beat_keys_similar(title, known) for known in known_titles):
                continue
            planned.append(
                ChapterBeat(
                    id=_next_beat_id(chapter_number, known_ids),
                    title=title,
                    summary=title,
                    sort_order=sort_order,
                    status="planned",
                )
            )
            known_titles.append(title)
            sort_order += 1
        return sorted(landed + planned, key=lambda b: (b.sort_order, b.id))

    beats = list(landed)
    sort_order = max((b.sort_order for b in beats), default=-1) + 1
    for title in incoming:
        beats.append(
            ChapterBeat(
                id=_next_beat_id(chapter_number, known_ids),
                title=title,
                summary=title,
                sort_order=sort_order,
                status="planned",
            )
        )
        sort_order += 1
    return beats


def replace_planned_beats(
    state: "StoryState",
    chapter_number: int,
    new_titles: List[str],
) -> List[ChapterBeat]:
    """Replace scan-generated planned beats while preserving landed history."""
    existing = list(state.get_chapter_beats(chapter_number))
    landed = [b for b in existing if (b.status or "").strip() == "landed"]
    known_ids = {b.id for b in existing}
    incoming: List[str] = []
    landed_titles = [b.title or b.summary for b in landed if _beat_key(b.title or b.summary)]
    for title in new_titles:
        title = (title or "").strip()
        if not title:
            continue
        if any(_beat_keys_similar(title, landed_title) for landed_title in landed_titles):
            continue
        _append_unique_beat_title(incoming, title)

    beats = list(landed)
    sort_order = max((b.sort_order for b in beats), default=-1) + 1
    for title in incoming:
        beats.append(
            ChapterBeat(
                id=_next_beat_id(chapter_number, known_ids),
                title=title,
                summary=title,
                sort_order=sort_order,
                status="planned",
            )
        )
        sort_order += 1
    return beats
