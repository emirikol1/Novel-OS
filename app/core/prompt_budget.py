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
SAFE_METRIC_LABEL_PARTS = frozenset({
    "AI Paragraphs",
    "App",
    "Auto-title chapters",
    "Cast",
    "Chapter",
    "Dashboard",
    "Deduplicate bible",
    "DedupAI",
    "Expand placeholders",
    "Extract all codex",
    "Extract all outlines",
    "Extract background",
    "Extract chapter",
    "Fix chapter alignment",
    "Generate character",
    "Generate chapter brief",
    "Generate draft",
    "Generate outline",
    "Generate plot description",
    "Import story",
    "LLM prompt",
    "LLM request",
    "Mine characters",
    "Mine plot threads",
    "Mine story bible",
    "Plan chapter",
    "Plan outline",
    "Plots",
    "Populate chapter briefs",
    "Redraft from brief",
    "Regenerate chapter",
    "Resolve duplicates",
    "Revise",
    "Story Bible",
    "Validate",
})


def word_count(text: str) -> int:
    return len((text or "").split())


def estimate_prompt_tokens(text: str) -> int:
    """Rough token estimate for budgeting (no tokenizer dependency)."""
    if not text:
        return 0
    return max(1, int(word_count(text) * 1.33) + len(text) // 500)


def _safe_metric_label(label: str) -> str:
    """Keep operational labels useful without emitting project/story identifiers."""
    raw = (label or "LLM prompt").strip()
    if not raw:
        return "LLM prompt"
    if "·" not in raw:
        return raw[:80] if raw in SAFE_METRIC_LABEL_PARTS or raw.startswith("Agent:") else "<label>"

    safe_parts: List[str] = []
    for part in [p.strip() for p in raw.split("·") if p.strip()]:
        if part in SAFE_METRIC_LABEL_PARTS:
            safe_parts.append(part)
        elif re.fullmatch(r"Ch\.\d+", part):
            safe_parts.append(part)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", part):
            safe_parts.append("<time>")
        elif part.startswith("Agent:"):
            safe_parts.append(part[:80])
        else:
            safe_parts.append("<project>")
    return " · ".join(safe_parts[:5])


def prompt_section_word_counts(text: str, *, max_sections: int = 8) -> List[int]:
    """Approximate markdown section sizes without logging section names/content."""
    sections: List[int] = []
    current: List[str] = []
    for line in (text or "").splitlines():
        if line.startswith("#") and current:
            sections.append(word_count("\n".join(current)))
            current = []
            if len(sections) >= max_sections:
                break
        current.append(line)
    if current and len(sections) < max_sections:
        sections.append(word_count("\n".join(current)))
    return sections


def log_prompt_metrics(
    user: str,
    *,
    system: str = "",
    label: str = "prompt",
) -> None:
    """Privacy-safe prompt metrics: sizes only, never prompt or response content."""
    user_words = word_count(user)
    system_words = word_count(system)
    sections = prompt_section_word_counts(user)
    section_bits = ", ".join(
        f"s{i + 1}={count}w" for i, count in enumerate(sections)
    ) or "none"
    safe_log(
        "LLM prompt metrics: "
        f"label={_safe_metric_label(label)}, "
        f"user_words={user_words}, user_tokens~{estimate_prompt_tokens(user)}, "
        f"system_words={system_words}, system_tokens~{estimate_prompt_tokens(system)}, "
        f"user_sections={section_bits}",
    )


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
