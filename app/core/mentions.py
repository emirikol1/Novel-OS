"""
Shared mention parsing and resolution for Novel OS manuscripts.

Syntax (portable Markdown):
  [[char:Full Name]]
  [[lore:Label]]
  [[lore:section_key:Label]]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import StoryState

RE_CHAR = re.compile(r"\[\[char:([^\]]+)\]\]")
RE_LORE_SECTION = re.compile(r"\[\[lore:([^:\]]+):([^\]]+)\]\]")
RE_LORE = re.compile(r"\[\[lore:([^\]]+)\]\]")

BIBLE_SECTION_META: tuple[tuple[str, str, bool], ...] = (
    ("logline", "Logline", False),
    ("tone", "Tone", False),
    ("themes", "Themes", True),
    ("setting_summary", "Setting", True),
    ("historical_context", "Historical context", True),
    ("premise_beats", "Premise beats", True),
    ("world_rules", "World rules", False),
    ("import_notes", "Story notes", False),
)


@dataclass
class MentionTarget:
    kind: str  # "char" | "lore"
    label: str
    id: Optional[str] = None
    section: Optional[str] = None
    aliases: List[str] = field(default_factory=list)


@dataclass
class ParsedMention:
    kind: str
    label: str
    raw: str
    start: int
    end: int
    section: Optional[str] = None


@dataclass
class ResolvedMention:
    kind: str
    label: str
    raw: str
    start: int
    end: int
    section: Optional[str] = None
    target: Optional[MentionTarget] = None
    broken: bool = False


def normalize_label(label: str) -> str:
    return label.strip().lower()


def strip_mentions(text: str) -> str:
    text = RE_CHAR.sub(r"\1", text)
    text = RE_LORE_SECTION.sub(r"\2", text)
    text = RE_LORE.sub(r"\1", text)
    return text


def _lore_item_label(item: Any) -> Optional[str]:
    if isinstance(item, str):
        t = item.strip()
        return t or None
    if isinstance(item, dict):
        o = item
        t = (o.get("note") or o.get("fact") or o.get("relationship") or "").strip()
        return t or None
    return None


def build_mention_targets(state: "StoryState") -> List[MentionTarget]:
    targets: List[MentionTarget] = []
    seen: set[str] = set()

    def add(target: MentionTarget) -> None:
        key = f"{target.kind}:{target.section or ''}:{normalize_label(target.label)}"
        if key in seen:
            return
        seen.add(key)
        targets.append(target)

    for char in state.get_all_characters():
        add(MentionTarget(
            kind="char",
            label=char.full_name,
            id=char.id,
            aliases=list(char.aliases or []),
        ))

    bible = state.story_bible or {}
    for key, _label, as_list in BIBLE_SECTION_META:
        val = bible.get(key)
        if isinstance(val, list):
            for item in val:
                lbl = _lore_item_label(item)
                if lbl:
                    add(MentionTarget(kind="lore", label=lbl, section=key))
        elif isinstance(val, str) and val.strip():
            add(MentionTarget(kind="lore", label=_label, section=key))
            for line in val.split("\n"):
                t = line.strip()
                if t:
                    add(MentionTarget(kind="lore", label=t, section=key))

    return targets


def parse_mentions(text: str) -> List[ParsedMention]:
    found: List[ParsedMention] = []

    def collect(pattern: re.Pattern[str], kind: str, with_section: bool) -> None:
        for m in pattern.finditer(text):
            if with_section:
                found.append(ParsedMention(
                    kind=kind,
                    section=m.group(1),
                    label=m.group(2),
                    raw=m.group(0),
                    start=m.start(),
                    end=m.end(),
                ))
            else:
                found.append(ParsedMention(
                    kind=kind,
                    label=m.group(1),
                    raw=m.group(0),
                    start=m.start(),
                    end=m.end(),
                ))

    collect(RE_CHAR, "char", False)
    collect(RE_LORE_SECTION, "lore", True)
    collect(RE_LORE, "lore", False)

    found.sort(key=lambda x: (x.start, -len(x.raw)))
    deduped: List[ParsedMention] = []
    end = 0
    for m in found:
        if m.start < end:
            continue
        deduped.append(m)
        end = m.end
    return deduped


def resolve_mention(
    parsed: ParsedMention | Dict[str, Any],
    targets: List[MentionTarget],
) -> Optional[MentionTarget]:
    if isinstance(parsed, ParsedMention):
        kind, label, section = parsed.kind, parsed.label, parsed.section
    else:
        kind = parsed["kind"]
        label = parsed["label"]
        section = parsed.get("section")

    want = normalize_label(label)

    if kind == "char":
        for t in targets:
            if t.kind != "char":
                continue
            if normalize_label(t.label) == want:
                return t
            if any(normalize_label(a) == want for a in t.aliases):
                return t
        return None

    if section:
        sec = section.strip().lower()
        for t in targets:
            if t.kind != "lore" or not t.section:
                continue
            if t.section.lower() == sec and normalize_label(t.label) == want:
                return t
        return None

    for t in targets:
        if t.kind == "lore" and normalize_label(t.label) == want:
            return t
    return None


def resolve_mentions_in_text(text: str, targets: List[MentionTarget]) -> List[ResolvedMention]:
    out: List[ResolvedMention] = []
    for parsed in parse_mentions(text):
        target = resolve_mention(parsed, targets)
        broken = target is None or (parsed.kind == "char" and not target.id)
        out.append(ResolvedMention(
            kind=parsed.kind,
            label=parsed.label,
            section=parsed.section,
            raw=parsed.raw,
            start=parsed.start,
            end=parsed.end,
            target=target,
            broken=broken,
        ))
    return out


def text_has_mentions(text: str) -> bool:
    return bool(RE_CHAR.search(text) or RE_LORE.search(text))
