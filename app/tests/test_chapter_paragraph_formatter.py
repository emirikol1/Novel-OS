"""Tests for paragraph/scene-break formatting validation."""

from __future__ import annotations

import pytest

from chapter_paragraph_formatter import (  # noqa: E402
    count_scene_breaks,
    prose_signature,
    validate_formatting_only,
)


def test_prose_signature_ignores_whitespace():
    original = "Line one. Line two."
    formatted = "Line one.\n\nLine two."
    assert prose_signature(original) == prose_signature(formatted)


def test_validate_allows_scene_breaks():
    original = "First scene ends here. Second scene begins."
    formatted = "First scene ends here.\n\n...\n\nSecond scene begins."
    validate_formatting_only(original, formatted)
    assert count_scene_breaks(formatted) == 1


def test_validate_rejects_word_change():
    original = "The colour of the sky was grey."
    formatted = "The color of the sky was gray."
    with pytest.raises(ValueError, match="changed the manuscript"):
        validate_formatting_only(original, formatted)


def test_validate_rejects_omission():
    original = "Alpha beta gamma."
    formatted = "Alpha gamma."
    with pytest.raises(ValueError, match="changed the manuscript"):
        validate_formatting_only(original, formatted)


def test_validate_preserves_archaic_hyphenation():
    original = "He was remorse-ful and weary."
    formatted = "He was remorse-ful\n\nand weary."
    validate_formatting_only(original, formatted)
