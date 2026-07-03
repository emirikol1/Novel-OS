"""
Compact mention context cards for agent prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Set

from mentions import (
    MentionTarget,
    ResolvedMention,
    build_mention_targets,
    resolve_mentions_in_text,
    text_has_mentions,
)

if TYPE_CHECKING:
    from state_manager import StoryState, Character

DEAD_KEYWORDS = ("dead", "killed", "deceased", "died")


def _char_card(char: "Character", *, critical_notes: List[str]) -> str:
    lines = [
        f"**{char.full_name}** ({char.role})",
        f"- Location: {char.current_location or 'unknown'}",
        f"- Emotional state: {char.emotional_state or 'unknown'}",
    ]
    if char.knowledge:
        know = "; ".join(char.knowledge[:6])
        if len(char.knowledge) > 6:
            know += f" (+{len(char.knowledge) - 6} more)"
        lines.append(f"- Knows: {know}")
    if char.notes.strip():
        note = char.notes.strip()
        if len(note) > 160:
            note = note[:157] + "..."
        lines.append(f"- Notes: {note}")
    if char.last_appearance_chapter:
        lines.append(f"- Last appeared: ch{char.last_appearance_chapter}")
    for note in critical_notes:
        lines.append(f"- ⚠ {note}")
    return "\n".join(lines)


def _lore_card(target: MentionTarget, bible: dict) -> str:
    section = target.section or ""
    label = target.label
    body = ""
    if section and section in bible:
        val = bible.get(section)
        if isinstance(val, str) and val.strip():
            body = val.strip()
            if len(body) > 200:
                body = body[:197] + "..."
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and label.lower() in item.lower():
                    body = item.strip()
                    break
                if isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str) and label.lower() in v.lower():
                            body = v.strip()
                            break
    sec_label = section.replace("_", " ") if section else "lore"
    lines = [f"**{label}** ({sec_label})"]
    if body:
        lines.append(f"- {body}")
    return "\n".join(lines)


def _critical_char_notes(char: "Character") -> List[str]:
    notes: List[str] = []
    es = (char.emotional_state or "").lower()
    n = (char.notes or "").lower()
    if any(k in es or k in n for k in DEAD_KEYWORDS):
        notes.append("flagged dead/killed in story memory — mention may be flashback or error")
    return notes


def build_mention_context_block(text: str, state: "StoryState") -> str:
    """Return a compact markdown block for prompt injection, or empty string."""
    if not text or not text_has_mentions(text):
        return ""

    targets = build_mention_targets(state)
    resolved = resolve_mentions_in_text(text, targets)
    if not resolved:
        return ""

    char_ids: Set[str] = set()
    lore_keys: Set[str] = set()
    char_cards: List[str] = []
    lore_cards: List[str] = []

    for rm in resolved:
        if rm.broken:
            continue
        if rm.kind == "char" and rm.target and rm.target.id:
            if rm.target.id in char_ids:
                continue
            char_ids.add(rm.target.id)
            char = state.get_character(rm.target.id)
            if char:
                char_cards.append(_char_card(char, critical_notes=_critical_char_notes(char)))
        elif rm.kind == "lore" and rm.target:
            key = f"{rm.target.section}:{rm.target.label}"
            if key in lore_keys:
                continue
            lore_keys.add(key)
            lore_cards.append(_lore_card(rm.target, state.story_bible or {}))

    if not char_cards and not lore_cards:
        return ""

    lines = [
        "## Mention context (signals only — not proof of on-page events)",
        "Resolved inline mentions from this text. Treat as author-marked relevance, not automatic truth.",
        "",
    ]
    if char_cards:
        lines.append("### Characters")
        lines.extend(char_cards)
        lines.append("")
    if lore_cards:
        lines.append("### Lore / world")
        lines.extend(lore_cards)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def mention_context_for_prompts(text: str, state: "StoryState") -> str:
    block = build_mention_context_block(text, state)
    if not block:
        return ""
    return block + "\n---\n\n"
