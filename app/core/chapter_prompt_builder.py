"""Shared Scribe prompt context blocks (brief, plot, style, outline)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from state_manager import ChapterState, StoryState


def build_scribe_context_block(
    state: "StoryState",
    chapter: "ChapterState",
    *,
    hint_text: str = "",
    outline_text: Optional[str] = None,
    budget=None,
) -> str:
    """Brief (canonical POV) + writing style + plot + stripped beat sheet."""
    from prompt_context import build_chapter_context_block  # noqa: WPS433

    return build_chapter_context_block(
        state,
        chapter,
        hint_text=hint_text,
        outline_text=outline_text,
        budget=budget,
    )
