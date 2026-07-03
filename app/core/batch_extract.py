"""
Sequential project-wide extraction jobs — outlines or codex (plots / cast / bible).

Each chapter is processed one at a time inside a single background job so LLM
calls do not compete with parallel chapter jobs. Results are previews only;
the author reviews and applies from the chapter UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from chapter_miner import (
    MINE_KINDS,
    ChapterMiner,
    apply_mine_preview_to_state,
    chapter_mine_preview_path,
)
from chapter_outline_generator import ChapterOutlineGenerator
from chapter_regenerator import ChapterRegenerator

BATCH_SOURCES = frozenset({"best", "draft", "revised", "final"})
BEST_SOURCE_ORDER = ("final", "revised", "draft")
CODEX_MINE_ORDER = ("plots", "characters", "bible")


def resolve_chapter_source(
    reader: ChapterRegenerator,
    number: int,
    source: str,
) -> tuple[str, str] | None:
    """Return (stage_label, text) or None when the chapter has no usable prose."""
    if source not in BATCH_SOURCES:
        raise ValueError(f"Invalid source {source!r}; expected best, draft, revised, or final")
    if source == "best":
        for stage in BEST_SOURCE_ORDER:
            try:
                return stage, reader.read_source(number, stage)
            except (FileNotFoundError, ValueError):
                continue
        return None
    try:
        return source, reader.read_source(number, source)
    except (FileNotFoundError, ValueError):
        return None


def _chapter_numbers(state, chapters: list[int] | None) -> list[int]:
    nums = sorted(chapters or list(state.chapters.keys()))
    return [n for n in nums if n in state.chapters]


def _saved_outline_path(project_path: str, number: int) -> Path:
    return Path(project_path) / "outputs" / f"chapter_{number:03d}_outline.md"


def chapter_has_outline(project_path: str, number: int) -> bool:
    """True when a saved outline or a pending outline preview exists."""
    gen = ChapterOutlineGenerator(project_path)
    if gen.preview_path(number).exists():
        return True
    return _saved_outline_path(project_path, number).exists()


def _feedback_dir(project_path: str) -> Path:
    return Path(project_path) / "outputs" / "feedback"


def chapter_has_codex_preview(project_path: str, number: int, kind: str) -> bool:
    return chapter_mine_preview_path(_feedback_dir(project_path), number, kind).exists()


def chapter_has_complete_codex(project_path: str, number: int) -> bool:
    return all(
        chapter_has_codex_preview(project_path, number, kind)
        for kind in CODEX_MINE_ORDER
    )


def _auto_accept_outline(
    project_path: str,
    number: int,
    gen: ChapterOutlineGenerator,
    log: Callable[[str], None],
) -> None:
    from prompt_context import strip_outline_pov_metadata  # noqa: WPS433

    preview_path = gen.preview_path(number)
    if not preview_path.exists():
        return
    text = strip_outline_pov_metadata(preview_path.read_text(encoding="utf-8"))
    if not text.strip():
        return
    out_path = _saved_outline_path(project_path, number)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    for path in (preview_path, gen.meta_path(number)):
        if path.exists():
            path.unlink()
    log(f"Chapter {number} outline saved (auto-accept).")


def _auto_accept_mine(
    project_path: str,
    number: int,
    kind: str,
    log: Callable[[str], None],
) -> None:
    from state_manager import StoryState, project_state_lock  # noqa: WPS433

    preview_path = chapter_mine_preview_path(_feedback_dir(project_path), number, kind)
    if not preview_path.exists():
        return
    data = json.loads(preview_path.read_text(encoding="utf-8"))
    parsed = data.get("parsed")
    if not isinstance(parsed, dict):
        return
    lock = project_state_lock(project_path)
    with lock:
        state = StoryState(project_path)
        changes = apply_mine_preview_to_state(state, number, kind, parsed)
        state.save_state()
        preview_path.unlink(missing_ok=True)
    if kind == "characters":
        try:
            from import_pipeline import ImportPipeline  # noqa: WPS433

            ImportPipeline(project_path).write_character_profiles()
        except Exception:  # noqa: BLE001
            pass
    log(f"Chapter {number} {kind} applied (auto-accept) — {len(changes)} update(s).")


def batch_outline_extract_stats(
    project_path: str,
    *,
    source: str = "best",
    chapters: list[int] | None = None,
) -> dict:
    if source not in BATCH_SOURCES:
        raise ValueError(f"Invalid source {source!r}")

    reader = ChapterRegenerator(project_path)
    state = reader.state
    numbers = _chapter_numbers(state, chapters)

    with_prose: list[int] = []
    missing: list[int] = []
    for number in numbers:
        if resolve_chapter_source(reader, number, source) is None:
            continue
        with_prose.append(number)
        if not chapter_has_outline(project_path, number):
            missing.append(number)

    return {
        "total_with_prose": len(with_prose),
        "missing_count": len(missing),
        "missing_chapters": missing,
    }


def batch_codex_extract_stats(
    project_path: str,
    *,
    source: str = "best",
    chapters: list[int] | None = None,
) -> dict:
    if source not in BATCH_SOURCES:
        raise ValueError(f"Invalid source {source!r}")

    reader = ChapterRegenerator(project_path)
    state = reader.state
    numbers = _chapter_numbers(state, chapters)

    with_prose: list[int] = []
    missing: list[int] = []
    for number in numbers:
        if resolve_chapter_source(reader, number, source) is None:
            continue
        with_prose.append(number)
        if not chapter_has_complete_codex(project_path, number):
            missing.append(number)

    return {
        "total_with_prose": len(with_prose),
        "missing_count": len(missing),
        "missing_chapters": missing,
    }


def batch_extract_outlines(
    project_path: str,
    *,
    source: str = "best",
    skip_existing: bool = True,
    auto_accept: bool = False,
    chapters: list[int] | None = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    log = on_progress or (lambda _msg: None)
    if source not in BATCH_SOURCES:
        raise ValueError(f"Invalid source {source!r}")

    reader = ChapterRegenerator(project_path)
    gen = ChapterOutlineGenerator(project_path)
    state = reader.state
    numbers = _chapter_numbers(state, chapters)
    if not numbers:
        raise ValueError("No chapters available for outline extraction.")

    generated: list[int] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    log(f"Batch outline extraction — {len(numbers)} chapter(s), source={source}")

    for idx, number in enumerate(numbers, start=1):
        from job_control import check_job_cancelled  # noqa: WPS433

        check_job_cancelled()

        if skip_existing and chapter_has_outline(project_path, number):
            skipped.append({
                "chapter": number,
                "reason": "Outline already exists (saved or preview pending).",
            })
            continue

        resolved = resolve_chapter_source(reader, number, source)
        if resolved is None:
            skipped.append({
                "chapter": number,
                "reason": "No final, revised, or draft text found.",
            })
            continue

        stage_label, _text = resolved
        log(f"[{idx}/{len(numbers)}] Outlining chapter {number} from {stage_label}…")
        try:
            gen.generate(number, source=stage_label, on_progress=log)
            if auto_accept:
                _auto_accept_outline(project_path, number, gen, log)
            generated.append(number)
            log(
                f"Chapter {number} outline "
                f"{'saved' if auto_accept else 'preview ready'}."
            )
        except Exception as exc:  # noqa: BLE001 — continue batch on single-chapter failure
            failed.append({"chapter": number, "error": f"{type(exc).__name__}: {exc}"})
            log(f"Chapter {number} outline failed: {type(exc).__name__}: {exc}")

    log(
        f"Batch outlines done — generated {len(generated)}, "
        f"skipped {len(skipped)}, failed {len(failed)}."
    )
    return {"generated": generated, "skipped": skipped, "failed": failed}


def batch_extract_codex(
    project_path: str,
    *,
    source: str = "best",
    skip_existing: bool = True,
    auto_accept: bool = False,
    chapters: list[int] | None = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    log = on_progress or (lambda _msg: None)
    if source not in BATCH_SOURCES:
        raise ValueError(f"Invalid source {source!r}")

    reader = ChapterRegenerator(project_path)
    miner = ChapterMiner(project_path)
    state = reader.state
    numbers = _chapter_numbers(state, chapters)
    if not numbers:
        raise ValueError("No chapters available for codex extraction.")

    generated: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    log(
        f"Batch codex extraction — {len(numbers)} chapter(s), "
        f"{len(CODEX_MINE_ORDER)} passes each, source={source}",
    )

    for idx, number in enumerate(numbers, start=1):
        from job_control import check_job_cancelled  # noqa: WPS433

        check_job_cancelled()

        resolved = resolve_chapter_source(reader, number, source)
        if resolved is None:
            for kind in CODEX_MINE_ORDER:
                skipped.append({
                    "chapter": number,
                    "kind": kind,
                    "reason": "No final, revised, or draft text found.",
                })
            continue

        stage_label, _text = resolved
        for kind in CODEX_MINE_ORDER:
            check_job_cancelled()
            if kind not in MINE_KINDS:
                continue

            preview_path = chapter_mine_preview_path(miner.feedback_dir, number, kind)
            if skip_existing and preview_path.exists():
                skipped.append({
                    "chapter": number,
                    "kind": kind,
                    "reason": f"{kind} preview already exists.",
                })
                continue

            log(f"[{idx}/{len(numbers)}] Mining {kind} from chapter {number} ({stage_label})…")
            try:
                miner.mine(number, kind, source=stage_label, on_progress=log)
                if auto_accept:
                    _auto_accept_mine(project_path, number, kind, log)
                generated.append({"chapter": number, "kind": kind})
                log(
                    f"Chapter {number} {kind} "
                    f"{'applied' if auto_accept else 'preview ready'}."
                )
            except Exception as exc:  # noqa: BLE001
                failed.append({
                    "chapter": number,
                    "kind": kind,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                log(f"Chapter {number} {kind} failed: {type(exc).__name__}: {exc}")

    log(
        f"Batch codex done — generated {len(generated)}, "
        f"skipped {len(skipped)}, failed {len(failed)}."
    )
    return {"generated": generated, "skipped": skipped, "failed": failed}
