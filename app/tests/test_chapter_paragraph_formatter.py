"""Tests for paragraph/scene-break formatting validation."""

from __future__ import annotations

import pytest

from chapter_paragraph_formatter import (  # noqa: E402
    count_broken_line_hyphens,
    count_scene_breaks,
    dialogue_quote_signature,
    extract_quote_checked_chapter,
    prose_signature,
    validate_dialogue_quotes_only,
    validate_formatting_only,
    _dialogue_quote_prompt,
    _paragraph_prompt,
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


def test_paragraph_prompt_tells_ai_not_to_fix_split_edges():
    prompt = _paragraph_prompt(2, "draft", "continued sentence fragment", title="")
    assert "beginning and/or end may be cut off" in prompt
    assert "Do **not** repair, complete, remove, or otherwise fix incomplete" in prompt


def test_dialogue_quote_signature_ignores_double_quotes_and_whitespace_only():
    original = 'She said hello. It was Johns book.'
    checked = '"She said hello."\n\nIt was Johns book.'
    assert dialogue_quote_signature(original) == dialogue_quote_signature(checked)


def test_validate_dialogue_quotes_allows_quote_marks_and_whitespace():
    original = "She said hello. Then she left."
    checked = '"She said hello."\n\nThen she left.'
    validate_dialogue_quotes_only(original, checked)


def test_validate_dialogue_quotes_allows_broken_line_hyphen_repair():
    original = "The exam-\nple was clear. She said hello."
    checked = 'The example was clear. "She said hello."'
    validate_dialogue_quotes_only(original, checked)
    assert count_broken_line_hyphens(original) == 1
    assert count_broken_line_hyphens(checked) == 0


def test_validate_dialogue_quotes_rejects_normal_hyphen_removal():
    original = "The well-being of the town mattered."
    checked = '"The wellbeing of the town mattered."'
    with pytest.raises(ValueError, match="Quote-checked text changed"):
        validate_dialogue_quotes_only(original, checked)


def test_dialogue_quote_prompt_mentions_line_wrap_hyphenation_only():
    prompt = _dialogue_quote_prompt(2, "draft", "The exam-\nple was clear.", title="")
    assert "line-wrap hyphenation" in prompt
    assert "Do **not** remove intentional hyphens" in prompt


def test_validate_dialogue_quotes_rejects_punctuation_change():
    original = "She said hello. Then she left."
    checked = '"She said hello!" Then she left.'
    with pytest.raises(ValueError, match="Quote-checked text changed"):
        validate_dialogue_quotes_only(original, checked)


def test_validate_dialogue_quotes_rejects_apostrophe_change():
    original = "John's answer was quiet."
    checked = '"Johns answer was quiet."'
    with pytest.raises(ValueError, match="Quote-checked text changed"):
        validate_dialogue_quotes_only(original, checked)


def test_extract_quote_checked_chapter_block():
    raw = "note\n[QUOTE_CHECKED_CHAPTER]\n\"Hello.\"\n[/QUOTE_CHECKED_CHAPTER]"
    assert extract_quote_checked_chapter(raw) == '"Hello."'
