"""Tests for chapter boundary alignment."""

from chapter_boundary_aligner import (
    apply_boundary_move,
    head_paragraphs,
    parse_alignment_response,
    pair_prose_signature,
    tail_paragraphs,
    validate_pair_unchanged,
)


def test_tail_and_head_paragraphs():
    text = "Para one.\n\nPara two.\n\nPara three."
    assert tail_paragraphs(text, 2) == "Para two.\n\nPara three."
    assert head_paragraphs(text, 2) == "Para one.\n\nPara two."


def test_apply_move_to_previous():
    a = "First chapter ends here."
    b = "Mid-sentence continues in chapter two.\n\nNew paragraph."
    move = "Mid-sentence continues in chapter two."
    new_a, new_b = apply_boundary_move(a, b, direction="to_previous", move_text=move)
    assert new_a.endswith(move)
    assert new_b.startswith("New paragraph.")
    validate_pair_unchanged(a, b, new_a, new_b)


def test_apply_move_to_next():
    a = "Ends abruptly mid-thought and"
    b = "continues here.\n\nLater scene."
    move = "and"
    new_a, new_b = apply_boundary_move(a, b, direction="to_next", move_text=move)
    assert new_a.endswith("Ends abruptly mid-thought")
    assert new_b.startswith("andcontinues here.")
    validate_pair_unchanged(a, b, new_a, new_b)


def test_pair_signature_unchanged_after_move():
    a = "Alpha block.\n\nSecond para."
    b = "Third starts wrong.\n\nFourth para."
    move = "Third starts wrong."
    new_a, new_b = apply_boundary_move(a, b, direction="to_previous", move_text=move)
    assert pair_prose_signature(a, b) == pair_prose_signature(new_a, new_b)


def test_parse_no_change():
    raw = "[BOUNDARY_ALIGNMENT]\nstatus: no_change\n[/BOUNDARY_ALIGNMENT]"
    status, direction, text = parse_alignment_response(raw)
    assert status == "no_change"
    assert direction is None
    assert text == ""


def test_parse_adjusted():
    raw = """[BOUNDARY_ALIGNMENT]
status: adjusted
move_direction: to_previous
move_text: |
The rest of the sentence.
[/BOUNDARY_ALIGNMENT]"""
    status, direction, text = parse_alignment_response(raw)
    assert status == "adjusted"
    assert direction == "to_previous"
    assert "rest of the sentence" in text


def test_validate_rejects_word_change():
    a, b = "Hello world.", "Next chapter."
    try:
        validate_pair_unchanged(a, b, "Hello there.", b)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "manuscript text" in str(exc).lower()
