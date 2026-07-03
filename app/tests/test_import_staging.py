"""Tests for import staging and chunked chapter extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from import_pipeline import IMPORT_CHUNK_WORDS, split_import_chunks
from import_staging import resolve_upload, save_upload, staging_root


def test_split_import_chunks_paragraph_aware():
    paras = [f"para{i} " + " ".join(f"w{j}" for j in range(500)) for i in range(5)]
    text = "\n\n".join(paras)
    chunks = split_import_chunks(text, max_words=600)
    assert len(chunks) >= 4
    for chunk in chunks:
        assert len(chunk.split()) <= 650


def test_split_import_chunks_single_small():
    text = "short chapter text here"
    assert split_import_chunks(text) == [text]


def test_save_and_resolve_upload(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr("import_staging.staging_root", lambda: staging)
    upload_id, path = save_upload(b"hello world", "sample.txt")
    assert path.is_file()
    assert resolve_upload(upload_id) == path


def test_save_upload_rejects_empty():
    with pytest.raises(ValueError, match="Empty"):
        save_upload(b"", "x.txt")


def test_chunk_default_matches_env():
    words = " ".join(f"w{i}" for i in range(IMPORT_CHUNK_WORDS + 100))
    chunks = split_import_chunks(words)
    assert len(chunks) == 2
