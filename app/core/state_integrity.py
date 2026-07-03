"""
Guards story_state.json against accidental registry wipes.

Manuscript prose lives under outputs/manuscript/ — chapter registry entries must
never disappear from story_state.json unless the author explicitly deletes a chapter.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Set

if TYPE_CHECKING:
    from state_manager import ChapterState, StoryState

STATE_HISTORY_DIR = "history"
STATE_HISTORY_KEEP = 30
MANUSCRIPT_STAGE_RE = re.compile(
    r"^chapter_(\d{3})_(draft|revised|final)\.md$",
    re.IGNORECASE,
)
OUTLINE_RE = re.compile(r"^chapter_(\d{3})_outline\.md$", re.IGNORECASE)
SOURCE_RE = re.compile(r"^chapter_(\d{3})_[^.]+\.txt$", re.IGNORECASE)


def _chapter_count(payload: Dict[str, Any]) -> int:
    chapters = payload.get("chapters")
    return len(chapters) if isinstance(chapters, dict) else 0


def discover_chapter_numbers_from_artifacts(project_path: Path) -> Set[int]:
    """Chapter numbers with prose or planning artifacts on disk (filesystem truth)."""
    root = Path(project_path)
    found: Set[int] = set()

    manuscript = root / "outputs" / "manuscript"
    if manuscript.is_dir():
        for path in manuscript.iterdir():
            if not path.is_file():
                continue
            match = MANUSCRIPT_STAGE_RE.match(path.name)
            if not match:
                continue
            if path.read_text(encoding="utf-8", errors="replace").strip():
                found.add(int(match.group(1)))

    outputs = root / "outputs"
    if outputs.is_dir():
        for path in outputs.iterdir():
            if path.is_file() and OUTLINE_RE.match(path.name):
                if path.read_text(encoding="utf-8", errors="replace").strip():
                    found.add(int(OUTLINE_RE.match(path.name).group(1)))

    sources = outputs / "sources"
    if sources.is_dir():
        for path in sources.iterdir():
            if not path.is_file():
                continue
            match = SOURCE_RE.match(path.name)
            if match and path.read_text(encoding="utf-8", errors="replace").strip():
                found.add(int(match.group(1)))

    return found


def _best_manuscript_text(project_path: Path, number: int) -> tuple[str, str]:
    """Return (stage, text) preferring final > revised > draft."""
    manuscript = Path(project_path) / "outputs" / "manuscript"
    for stage in ("final", "revised", "draft"):
        path = manuscript / f"chapter_{number:03d}_{stage}.md"
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return stage, text
    return "", ""


def chapter_stub_from_artifacts(project_path: Path, number: int) -> Dict[str, Any]:
    """Minimal chapter registry row rebuilt from on-disk manuscript artifacts."""
    stage, text = _best_manuscript_text(project_path, number)
    status = "drafted" if stage else "planned"
    return {
        "number": number,
        "title": "",
        "status": status,
        "pov_character": "",
        "location": "",
        "time": "",
        "word_count": len(text.split()) if text else 0,
        "target_word_count": 2500,
        "scenes": [],
        "plot_advances": [],
        "character_development": {},
        "emotional_beats": [],
        "new_information": [],
        "foreshadowing_planted": [],
        "foreshadowing_resolved": [],
        "hooks_start": [],
        "hooks_end": [],
        "continuity_checks": {},
        "quality_scores": {},
        "last_modified": datetime.now(timezone.utc).isoformat(),
    }


def merge_registry_dict(
    incoming: Dict[str, Any],
    on_disk: Dict[str, Any],
    *,
    removals: Optional[Iterable[str]] = None,
    preserve_keys: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Additive merge for string-keyed registries.

    Keys present on disk are kept unless explicitly removed. Incoming values overlay
    disk for keys that appear in incoming.
    """
    merged = dict(on_disk)
    merged.update(incoming)
    for key in removals or ():
        if preserve_keys and key in preserve_keys:
            continue
        merged.pop(key, None)
    return merged


def merge_chapters_for_save(
    incoming: Dict[str, Any],
    on_disk: Dict[str, Any],
    project_path: Path,
    *,
    removals: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """
    Merge chapter registry rows for save.

    When memory carries chapter updates, it defines the chapter number set (renumber,
    delete). Rows only reappear from disk/manuscript when memory omitted a chapter
    that still has on-disk prose — the stale-save / crash-recovery path.
    """
    incoming_ch = {str(k): v for k, v in (incoming or {}).items()}
    on_disk_ch = {str(k): v for k, v in (on_disk or {}).items()}
    removal_nums = set(removals or ())
    artifact_nums = discover_chapter_numbers_from_artifacts(project_path) - removal_nums

    if incoming_ch:
        merged = dict(incoming_ch)
        for key, val in on_disk_ch.items():
            try:
                num = int(key)
            except (TypeError, ValueError):
                continue
            if num in removal_nums or key in merged:
                continue
            if num in artifact_nums:
                merged[key] = val
    else:
        merged = dict(on_disk_ch)

    for number in removal_nums:
        merged.pop(str(number), None)

    wiped_registry = not incoming_ch and not on_disk_ch
    allowed_numbers = {int(k) for k in on_disk_ch} | {int(k) for k in incoming_ch}
    for number in artifact_nums:
        key = str(number)
        if key in merged:
            continue
        if wiped_registry or number in allowed_numbers:
            merged[key] = on_disk_ch.get(key) or chapter_stub_from_artifacts(project_path, number)

    return merged


def merge_save_payload(
    incoming: Dict[str, Any],
    on_disk: Dict[str, Any],
    project_path: Path,
    *,
    chapter_removals: Optional[Iterable[int]] = None,
    character_removals: Optional[Iterable[str]] = None,
    plot_removals: Optional[Iterable[str]] = None,
    graph_node_removals: Optional[Iterable[str]] = None,
    graph_edge_removals: Optional[Iterable[str]] = None,
    chapter_brief_removals: Optional[Iterable[int]] = None,
    chapter_beat_removals: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """Produce the dict to write — incoming updates cannot wipe registries."""
    merged = dict(incoming)
    merged["chapters"] = merge_chapters_for_save(
        incoming.get("chapters") or {},
        on_disk.get("chapters") or {},
        project_path,
        removals=chapter_removals,
    )
    merged["characters"] = merge_registry_dict(
        incoming.get("characters") or {},
        on_disk.get("characters") or {},
        removals=character_removals,
    )
    merged["plot_threads"] = merge_registry_dict(
        incoming.get("plot_threads") or {},
        on_disk.get("plot_threads") or {},
        removals=plot_removals,
    )
    merged["story_graph_nodes"] = merge_registry_dict(
        incoming.get("story_graph_nodes") or {},
        on_disk.get("story_graph_nodes") or {},
        removals=graph_node_removals,
    )
    merged["story_graph_edges"] = merge_registry_dict(
        incoming.get("story_graph_edges") or {},
        on_disk.get("story_graph_edges") or {},
        removals=graph_edge_removals,
    )
    merged["chapter_briefs"] = merge_chapter_briefs_for_save(
        {str(k): v for k, v in (incoming.get("chapter_briefs") or {}).items()},
        {str(k): v for k, v in (on_disk.get("chapter_briefs") or {}).items()},
        set(merged["chapters"].keys()),
        chapter_removals=chapter_removals,
        brief_removals=chapter_brief_removals,
    )
    merged["chapter_beats"] = merge_chapter_beats_for_save(
        {str(k): v for k, v in (incoming.get("chapter_beats") or {}).items()},
        {str(k): v for k, v in (on_disk.get("chapter_beats") or {}).items()},
        set(merged["chapters"].keys()),
        chapter_removals=chapter_removals,
        beat_removals=chapter_beat_removals,
    )

    if not (incoming.get("metadata") or {}) and on_disk.get("metadata"):
        merged["metadata"] = on_disk["metadata"]
    if not (incoming.get("story_bible") or {}) and on_disk.get("story_bible"):
        merged["story_bible"] = on_disk["story_bible"]

    if not _chapter_count(incoming) and _chapter_count(merged):
        merged["last_saved"] = datetime.now(timezone.utc).isoformat()

    return merged


def merge_chapter_briefs_for_save(
    incoming: Dict[str, Any],
    on_disk: Dict[str, Any],
    chapter_keys: Set[str],
    *,
    chapter_removals: Optional[Iterable[int]] = None,
    brief_removals: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """Briefs follow chapters, but incoming brief updates may precede a chapter row."""
    removal_keys = {str(n) for n in (chapter_removals or ())}
    removal_keys |= {str(n) for n in (brief_removals or ())}
    allowed_keys = set(chapter_keys) | set(incoming.keys())
    merged: Dict[str, Any] = {}
    for key in allowed_keys:
        if key in removal_keys:
            continue
        if key in incoming:
            merged[key] = incoming[key]
        elif key in on_disk:
            merged[key] = on_disk[key]
    return merged


def merge_chapter_beats_for_save(
    incoming: Dict[str, Any],
    on_disk: Dict[str, Any],
    chapter_keys: Set[str],
    *,
    chapter_removals: Optional[Iterable[int]] = None,
    beat_removals: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    removal_keys = {str(n) for n in (chapter_removals or ())}
    removal_keys |= {str(n) for n in (beat_removals or ())}
    allowed_keys = set(chapter_keys) | set(incoming.keys())
    merged: Dict[str, Any] = {}
    for key in allowed_keys:
        if key in removal_keys:
            continue
        if key in incoming:
            merged[key] = incoming[key]
        elif key in on_disk:
            merged[key] = on_disk[key]
    return merged


def should_recover_wiped_registry_on_load(state_file: Path, data: Dict[str, Any]) -> bool:
    """
    Return True when the on-disk registry was wiped but recoverable content exists.

    Fresh projects from initialize_project have a title but empty chapters and must
    not adopt stray manuscript/orphan files on load. A wiped registry is detected
    via backup/history snapshots, or an anonymous empty shell with artifacts only.
    """
    if data.get("chapters"):
        return False

    project_path = state_file.parent.parent.parent
    if not discover_chapter_numbers_from_artifacts(project_path):
        return False

    backup_path = state_file.with_suffix(".json.bak")
    if backup_path.is_file():
        try:
            backup = json.loads(backup_path.read_text(encoding="utf-8"))
            if backup.get("chapters"):
                return True
        except json.JSONDecodeError:
            return True

    history_dir = state_file.parent / STATE_HISTORY_DIR
    if history_dir.is_dir():
        for snap in sorted(
            history_dir.glob("story_state_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                snap_data = json.loads(snap.read_text(encoding="utf-8"))
                if snap_data.get("chapters"):
                    return True
            except json.JSONDecodeError:
                continue

    # Anonymous empty JSON (no project title) with manuscript files — trust disk.
    if not (data.get("metadata") or {}).get("title"):
        return True

    return False


def reconcile_chapters_from_artifacts(
    state: "StoryState",
    *,
    registry_numbers: Set[int],
) -> list[int]:
    """
    Ensure registry rows exist for chapters backed by on-disk artifacts.

    ``registry_numbers`` is the chapter number set from persisted JSON (on load,
    from the file just read; on save, from on-disk state before merge). When that
    set is empty (wiped registry), recover every chapter that has manuscript files.
    Otherwise only recover numbers in ``registry_numbers`` — orphan manuscript
    files that were never registered stay out of the registry until import.
    """
    artifact_nums = discover_chapter_numbers_from_artifacts(state.project_path)
    loaded_nums = set(state.chapters.keys())

    if not registry_numbers:
        missing = artifact_nums - loaded_nums
    else:
        missing = (registry_numbers & artifact_nums) - loaded_nums

    restored: list[int] = []
    for number in sorted(missing):
        stub = chapter_stub_from_artifacts(state.project_path, number)
        from state_manager import ChapterState  # noqa: WPS433

        state.chapters[number] = ChapterState.from_dict(stub)
        restored.append(number)
    return restored


def append_state_history(state_file: Path, data: Dict[str, Any]) -> None:
    """Keep a rolling window of prior story_state snapshots."""
    if _chapter_count(data) < 1:
        return
    history_dir = state_file.parent / STATE_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    dest = history_dir / f"story_state_{stamp}.json"
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    snapshots = sorted(history_dir.glob("story_state_*.json"), key=lambda p: p.stat().st_mtime)
    while len(snapshots) > STATE_HISTORY_KEEP:
        oldest = snapshots.pop(0)
        oldest.unlink(missing_ok=True)


def read_best_state_json(state_file: Path) -> Optional[Dict[str, Any]]:
    """Read primary state, then .bak, then newest history snapshot."""
    backup_path = state_file.with_suffix(".json.bak")
    history_dir = state_file.parent / STATE_HISTORY_DIR
    candidates = [state_file, backup_path]
    if history_dir.is_dir():
        history = sorted(
            history_dir.glob("story_state_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        candidates.extend(history)

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None
