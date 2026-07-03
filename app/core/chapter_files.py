"""On-disk chapter artifact rename helpers (shared by API services and splitter)."""

from __future__ import annotations

from pathlib import Path


def _chapter_number_in_filename(name: str, number: int) -> bool:
    """True when filename belongs to chapter `number` (not e.g. 002 inside 0020)."""
    token = f"chapter_{number:03d}"
    idx = name.find(token)
    if idx < 0:
        return False
    after = idx + len(token)
    if after >= len(name):
        return True
    return name[after] in ("_", ".")


def chapter_artifact_paths(proj: Path, number: int) -> list[Path]:
    nnn = f"{number:03d}"
    out = proj / "outputs"
    if not out.exists():
        return []
    return sorted(
        path
        for path in out.rglob("*")
        if path.is_file() and _chapter_number_in_filename(path.name, number)
    )


def chapter_file_rename_steps(proj: Path, from_num: int, to_num: int) -> list[tuple[Path, Path]]:
    if from_num == to_num:
        return []
    return [
        (
            path,
            path.parent / path.name.replace(f"chapter_{from_num:03d}", f"chapter_{to_num:03d}", 1),
        )
        for path in chapter_artifact_paths(proj, from_num)
    ]


def preflight_chapter_file_renames(
    proj: Path,
    steps: list[tuple[Path, Path]],
) -> None:
    out = proj / "outputs"
    existing = {path for path in out.rglob("*") if path.is_file()} if out.exists() else set()
    seen_dests: set[Path] = set()
    for src, dest in steps:
        if src not in existing:
            raise FileNotFoundError(f"Expected chapter file missing: {src}")
        if dest in seen_dests:
            raise FileExistsError(f"Chapter file rename plan conflict: duplicate destination {dest}")
        seen_dests.add(dest)
        if dest in existing and dest != src:
            raise FileExistsError(f"Chapter file collision: {dest}")


def apply_chapter_file_renames(steps: list[tuple[Path, Path]]) -> None:
    for src, dest in steps:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
