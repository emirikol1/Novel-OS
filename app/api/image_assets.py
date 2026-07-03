"""Shared safe image asset validation and on-disk storage."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class ImageAssetError(ValueError):
    pass


def assert_safe_asset_id(value: str) -> None:
    if not value or not _SAFE_ID_RE.match(value):
        raise ImageAssetError(f"Invalid asset id: {value!r}")


def detect_image_extension(data: bytes) -> str:
    if len(data) < 12:
        raise ImageAssetError("Image file is too small")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise ImageAssetError("Unrecognized or unsupported image format")


def media_type_for_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return _MEDIA_TYPES.get(ext, "application/octet-stream")


def assert_safe_stored_filename(filename: str) -> None:
    if not filename or Path(filename).name != filename:
        raise ImageAssetError("Invalid image filename")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ImageAssetError("Invalid image filename")
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ImageAssetError("Invalid image extension")


def asset_dir(root: Path, *parts: str) -> Path:
    for part in parts:
        assert_safe_asset_id(part)
    return root.joinpath(*parts)


def resolve_image_path(root: Path, *parts: str, filename: str) -> Path:
    assert_safe_stored_filename(filename)
    full = (asset_dir(root, *parts) / filename).resolve()
    resolved_root = root.resolve()
    if os.path.commonpath([str(full), str(resolved_root)]) != str(resolved_root):
        raise ImageAssetError("Image path escapes project assets")
    if not full.is_file():
        raise FileNotFoundError(filename)
    return full


def store_image(root: Path, *parts: str, data: bytes) -> str:
    ext = detect_image_extension(data)
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    dest_dir = asset_dir(root, *parts)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return filename


def remove_image(root: Path, *parts: str, filename: str) -> None:
    if not filename:
        return
    try:
        path = resolve_image_path(root, *parts, filename=filename)
    except (ImageAssetError, FileNotFoundError):
        return
    path.unlink(missing_ok=True)


def remove_asset_dir(root: Path, *parts: str) -> None:
    d = asset_dir(root, *parts)
    if d.is_dir():
        for child in d.iterdir():
            if child.is_file():
                child.unlink(missing_ok=True)
        d.rmdir()
