"""
Budgeted story bible and story graph context for agent prompts.

Collects durable bible sections and graph nodes with ranking, caps, and
omission diagnostics — no embeddings or full-corpus dumps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

if TYPE_CHECKING:
    from state_manager import StoryState
    from story_graph import ChapterBrief, StoryGraphNode

# Durable bible sections (tone lives on style_profile, not bible authority).
BIBLE_SECTIONS: Tuple[Tuple[str, str, int], ...] = (
    ("logline", "Logline", 100),
    ("themes", "Themes", 80),
    ("setting_summary", "Setting", 75),
    ("premise_beats", "Premise beats", 70),
    ("world_rules", "World rules", 65),
    ("historical_context", "Historical context", 60),
    ("import_notes", "Story notes", 55),
)

STATUS_SCORE = {
    "active": 20,
    "foreshadowed": 15,
    "resolved": 8,
    "abandoned": 2,
}


@dataclass(frozen=True)
class ContextBudget:
    max_items: int = 10
    max_chars: int = 4000
    max_selected_nodes: int = 8
    max_related_nodes: int = 4


BUDGET_OUTLINE = ContextBudget(max_items=6, max_chars=2500, max_selected_nodes=6, max_related_nodes=3)
BUDGET_DRAFT = ContextBudget(max_items=8, max_chars=3500, max_selected_nodes=8, max_related_nodes=4)
BUDGET_REVISE = ContextBudget(max_items=8, max_chars=3500, max_selected_nodes=8, max_related_nodes=4)
BUDGET_VALIDATION = ContextBudget(max_items=14, max_chars=7000, max_selected_nodes=12, max_related_nodes=6)
BUDGET_PLOT_SUPPORT = ContextBudget(max_items=12, max_chars=6000, max_selected_nodes=10, max_related_nodes=5)


@dataclass
class ResolvedContextItem:
    key: str
    label: str
    body: str
    reason: str
    score: float = 0.0


@dataclass
class ResolvedContext:
    items: List[ResolvedContextItem] = field(default_factory=list)
    omitted_count: int = 0
    omitted_labels: List[str] = field(default_factory=list)
    omitted_reason: str = "budget cap"


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        lines = [str(x).strip() for x in value if str(x).strip()]
        return "; ".join(lines)
    text = str(value).strip()
    if text.lower() in ("none", "unknown", "n/a", "{}"):
        return ""
    return text


def _text_match_bonus(hint: str, *parts: str) -> float:
    if not hint:
        return 0.0
    hay = hint.lower()
    bonus = 0.0
    for part in parts:
        for token in re.findall(r"[a-z0-9']{4,}", (part or "").lower()):
            if token in hay:
                bonus += 12.0
                break
    return min(bonus, 36.0)


def _collect_bible_items(state: "StoryState") -> List[ResolvedContextItem]:
    bible = state.story_bible or {}
    items: List[ResolvedContextItem] = []

    for key, label, base_score in BIBLE_SECTIONS:
        raw = bible.get(key)
        body = _norm_text(raw)
        if not body:
            continue
        if isinstance(raw, list):
            lines = [str(x).strip() for x in raw if str(x).strip()]
            body = "\n".join(f"- {line}" for line in lines)
        items.append(
            ResolvedContextItem(
                key=f"bible:{key}",
                label=label,
                body=body,
                reason="section_default",
                score=float(base_score),
            ),
        )

    setting = bible.get("setting")
    if isinstance(setting, dict) and setting:
        bits = []
        for fld in ("place", "time", "atmosphere", "summary"):
            val = setting.get(fld)
            if val and str(val).strip():
                bits.append(f"- {fld}: {val}")
        if bits:
            items.append(
                ResolvedContextItem(
                    key="bible:setting_structured",
                    label="Setting (structured)",
                    body="\n".join(bits),
                    reason="section_default",
                    score=74.0,
                ),
            )

    return items


def _rank_bible_items(
    items: List[ResolvedContextItem],
    *,
    hint_text: str = "",
) -> List[ResolvedContextItem]:
    ranked: List[ResolvedContextItem] = []
    for item in items:
        bonus = _text_match_bonus(hint_text, item.label, item.body)
        reason = item.reason
        score = item.score + bonus
        if bonus > 0:
            reason = "text_match"
        ranked.append(
            ResolvedContextItem(
                key=item.key,
                label=item.label,
                body=item.body,
                reason=reason,
                score=score,
            ),
        )
    ranked.sort(key=lambda i: (-i.score, i.label.lower()))
    return ranked


def _apply_item_budget(
    ranked: List[ResolvedContextItem],
    budget: ContextBudget,
) -> ResolvedContext:
    selected: List[ResolvedContextItem] = []
    omitted_labels: List[str] = []
    char_total = 0

    for item in ranked:
        item_len = len(item.body) + len(item.label) + 16
        if len(selected) >= budget.max_items:
            omitted_labels.append(item.label)
            continue
        if char_total + item_len > budget.max_chars and selected:
            omitted_labels.append(item.label)
            continue
        selected.append(item)
        char_total += item_len

    return ResolvedContext(
        items=selected,
        omitted_count=len(omitted_labels),
        omitted_labels=omitted_labels,
        omitted_reason="budget cap",
    )


def resolve_bible_context(
    state: "StoryState",
    *,
    budget: ContextBudget = BUDGET_OUTLINE,
    hint_text: str = "",
) -> ResolvedContext:
    """Rank and cap durable story bible sections for prompt injection."""
    items = _collect_bible_items(state)
    if not items:
        return ResolvedContext()
    ranked = _rank_bible_items(items, hint_text=hint_text)
    return _apply_item_budget(ranked, budget)


def _node_neighbors(state: "StoryState", node_id: str) -> Dict[str, str]:
    """Map related node id -> edge reason label."""
    related: Dict[str, str] = {}
    for edge in state.story_graph_edges.values():
        if edge.kind == "character_relationship":
            continue
        src, tgt = edge.source_id, edge.target_id
        if src == node_id and tgt in state.story_graph_nodes:
            related.setdefault(tgt, f"outgoing {edge.kind}")
        elif tgt == node_id and src in state.story_graph_nodes:
            related.setdefault(src, f"incoming {edge.kind}")
    return related


def _node_body(state: "StoryState", node: "StoryGraphNode") -> str:
    desc = (node.description or "").strip()
    if len(desc) > 160:
        desc = desc[:157].rstrip() + "..."
    line = f"({node.kind}, {node.status}, priority {node.priority})"
    if desc:
        line += f" — {desc}"
    linked = []
    for cid in node.linked_character_ids or []:
        char = state.characters.get(cid)
        if char:
            linked.append(char.full_name)
    if linked:
        line += f" | linked chars: {', '.join(linked)}"
    return line


def _score_graph_node(
    node: "StoryGraphNode",
    *,
    reason: str,
    active_char_ids: Set[str],
    hint_text: str,
    explicit: bool,
) -> float:
    score = float(node.priority or 1) * 5.0
    score += STATUS_SCORE.get((node.status or "").lower(), 5)
    if explicit:
        score += 200.0
    if reason.startswith("related"):
        score += 30.0
    if active_char_ids & set(node.linked_character_ids or []):
        score += 40.0
    score += _text_match_bonus(hint_text, node.title, node.description)
    return score


def resolve_graph_nodes(
    state: "StoryState",
    *,
    selected_node_ids: Sequence[str],
    active_character_ids: Optional[Sequence[str]] = None,
    budget: ContextBudget = BUDGET_DRAFT,
    hint_text: str = "",
) -> ResolvedContext:
    """Rank selected graph nodes plus limited edge-related neighbors."""
    active_chars = {c for c in (active_character_ids or []) if (c or "").strip()}
    explicit_ids = [nid for nid in selected_node_ids if (nid or "").strip()]

    candidates: Dict[str, ResolvedContextItem] = {}
    for nid in explicit_ids[: budget.max_selected_nodes]:
        node = state.story_graph_nodes.get(nid)
        if not node:
            candidates[nid] = ResolvedContextItem(
                key=f"graph:{nid}",
                label=nid,
                body=f"[unknown story node id: {nid}]",
                reason="explicit_selection",
                score=200.0,
            )
            continue
        candidates[nid] = ResolvedContextItem(
            key=f"graph:{nid}",
            label=node.title,
            body=_node_body(state, node),
            reason="explicit_selection",
            score=_score_graph_node(
                node,
                reason="explicit_selection",
                active_char_ids=active_chars,
                hint_text=hint_text,
                explicit=True,
            ),
        )

    related_pool: List[Tuple[float, str, ResolvedContextItem]] = []
    seen_related: Set[str] = set(explicit_ids)
    for nid in explicit_ids[: budget.max_selected_nodes]:
        for rel_id, edge_reason in _node_neighbors(state, nid).items():
            if rel_id in seen_related:
                continue
            node = state.story_graph_nodes.get(rel_id)
            if not node:
                continue
            seen_related.add(rel_id)
            item = ResolvedContextItem(
                key=f"graph:{rel_id}",
                label=node.title,
                body=_node_body(state, node),
                reason=f"related ({edge_reason})",
                score=_score_graph_node(
                    node,
                    reason=f"related ({edge_reason})",
                    active_char_ids=active_chars,
                    hint_text=hint_text,
                    explicit=False,
                ),
            )
            related_pool.append((item.score, rel_id, item))

    related_pool.sort(key=lambda t: (-t[0], t[1]))
    for _, rel_id, item in related_pool[: budget.max_related_nodes]:
        candidates[rel_id] = item

    all_items = list(candidates.values())
    all_items.sort(key=lambda i: (-i.score, i.label.lower()))

    selected: List[ResolvedContextItem] = []
    omitted_labels: List[str] = []
    char_total = 0
    max_graph_items = budget.max_selected_nodes + budget.max_related_nodes

    for item in all_items:
        item_len = len(item.body) + len(item.label) + 24
        if len(selected) >= max_graph_items:
            omitted_labels.append(item.label)
            continue
        if char_total + item_len > budget.max_chars and selected:
            omitted_labels.append(item.label)
            continue
        selected.append(item)
        char_total += item_len

    extra_omitted = max(0, len(explicit_ids) - budget.max_selected_nodes)
    if extra_omitted:
        for nid in explicit_ids[budget.max_selected_nodes :]:
            node = state.story_graph_nodes.get(nid)
            omitted_labels.append(node.title if node else nid)

    return ResolvedContext(
        items=selected,
        omitted_count=len(omitted_labels),
        omitted_labels=omitted_labels,
        omitted_reason="budget cap",
    )


def format_bible_context_block(
    resolved: ResolvedContext,
    *,
    empty_message: str = "(Story bible is empty — rely on other context only.)",
) -> str:
    if not resolved.items:
        if resolved.omitted_count:
            return _format_omission_footer(resolved, header="## Story bible\n")
        return empty_message if not resolved.omitted_labels else ""

    lines = ["## Story bible"]
    for item in resolved.items:
        lines.append(f"### {item.label}")
        lines.append(item.body)
    footer = _format_omission_footer(resolved)
    if footer:
        lines.append(footer.rstrip())
    return "\n\n".join(lines)


def format_graph_nodes_block(
    resolved: ResolvedContext,
    *,
    section_title: str = "### Active Story Nodes",
) -> str:
    if not resolved.items and not resolved.omitted_count:
        return ""
    lines = [section_title]
    for item in resolved.items:
        prefix = f"[{item.reason}] " if item.reason != "explicit_selection" else ""
        lines.append(f"- **{item.label}** {prefix}{item.body}")
    footer = _format_omission_footer(resolved)
    if footer:
        lines.append(footer.rstrip())
    return "\n".join(lines)


def _format_omission_footer(resolved: ResolvedContext, header: str = "") -> str:
    if not resolved.omitted_count:
        return ""
    sample = resolved.omitted_labels[:5]
    more = resolved.omitted_count - len(sample)
    names = ", ".join(sample)
    if more > 0:
        names += f", +{more} more"
    note = f"_(Omitted {resolved.omitted_count} item(s) due to {resolved.omitted_reason}: {names})_"
    return f"{header}{note}" if header else note


def format_bible_context_for_prompt(
    state: "StoryState",
    *,
    budget: ContextBudget = BUDGET_OUTLINE,
    hint_text: str = "",
) -> str:
    """Convenience: resolve + format bible context."""
    resolved = resolve_bible_context(state, budget=budget, hint_text=hint_text)
    return format_bible_context_block(resolved)


def resolve_brief_graph_context(
    state: "StoryState",
    brief: "ChapterBrief",
    *,
    budget: ContextBudget = BUDGET_DRAFT,
    hint_text: str = "",
) -> ResolvedContext:
    return resolve_graph_nodes(
        state,
        selected_node_ids=brief.active_node_ids or [],
        active_character_ids=brief.active_character_ids or [],
        budget=budget,
        hint_text=hint_text,
    )
