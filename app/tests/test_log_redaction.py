"""Tests for story-data log redaction helpers."""

from log_redaction import redact_text, safe_log, sanitize_operational_log, size_ref


def test_size_ref_empty():
    assert size_ref("") == "empty"
    assert size_ref(None) == "empty"


def test_size_ref_counts():
    assert size_ref("hello world") == "11 chars, ~2 words"


def test_redact_text():
    assert redact_text("secret prose") == "[REDACTED text: 12 chars, ~2 words]"
    assert redact_text("") == "[empty text]"


def test_sanitize_operational_log_short():
    assert sanitize_operational_log("Mining characters from chapter 3…") == (
        "Mining characters from chapter 3…"
    )


def test_sanitize_operational_log_long_narrative():
    prose = " ".join(["word"] * 50)
    out = sanitize_operational_log(prose)
    assert out.startswith("[REDACTED log line:")


def test_sanitize_operational_log_keeps_redacted_markers():
    line = "    • [mine] event logged (42 chars, ~8 words)"
    assert sanitize_operational_log(line) == line


def test_safe_log_writes_sanitized(capsys):
    safe_log("Mining plot threads…")
    assert "Mining plot threads" in capsys.readouterr().out
