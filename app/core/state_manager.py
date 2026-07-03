"""
Novel OS - State Management System

Centralized state management for the Novel OS architecture.
Maintains story bible, character database, plot tracker, timeline, and style profile.
"""

import json
import os
import shutil
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict, fields
from typing import List, Dict, Optional, Any, Set
from pathlib import Path

from story_graph import (
    ChapterBeat,
    ChapterBrief,
    StoryGraphEdge,
    StoryGraphNode,
    migrate_plot_threads_to_graph,
)
from state_migration import (
    CURRENT_SCHEMA_VERSION,
    LEGACY_SCHEMA_VERSION,
    migrate_story_state,
)
from state_integrity import (
    append_state_history,
    merge_save_payload,
    read_best_state_json,
    reconcile_chapters_from_artifacts,
    should_recover_wiped_registry_on_load,
)


_project_locks: dict[str, threading.RLock] = {}
_project_locks_guard = threading.Lock()


def project_state_lock(project_path: str) -> threading.RLock:
    """Serialize load/apply/save for one project (parallel miners, extractors, etc.)."""
    key = str(Path(project_path).resolve())
    with _project_locks_guard:
        if key not in _project_locks:
            _project_locks[key] = threading.RLock()
        return _project_locks[key]


@dataclass
class Character:
    """Represents a character in the story."""
    id: str
    full_name: str
    role: str  # protagonist, antagonist, supporting, etc.
    age: Optional[int] = None
    physical_description: str = ""
    internal_desire: str = ""
    external_goal: str = ""
    fear: str = ""
    weakness: str = ""
    strength: str = ""
    secret: str = ""
    arc_stage: str = "beginning"  # beginning, middle, climax, resolution
    arc_progress: int = 0  # 0-100
    relationships: Dict[str, str] = field(default_factory=dict)
    knowledge: List[str] = field(default_factory=list)
    possessions: List[str] = field(default_factory=list)
    current_location: str = ""
    emotional_state: str = ""
    last_appearance_chapter: int = 0
    notes: str = ""
    aliases: List[str] = field(default_factory=list)
    portrait_filename: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        from dataclasses import fields
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("aliases", [])
        return cls(**kwargs)
    
    def all_names(self) -> List[str]:
        """Canonical name plus registered aliases."""
        names = [self.full_name]
        names.extend(a for a in self.aliases if a.strip())
        return names


@dataclass
class PlotThread:
    """Represents a plot thread or storyline."""
    id: str
    name: str
    description: str
    thread_type: str  # main, subplot, character_arc, mystery
    status: str = "active"  # active, resolved, abandoned, foreshadowed
    priority: int = 1  # 1-5, 5 being highest
    sort_order: int = 0
    subplots: List[str] = field(default_factory=list)
    start_chapter: int = 0
    target_resolution_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)
    related_threads: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_planted: List[int] = field(default_factory=list)
    last_updated_chapter: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlotThread':
        from dataclasses import fields
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("subplots", [])
        kwargs.setdefault("sort_order", 0)
        return cls(**kwargs)


@dataclass
class ChapterState:
    """Represents the state of a chapter."""
    number: int
    title: str = ""
    title_source: str = ""  # "" | manual | auto
    part_of: int = 0  # parent chapter when split (e.g. 1a/1b → part_of=1)
    part_label: str = ""  # "a", "b", … when this row is a split segment
    status: str = "planned"  # planned, drafting, drafted, editing, edited, validated, complete
    pov_character: str = ""
    location: str = ""
    time: str = ""
    word_count: int = 0
    target_word_count: int = 2500
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    plot_advances: List[str] = field(default_factory=list)
    character_development: Dict[str, str] = field(default_factory=dict)
    emotional_beats: List[str] = field(default_factory=list)
    new_information: List[str] = field(default_factory=list)
    foreshadowing_planted: List[str] = field(default_factory=list)
    foreshadowing_resolved: List[str] = field(default_factory=list)
    hooks_start: List[str] = field(default_factory=list)
    hooks_end: List[str] = field(default_factory=list)
    continuity_checks: Dict[str, Any] = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    last_modified: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChapterState':
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        return cls(**kwargs)


@dataclass
class StyleProfile:
    """Defines the writing style for the novel."""
    name: str = "default"
    description: str = ""
    tone: str = "neutral"  # dark, light, humorous, serious, etc.
    point_of_view: str = "third_limited"  # first, third_limited, third_omniscient
    tense: str = "past"  # past, present
    prose_style: str = "balanced"  # lyrical, minimalist, cinematic, intimate, suspenseful
    avg_sentence_length: int = 15
    vocabulary_level: str = "moderate"  # simple, moderate, complex
    dialogue_ratio: float = 0.3  # 0-1
    description_ratio: float = 0.3  # 0-1
    internal_monologue_ratio: float = 0.2  # 0-1
    paragraph_max_sentences: int = 5
    chapter_target_words: int = 2500
    scene_break_marker: str = "***"
    dialect_notes: str = ""
    genre_conventions: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    preferred_words: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StyleProfile':
        return cls(**data)


@dataclass
class TimelineEvent:
    """Represents an event in the story timeline."""
    id: str
    description: str
    chapter: int
    day: Optional[int] = None
    time: Optional[str] = None
    location: str = ""
    characters_present: List[str] = field(default_factory=list)
    event_type: str = "scene"  # scene, backstory, flashback, summary
    significance: str = "minor"  # minor, major, turning_point, climax
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimelineEvent':
        return cls(**data)


class StoryState:
    """
    Central state manager for Novel OS.
    Maintains all story data and provides CRUD operations.
    """
    
    def __init__(
        self,
        project_path: str,
        *,
        persist_migration: bool = False,
        auto_migrate: bool = True,
    ):
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / "outputs" / "state"
        self.state_file = self.state_dir / "story_state.json"
        self._persist_migration = persist_migration
        
        # Core data structures
        self.schema_version: int = LEGACY_SCHEMA_VERSION
        self.metadata: Dict[str, Any] = {}
        self.story_bible: Dict[str, Any] = {}
        self.characters: Dict[str, Character] = {}
        self.plot_threads: Dict[str, PlotThread] = {}
        self.chapters: Dict[int, ChapterState] = {}
        self.timeline: List[TimelineEvent] = []
        self.style_profile: StyleProfile = StyleProfile()
        # Story graph / plot mind map (Phase 1 — stored in story_state.json)
        self.story_graph_nodes: Dict[str, StoryGraphNode] = {}
        self.story_graph_edges: Dict[str, StoryGraphEdge] = {}
        self.chapter_briefs: Dict[int, ChapterBrief] = {}
        self.chapter_beats: Dict[int, List[ChapterBeat]] = {}
        
        # Session tracking
        self.session_log: List[Dict[str, Any]] = []
        self._loaded_from_disk = False
        self._pending_chapter_removals: Set[int] = set()
        self._pending_character_removals: Set[str] = set()
        self._pending_plot_removals: Set[str] = set()
        self._pending_graph_node_removals: Set[str] = set()
        self._pending_graph_edge_removals: Set[str] = set()
        self._pending_chapter_brief_removals: Set[int] = set()
        self._pending_chapter_beat_removals: Set[int] = set()
        
        self._ensure_directories()
        self._load_state()
        if auto_migrate:
            self._maybe_migrate_after_load()
    
    def _maybe_migrate_after_load(self) -> None:
        # Never auto-persist migration on a fresh in-memory project (missing/corrupt load).
        if not self._loaded_from_disk:
            return
        result = migrate_story_state(self)
        if result.changed and self._persist_migration:
            self.save_state()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _read_state_json(self) -> Optional[Dict[str, Any]]:
        return read_best_state_json(self.state_file)

    def _apply_state_dict(self, data: Dict[str, Any]) -> None:
        raw_version = data.get('schema_version')
        self.schema_version = (
            int(raw_version) if raw_version is not None else LEGACY_SCHEMA_VERSION
        )
        self.metadata = data.get('metadata', {})
        self.story_bible = data.get('story_bible', {})
        self.characters = {
            k: Character.from_dict(v)
            for k, v in data.get('characters', {}).items()
        }
        self.plot_threads = {
            k: PlotThread.from_dict(v)
            for k, v in data.get('plot_threads', {}).items()
        }
        self.chapters = {
            int(k): ChapterState.from_dict(v)
            for k, v in data.get('chapters', {}).items()
        }
        self.timeline = [
            TimelineEvent.from_dict(e)
            for e in data.get('timeline', [])
        ]
        self.style_profile = StyleProfile.from_dict(
            data.get('style_profile', {})
        )
        self.story_graph_nodes = {
            k: StoryGraphNode.from_dict(v)
            for k, v in data.get('story_graph_nodes', {}).items()
        }
        self.story_graph_edges = {
            k: StoryGraphEdge.from_dict(v)
            for k, v in data.get('story_graph_edges', {}).items()
        }
        self.chapter_briefs = {
            int(k): ChapterBrief.from_dict(v)
            for k, v in data.get('chapter_briefs', {}).items()
        }
        self.chapter_beats = {
            int(k): [ChapterBeat.from_dict(b) for b in beats]
            for k, beats in data.get('chapter_beats', {}).items()
        }
        self.session_log = data.get('session_log', [])
    
    def _load_state(self):
        """Load state from disk if it exists (serialized per project)."""
        lock = project_state_lock(str(self.project_path))
        with lock:
            data = self._read_state_json()
            if data is None:
                self._loaded_from_disk = False
                return
            self._apply_state_dict(data)
            self._loaded_from_disk = True
            persisted_nums = {int(k) for k in data.get("chapters", {})}
            if persisted_nums:
                reconcile_chapters_from_artifacts(self, registry_numbers=persisted_nums)
            elif should_recover_wiped_registry_on_load(self.state_file, data):
                reconcile_chapters_from_artifacts(self, registry_numbers=set())

    def _state_payload(self) -> Dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'metadata': self.metadata,
            'story_bible': self.story_bible,
            'characters': {k: v.to_dict() for k, v in self.characters.items()},
            'plot_threads': {k: v.to_dict() for k, v in self.plot_threads.items()},
            'chapters': {k: v.to_dict() for k, v in self.chapters.items()},
            'timeline': [e.to_dict() for e in self.timeline],
            'style_profile': self.style_profile.to_dict(),
            'story_graph_nodes': {k: v.to_dict() for k, v in self.story_graph_nodes.items()},
            'story_graph_edges': {k: v.to_dict() for k, v in self.story_graph_edges.items()},
            'chapter_briefs': {k: v.to_dict() for k, v in self.chapter_briefs.items()},
            'chapter_beats': {
                k: [b.to_dict() for b in beats]
                for k, beats in self.chapter_beats.items()
            },
            'session_log': self.session_log,
            'last_saved': datetime.now().isoformat(),
        }

    def save_state(self):
        """Save current state to disk (additive merge — registries cannot be wiped by stale writes)."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        lock = project_state_lock(str(self.project_path))
        with lock:
            on_disk: Dict[str, Any] = {}
            if self.state_file.exists():
                try:
                    on_disk = json.loads(self.state_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    on_disk = read_best_state_json(self.state_file) or {}

            on_disk_nums = {int(k) for k in on_disk.get("chapters", {})}
            registry_numbers = on_disk_nums | set(self.chapters.keys())
            reconcile_chapters_from_artifacts(self, registry_numbers=registry_numbers)
            incoming = self._state_payload()

            data = merge_save_payload(
                incoming,
                on_disk,
                self.project_path,
                chapter_removals=self._pending_chapter_removals,
                character_removals=self._pending_character_removals,
                plot_removals=self._pending_plot_removals,
                graph_node_removals=self._pending_graph_node_removals,
                graph_edge_removals=self._pending_graph_edge_removals,
                chapter_brief_removals=self._pending_chapter_brief_removals,
                chapter_beat_removals=self._pending_chapter_beat_removals,
            )
            self._pending_chapter_removals.clear()
            self._pending_character_removals.clear()
            self._pending_plot_removals.clear()
            self._pending_graph_node_removals.clear()
            self._pending_graph_edge_removals.clear()
            self._pending_chapter_brief_removals.clear()
            self._pending_chapter_beat_removals.clear()

            tmp_path = self.state_file.with_suffix('.json.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.state_file)
            backup_path = self.state_file.with_suffix('.json.bak')
            if data.get("chapters"):
                shutil.copy2(self.state_file, backup_path)
            append_state_history(self.state_file, data)
            self._loaded_from_disk = True
            self._apply_state_dict(data)
    
    # ===== Character Management =====
    
    def add_character(self, character: Character) -> str:
        """Add a new character to the database."""
        self.characters[character.id] = character
        self._log_action('character_added', {'character_id': character.id})
        return character.id
    
    def update_character(self, character_id: str, updates: Dict[str, Any]):
        """Update character fields."""
        if character_id in self.characters:
            char = self.characters[character_id]
            for key, value in updates.items():
                if hasattr(char, key):
                    setattr(char, key, value)
            self._log_action('character_updated', {
                'character_id': character_id,
                'updates': list(updates.keys())
            })
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """Retrieve a character by ID."""
        return self.characters.get(character_id)
    
    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Find a character by full name or alias (case-insensitive)."""
        needle = name.strip().lower()
        if not needle:
            return None
        for char in self.characters.values():
            if char.full_name.lower() == needle:
                return char
            for alias in char.aliases:
                if alias.strip().lower() == needle:
                    return char
        return None

    def add_character_alias(self, character_id: str, alias: str) -> bool:
        """Register an alternate name for a character."""
        alias = alias.strip()
        if not alias:
            return False
        char = self.characters.get(character_id)
        if char is None:
            return False
        if alias.lower() == char.full_name.lower():
            return False
        known = {char.full_name.lower(), *(a.lower() for a in char.aliases)}
        if alias.lower() in known:
            return False
        char.aliases.append(alias)
        self._log_action('character_alias_added', {'character_id': character_id, 'alias': alias})
        return True
    
    def get_all_characters(self) -> List[Character]:
        """Get all characters as a list."""
        return list(self.characters.values())
    
    def update_character_location(self, character_id: str, location: str, chapter: int):
        """Update a character's current location."""
        if character_id in self.characters:
            char = self.characters[character_id]
            char.current_location = location
            char.last_appearance_chapter = chapter
    
    def update_character_arc(self, character_id: str, new_stage: str, progress: int):
        """Update a character's arc stage and progress."""
        if character_id in self.characters:
            char = self.characters[character_id]
            char.arc_stage = new_stage
            char.arc_progress = max(0, min(100, progress))

    def delete_character(self, character_id: str) -> bool:
        """Remove a character and scrub references from plot threads and timeline."""
        char = self.characters.pop(character_id, None)
        if char is None:
            return False
        self._pending_character_removals.add(character_id)
        for thread in self.plot_threads.values():
            thread.related_characters = [
                cid for cid in thread.related_characters if cid != character_id
            ]
        self.timeline = [
            e for e in self.timeline if character_id not in e.characters_present
        ]
        for brief in self.chapter_briefs.values():
            brief.active_character_ids = [
                cid for cid in brief.active_character_ids if cid != character_id
            ]
            brief.mentioned_character_ids = [
                cid for cid in brief.mentioned_character_ids if cid != character_id
            ]
            if brief.pov_character_id == character_id:
                brief.pov_character_id = ""
        for node in self.story_graph_nodes.values():
            node.linked_character_ids = [
                cid for cid in node.linked_character_ids if cid != character_id
            ]
        self._log_action('character_deleted', {
            'character_id': character_id,
            'name': char.full_name,
        })
        return True
    
    # ===== Plot Thread Management =====
    
    def _plot_thread_sort_key(self, thread: PlotThread) -> tuple:
        return (thread.sort_order, -thread.priority, thread.name.lower())

    def get_ordered_plot_threads(self) -> List[PlotThread]:
        """All plot threads in display / prompt order."""
        threads = list(self.plot_threads.values())
        if threads and len({t.sort_order for t in threads}) == 1:
            threads.sort(key=lambda t: (-t.priority, t.name.lower()))
        else:
            threads.sort(key=self._plot_thread_sort_key)
        return threads

    def add_plot_thread(self, thread: PlotThread) -> str:
        """Add a new plot thread."""
        if self.plot_threads and thread.sort_order == 0:
            thread.sort_order = max(t.sort_order for t in self.plot_threads.values()) + 1
        self.plot_threads[thread.id] = thread
        self._log_action('plot_thread_added', {'thread_id': thread.id})
        return thread.id

    def reorder_plot_threads(self, ordered_ids: List[str]) -> None:
        """Persist drag-and-drop order."""
        for i, tid in enumerate(ordered_ids):
            if tid in self.plot_threads:
                self.plot_threads[tid].sort_order = i
        self._log_action('plot_threads_reordered', {'order': ordered_ids})
    
    def update_plot_thread(self, thread_id: str, updates: Dict[str, Any]):
        """Update plot thread fields."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            for key, value in updates.items():
                if hasattr(thread, key):
                    setattr(thread, key, value)
    
    def get_plot_thread(self, thread_id: str) -> Optional[PlotThread]:
        """Retrieve a plot thread by ID."""
        return self.plot_threads.get(thread_id)
    
    def get_active_plot_threads(self) -> List[PlotThread]:
        """Active plot threads in sort order (for prompts)."""
        return [t for t in self.get_ordered_plot_threads() if t.status == 'active']
    
    def get_unresolved_threads(self) -> List[PlotThread]:
        """Get threads that need resolution."""
        return [
            t for t in self.plot_threads.values()
            if t.status in ['active', 'foreshadowed']
        ]
    
    def add_milestone_to_thread(self, thread_id: str, description: str, chapter: int):
        """Add a milestone to a plot thread."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            milestone = {
                'description': description,
                'chapter': chapter,
                'timestamp': datetime.now().isoformat()
            }
            thread.milestones.append(milestone)
            thread.last_updated_chapter = chapter
    
    def resolve_plot_thread(self, thread_id: str, chapter: int):
        """Mark a plot thread as resolved."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            thread.status = 'resolved'
            self.add_milestone_to_thread(thread_id, 'Thread resolved', chapter)

    def delete_plot_thread(self, thread_id: str) -> bool:
        """Remove a plot thread."""
        if self.plot_threads.pop(thread_id, None) is None:
            return False
        self._pending_plot_removals.add(thread_id)
        self._log_action('plot_thread_deleted', {'thread_id': thread_id})
        return True

    # ===== Story Graph =====

    def get_ordered_story_graph_nodes(self) -> List[StoryGraphNode]:
        """Graph nodes in sort_order, then title."""
        nodes = list(self.story_graph_nodes.values())
        nodes.sort(key=lambda n: (n.sort_order, n.title.lower()))
        return nodes

    def add_story_graph_node(self, node: StoryGraphNode) -> str:
        self.story_graph_nodes[node.id] = node
        self._log_action('story_graph_node_added', {'node_id': node.id})
        return node.id

    def get_story_graph_node(self, node_id: str) -> Optional[StoryGraphNode]:
        return self.story_graph_nodes.get(node_id)

    def update_story_graph_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        node = self.story_graph_nodes.get(node_id)
        if node is None:
            return False
        for key, value in updates.items():
            if hasattr(node, key):
                setattr(node, key, value)
        self._log_action('story_graph_node_updated', {'node_id': node_id})
        return True

    def delete_story_graph_node(self, node_id: str) -> bool:
        if self.story_graph_nodes.pop(node_id, None) is None:
            return False
        self._pending_graph_node_removals.add(node_id)
        removed_edges = [
            eid for eid, edge in self.story_graph_edges.items()
            if edge.source_id == node_id or edge.target_id == node_id
        ]
        for eid in removed_edges:
            self._pending_graph_edge_removals.add(eid)
        self.story_graph_edges = {
            eid: edge for eid, edge in self.story_graph_edges.items()
            if eid not in removed_edges
        }
        for brief in self.chapter_briefs.values():
            brief.active_node_ids = [nid for nid in brief.active_node_ids if nid != node_id]
        for beats in self.chapter_beats.values():
            for beat in beats:
                beat.linked_node_ids = [
                    nid for nid in (beat.linked_node_ids or []) if nid != node_id
                ]
        self._log_action('story_graph_node_deleted', {'node_id': node_id})
        return True

    def add_story_graph_edge(self, edge: StoryGraphEdge) -> str:
        self.story_graph_edges[edge.id] = edge
        self._log_action('story_graph_edge_added', {'edge_id': edge.id})
        return edge.id

    def get_story_graph_edge(self, edge_id: str) -> Optional[StoryGraphEdge]:
        return self.story_graph_edges.get(edge_id)

    def update_story_graph_edge(self, edge_id: str, updates: Dict[str, Any]) -> bool:
        edge = self.story_graph_edges.get(edge_id)
        if edge is None:
            return False
        for key, value in updates.items():
            if hasattr(edge, key):
                setattr(edge, key, value)
        self._log_action('story_graph_edge_updated', {'edge_id': edge_id})
        return True

    def delete_story_graph_edge(self, edge_id: str) -> bool:
        if self.story_graph_edges.pop(edge_id, None) is None:
            return False
        self._pending_graph_edge_removals.add(edge_id)
        self._log_action('story_graph_edge_deleted', {'edge_id': edge_id})
        return True

    def migrate_story_graph_from_plot_threads(self, *, force: bool = False) -> Dict[str, Any]:
        """Non-destructive migration from legacy plot_threads into the story graph."""
        result = migrate_plot_threads_to_graph(self, force=force)
        if not result.get('skipped'):
            self._log_action('story_graph_migrated', result)
        return result

    def get_chapter_brief(self, chapter_number: int) -> Optional[ChapterBrief]:
        return self.chapter_briefs.get(chapter_number)

    def set_chapter_brief(self, brief: ChapterBrief) -> ChapterBrief:
        self.chapter_briefs[brief.chapter_number] = brief
        self._log_action('chapter_brief_saved', {'chapter': brief.chapter_number})
        return brief

    def delete_chapter_brief(self, chapter_number: int) -> bool:
        if self.chapter_briefs.pop(chapter_number, None) is None:
            return False
        self._pending_chapter_brief_removals.add(chapter_number)
        self._log_action('chapter_brief_deleted', {'chapter': chapter_number})
        return True

    def get_chapter_beats(self, chapter_number: int) -> List[ChapterBeat]:
        beats = list(self.chapter_beats.get(chapter_number, []))
        beats.sort(key=lambda b: (b.sort_order, b.id))
        return beats

    def set_chapter_beats(self, chapter_number: int, beats: List[ChapterBeat]) -> List[ChapterBeat]:
        ordered = sorted(beats, key=lambda b: (b.sort_order, b.id))
        self.chapter_beats[chapter_number] = ordered
        self._log_action('chapter_beats_saved', {'chapter': chapter_number, 'count': len(ordered)})
        return ordered

    def add_chapter_beat(self, chapter_number: int, beat: ChapterBeat) -> ChapterBeat:
        beats = list(self.chapter_beats.get(chapter_number, []))
        beats.append(beat)
        self.chapter_beats[chapter_number] = beats
        self._log_action('chapter_beat_added', {'chapter': chapter_number, 'beat_id': beat.id})
        return beat

    def update_chapter_beat(
        self, chapter_number: int, beat_id: str, updates: Dict[str, Any],
    ) -> Optional[ChapterBeat]:
        beats = self.chapter_beats.get(chapter_number)
        if not beats:
            return None
        for beat in beats:
            if beat.id == beat_id:
                for key, value in updates.items():
                    if hasattr(beat, key):
                        setattr(beat, key, value)
                self._log_action('chapter_beat_updated', {'chapter': chapter_number, 'beat_id': beat_id})
                return beat
        return None

    def delete_chapter_beat(self, chapter_number: int, beat_id: str) -> bool:
        beats = self.chapter_beats.get(chapter_number)
        if not beats:
            return False
        remaining = [b for b in beats if b.id != beat_id]
        if len(remaining) == len(beats):
            return False
        if remaining:
            self.chapter_beats[chapter_number] = remaining
        else:
            self.chapter_beats.pop(chapter_number, None)
            self._pending_chapter_beat_removals.add(chapter_number)
        self._log_action('chapter_beat_deleted', {'chapter': chapter_number, 'beat_id': beat_id})
        return True

    def reorder_chapter_beats(self, chapter_number: int, ordered_ids: List[str]) -> List[ChapterBeat]:
        beats = self.chapter_beats.get(chapter_number, [])
        by_id = {b.id: b for b in beats}
        reordered: List[ChapterBeat] = []
        for i, bid in enumerate(ordered_ids):
            beat = by_id.get(bid)
            if beat is None:
                continue
            beat.sort_order = i
            reordered.append(beat)
        for beat in beats:
            if beat.id not in ordered_ids:
                beat.sort_order = len(reordered)
                reordered.append(beat)
        self.chapter_beats[chapter_number] = reordered
        self._log_action('chapter_beats_reordered', {'chapter': chapter_number})
        return reordered
    
    # ===== Chapter Management =====
    
    def create_chapter(self, number: int, title: str = "") -> ChapterState:
        """Create a new chapter entry."""
        chapter = ChapterState(number=number, title=title)
        self.chapters[number] = chapter
        self._log_action('chapter_created', {'chapter': number})
        return chapter
    
    def get_chapter(self, number: int) -> Optional[ChapterState]:
        """Retrieve chapter state by number."""
        return self.chapters.get(number)
    
    def update_chapter(self, number: int, updates: Dict[str, Any]):
        """Update chapter fields."""
        if number in self.chapters:
            chapter = self.chapters[number]
            for key, value in updates.items():
                if hasattr(chapter, key):
                    setattr(chapter, key, value)
            chapter.last_modified = datetime.now().isoformat()
    
    def get_chapter_count(self) -> int:
        """Get total number of chapters."""
        return len(self.chapters)
    
    def get_completed_chapters(self) -> List[ChapterState]:
        """Get all chapters marked as complete."""
        return [
            c for c in self.chapters.values()
            if c.status == 'complete'
        ]

    def delete_chapter(self, number: int) -> bool:
        """Remove a chapter from state and scrub Structure V2 references."""
        if self.chapters.pop(number, None) is None:
            return False
        self._pending_chapter_removals.add(number)
        self.timeline = [e for e in self.timeline if e.chapter != number]
        self.chapter_briefs.pop(number, None)
        self._pending_chapter_brief_removals.add(number)
        self.chapter_beats.pop(number, None)
        self._pending_chapter_beat_removals.add(number)
        self._scrub_chapter_from_v2_structure(number)
        self._log_action('chapter_deleted', {'chapter': number})
        return True

    def _scrub_chapter_from_v2_structure(self, number: int) -> None:
        """Remove a chapter number from graph lifespan fields and pins."""
        for node in self.story_graph_nodes.values():
            if node.start_chapter == number:
                node.start_chapter = 0
            if node.resolution_chapter == number:
                node.resolution_chapter = None
            node.chapter_pins = [c for c in (node.chapter_pins or []) if c != number]

    def _remap_chapter_in_v2_structure(self, old: int, new: int) -> None:
        """Update node lifespan, pins, and chapter_beats keys after renumber."""
        for node in self.story_graph_nodes.values():
            if node.start_chapter == old:
                node.start_chapter = new
            if node.resolution_chapter == old:
                node.resolution_chapter = new
            node.chapter_pins = sorted(
                new if pin == old else pin for pin in (node.chapter_pins or [])
            )
        beats = self.chapter_beats.pop(old, None)
        if beats is not None:
            self.chapter_beats[new] = beats

    def reassign_chapter(self, from_number: int, to_number: int) -> str:
        """Move a chapter to a new number, or swap with an existing chapter."""
        if from_number not in self.chapters:
            raise ValueError(f"Chapter {from_number} not found")
        if from_number == to_number:
            return "unchanged"
        if to_number in self.chapters:
            self._swap_chapter_numbers(from_number, to_number)
            self._log_action('chapter_swapped', {'a': from_number, 'b': to_number})
            return "swapped"
        ch = self.chapters.pop(from_number)
        ch.number = to_number
        self.chapters[to_number] = ch
        self._remap_chapter_number(from_number, to_number)
        self._log_action('chapter_reassigned', {'from': from_number, 'to': to_number})
        return "moved"

    def _remap_chapter_number(self, old: int, new: int) -> None:
        brief = self.chapter_briefs.pop(old, None)
        if brief is not None:
            brief.chapter_number = new
            self.chapter_briefs[new] = brief
        self._remap_chapter_in_v2_structure(old, new)
        for event in self.timeline:
            if event.chapter == old:
                event.chapter = new
        for char in self.characters.values():
            if char.last_appearance_chapter == old:
                char.last_appearance_chapter = new
        for thread in self.plot_threads.values():
            if thread.start_chapter == old:
                thread.start_chapter = new
            if thread.last_updated_chapter == old:
                thread.last_updated_chapter = new
            if thread.target_resolution_chapter == old:
                thread.target_resolution_chapter = new
            thread.foreshadowing_planted = [
                new if ch == old else ch for ch in thread.foreshadowing_planted
            ]
            for ms in thread.milestones:
                if ms.get("chapter") == old:
                    ms["chapter"] = new

    def _swap_chapter_numbers(self, a: int, b: int) -> None:
        ch_a = self.chapters[a]
        ch_b = self.chapters[b]
        ch_a.number = b
        ch_b.number = a
        self.chapters[b] = ch_a
        self.chapters[a] = ch_b
        brief_a = self.chapter_briefs.pop(a, None)
        brief_b = self.chapter_briefs.pop(b, None)
        if brief_a is not None:
            brief_a.chapter_number = b
            self.chapter_briefs[b] = brief_a
        if brief_b is not None:
            brief_b.chapter_number = a
            self.chapter_briefs[a] = brief_b
        beats_a = self.chapter_beats.pop(a, None)
        beats_b = self.chapter_beats.pop(b, None)
        if beats_a is not None:
            self.chapter_beats[b] = beats_a
        if beats_b is not None:
            self.chapter_beats[a] = beats_b
        sentinel = -(max(a, b) + 100000)
        for node in self.story_graph_nodes.values():
            if node.start_chapter == a:
                node.start_chapter = sentinel
            elif node.start_chapter == b:
                node.start_chapter = a
            if node.resolution_chapter == a:
                node.resolution_chapter = sentinel
            elif node.resolution_chapter == b:
                node.resolution_chapter = a
            node.chapter_pins = [
                sentinel if pin == a else (a if pin == b else pin)
                for pin in (node.chapter_pins or [])
            ]
        for node in self.story_graph_nodes.values():
            if node.start_chapter == sentinel:
                node.start_chapter = b
            if node.resolution_chapter == sentinel:
                node.resolution_chapter = b
            node.chapter_pins = [
                b if pin == sentinel else pin for pin in (node.chapter_pins or [])
            ]
        for event in self.timeline:
            if event.chapter == a:
                event.chapter = sentinel
            elif event.chapter == b:
                event.chapter = a
        for event in self.timeline:
            if event.chapter == sentinel:
                event.chapter = b
        for char in self.characters.values():
            if char.last_appearance_chapter == a:
                char.last_appearance_chapter = sentinel
            elif char.last_appearance_chapter == b:
                char.last_appearance_chapter = a
        for char in self.characters.values():
            if char.last_appearance_chapter == sentinel:
                char.last_appearance_chapter = b
        for thread in self.plot_threads.values():
            for field in ("start_chapter", "last_updated_chapter", "target_resolution_chapter"):
                val = getattr(thread, field)
                if val == a:
                    setattr(thread, field, sentinel)
                elif val == b:
                    setattr(thread, field, a)
            thread.foreshadowing_planted = [
                sentinel if ch == a else (a if ch == b else ch)
                for ch in thread.foreshadowing_planted
            ]
            thread.foreshadowing_planted = [
                b if ch == sentinel else ch for ch in thread.foreshadowing_planted
            ]
            for ms in thread.milestones:
                ch_num = ms.get("chapter")
                if ch_num == a:
                    ms["chapter"] = sentinel
                elif ch_num == b:
                    ms["chapter"] = a
            for ms in thread.milestones:
                if ms.get("chapter") == sentinel:
                    ms["chapter"] = b
    
    # ===== Timeline Management =====
    
    def add_timeline_event(self, event: TimelineEvent):
        """Add an event to the timeline."""
        self.timeline.append(event)
        self.timeline.sort(key=lambda e: (e.chapter, e.day or 0))
        self._log_action('timeline_event_added', {'event_id': event.id})

    def get_timeline_event(self, event_id: str) -> Optional[TimelineEvent]:
        """Retrieve a timeline event by ID."""
        for event in self.timeline:
            if event.id == event_id:
                return event
        return None

    def update_timeline_event(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Update timeline event fields."""
        event = self.get_timeline_event(event_id)
        if event is None:
            return False
        for key, value in updates.items():
            if hasattr(event, key):
                setattr(event, key, value)
        self.timeline.sort(key=lambda e: (e.chapter, e.day or 0))
        self._log_action('timeline_event_updated', {'event_id': event_id})
        return True

    def delete_timeline_event(self, event_id: str) -> bool:
        """Remove a timeline event."""
        before = len(self.timeline)
        self.timeline = [e for e in self.timeline if e.id != event_id]
        if len(self.timeline) < before:
            self._log_action('timeline_event_deleted', {'event_id': event_id})
            return True
        return False
    
    def get_timeline_for_chapter(self, chapter: int) -> List[TimelineEvent]:
        """Get all timeline events for a specific chapter."""
        return [e for e in self.timeline if e.chapter == chapter]
    
    def get_character_timeline(self, character_id: str) -> List[TimelineEvent]:
        """Get all timeline events featuring a character."""
        return [
            e for e in self.timeline
            if character_id in e.characters_present
        ]
    
    # ===== Style Management =====
    
    def set_style_profile(self, profile: StyleProfile):
        """Set the novel's style profile."""
        self.style_profile = profile
        self._log_action('style_profile_updated', {'profile_name': profile.name})
    
    def get_style_profile(self) -> StyleProfile:
        """Get the current style profile."""
        return self.style_profile
    
    # ===== Story Bible Management =====
    
    def update_story_bible(self, section: str, data: Any):
        """Update a section of the story bible."""
        self.story_bible[section] = data
        self._log_action('story_bible_updated', {'section': section})
    
    def get_story_bible_section(self, section: str) -> Any:
        """Retrieve a section from the story bible."""
        return self.story_bible.get(section)
    
    # ===== Metadata =====
    
    def set_metadata(self, key: str, value: Any):
        """Set a metadata value."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default=None) -> Any:
        """Get a metadata value."""
        return self.metadata.get(key, default)
    
    # ===== Session Logging =====
    
    def _log_action(self, action: str, details: Dict[str, Any]):
        """Log an action to the session log."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details
        }
        self.session_log.append(entry)
    
    def get_session_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session log entries."""
        return self.session_log[-limit:]
    
    # ===== State Summaries =====
    
    def get_story_summary(self) -> str:
        """Generate a text summary of the story state."""
        lines = [
            f"# Story Summary: {self.metadata.get('title', 'Untitled')}",
            f"",
            f"## Metadata",
            f"- Genre: {self.metadata.get('genre', 'Unknown')}",
            f"- Chapters: {len(self.chapters)}",
            f"- Characters: {len(self.characters)}",
            f"- Active Plot Threads: {len(self.get_active_plot_threads())}",
            f"",
            f"## Characters",
        ]
        
        for char in self.characters.values():
            lines.append(f"- **{char.full_name}** ({char.role}): {char.arc_stage} ({char.arc_progress}%)")
        
        lines.extend([
            f"",
            f"## Active Plot Threads",
        ])
        
        for thread in self.get_active_plot_threads():
            lines.append(f"- **{thread.name}** (Priority {thread.priority})")
        
        return '\n'.join(lines)
    
    def get_continuity_context(self, chapter: int) -> Dict[str, Any]:
        """Get context needed for continuity checking."""
        return {
            'chapter': chapter,
            'character_locations': {
                cid: char.current_location
                for cid, char in self.characters.items()
            },
            'character_emotional_states': {
                cid: char.emotional_state
                for cid, char in self.characters.items()
            },
            'active_threads': [
                t.to_dict() for t in self.get_active_plot_threads()
            ],
            'foreshadowing_active': [
                t.to_dict() for t in self.plot_threads.values()
                if t.status == 'foreshadowed'
            ],
            'previous_chapter_events': [
                e.to_dict() for e in self.get_timeline_for_chapter(chapter - 1)
            ] if chapter > 1 else []
        }


def initialize_project(project_path: str, title: str, genre: str) -> StoryState:
    """Initialize a new novel project with default state."""
    state = StoryState(project_path)
    state.schema_version = CURRENT_SCHEMA_VERSION
    
    # Set metadata
    state.set_metadata('title', title)
    state.set_metadata('genre', genre)
    state.set_metadata('created', datetime.now().isoformat())
    state.set_metadata('version', '1.0')
    
    # Initialize story bible with defaults
    state.update_story_bible('genre', genre)
    state.update_story_bible('themes', [])
    state.update_story_bible('tone', '')
    state.update_story_bible('setting', {
        'time_period': '',
        'primary_location': '',
        'world_rules': {}
    })
    state.update_story_bible('magic_system' if 'fantasy' in genre.lower() else 'technology', {})
    
    # Save initial state
    state.save_state()
    
    return state


if __name__ == '__main__':
    # Demo usage
    state = initialize_project('.', 'Demo Novel', 'Science Fiction')
    
    # Add a character
    protagonist = Character(
        id='char_001',
        full_name='Aria Chen',
        role='protagonist',
        internal_desire='Find belonging',
        external_goal='Stop the AI uprising',
        arc_stage='beginning',
        arc_progress=0
    )
    state.add_character(protagonist)
    
    # Add a plot thread
    main_thread = PlotThread(
        id='plot_001',
        name='The Uprising',
        description='AI systems begin to rebel against human control',
        thread_type='main',
        priority=5
    )
    state.add_plot_thread(main_thread)
    
    # Save
    state.save_state()
    
    print(state.get_story_summary())
