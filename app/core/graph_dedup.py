"""
Detect and merge duplicate story graph nodes.

Complements legacy plot-thread dedup (entity_dedup) — does not replace it.
Used by the Story Graph panel and chapter-brief hygiene.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from entity_dedup import DuplicateGroup, _union_find_groups, plot_match_score
from log_redaction import size_ref

if TYPE_CHECKING:
    from state_manager import StoryState


def description_match_score(a: str, b: str) -> float:
    """0–1 similarity between two node descriptions."""
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    return SequenceMatcher(None, a, b).ratio()


def graph_node_match_score(
    title_a: str,
    title_b: str,
    *,
    kind_a: str = "",
    kind_b: str = "",
    description_a: str = "",
    description_b: str = "",
    legacy_a: str = "",
    legacy_b: str = "",
) -> float:
    """0–1 similarity between two story graph nodes."""
    title_score = plot_match_score(title_a, title_b)
    if title_a.strip().lower() == title_b.strip().lower():
        title_score = max(title_score, 1.0)

    if legacy_a and legacy_b and legacy_a == legacy_b:
        return max(title_score, 0.92)

    if title_score < 0.78:
        desc_score = description_match_score(description_a, description_b)
        if desc_score >= 0.9 and kind_a == kind_b and kind_a:
            return 0.8 + desc_score * 0.15
        return 0.0

    desc_score = description_match_score(description_a, description_b)
    kind_bonus = 0.04 if kind_a and kind_a == kind_b else 0.0
    combined = title_score * 0.82 + desc_score * 0.13 + kind_bonus
    if title_score >= 0.95:
        combined = max(combined, title_score)
    return min(1.0, combined)


def _node_richness(state: "StoryState", node_id: str) -> int:
    node = state.story_graph_nodes[node_id]
    score = len(node.title) * 2 + len(node.description or "")
    if node.linked_character_ids:
        score += len(node.linked_character_ids) * 3
    if node.legacy_plot_thread_id:
        score += 5
    edge_count = sum(
        1 for e in state.story_graph_edges.values()
        if e.source_id == node_id or e.target_id == node_id
    )
    score += edge_count * 2
    return score


def _pick_graph_keep(state: "StoryState", ids: List[str]) -> str:
    return max(ids, key=lambda nid: _node_richness(state, nid))


def find_graph_duplicate_groups(
    state: "StoryState", *, min_score: float = 0.78,
) -> List[DuplicateGroup]:
    """Cluster story graph nodes with similar titles/kinds/descriptions."""
    nodes = list(state.story_graph_nodes.values())
    if len(nodes) < 2:
        return []

    pairs: List[tuple[str, str, float]] = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            score = graph_node_match_score(
                a.title,
                b.title,
                kind_a=a.kind,
                kind_b=b.kind,
                description_a=a.description,
                description_b=b.description,
                legacy_a=a.legacy_plot_thread_id,
                legacy_b=b.legacy_plot_thread_id,
            )
            if score >= min_score:
                pairs.append((a.id, b.id, score))

    raw_groups = _union_find_groups([(a, b) for a, b, _ in pairs])
    score_map = {(a, b): s for a, b, s in pairs}
    score_map.update({(b, a): s for a, b, s in pairs})

    out: List[DuplicateGroup] = []
    for g in raw_groups:
        keep = _pick_graph_keep(state, g)
        confs = [score_map.get((a, b), min_score) for i, a in enumerate(g) for b in g[i + 1:]]
        confidence = max(confs) if confs else min_score
        titles = [state.story_graph_nodes[nid].title for nid in g]
        kinds = {state.story_graph_nodes[nid].kind for nid in g}
        kind_note = f" ({', '.join(sorted(kinds))})" if len(kinds) == 1 else ""
        out.append(DuplicateGroup(
            kind="story_graph_node",
            confidence=round(confidence, 2),
            reason=f"Similar graph nodes{kind_note}: {', '.join(titles)}",
            suggested_keep_id=keep,
            members=[
                {
                    "id": nid,
                    "label": state.story_graph_nodes[nid].title,
                    "node_kind": state.story_graph_nodes[nid].kind,
                    "legacy_plot_thread_id": state.story_graph_nodes[nid].legacy_plot_thread_id,
                }
                for nid in g
            ],
        ))
    out.sort(key=lambda x: (-x.confidence, x.members[0]["label"]))
    return out


def scan_graph_duplicates(state: "StoryState", *, min_score: float = 0.78) -> Dict[str, Any]:
    return {"groups": find_graph_duplicate_groups(state, min_score=min_score)}


def filter_stale_graph_groups(
    state: "StoryState", groups: List[dict],
) -> List[dict]:
    """Drop suggestion groups whose members no longer exist."""
    valid: List[dict] = []
    for g in groups:
        members = g.get("members") or []
        if len(members) < 2:
            continue
        if all(m.get("id") in state.story_graph_nodes for m in members):
            valid.append(g)
    return valid


def merge_graph_nodes(
    state: "StoryState",
    keep_id: str,
    merge_ids: List[str],
    *,
    title_override: str = "",
) -> List[str]:
    """Merge duplicate graph nodes into keep_id; rewire edges and chapter briefs."""
    log: List[str] = []
    if keep_id not in state.story_graph_nodes:
        raise ValueError(f"Unknown graph node: {keep_id}")

    merge_ids = [mid for mid in merge_ids if mid != keep_id and mid in state.story_graph_nodes]
    if not merge_ids:
        return log

    keep = state.story_graph_nodes[keep_id]
    merge_set = set(merge_ids)

    if title_override.strip():
        keep.title = title_override.strip()
        log.append(f"Set keep title ({size_ref(keep.title)})")

    linked = set(keep.linked_character_ids)
    descriptions: List[str] = []
    if keep.description.strip():
        descriptions.append(keep.description.strip())

    for mid in merge_ids:
        node = state.story_graph_nodes[mid]
        log.append(f"Merged graph node {mid} into {keep_id} (title: {size_ref(node.title)})")
        linked.update(node.linked_character_ids)
        if node.description.strip() and node.description.strip() not in descriptions:
            descriptions.append(node.description.strip())
        if not keep.legacy_plot_thread_id and node.legacy_plot_thread_id:
            keep.legacy_plot_thread_id = node.legacy_plot_thread_id

    keep.linked_character_ids = sorted(linked)
    if len(descriptions) > 1:
        keep.description = "\n\n".join(descriptions)
    elif descriptions and not keep.description.strip():
        keep.description = descriptions[0]

    # Rewire edges from merged nodes to keep_id; drop self-loops and duplicates.
    for edge in list(state.story_graph_edges.values()):
        if edge.source_id in merge_set:
            edge.source_id = keep_id
        if edge.target_id in merge_set:
            edge.target_id = keep_id

    to_delete_edges: List[str] = []
    seen_keys: Dict[tuple[str, str, str], str] = {}
    for eid, edge in list(state.story_graph_edges.items()):
        if edge.source_id == edge.target_id:
            to_delete_edges.append(eid)
            continue
        key = (edge.source_id, edge.target_id, edge.kind)
        if key in seen_keys:
            to_delete_edges.append(eid)
        else:
            seen_keys[key] = eid

    for eid in to_delete_edges:
        state.delete_story_graph_edge(eid)
        log.append(f"Removed redundant edge {eid}")

    for brief in state.chapter_briefs.values():
        new_ids: List[str] = []
        for nid in brief.active_node_ids:
            resolved = keep_id if nid in merge_set else nid
            if resolved not in new_ids:
                new_ids.append(resolved)
        if new_ids != brief.active_node_ids:
            brief.active_node_ids = new_ids
            log.append(f"Updated chapter {brief.chapter_number} brief active nodes")

    for mid in merge_ids:
        state.delete_story_graph_node(mid)

    return log


def auto_resolve_graph_duplicates(
    state: "StoryState", *, min_confidence: float = 0.95,
) -> List[str]:
    """Auto-merge only very high-confidence graph duplicate groups."""
    log: List[str] = []
    for group in find_graph_duplicate_groups(state):
        if group.confidence < min_confidence:
            continue
        merge_ids = [m["id"] for m in group.members if m["id"] != group.suggested_keep_id]
        if merge_ids:
            log.extend(merge_graph_nodes(state, group.suggested_keep_id, merge_ids))
    return log
