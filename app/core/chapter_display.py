"""Human-readable chapter labels (including split parts like 1a, 1b)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import ChapterState


def chapter_display_label(chapter: "ChapterState") -> str:
    part_of = int(getattr(chapter, "part_of", 0) or 0)
    part_label = (getattr(chapter, "part_label", "") or "").strip()
    if part_of > 0 and part_label:
        return f"{part_of}{part_label}"
    return str(chapter.number)


def chapter_sort_key(chapter: "ChapterState") -> tuple:
    part_of = int(getattr(chapter, "part_of", 0) or 0)
    part_label = (getattr(chapter, "part_label", "") or "").strip()
    parent = part_of if part_of > 0 else chapter.number
    return (parent, part_label, chapter.number)
