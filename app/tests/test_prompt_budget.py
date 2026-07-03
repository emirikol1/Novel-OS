"""Tests for prompt_budget chunking and labels."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import prompt_budget  # noqa: E402
from prompt_budget import log_prompt_metrics, part_label, split_text_chunks, word_count  # noqa: E402


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


def test_log_prompt_metrics_redacts_project_label(monkeypatch):
    messages = []
    monkeypatch.setattr(prompt_budget, "safe_log", lambda message: messages.append(message))

    log_prompt_metrics(
        "# Prompt\nUse synthetic context only.",
        system="System instruction.",
        label="Chapter · secret_project_slug · Ch.3 · Generate draft · 2026-01-01 00:00",
    )

    assert messages
    msg = messages[0]
    assert "secret_project_slug" not in msg
    assert "<project>" in msg
    assert "user_words=" in msg
    assert "user_tokens~" in msg


def test_log_prompt_metrics_redacts_plain_word_project_label(monkeypatch):
    messages = []
    monkeypatch.setattr(prompt_budget, "safe_log", lambda message: messages.append(message))

    log_prompt_metrics(
        "# Prompt\nUse synthetic context only.",
        label="Chapter · Plain Word Project · Ch.3 · Generate draft · 2026-01-01 00:00",
    )

    assert messages
    msg = messages[0]
    assert "Plain Word Project" not in msg
    assert "Chapter · <project> · Ch.3 · Generate draft · <time>" in msg
