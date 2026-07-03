"""
Story Graph / Plot Mind Map — Phase 1 data model and migration helpers.

Graph nodes, edges, and chapter briefs are stored in story_state.json alongside
plot_threads (additive compatibility). Project backup/portable export already
includes outputs/state/story_state.json, so no separate DB rows are required.

Character-to-character edges use kind='character_relationship' with character IDs
as source_id/target_id (not graph node IDs).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict, fields
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from relationship_roles import display_relationship_label

if TYPE_CHECKING:
    from state_manager import ChapterState, StoryState


@dataclass
class StoryGraphLayout:
    """Persisted canvas position for GraphWorkbench."""
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> Optional["StoryGraphLayout"]:
        if not data:
            return None
        return cls(
            x=float(data.get("x", 0) or 0),
            y=float(data.get("y", 0) or 0),
        )


@dataclass
class ChapterBeat:
    """Chapter-local beat row used by planning, prompts, and landed-beat review."""
    id: str
    title: str
    summary: str = ""
    sort_order: int = 0
    status: str = "planned"  # planned | landed
    linked_node_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterBeat":
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("summary", "")
        kwargs.setdefault("sort_order", 0)
        kwargs.setdefault("status", "planned")
        kwargs.setdefault("linked_node_ids", [])
        return cls(**kwargs)


@dataclass
class StoryGraphNode:
    """A node in the story graph / plot mind map."""
    id: str
    kind: str  # plot_thread, subplot, beat, character_arc, mystery, theme, other
    title: str
    description: str = ""
    status: str = "active"  # active, resolved, abandoned, foreshadowed
    priority: int = 1
    linked_character_ids: List[str] = field(default_factory=list)
    legacy_plot_thread_id: str = ""
    created_from: str = ""  # manual, migration, import
    sort_order: int = 0
    start_chapter: int = 0  # 0 = unset; normalize_start_chapter -> 1
    resolution_chapter: Optional[int] = None  # null = open-ended
    layout: Optional[StoryGraphLayout] = None
    act: int = 0
    chapter_pins: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if self.layout is None:
            out.pop("layout", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryGraphNode":
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("linked_character_ids", [])
        kwargs.setdefault("sort_order", 0)
        kwargs.setdefault("start_chapter", 0)
        kwargs.setdefault("resolution_chapter", None)
        kwargs.setdefault("act", 0)
        kwargs.setdefault("chapter_pins", [])
        if "layout" in data:
            kwargs["layout"] = StoryGraphLayout.from_dict(data.get("layout"))
        return cls(**kwargs)


@dataclass
class StoryGraphEdge:
    """Directed edge between graph nodes or character IDs."""
    id: str
    source_id: str
    target_id: str
    kind: str  # contains, advances, relates, foreshadows, resolves, character_relationship
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryGraphEdge":
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        return cls(**kwargs)


@dataclass
class ChapterBrief:
    """Author-facing brief for planning a chapter against the story graph."""
    chapter_number: int
    pov_character_id: str = ""
    pov_mode: str = ""  # first_person, third_limited, third_omniscient, second_person, epistolary, other
    tone: str = ""
    tense: str = ""
    prose_style: str = ""
    vocabulary_level: str = ""
    style_notes: str = ""
    target_word_count: int = 0
    active_character_ids: List[str] = field(default_factory=list)
    mentioned_character_ids: List[str] = field(default_factory=list)
    active_node_ids: List[str] = field(default_factory=list)
    required_beats: List[str] = field(default_factory=list)
    landed_beats: List[str] = field(default_factory=list)
    continuity_notes: str = ""
    ending_hook: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterBrief":
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("pov_mode", "")
        kwargs.setdefault("tone", "")
        kwargs.setdefault("tense", "")
        kwargs.setdefault("prose_style", "")
        kwargs.setdefault("vocabulary_level", "")
        kwargs.setdefault("style_notes", "")
        kwargs.setdefault("target_word_count", 0)
        kwargs.setdefault("active_character_ids", [])
        kwargs.setdefault("mentioned_character_ids", [])
        kwargs.setdefault("active_node_ids", [])
        kwargs.setdefault("required_beats", [])
        kwargs.setdefault("landed_beats", [])
        return cls(**kwargs)


def normalize_start_chapter(start_chapter: int) -> int:
    """Treat 0 as unset and default to chapter 1."""
    value = int(start_chapter or 0)
    return 1 if value <= 0 else value


def node_eligible_at_chapter(node: StoryGraphNode, chapter_number: int) -> bool:
    """True when chapter_number falls within the node's lifespan."""
    if chapter_number < 1:
        return False
    start = normalize_start_chapter(node.start_chapter)
    if chapter_number < start:
        return False
    resolution = node.resolution_chapter
    if resolution is not None and chapter_number > int(resolution):
        return False
    return True


def eligible_graph_nodes(state: "StoryState", chapter_number: int) -> List[StoryGraphNode]:
    """Graph nodes whose lifespan includes chapter_number."""
    return [
        node for node in state.story_graph_nodes.values()
        if node_eligible_at_chapter(node, chapter_number)
    ]


def normalize_brief_characters(brief: ChapterBrief) -> None:
    """Ensure active_character_ids is a subset of mentioned_character_ids."""
    mentioned = list(brief.mentioned_character_ids or [])
    seen = {cid for cid in mentioned if (cid or "").strip()}
    brief.mentioned_character_ids = [cid for cid in mentioned if (cid or "").strip()]
    for cid in brief.active_character_ids or []:
        cid = (cid or "").strip()
        if cid and cid not in seen:
            brief.mentioned_character_ids.append(cid)
            seen.add(cid)


def validate_brief_active_nodes(
    state: "StoryState",
    brief: ChapterBrief,
) -> List[str]:
    """Return node ids in active_node_ids that are outside lifespan for this chapter."""
    chapter_number = brief.chapter_number
    invalid: List[str] = []
    for nid in brief.active_node_ids or []:
        nid = (nid or "").strip()
        if not nid:
            continue
        node = state.story_graph_nodes.get(nid)
        if node is None or not node_eligible_at_chapter(node, chapter_number):
            invalid.append(nid)
    return invalid


def sync_chapter_pins_for_brief(state: "StoryState", brief: ChapterBrief) -> None:
    """Treat the brief as authoritative and mirror its active nodes onto all node pins."""
    chapter_number = brief.chapter_number
    active = {(nid or "").strip() for nid in (brief.active_node_ids or []) if (nid or "").strip()}
    for node in state.story_graph_nodes.values():
        pins = list(node.chapter_pins or [])
        if node.id in active:
            if chapter_number not in pins:
                pins.append(chapter_number)
        else:
            pins = [c for c in pins if c != chapter_number]
        node.chapter_pins = sorted(set(pins))


def sync_brief_active_from_pin(
    state: "StoryState",
    node_id: str,
    chapter_number: int,
    *,
    pinned: bool,
) -> None:
    """Treat one node pin toggle as authoritative and mirror it back to the brief."""
    node = state.story_graph_nodes.get(node_id)
    if node is None:
        return
    pins = list(node.chapter_pins or [])
    if pinned:
        if chapter_number not in pins:
            pins.append(chapter_number)
    else:
        pins = [c for c in pins if c != chapter_number]
    node.chapter_pins = sorted(set(pins))

    brief = state.get_chapter_brief(chapter_number)
    if brief is None:
        return
    active = list(brief.active_node_ids or [])
    if pinned:
        if node_id not in active:
            active.append(node_id)
    else:
        active = [nid for nid in active if nid != node_id]
    brief.active_node_ids = active


def new_chapter_beat_id(state: "StoryState", chapter_number: int) -> str:
    """Allocate a unique beat id for a chapter."""
    existing = state.chapter_beats.get(chapter_number, [])
    n = len(existing) + 1
    beat_id = f"beat_{chapter_number}_{n:03d}"
    known = {beat.id for beat in existing}
    while beat_id in known:
        n += 1
        beat_id = f"beat_{chapter_number}_{n:03d}"
    return beat_id


def character_display_name(state: "StoryState", character_id: str) -> str:
    """Resolve a character id to full name, with a safe fallback label."""
    cid = (character_id or "").strip()
    if not cid:
        return ""
    char = state.characters.get(cid)
    if char:
        return char.full_name
    return f"[unknown character id: {cid}]"


def legacy_chapter_pov_character_id(
    state: "StoryState",
    chapter_number: int,
) -> str:
    """Resolve old chapter.pov_character name to a character id for display migration."""
    chapter = state.get_chapter(chapter_number)
    if chapter is None or not (chapter.pov_character or "").strip():
        return ""
    name = chapter.pov_character.strip().lower()
    for cid, char in state.characters.items():
        names = [char.full_name, *getattr(char, "aliases", [])]
        if any((n or "").strip().lower() == name for n in names):
            return cid
    return ""


def apply_brief_pov_to_chapter(
    state: "StoryState",
    chapter: "ChapterState",
    brief: Optional[ChapterBrief],
    *,
    explicit_pov: str = "",
) -> None:
    """Set chapter.pov_character from the brief unless the caller passed explicit POV."""
    if (explicit_pov or "").strip():
        return
    if brief is None or not (brief.pov_character_id or "").strip():
        return
    name = character_display_name(state, brief.pov_character_id)
    if name.startswith("[unknown"):
        return
    chapter.pov_character = name


def apply_brief_target_to_chapter(
    state: "StoryState",
    chapter: "ChapterState",
    brief: Optional[ChapterBrief],
) -> None:
    """Mirror resolved brief target onto chapter record (derived only — not a second source)."""
    from prompt_context import effective_target_word_count  # noqa: WPS433

    chapter.target_word_count = effective_target_word_count(brief, state, chapter)


def legacy_chapter_target_override(
    state: "StoryState",
    chapter_number: int,
) -> int:
    """One-time read of old chapter-only target overrides not yet on the brief."""
    from prompt_context import project_chapter_target_default  # noqa: WPS433

    chapter = state.get_chapter(chapter_number)
    if chapter is None:
        return 0
    legacy = int(chapter.target_word_count or 0)
    if legacy <= 0:
        return 0
    if legacy == project_chapter_target_default(state):
        return 0
    return legacy


def _format_character_brief_line(state: "StoryState", character_id: str) -> str:
    cid = (character_id or "").strip()
    if not cid:
        return ""
    char = state.characters.get(cid)
    if not char:
        return f"- [unknown character id: {cid}]"
    line = (
        f"- **{char.full_name}** ({char.role}) — "
        f"location: {char.current_location or 'Unknown'}, "
        f"emotion: {char.emotional_state or 'Unknown'}, "
        f"arc: {char.arc_stage} ({char.arc_progress}%)"
    )
    relationships = []
    for other_id, label in (char.relationships or {}).items():
        other = state.characters.get(other_id)
        if not other:
            continue
        display = display_relationship_label(label)
        if display:
            relationships.append(f"{other.full_name}: {display}")
    if relationships:
        line += f", relationships: {'; '.join(relationships[:6])}"
        if len(relationships) > 6:
            line += f" (+{len(relationships) - 6} more)"
    return line


def _format_story_graph_node_line(state: "StoryState", node_id: str) -> str:
    nid = (node_id or "").strip()
    if not nid:
        return ""
    node = state.story_graph_nodes.get(nid)
    if not node:
        return f"- [unknown story node id: {nid}]"
    desc = (node.description or "").strip()
    if len(desc) > 160:
        desc = desc[:157].rstrip() + "..."
    line = (
        f"- **{node.title}** ({node.kind}, {node.status}, priority {node.priority})"
    )
    if desc:
        line += f" — {desc}"
    linked = [
        character_display_name(state, cid)
        for cid in (node.linked_character_ids or [])
        if (cid or "").strip()
    ]
    if linked:
        line += f" | linked chars: {', '.join(linked)}"
    return line


def format_chapter_brief_prompt_context(
    state: "StoryState",
    brief: ChapterBrief,
    *,
    hint_text: str = "",
    budget=None,
) -> str:
    """
    Compact Markdown block for Architect/Scribe prompts from an author chapter brief.

    Missing character or node ids produce inline warnings; never raises.
    Story graph nodes are budgeted; related neighbors may appear with reasons.
    """
    from context_resolver import BUDGET_DRAFT, format_graph_nodes_block, resolve_brief_graph_context

    if budget is None:
        budget = BUDGET_DRAFT
    from prompt_context import (  # noqa: WPS433
        effective_pov_mode,
        effective_target_word_count,
        format_brief_style_section,
        format_pov_mode_label,
    )

    sections: List[str] = ["## Chapter Brief (canonical — POV, writing style, cast, and story focus)"]

    chapter = state.get_chapter(brief.chapter_number)
    target = effective_target_word_count(brief, state, chapter)
    inherit_note = ""
    if (brief.target_word_count or 0) <= 0:
        inherit_note = " _(project default)_"
    sections.append(f"### Target Length\n- **Target word count:** {target:,} words{inherit_note}")

    pov_id = (brief.pov_character_id or "").strip()
    pov_mode = effective_pov_mode(brief, state.style_profile)
    pov_lines: List[str] = []
    if pov_mode:
        pov_lines.append(f"- Narrative perspective: **{format_pov_mode_label(pov_mode)}**")
    if pov_id:
        pov_name = character_display_name(state, pov_id)
        char = state.characters.get(pov_id)
        role = f" ({char.role})" if char else ""
        if pov_name.startswith("[unknown"):
            pov_lines.append(f"- Warning: {pov_name}")
        else:
            pov_lines.append(f"- Viewpoint character: **{pov_name}**{role}")
    if pov_lines:
        sections.append("### POV\n" + "\n".join(pov_lines))

    style_block = format_brief_style_section(brief, state.style_profile)
    if style_block:
        sections.append(style_block)

    mentioned_ids = list(brief.mentioned_character_ids or [])
    if not mentioned_ids and brief.active_character_ids:
        mentioned_ids = list(brief.active_character_ids)
    mentioned_lines: List[str] = []
    for cid in mentioned_ids:
        cid = (cid or "").strip()
        if not cid:
            continue
        char = state.characters.get(cid)
        if not char:
            mentioned_lines.append(f"- [unknown character id: {cid}]")
        else:
            mentioned_lines.append(f"- **{char.full_name}** ({char.role})")
    if mentioned_lines:
        sections.append("### Mentioned Characters\n" + "\n".join(mentioned_lines))

    char_lines = [
        line for cid in (brief.active_character_ids or [])
        if (line := _format_character_brief_line(state, cid))
    ]
    if char_lines:
        sections.append("### Active Characters\n" + "\n".join(char_lines))

    graph_block = format_graph_nodes_block(
        resolve_brief_graph_context(state, brief, budget=budget, hint_text=hint_text),
    )
    if graph_block:
        sections.append(graph_block)

    from chapter_brief_utils import beats_for_prompt, format_chapter_beats_section  # noqa: WPS433

    chapter_beats = beats_for_prompt(state, brief.chapter_number, brief)
    beats_block = format_chapter_beats_section(chapter_beats, include_status=True, state=state)
    if beats_block:
        sections.append(beats_block)

    notes = (brief.continuity_notes or "").strip()
    if notes:
        sections.append(f"### Continuity Notes\n{notes}")

    hook = (brief.ending_hook or "").strip()
    if hook:
        sections.append(f"### Ending Hook\n{hook}")

    return "\n\n".join(sections) + "\n"


def _normalize_subplot_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _subplot_node_id(subplot_text: str) -> str:
    normalized = _normalize_subplot_title(subplot_text)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return f"graph_node_subplot_{digest}"


def _edge_id(source_id: str, target_id: str, kind: str) -> str:
    return f"graph_edge_{source_id}_{target_id}_{kind}"


def _graph_is_empty(state: "StoryState") -> bool:
    return not state.story_graph_nodes and not state.story_graph_edges


def _clear_migration_artifacts(state: "StoryState") -> None:
    """Remove nodes/edges created by migration before a forced remigration."""
    migrated_ids = {
        nid for nid, node in state.story_graph_nodes.items()
        if node.created_from == "migration"
    }
    for nid in migrated_ids:
        state.story_graph_nodes.pop(nid, None)
    to_drop = [
        eid for eid, edge in state.story_graph_edges.items()
        if edge.kind == "character_relationship"
        or edge.source_id in migrated_ids
        or edge.target_id in migrated_ids
    ]
    for eid in to_drop:
        state.story_graph_edges.pop(eid, None)


def migrate_plot_threads_to_graph(state: "StoryState", *, force: bool = False) -> Dict[str, Any]:
    """
    Build story graph nodes/edges from plot_threads, subplots, and character relationships.

    Non-destructive: never modifies plot_threads or manuscripts. Skips when the graph
    already has content unless force=True. On force, removes prior migration artifacts
    and rebuilds; manually created nodes (created_from != 'migration') are kept.

    Returns counts: nodes_created, edges_created, skipped (bool).
    """
    if not _graph_is_empty(state) and not force:
        return {"nodes_created": 0, "edges_created": 0, "skipped": True}

    if force:
        _clear_migration_artifacts(state)

    nodes_created = 0
    edges_created = 0

    thread_node_ids: Dict[str, str] = {}
    subplot_node_ids: Dict[str, str] = {}

    for thread in state.get_ordered_plot_threads():
        node_id = f"graph_node_{thread.id}"
        if node_id not in state.story_graph_nodes:
            state.story_graph_nodes[node_id] = StoryGraphNode(
                id=node_id,
                kind=thread.thread_type or "plot_thread",
                title=thread.name,
                description=thread.description,
                status=thread.status,
                priority=thread.priority,
                linked_character_ids=list(thread.related_characters),
                legacy_plot_thread_id=thread.id,
                created_from="migration",
                sort_order=thread.sort_order,
            )
            nodes_created += 1
        thread_node_ids[thread.id] = node_id

        for i, subplot_text in enumerate(thread.subplots):
            text = (subplot_text or "").strip()
            if not text:
                continue
            normalized = _normalize_subplot_title(text)
            sub_id = subplot_node_ids.get(normalized) or _subplot_node_id(text)
            if sub_id not in state.story_graph_nodes:
                state.story_graph_nodes[sub_id] = StoryGraphNode(
                    id=sub_id,
                    kind="subplot",
                    title=text,
                    description="",
                    status=thread.status,
                    priority=max(1, thread.priority - 1),
                    linked_character_ids=list(thread.related_characters),
                    legacy_plot_thread_id=thread.id,
                    created_from="migration",
                    sort_order=thread.sort_order * 100 + i + 1,
                )
                nodes_created += 1
            else:
                # A subplot can belong to multiple plots. Merge linked characters
                # from every legacy parent that references the shared subplot.
                node = state.story_graph_nodes[sub_id]
                for cid in thread.related_characters:
                    if cid not in node.linked_character_ids:
                        node.linked_character_ids.append(cid)
            subplot_node_ids[normalized] = sub_id
            eid = _edge_id(node_id, sub_id, "contains")
            if eid not in state.story_graph_edges:
                state.story_graph_edges[eid] = StoryGraphEdge(
                    id=eid,
                    source_id=node_id,
                    target_id=sub_id,
                    kind="contains",
                    label="subplot",
                )
                edges_created += 1

    for thread in state.plot_threads.values():
        parent_nid = thread_node_ids.get(thread.id)
        if not parent_nid:
            continue
        for related_id in thread.related_threads:
            child_nid = thread_node_ids.get(related_id)
            if not child_nid:
                continue
            eid = _edge_id(parent_nid, child_nid, "relates")
            if eid not in state.story_graph_edges:
                state.story_graph_edges[eid] = StoryGraphEdge(
                    id=eid,
                    source_id=parent_nid,
                    target_id=child_nid,
                    kind="relates",
                    label="related thread",
                )
                edges_created += 1

    seen_pairs: set[tuple[str, str]] = set()
    for char in state.characters.values():
        for other_id, rel_label in char.relationships.items():
            if other_id not in state.characters:
                continue
            pair = tuple(sorted((char.id, other_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            eid = _edge_id(char.id, other_id, "character_relationship")
            if eid not in state.story_graph_edges:
                state.story_graph_edges[eid] = StoryGraphEdge(
                    id=eid,
                    source_id=char.id,
                    target_id=other_id,
                    kind="character_relationship",
                    label=display_relationship_label(rel_label),
                )
                edges_created += 1

    return {"nodes_created": nodes_created, "edges_created": edges_created, "skipped": False}
