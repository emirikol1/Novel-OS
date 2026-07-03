"""
Shared prompt size helpers — chunk long prose and warn before oversized LLM calls.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

from log_redaction import safe_log

DEFAULT_CHUNK_WORDS = int(os.environ.get("NOVEL_OS_PROMPT_CHUNK_WORDS", "6000"))
WARN_PROMPT_WORDS = int(os.environ.get("NOVEL_OS_WARN_PROMPT_WORDS", "12000"))
MAX_PROMPT_WORDS = int(os.environ.get("NOVEL_OS_MAX_PROMPT_WORDS", "0"))
DEFAULT_SPLIT_WORDS = int(os.environ.get("NOVEL_OS_CHAPTER_SPLIT_WORDS", "6000"))


def word_count(text: str) -> int:
    return len((text or "").split())


def estimate_prompt_tokens(text: str) -> int:
    """Rough token estimate for budgeting (no tokenizer dependency)."""
    if not text:
        return 0
    return max(1, int(word_count(text) * 1.33) + len(text) // 500)


def split_text_chunks(text: str, max_words: Optional[int] = None) -> List[str]:
    """Split long prose into LLM-sized chunks (paragraph-aware when possible)."""
    limit = max_words or DEFAULT_CHUNK_WORDS
    words = text.split()
    if len(words) <= limit:
        return [text]

    chunks: List[str] = []
    buf: List[str] = []
    buf_words = 0

    def flush() -> None:
        nonlocal buf, buf_words
        if buf:
            chunks.append("\n\n".join(buf).strip())
            buf = []
            buf_words = 0

    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        pw = len(para.split())
        if pw > limit:
            flush()
            pw_list = para.split()
            for i in range(0, len(pw_list), limit):
                chunks.append(" ".join(pw_list[i: i + limit]))
            continue
        if buf_words + pw > limit and buf:
            flush()
        buf.append(para)
        buf_words += pw
    flush()
    return [c for c in chunks if c.strip()]


def check_prompt_budget(user: str, *, label: str = "prompt") -> None:
    """
    Log or reject oversized prompts before an LLM call.

    NOVEL_OS_MAX_PROMPT_WORDS=0 (default) never hard-fails — chunking handles long inputs.
    """
    wc = word_count(user)
    est = estimate_prompt_tokens(user)
    if MAX_PROMPT_WORDS > 0 and wc > MAX_PROMPT_WORDS:
        raise RuntimeError(
            f"{label} is ~{wc:,} words (~{est:,} tokens), above NOVEL_OS_MAX_PROMPT_WORDS={MAX_PROMPT_WORDS:,}. "
            "Split the chapter (Split into parts) or raise your model context length."
        )
    if wc > WARN_PROMPT_WORDS:
        safe_log(
            f"Large {label}: ~{wc:,} words (~{est:,} tokens). "
            "If the model rejects the request, split the chapter into parts or load a larger context."
        )


def part_label(index: int) -> str:
    """0 -> 'a', 1 -> 'b', … 25 -> 'z', 26 -> 'aa'."""
    if index < 0:
        return "a"
    label = ""
    n = index
    while True:
        label = chr(ord("a") + (n % 26)) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label
