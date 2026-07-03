"""Tests for prompt_budget chunking and labels."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from prompt_budget import part_label, split_text_chunks, word_count  # noqa: E402


def test_split_text_chunks_single():
    text = " ".join(f"w{i}" for i in range(100))
    assert split_text_chunks(text, max_words=200) == [text]


def test_split_text_chunks_multiple():
    text = " ".join(f"w{i}" for i in range(250))
    chunks = split_text_chunks(text, max_words=100)
    assert len(chunks) == 3
    assert sum(word_count(c) for c in chunks) == 250


def test_part_label_sequence():
    assert part_label(0) == "a"
    assert part_label(1) == "b"
    assert part_label(25) == "z"
    assert part_label(26) == "aa"
