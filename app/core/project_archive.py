"""
Shared helpers for project backup/package archives.

Archives include outputs/ and assets/{maps,portraits}/ plus db_export.json.
Zip extraction validates member paths — never trust archive paths blindly.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import Iterator

ARCHIVE_TOP_DIRS = ("outputs", "assets")
ROOT_FILES = frozenset({"db_export.json", "package_manifest.json", "manifest.json"})
_ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def iter_project_archive_files(project_dir: Path) -> Iterator[tuple[Path, str]]:
    """Yield (disk_path, arcname) for files included in backup/package zips."""
    for sub in ARCHIVE_TOP_DIRS:
        root = project_dir / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                yield path, path.relative_to(project_dir).as_posix()


def is_safe_zip_member(name: str) -> bool:
    """Return True if a zip member path may be extracted into a project folder."""
    norm = name.replace("\\", "/").lstrip("./")
    if norm in ROOT_FILES:
        return True
    if norm.startswith("/") or ".." in Path(norm).parts:
        return False
    parts = Path(norm).parts
    if not parts:
        return False
    if parts[0] == "outputs":
        return True
    if parts[0] == "assets" and len(parts) == 4 and parts[1] in ("maps", "portraits"):
        asset_id, filename = parts[2], parts[3]
        if not _SAFE_ID_RE.match(asset_id):
            return False
        if Path(filename).name != filename or ".." in filename or "/" in filename:
            return False
        return Path(filename).suffix.lower() in _ALLOWED_EXTENSIONS
    return False


def safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract only validated members from a zip archive."""
    dest.mkdir(parents=True, exist_ok=True)
    resolved_dest = dest.resolve()
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        if not is_safe_zip_member(name):
            continue
        target = (dest / name).resolve()
        if not str(target).startswith(str(resolved_dest) + "/") and target != resolved_dest:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def restore_project_tree(extract_root: Path, project_dir: Path) -> None:
    """Replace outputs/ and optional assets/ from an extracted archive."""
    outputs_src = extract_root / "outputs"
    if not outputs_src.is_dir():
        raise ValueError("Archive is missing outputs/")
    outputs_dest = project_dir / "outputs"
    if outputs_dest.exists():
        shutil.rmtree(outputs_dest)
    shutil.copytree(outputs_src, outputs_dest)

    assets_src = extract_root / "assets"
    if assets_src.is_dir():
        assets_dest = project_dir / "assets"
        if assets_dest.exists():
            shutil.rmtree(assets_dest)
        shutil.copytree(assets_src, assets_dest)
