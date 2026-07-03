#!/usr/bin/env python3
"""CLI for stashing, listing, and restoring Novel OS projects."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
CORE = APP / "core"
API = APP / "api"
for entry in (CORE, API):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from api.services import BadRequest, ProjectNotFound, ProjectService  # noqa: E402


def resolve_paths() -> tuple[Path, Path, Path]:
    home = Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))
    projects = Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", home / "projects"))
    stashed = Path(os.environ.get("NOVEL_OS_STASHED_DIR", home / "stashed"))
    return home, projects, stashed


def _tree_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _print_record(record: dict) -> None:
    for key in sorted(record):
        print(f"{key}: {record[key]}")


def _print_records(records: list[dict]) -> None:
    for index, record in enumerate(records):
        if index:
            print()
        _print_record(record)


def _stash_zip_record(stashed_root: Path, stash_id: str, filename: str, stashed_at: str = "") -> dict:
    zip_path = stashed_root / filename
    size_bytes = zip_path.stat().st_size if zip_path.exists() else 0
    record = {
        "stash_id": stash_id,
        "path": str(zip_path.resolve()),
        "size_bytes": size_bytes,
    }
    if stashed_at:
        record["stashed_at"] = stashed_at
    return record


def _project_record(projects_root: Path, project_id: str) -> dict:
    project_path = projects_root / project_id
    return {
        "project_id": project_id,
        "path": str(project_path.resolve()),
        "size_bytes": _tree_size(project_path) if project_path.exists() else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list", action="store_true", help="List stashed projects")
    group.add_argument("--restore", metavar="STASH_ID", help="Unstash a project back to the library")
    parser.add_argument(
        "project_id",
        nargs="?",
        help="Active project id to stash (default action)",
    )
    args = parser.parse_args()

    _home, projects_root, stashed_root = resolve_paths()
    os.environ.setdefault("NOVEL_OS_STASHED_DIR", str(stashed_root))
    svc = ProjectService(projects_root)

    try:
        if args.list:
            records = [
                _stash_zip_record(stashed_root, entry.id, entry.filename, entry.stashed_at)
                for entry in svc.list_stashed_projects()
            ]
            _print_records(records)
            return 0
        if args.restore:
            restored = svc.restore_stashed_project(args.restore)
            _print_record(_project_record(projects_root, restored.id))
            return 0
        if not args.project_id:
            parser.error("project_id is required unless --list or --restore is used")
        stashed = svc.stash_project(args.project_id)
        _print_record(
            _stash_zip_record(stashed_root, stashed.id, stashed.filename, stashed.stashed_at)
        )
        return 0
    except ProjectNotFound as exc:
        print(f"error: project not found: {exc.args[0]}", file=sys.stderr)
    except BadRequest as exc:
        print(f"error: {exc}", file=sys.stderr)
    except FileNotFoundError as exc:
        target = exc.args[0] if exc.args else "unknown"
        print(f"error: not found: {target}", file=sys.stderr)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
