"""Plain-language summaries for chapter mine preview modals (author-facing)."""

from __future__ import annotations

import re
from typing import Any

_SKIP_MARKERS = (
    "no plot thread",
    "not found on",
    "resolved subplot not found",
    "unknown graph node",
    "no parent for",
    "no parent plot",
    "skipped malformed",
    "skipped duplicate",
)


def _is_skip_line(line: str) -> bool:
    low = line.lower()
    return any(marker in low for marker in _SKIP_MARKERS)


def _strip_log_prefix(line: str) -> str:
    if "]" in line:
        return line.split("]", 1)[1].strip()
    return line.strip()


def _humanize_apply_line(kind: str, line: str) -> str:
    low = line.lower()
    if kind == "plots":
        if "plot event" in low:
            match = re.search(r"\+(\d+)\s+new", line)
            if match:
                n = match.group(1)
                return (
                    f"Add {n} plot-event note(s) to this chapter's internal metadata "
                    "(chapter codex only — not Story Graph nodes)."
                )
            return "Add a plot-event note to this chapter's internal metadata."
        if "plot thread updated" in low:
            return "Update an existing legacy Plot Thread."
        if "new plot thread" in low:
            return "Create a new legacy Plot Thread."
        if "subplot on" in low:
            return "Add a subplot line under an existing major plot thread."
        if "graph node lifespan updated" in low:
            return "Update a Story Graph node's start/end chapter lifespan."
        if "resolved subplot removed" in low:
            return "Mark a subplot as resolved and remove it from active tracking."
        if "related" in low and "subplot of" in low:
            return "Nest a related plot under a major arc as a subplot."
    if kind == "characters":
        if "new character" in low:
            return "Add a new cast member."
        if "relationship to" in low:
            return "Add or update a character relationship label."
        if "character update" in low or ": " in line:
            return "Update an existing character profile field."
    if kind == "bible":
        if "story bible" in low or "world facts" in low or "setting" in low:
            return "Add durable story bible notes."
    return _strip_log_prefix(line)


def _humanize_skip_line(kind: str, line: str) -> str:
    low = line.lower()
    if "no plot thread for subplot beat" in low:
        return (
            "Subplot beat skipped — the AI named a parent plot that doesn't exist as a "
            "legacy Plot Thread. If you plan in Story Graph, add beats there instead."
        )
    if "unknown graph node for lifespan" in low:
        return (
            "Story Graph lifespan change skipped — the node title didn't match any graph "
            "node in your project (check exact titles on the Story Graph tab)."
        )
    if "resolved subplot not found" in low:
        return (
            "Resolve-subplot skipped — that subplot isn't listed under the parent thread "
            "the AI named."
        )
    if "no parent plot" in low or "no parent for" in low:
        return "Subplot skipped — couldn't find the parent major plot thread the AI named."
    if "skipped duplicate" in low:
        return "Skipped a duplicate plot entry that's already in your project."
    if "skipped malformed" in low:
        return "Skipped a malformed line in the AI response."
    return _strip_log_prefix(line)


def _proposed_from_parsed(kind: str, parsed: dict[str, Any]) -> list[str]:
    """What the AI asked to change (readable names from parsed payload)."""
    out: list[str] = []
    if kind == "plots":
        for item in parsed.get("plot_events") or []:
            text = str(item).strip()
            if text:
                out.append(f"Plot event: {text}")
        for raw in parsed.get("subplot_beats") or []:
            parts = [p.strip() for p in str(raw).split("|")]
            if len(parts) >= 2:
                out.append(f"Subplot beat on “{parts[0]}”: {parts[1]}")
        for raw in parsed.get("plot_lifespan_updates") or []:
            parts = [p.strip() for p in str(raw).split("|")]
            if parts:
                out.append(f"Graph lifespan for “{parts[0]}”")
        for raw in parsed.get("subplot_threads") or []:
            parts = [p.strip() for p in str(raw).split("|")]
            if len(parts) >= 2:
                out.append(f"New subplot “{parts[1]}” under “{parts[0]}”")
        for raw in parsed.get("resolved_subplots") or []:
            parts = [p.strip() for p in str(raw).split("|")]
            if len(parts) >= 2:
                out.append(f"Resolve subplot “{parts[1]}” under “{parts[0]}”")
    elif kind == "characters":
        for raw in parsed.get("new_characters") or []:
            out.append(f"New character: {str(raw).split('|')[0].strip()}")
        for raw in parsed.get("character_updates") or []:
            out.append(f"Character update: {str(raw).strip()}")
        for raw in parsed.get("relationship_updates") or []:
            parts = [p.strip() for p in str(raw).split("|")]
            if len(parts) >= 3:
                out.append(f"Relationship: {parts[0]} → {parts[2]} ({parts[1]})")
    elif kind == "bible":
        for raw in parsed.get("world_facts") or []:
            out.append(f"World fact: {str(raw).strip()}")
        for raw in parsed.get("story_bible_notes") or []:
            out.append(f"Bible note: {str(raw).strip()}")
    return out


def _advice_for(kind: str, will_apply: list[str], skipped: list[str]) -> str:
    if not skipped:
        if will_apply:
            return "Review the list below. Apply writes these updates to your project; Discard closes without saving."
        return "The AI didn't propose any registry changes. Discard to close."
    if kind == "plots" and len(skipped) >= len(will_apply):
        return (
            "Most of the AI's plot suggestions could not be matched to your project. "
            "Structure V2 projects usually keep arcs on the Story Graph tab, while Mine plots "
            "still updates legacy Plot Threads and chapter plot-event notes. "
            "Discard unless you want the small “Will apply” items below. "
            "For graph structure, edit Story Graph or chapter beats directly."
        )
    if will_apply:
        return (
            "Some suggestions applied cleanly; others were skipped because names didn't match "
            "your cast, plot threads, or graph nodes. Apply only if you want the successful items."
        )
    return (
        "Nothing in this preview can be applied — every suggestion failed to match your project. "
        "Discard to close. Fix names on Story Graph / Plot Threads, then mine again if needed."
    )


def build_mine_preview_ui(kind: str, parsed: dict[str, Any], technical_log: list[str]) -> dict[str, Any]:
    """Build author-facing preview summary for the mine modal."""
    will_apply: list[str] = []
    skipped: list[str] = []
    for line in technical_log:
        if _is_skip_line(line):
            skipped.append(_humanize_skip_line(kind, line))
        else:
            will_apply.append(_humanize_apply_line(kind, line))

    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    will_apply = _dedupe(will_apply)
    skipped = _dedupe(skipped)
    proposed = _proposed_from_parsed(kind, parsed)

    return {
        "will_apply": will_apply,
        "skipped": skipped,
        "proposed": proposed,
        "can_apply": len(will_apply) > 0,
        "advice": _advice_for(kind, will_apply, skipped),
    }
