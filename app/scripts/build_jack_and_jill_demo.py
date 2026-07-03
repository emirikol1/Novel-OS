#!/usr/bin/env python3
"""Build the Jack and Jill demo project into the library (and optional stash zip)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
CORE = APP / "core"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(APP))

from demo_jack_and_jill import (  # noqa: E402
    DEMO_AUTHOR,
    DEMO_GENRE,
    DEMO_SLUG,
    DEMO_TITLE,
    populate_jack_and_jill_demo,
    write_jack_and_jill_artifacts,
)
from api.services import build_orchestrator  # noqa: E402
from state_manager import StoryState  # noqa: E402


def _install_root() -> Path:
    return Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))


def _projects_root() -> Path:
    return Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", _install_root() / "projects"))


def _db_url() -> str:
    explicit = os.environ.get("NOVEL_OS_DB")
    if explicit:
        return explicit
    for candidate in (_install_root() / "app" / "novel_os.db", _install_root() / "novel_os.db"):
        if candidate.exists():
            return f"sqlite:///{candidate.as_posix()}"
    return f"sqlite:///{(_install_root() / 'app' / 'novel_os.db').as_posix()}"


def _seed_db_extras(project_id: str) -> None:
    from api import db  # noqa: WPS433

    db.configure(_db_url())
    db.ingest_project(_projects_root(), project_id)

    db.research_spark_create(
        project_id,
        title="Nursery rhyme origins",
        body="Traditional English rhyme; first printed versions appear in the 18th century.",
        kind="reference",
        tags=["demo", "folklore"],
        link_chapter=1,
        link_character_id="char_jack",
    )
    db.research_spark_create(
        project_id,
        title="Hill paths and village wells",
        body="Fetching water uphill is a common folkloric errand — useful physical stakes for children.",
        kind="note",
        tags=["demo", "setting"],
        link_chapter=1,
    )
    db.comment_add(
        project_id,
        chapter=1,
        body="Demo note: this chapter is intentionally complete through Final for onboarding.",
        stage="final",
    )


def build_demo(*, force: bool, stash: bool) -> Path:
    projects = _projects_root()
    projects.mkdir(parents=True, exist_ok=True)
    project_dir = projects / DEMO_SLUG

    if project_dir.exists():
        if not force:
            raise SystemExit(
                f"Project folder already exists: {project_dir}\n"
                "Re-run with --force to replace it.",
            )
        shutil.rmtree(project_dir)

    orch = build_orchestrator(str(project_dir))
    orch.init_project(DEMO_TITLE, DEMO_GENRE, DEMO_AUTHOR)

    state = StoryState(str(project_dir))
    populate_jack_and_jill_demo(state)
    state.save_state()
    write_jack_and_jill_artifacts(project_dir)
    _seed_db_extras(DEMO_SLUG)

    if stash:
        from api import db  # noqa: WPS433
        from project_portable import build_package_bytes  # noqa: WPS433
        from project_stash import stash_project  # noqa: WPS433

        stashed_dir = Path(os.environ.get("NOVEL_OS_STASHED_DIR", _install_root() / "stashed"))
        export = db.export_project_data(DEMO_SLUG)
        zip_bytes = build_package_bytes(
            project_dir,
            export,
            project_id=DEMO_SLUG,
            title=DEMO_TITLE,
        )
        stash_project(
            project_dir,
            stashed_dir,
            zip_bytes,
            {
                "id": DEMO_SLUG,
                "title": DEMO_TITLE,
                "genre": DEMO_GENRE,
                "chapter_count": len(state.chapters),
            },
        )
        shutil.rmtree(project_dir)
        print(f"Stashed demo at {stashed_dir / (DEMO_SLUG + '.novel-os.zip')}")
        print("Restore from the sidebar Stashed panel or: POST /api/stashed/jack-and-jill/restore")
    else:
        print(f"Demo project ready at {project_dir}")
        print(f"Open in Novel OS: /projects/{DEMO_SLUG}")

    return project_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing jack-and-jill project folder",
    )
    parser.add_argument(
        "--stash",
        action="store_true",
        help="Write stash zip instead of leaving project in the library",
    )
    args = parser.parse_args()
    build_demo(force=args.force, stash=args.stash)


if __name__ == "__main__":
    main()
