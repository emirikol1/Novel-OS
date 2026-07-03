"""Reviewable change records and deterministic first-slice graph suggestions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from relationship_roles import display_relationship_label
from story_graph import StoryGraphEdge, StoryGraphNode, node_eligible_at_chapter

if TYPE_CHECKING:
    from state_manager import StoryState


REVIEWABLE_STATUSES = frozenset({
    "pending",
    "applied_needs_review",
    "reviewed",
    "dismissed",
    "reverted",
    "blocked",
})
GRAPH_SUGGESTION_SOURCE = "graph_suggestions"


class ReviewableChangeActionError(ValueError):
    """Raised when a requested state transition is not valid."""


@dataclass
class ReviewableChange:
    """A persisted preview/apply/revert record for author-reviewable mutations."""

    id: str
    kind: str
    title: str
    summary: str = ""
    reason: str = ""
    source: str = ""
    status: str = "pending"
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    applied_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    target: Dict[str, Any] = field(default_factory=dict)
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    conflicts: List[str] = field(default_factory=list)
    revert_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewableChange":
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in (data or {}).items() if k in valid}
        kwargs.setdefault("summary", "")
        kwargs.setdefault("reason", "")
        kwargs.setdefault("source", "")
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("confidence", 1.0)
        kwargs.setdefault("created_at", _now_iso())
        kwargs.setdefault("updated_at", kwargs["created_at"])
        kwargs.setdefault("target", {})
        kwargs.setdefault("conflicts", [])
        kwargs.setdefault("revert_available", False)
        if kwargs["status"] not in REVIEWABLE_STATUSES:
            kwargs["status"] = "pending"
        return cls(**kwargs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id_part(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_]+", "_", (value or "").strip())
    return out.strip("_") or "item"


def _change_id(*parts: str) -> str:
    raw = "::".join(parts)
    safe = "_".join(_safe_id_part(p) for p in parts)
    if len(safe) <= 96:
        return f"rc_{safe}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"rc_{safe[:80]}_{digest}"


def _graph_edge_id(source_id: str, target_id: str, kind: str) -> str:
    return f"graph_edge_{source_id}_{target_id}_{kind}"


def _payload_equal(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return left == right


def _mark_updated(change: ReviewableChange) -> None:
    change.updated_at = _now_iso()


def _block(change: ReviewableChange, conflicts: List[str]) -> ReviewableChange:
    change.status = "blocked"
    change.conflicts = conflicts
    change.revert_available = bool(change.applied_at)
    _mark_updated(change)
    return change


def _upsert_pending_change(state: "StoryState", proposal: ReviewableChange) -> Optional[ReviewableChange]:
    existing = state.reviewable_changes.get(proposal.id)
    if existing and existing.status != "pending":
        return None
    if existing:
        proposal.created_at = existing.created_at
        proposal.status = existing.status
        proposal.applied_at = existing.applied_at
        proposal.reviewed_at = existing.reviewed_at
    state.reviewable_changes[proposal.id] = proposal
    return proposal


def _plot_thread_node_payload(thread: Any) -> Dict[str, Any]:
    node = StoryGraphNode(
        id=f"graph_node_{thread.id}",
        kind=thread.thread_type or "plot_thread",
        title=thread.name,
        description=thread.description,
        status=thread.status,
        priority=thread.priority,
        linked_character_ids=list(thread.related_characters),
        legacy_plot_thread_id=thread.id,
        created_from="reviewable_change",
        sort_order=thread.sort_order,
    )
    return node.to_dict()


def _edge_payload(source_id: str, target_id: str, kind: str, label: str = "") -> Dict[str, Any]:
    return StoryGraphEdge(
        id=_graph_edge_id(source_id, target_id, kind),
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=label,
    ).to_dict()


def _has_graph_node_for_plot_thread(state: "StoryState", thread_id: str) -> bool:
    return any(
        node.legacy_plot_thread_id == thread_id
        for node in state.story_graph_nodes.values()
    )


def _has_character_relationship_edge(state: "StoryState", source_id: str, target_id: str) -> bool:
    pair = {source_id, target_id}
    return any(
        edge.kind == "character_relationship"
        and {edge.source_id, edge.target_id} == pair
        for edge in state.story_graph_edges.values()
    )


def generate_graph_reviewable_changes(state: "StoryState") -> List[ReviewableChange]:
    """Create deterministic graph suggestions without applying them."""
    generated: List[ReviewableChange] = []

    for thread in state.get_ordered_plot_threads():
        if _has_graph_node_for_plot_thread(state, thread.id):
            continue
        node_id = f"graph_node_{thread.id}"
        if node_id in state.story_graph_nodes:
            continue
        after = _plot_thread_node_payload(thread)
        change = ReviewableChange(
            id=_change_id("graph_node", "legacy_plot_thread", thread.id),
            kind="story_graph_node",
            title=f"Create graph node for plot thread {thread.id}",
            summary=f"Adds a story graph node linked to legacy plot thread id {thread.id}.",
            reason=f"Legacy plot thread id {thread.id} has no linked graph node.",
            source=GRAPH_SUGGESTION_SOURCE,
            confidence=1.0,
            target={"type": "story_graph_node", "id": node_id},
            before=None,
            after=after,
            revert_available=False,
        )
        saved = _upsert_pending_change(state, change)
        if saved:
            generated.append(saved)

    seen_pairs: set[tuple[str, str]] = set()
    for char_id in sorted(state.characters):
        char = state.characters[char_id]
        for other_id in sorted(char.relationships):
            if other_id not in state.characters:
                continue
            pair = tuple(sorted((char.id, other_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            if _has_character_relationship_edge(state, char.id, other_id):
                continue
            label = display_relationship_label(char.relationships.get(other_id, ""))
            after = _edge_payload(char.id, other_id, "character_relationship", label)
            change = ReviewableChange(
                id=_change_id("graph_edge", "character_relationship", char.id, other_id),
                kind="story_graph_edge",
                title=f"Create relationship edge {char.id} to {other_id}",
                summary=f"Adds a character_relationship edge for character ids {char.id} and {other_id}.",
                reason=f"Character id {char.id} stores a relationship to {other_id}, but no graph edge exists.",
                source=GRAPH_SUGGESTION_SOURCE,
                confidence=1.0,
                target={"type": "story_graph_edge", "id": after["id"]},
                before=None,
                after=after,
                revert_available=False,
            )
            saved = _upsert_pending_change(state, change)
            if saved:
                generated.append(saved)

    desired_pins: Dict[str, set[int]] = {}
    for chapter_number, brief in sorted(state.chapter_briefs.items()):
        for node_id in brief.active_node_ids or []:
            node = state.story_graph_nodes.get(node_id)
            if node is not None and node_eligible_at_chapter(node, chapter_number):
                desired_pins.setdefault(node_id, set()).add(chapter_number)
    for chapter_number, beats in sorted(state.chapter_beats.items()):
        for beat in beats:
            for node_id in beat.linked_node_ids or []:
                node = state.story_graph_nodes.get(node_id)
                if node is not None and node_eligible_at_chapter(node, chapter_number):
                    desired_pins.setdefault(node_id, set()).add(chapter_number)

    for node_id in sorted(desired_pins):
        node = state.story_graph_nodes[node_id]
        current = sorted(set(node.chapter_pins or []))
        missing = sorted(desired_pins[node_id] - set(current))
        if not missing:
            continue
        after_pins = sorted(set(current) | set(missing))
        change = ReviewableChange(
            id=_change_id("graph_pin", node_id),
            kind="story_graph_chapter_pin",
            title=f"Pin graph node {node_id} to {len(missing)} chapter(s)",
            summary=f"Adds missing chapter pins {missing} to graph node id {node_id}.",
            reason=f"Brief or beat links reference node id {node_id} in chapters {missing}.",
            source=GRAPH_SUGGESTION_SOURCE,
            confidence=0.95,
            target={"type": "story_graph_node", "id": node_id, "field": "chapter_pins"},
            before={"chapter_pins": current},
            after={"chapter_pins": after_pins},
            revert_available=False,
        )
        saved = _upsert_pending_change(state, change)
        if saved:
            generated.append(saved)

    return generated


def apply_reviewable_change(state: "StoryState", change: ReviewableChange) -> ReviewableChange:
    """Apply a supported reviewable change, blocking on conflicts instead of overwriting."""
    if change.status in {"dismissed", "reverted", "reviewed"}:
        raise ReviewableChangeActionError(f"Cannot apply a {change.status} change.")
    if change.status == "applied_needs_review":
        return change

    conflicts = _apply_graph_change(state, change)
    if conflicts:
        return _block(change, conflicts)

    now = _now_iso()
    change.status = "applied_needs_review"
    change.applied_at = change.applied_at or now
    change.updated_at = now
    change.conflicts = []
    change.revert_available = True
    return change


def dismiss_reviewable_change(change: ReviewableChange) -> ReviewableChange:
    if change.status in {"applied_needs_review", "reviewed"}:
        raise ReviewableChangeActionError("Applied changes must be reverted or marked reviewed.")
    change.status = "dismissed"
    change.conflicts = []
    change.revert_available = False
    _mark_updated(change)
    return change


def mark_reviewable_change_reviewed(change: ReviewableChange) -> ReviewableChange:
    change.status = "reviewed"
    change.reviewed_at = _now_iso()
    change.conflicts = []
    change.revert_available = bool(change.applied_at)
    _mark_updated(change)
    return change


def revert_reviewable_change(state: "StoryState", change: ReviewableChange) -> ReviewableChange:
    if not change.applied_at:
        raise ReviewableChangeActionError("Only applied changes can be reverted.")
    if change.status == "reverted":
        return change

    conflicts = _revert_graph_change(state, change)
    if conflicts:
        return _block(change, conflicts)

    change.status = "reverted"
    change.conflicts = []
    change.revert_available = False
    _mark_updated(change)
    return change


def _apply_graph_change(state: "StoryState", change: ReviewableChange) -> List[str]:
    target = change.target or {}
    after = change.after or {}
    if change.kind == "story_graph_node":
        node_id = target.get("id") or after.get("id")
        if not node_id:
            return ["Missing story graph node id."]
        current = state.story_graph_nodes.get(node_id)
        if current is not None:
            if _payload_equal(current.to_dict(), after):
                return []
            return [f"Story graph node id {node_id} already exists with different fields."]
        state.add_story_graph_node(StoryGraphNode.from_dict(after))
        return []

    if change.kind == "story_graph_edge":
        edge_id = target.get("id") or after.get("id")
        if not edge_id:
            return ["Missing story graph edge id."]
        current = state.story_graph_edges.get(edge_id)
        if current is not None:
            if _payload_equal(current.to_dict(), after):
                return []
            return [f"Story graph edge id {edge_id} already exists with different fields."]
        state.add_story_graph_edge(StoryGraphEdge.from_dict(after))
        return []

    if change.kind == "story_graph_chapter_pin":
        node_id = target.get("id")
        node = state.story_graph_nodes.get(node_id)
        if node is None:
            return [f"Story graph node id {node_id} does not exist."]
        before_pins = sorted((change.before or {}).get("chapter_pins") or [])
        after_pins = sorted(after.get("chapter_pins") or [])
        current_pins = sorted(node.chapter_pins or [])
        if current_pins == after_pins:
            return []
        if current_pins != before_pins:
            return [f"Chapter pins for node id {node_id} changed since suggestion generation."]
        node.chapter_pins = after_pins
        return []

    return [f"Unsupported reviewable change kind {change.kind}."]


def _revert_graph_change(state: "StoryState", change: ReviewableChange) -> List[str]:
    target = change.target or {}
    after = change.after or {}
    if change.kind == "story_graph_node":
        node_id = target.get("id") or after.get("id")
        current = state.story_graph_nodes.get(node_id)
        if current is None:
            return []
        if not _payload_equal(current.to_dict(), after):
            return [f"Story graph node id {node_id} changed after apply."]
        edge_refs = [
            edge.id for edge in state.story_graph_edges.values()
            if edge.source_id == node_id or edge.target_id == node_id
        ]
        if edge_refs:
            return [f"Story graph node id {node_id} still has edge references: {edge_refs}."]
        brief_refs = [
            number for number, brief in state.chapter_briefs.items()
            if node_id in (brief.active_node_ids or [])
        ]
        if brief_refs:
            return [f"Story graph node id {node_id} is still active in chapter briefs {sorted(brief_refs)}."]
        beat_refs = [
            number for number, beats in state.chapter_beats.items()
            if any(node_id in (beat.linked_node_ids or []) for beat in beats)
        ]
        if beat_refs:
            return [f"Story graph node id {node_id} is still linked from chapter beats {sorted(beat_refs)}."]
        state.delete_story_graph_node(node_id)
        return []

    if change.kind == "story_graph_edge":
        edge_id = target.get("id") or after.get("id")
        current = state.story_graph_edges.get(edge_id)
        if current is None:
            return []
        if not _payload_equal(current.to_dict(), after):
            return [f"Story graph edge id {edge_id} changed after apply."]
        state.delete_story_graph_edge(edge_id)
        return []

    if change.kind == "story_graph_chapter_pin":
        node_id = target.get("id")
        node = state.story_graph_nodes.get(node_id)
        if node is None:
            return [f"Story graph node id {node_id} does not exist."]
        before_pins = sorted((change.before or {}).get("chapter_pins") or [])
        after_pins = sorted(after.get("chapter_pins") or [])
        current_pins = sorted(node.chapter_pins or [])
        if current_pins != after_pins:
            return [f"Chapter pins for node id {node_id} changed after apply."]
        node.chapter_pins = before_pins
        return []

    return [f"Unsupported reviewable change kind {change.kind}."]
