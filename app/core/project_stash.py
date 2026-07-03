"""
Stashed projects — archived zips removed from the active library.

Each stash is a portable .novel-os.zip plus a manifest entry under stashed/.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Tuple

from project_portable import MANIFEST_NAME as PACKAGE_MANIFEST_NAME

STASH_EXT = ".novel-os.zip"
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_path(stashed_dir: Path) -> Path:
    return stashed_dir / MANIFEST_NAME


def _load_manifest(stashed_dir: Path) -> dict:
    path = _manifest_path(stashed_dir)
    if not path.exists():
        return {"version": MANIFEST_VERSION, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(stashed_dir: Path, data: dict) -> None:
    stashed_dir.mkdir(parents=True, exist_ok=True)
    data["version"] = MANIFEST_VERSION
    _manifest_path(stashed_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _stash_filename(stash_id: str) -> str:
    return f"{stash_id}{STASH_EXT}"


def _read_package_manifest_from_zip(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as zf:
        raw = zf.read(PACKAGE_MANIFEST_NAME)
    return json.loads(raw.decode("utf-8"))


def _entry_from_zip(zip_path: Path) -> dict | None:
    try:
        manifest = _read_package_manifest_from_zip(zip_path)
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        return None
    stash_id = manifest.get("source_project_id") or zip_path.name[: -len(STASH_EXT)]
    stat = zip_path.stat()
    return {
        "id": stash_id,
        "title": manifest.get("title") or stash_id,
        "genre": "",
        "chapter_count": 0,
        "stashed_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "filename": zip_path.name,
        "size_bytes": stat.st_size,
    }


def _find_stash_zip(stashed_dir: Path, stash_id: str) -> Path | None:
    manifest = _load_manifest(stashed_dir)
    for entry in manifest.get("entries", []):
        if entry.get("id") == stash_id:
            zip_path = stashed_dir / entry.get("filename", _stash_filename(stash_id))
            if zip_path.exists():
                return zip_path
    candidate = stashed_dir / _stash_filename(stash_id)
    if candidate.exists():
        return candidate
    return None


def stash_project(
    project_dir: Path,
    stashed_dir: Path,
    zip_bytes: bytes,
    metadata: dict,
) -> dict:
    """Write {id}.novel-os.zip and update stashed/manifest.json."""
    del project_dir  # caller removes the live project; path kept for API symmetry
    stashed_dir.mkdir(parents=True, exist_ok=True)
    stash_id = metadata["id"]
    filename = _stash_filename(stash_id)
    (stashed_dir / filename).write_bytes(zip_bytes)

    entry = {
        "id": stash_id,
        "title": metadata["title"],
        "genre": metadata.get("genre", ""),
        "chapter_count": int(metadata.get("chapter_count", 0)),
        "stashed_at": metadata.get("stashed_at") or _now(),
        "filename": filename,
        "size_bytes": len(zip_bytes),
    }

    manifest = _load_manifest(stashed_dir)
    entries = [e for e in manifest.get("entries", []) if e.get("id") != stash_id]
    entries.append(entry)
    manifest["entries"] = entries
    _save_manifest(stashed_dir, manifest)
    return entry


def list_stashed(stashed_dir: Path) -> list[dict]:
    """List stash entries from manifest.json, with zip-scan fallback."""
    if not stashed_dir.is_dir():
        return []

    manifest = _load_manifest(stashed_dir)
    entries: list[dict] = []
    seen: set[str] = set()
    for entry in manifest.get("entries", []):
        stash_id = entry.get("id")
        if not stash_id:
            continue
        zip_path = stashed_dir / entry.get("filename", _stash_filename(stash_id))
        if not zip_path.exists():
            continue
        entries.append({
            **entry,
            "filename": zip_path.name,
            "size_bytes": zip_path.stat().st_size,
        })
        seen.add(stash_id)

    if entries:
        entries.sort(key=lambda e: e.get("stashed_at", ""), reverse=True)
        return entries

    for zip_path in sorted(stashed_dir.glob(f"*{STASH_EXT}")):
        entry = _entry_from_zip(zip_path)
        if entry is None or entry["id"] in seen:
            continue
        entries.append(entry)
        seen.add(entry["id"])

    entries.sort(key=lambda e: e.get("stashed_at", ""), reverse=True)
    return entries


def delete_stashed(stashed_dir: Path, stash_id: str) -> bool:
    """Remove a stash zip and its manifest entry. Returns False if not found."""
    zip_path = _find_stash_zip(stashed_dir, stash_id)
    if zip_path is None:
        return False
    zip_path.unlink(missing_ok=True)

    manifest = _load_manifest(stashed_dir)
    entries = [e for e in manifest.get("entries", []) if e.get("id") != stash_id]
    manifest["entries"] = entries
    _save_manifest(stashed_dir, manifest)
    return True


def restore_stashed(
    stashed_dir: Path,
    projects_root: Path,
    stash_id: str,
    import_fn: Callable[[bytes], Tuple[str, str]],
) -> Tuple[str, str]:
    """Read stash zip, import via callback, then remove stash."""
    del projects_root  # import_fn closes over the active projects root
    zip_path = _find_stash_zip(stashed_dir, stash_id)
    if zip_path is None:
        raise FileNotFoundError(f"Stashed project {stash_id!r} not found.")
    zip_bytes = zip_path.read_bytes()
    project_id, title = import_fn(zip_bytes)
    delete_stashed(stashed_dir, stash_id)
    return project_id, title
