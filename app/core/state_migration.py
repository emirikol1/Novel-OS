"""
Schema migration for story_state.json (Structure V2).

Runs ordered, idempotent v1→v2 steps for graph nodes, lifespans, chapter
briefs, chapter beats, and chapter pins.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from story_graph import (
    migrate_plot_threads_to_graph,
    normalize_brief_characters,
    normalize_start_chapter,
)

if TYPE_CHECKING:
    from state_manager import StoryState

CURRENT_SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1


@dataclass
class MigrationResult:
    """Outcome of migrate_story_state()."""

    changed: bool
    source_version: int
    target_version: int
    steps_applied: List[str] = field(default_factory=list)


def detect_schema_version(raw: Dict[str, Any]) -> int:
    """Read schema_version from raw JSON; missing or null => legacy v1."""
    version = raw.get("schema_version")
    if version is None:
        return LEGACY_SCHEMA_VERSION
    return int(version)


def _step_ensure_schema_version(state: "StoryState", target_version: int) -> bool:
    """Step 1: normalize missing schema_version on in-memory state."""
    if getattr(state, "schema_version", None) is None:
        state.schema_version = LEGACY_SCHEMA_VERSION
        return True
    return False


def _graph_is_empty(state: "StoryState") -> bool:
    return not state.story_graph_nodes and not state.story_graph_edges


def _step_migrate_graph_from_plot_threads(state: "StoryState", target_version: int) -> bool:
    """Step 2: plot_threads -> story_graph_nodes when graph is empty."""
    if not _graph_is_empty(state) or not state.plot_threads:
        return False
    result = migrate_plot_threads_to_graph(state, force=False)
    return not result.get("skipped", True)


def _step_backfill_node_lifespan(state: "StoryState", target_version: int) -> bool:
    """Step 3: copy plot thread lifespan onto graph nodes."""
    changed = False
    for node in state.story_graph_nodes.values():
        if int(node.start_chapter or 0) > 0:
            continue
        legacy_id = (node.legacy_plot_thread_id or "").strip()
        thread = state.plot_threads.get(legacy_id) if legacy_id else None
        if thread is not None:
            node.start_chapter = normalize_start_chapter(thread.start_chapter)
            node.resolution_chapter = thread.target_resolution_chapter
        else:
            node.start_chapter = 1
            node.resolution_chapter = None
        changed = True
    return changed


def _step_sync_brief_mentioned_characters(state: "StoryState", target_version: int) -> bool:
    """Step 4: normalize brief cast state lists."""
    changed = False
    for brief in state.chapter_briefs.values():
        before_mentioned = list(brief.mentioned_character_ids or [])
        before_active = list(brief.active_character_ids or [])
        normalize_brief_characters(brief)
        if (
            brief.mentioned_character_ids != before_mentioned
            or brief.active_character_ids != before_active
        ):
            changed = True
    return changed


def _step_migrate_brief_beats_to_chapter_beats(state: "StoryState", target_version: int) -> bool:
    """Step 5: old brief beat strings -> chapter_beats, then clear old fields."""
    from chapter_brief_utils import migrate_legacy_brief_beats_to_chapter_beats  # noqa: WPS433

    changed = False
    for chapter_number, brief in state.chapter_briefs.items():
        before = (
            len(state.chapter_beats.get(chapter_number, [])),
            list(brief.required_beats or []),
            list(brief.landed_beats or []),
        )
        migrate_legacy_brief_beats_to_chapter_beats(state, chapter_number, brief)
        after = (
            len(state.chapter_beats.get(chapter_number, [])),
            list(brief.required_beats or []),
            list(brief.landed_beats or []),
        )
        if before != after:
            changed = True
    return changed


def _step_sync_chapter_pins_from_briefs(state: "StoryState", target_version: int) -> bool:
    """Step 6: additive union of chapter_pins from brief active_node_ids."""
    changed = False
    for brief in state.chapter_briefs.values():
        chapter_number = brief.chapter_number
        active = {
            (nid or "").strip()
            for nid in (brief.active_node_ids or [])
            if (nid or "").strip()
        }
        for node_id in active:
            node = state.story_graph_nodes.get(node_id)
            if node is None:
                continue
            pins = list(node.chapter_pins or [])
            if chapter_number not in pins:
                pins.append(chapter_number)
                node.chapter_pins = sorted(set(pins))
                changed = True
    return changed


def _step_finalize_schema_version(state: "StoryState", target_version: int) -> bool:
    """Step 7: persist target schema_version on state."""
    if state.schema_version != target_version:
        state.schema_version = target_version
        return True
    return False


_MIGRATION_STEPS: List[tuple[str, Callable[["StoryState", int], bool]]] = [
    ("ensure_schema_version", _step_ensure_schema_version),
    ("migrate_graph_from_plot_threads", _step_migrate_graph_from_plot_threads),
    ("backfill_node_lifespan", _step_backfill_node_lifespan),
    ("sync_brief_mentioned_characters", _step_sync_brief_mentioned_characters),
    ("migrate_brief_beats_to_chapter_beats", _step_migrate_brief_beats_to_chapter_beats),
    ("sync_chapter_pins_from_briefs", _step_sync_chapter_pins_from_briefs),
    ("finalize_schema_version", _step_finalize_schema_version),
]


def migrate_story_state(
    state: "StoryState",
    *,
    target_version: int = CURRENT_SCHEMA_VERSION,
) -> MigrationResult:
    """
    Run v1→v2 migration steps in fixed order. Idempotent: safe to call repeatedly.
    """
    source_version = getattr(state, "schema_version", LEGACY_SCHEMA_VERSION)
    if source_version is None:
        source_version = LEGACY_SCHEMA_VERSION
        state.schema_version = source_version

    if source_version >= target_version:
        cleanup_steps: List[str] = []
        changed = False
        if _step_migrate_brief_beats_to_chapter_beats(state, target_version):
            cleanup_steps.append("migrate_brief_beats_to_chapter_beats")
            changed = True
        return MigrationResult(
            changed=changed,
            source_version=source_version,
            target_version=target_version,
            steps_applied=cleanup_steps,
        )

    steps_applied: List[str] = []
    changed = False
    for name, step_fn in _MIGRATION_STEPS:
        if step_fn(state, target_version):
            steps_applied.append(name)
            changed = True

    return MigrationResult(
        changed=changed,
        source_version=source_version,
        target_version=target_version,
        steps_applied=steps_applied,
    )


def migrate_raw_story_state_json(
    raw: Dict[str, Any],
    *,
    target_version: int = CURRENT_SCHEMA_VERSION,
) -> tuple[Dict[str, Any], MigrationResult]:
    """
    Apply migration to a raw story_state.json dict (for unit tests).

    Does not touch disk; returns a new dict with schema_version updated when needed.
    """
    from copy import deepcopy

    data = deepcopy(raw)
    source_version = detect_schema_version(data)
    if source_version >= target_version:
        return data, MigrationResult(
            changed=False,
            source_version=source_version,
            target_version=target_version,
            steps_applied=[],
        )

    import tempfile
    from pathlib import Path

    from state_manager import StoryState

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        state_dir = project_dir / "outputs" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "story_state.json"
        state_file.write_text(json.dumps(data), encoding="utf-8")

        state = StoryState(str(project_dir), persist_migration=False, auto_migrate=False)
        result = migrate_story_state(state, target_version=target_version)
        if result.changed:
            state.save_state()
            data = json.loads(state_file.read_text(encoding="utf-8"))
        return data, result
