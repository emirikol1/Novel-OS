#!/usr/bin/env python3
"""Block commits that appear to include private story data, PII, or secrets."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


DENY_PATH_PARTS = (
    "outputs/",
    "projects/",
    "/outputs/",
    "/projects/",
)

DENY_FILENAMES = {
    ".env",
    ".env.local",
    "story_state.json",
    "app_config.json",
}

DENY_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)

CONTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("SSN-like value", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("US phone-like value", re.compile(r"\b(?:\+1[-.\s])?(?:\(\d{3}\)[-.\s]?|\d{3}[-.\s])\d{3}[-.\s]\d{4}\b")),
]

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}


def git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def candidate_files(include_worktree: bool) -> list[Path]:
    staged = git_lines(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if staged or not include_worktree:
        return [Path(p) for p in staged]
    changed = git_lines(["diff", "--name-only", "--diff-filter=ACMR"])
    untracked = git_lines(["ls-files", "--others", "--exclude-standard"])
    return [Path(p) for p in [*changed, *untracked]]


def path_findings(path: Path) -> list[str]:
    normalized = path.as_posix()
    name = path.name
    findings: list[str] = []
    if any(part in normalized for part in DENY_PATH_PARTS):
        findings.append("runtime story/project data path")
    if name in DENY_FILENAMES:
        findings.append("private config or story state filename")
    if normalized.lower().endswith(DENY_SUFFIXES):
        findings.append("database/key material file type")
    if re.search(r"chapter_\d{3}_(draft|revised|final)\.md$", normalized):
        findings.append("manuscript chapter artifact")
    return findings


def content_findings(path: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except FileNotFoundError:
        return []
    findings: list[str] = []
    for label, pattern in CONTENT_PATTERNS:
        if pattern.search(text):
            findings.append(label)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worktree-if-empty",
        action="store_true",
        help="When nothing is staged, scan modified and untracked files.",
    )
    args = parser.parse_args()

    repo = Path(git_lines(["rev-parse", "--show-toplevel"])[0])
    os.chdir(repo)
    candidates = candidate_files(include_worktree=args.worktree_if_empty)
    problems: list[tuple[Path, list[str]]] = []

    for path in candidates:
        findings = [*path_findings(path), *content_findings(path)]
        if findings:
            problems.append((path, findings))

    if problems:
        print("Potential PII/story-data leak detected. Review before committing:", file=sys.stderr)
        for path, findings in problems:
            print(f"- {path}: {', '.join(findings)}", file=sys.stderr)
        return 1

    print(f"Leak check passed for {len(candidates)} candidate file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
