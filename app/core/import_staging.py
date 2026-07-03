"""Temporary storage for ebook files uploaded through the web UI."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


_ALLOWED_SUFFIXES = {".txt", ".text", ".epub", ""}


def staging_root() -> Path:
    home = Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))
    root = Path(os.environ.get("NOVEL_OS_IMPORT_STAGING_DIR", home / "run" / "import-staging"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._")
    return base or "upload.txt"


def save_upload(data: bytes, filename: str) -> tuple[str, Path]:
    """Persist raw upload bytes; return (upload_id, path)."""
    if not data:
        raise ValueError("Empty upload")
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type '{suffix or '(none)'}' — use .txt or .epub")
    upload_id = uuid.uuid4().hex
    root = staging_root()
    dest = root / f"{upload_id}_{_safe_filename(filename)}"
    dest.write_bytes(data)
    return upload_id, dest


def resolve_upload(upload_id: str) -> Path:
    upload_id = upload_id.strip()
    if not upload_id or not re.fullmatch(r"[a-f0-9]{32}", upload_id):
        raise ValueError("Invalid upload id")
    matches = sorted(staging_root().glob(f"{upload_id}_*"))
    if not matches:
        raise FileNotFoundError("Upload not found or expired")
    return matches[0]
