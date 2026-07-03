"""Redact user story/manuscript text from operational logs and change summaries."""

from __future__ import annotations

import logging
import sys

# Markers for lines that are already structural or standard diagnostics.
_OPERATIONAL_MARKERS = (
    "chars, ~",  # size_ref()
    "[REDACTED",
    "[empty ",
    "HTTP/",
    "Traceback (most recent",
    'File "',
    "uvicorn",
    "Application startup",
    "Mining ",
    "=== MINE",
    "=== BACKGROUND",
    "DONE:",
    "Dry-run",
    "word_count",
    " words)",
    "pid=",
    "Started ",
    "ready at",
    "ERROR:",
    "WARNING:",
    "INFO:",
)

_MAX_CLEAR_LINE = 160
_MAX_LINE = 2000


def size_ref(text: str | None) -> str:
    """Structural placeholder for narrative or PII string values."""
    if text is None or text == "":
        return "empty"
    words = len(text.split())
    return f"{len(text)} chars, ~{words} words"


def redact_text(text: str | None, *, label: str = "text") -> str:
    """Full redaction token suitable for logs and terminal output."""
    if text is None or text == "":
        return f"[empty {label}]"
    return f"[REDACTED {label}: {size_ref(text)}]"


def redact_entity_name(entity_id: str, name: str | None = None) -> str:
    """Prefer stable ids in logs; never emit display names."""
    if entity_id:
        return entity_id
    return redact_text(name, label="name")


def sanitize_operational_log(line: str) -> str:
    """Redact narrative blobs from a log line; keep structural diagnostics readable."""
    if not line:
        return line
    if any(marker in line for marker in _OPERATIONAL_MARKERS):
        return line if len(line) <= _MAX_LINE else f"{line[:_MAX_LINE]}… [truncated]"
    if len(line) <= _MAX_CLEAR_LINE:
        return line
    return redact_text(line, label="log line")


def safe_log(message: str, *, stream=None) -> None:
    """Write a sanitized line to operational logs (stdout → backend.log by default)."""
    out = stream if stream is not None else sys.stdout
    text = sanitize_operational_log(str(message).rstrip("\n"))
    print(text, file=out, flush=True)


class SanitizingLogFilter(logging.Filter):
    """logging.Filter that redacts narrative text from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        sanitized = sanitize_operational_log(msg)
        if sanitized != msg:
            record.msg = sanitized
            record.args = ()
        return True


def configure_sanitized_logging() -> None:
    """Attach sanitizing filter to root logger (uvicorn, app, workers)."""
    filt = SanitizingLogFilter()
    root = logging.getLogger()
    if not any(isinstance(f, SanitizingLogFilter) for f in root.filters):
        root.addFilter(filt)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, SanitizingLogFilter) for f in logger.filters):
            logger.addFilter(filt)
