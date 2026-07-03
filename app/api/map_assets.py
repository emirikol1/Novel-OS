"""Safe on-disk storage for project map images."""

from __future__ import annotations

from pathlib import Path

from . import image_assets

MapAssetError = image_assets.ImageAssetError
ALLOWED_EXTENSIONS = image_assets.ALLOWED_EXTENSIONS


def assert_safe_map_id(value: str) -> None:
    image_assets.assert_safe_asset_id(value)


def maps_root(project_dir: Path) -> Path:
    return project_dir / "assets" / "maps"


def map_asset_dir(project_dir: Path, map_id: str) -> Path:
    return image_assets.asset_dir(maps_root(project_dir), map_id)


def detect_image_extension(data: bytes) -> str:
    return image_assets.detect_image_extension(data)


def media_type_for_filename(filename: str) -> str:
    return image_assets.media_type_for_filename(filename)


def assert_safe_stored_filename(filename: str) -> None:
    image_assets.assert_safe_stored_filename(filename)


def resolve_map_image_path(project_dir: Path, map_id: str, filename: str) -> Path:
    return image_assets.resolve_image_path(
        maps_root(project_dir), map_id, filename=filename
    )


def store_map_image(project_dir: Path, map_id: str, data: bytes) -> str:
    return image_assets.store_image(maps_root(project_dir), map_id, data=data)


def remove_map_image(project_dir: Path, map_id: str, filename: str) -> None:
    image_assets.remove_image(maps_root(project_dir), map_id, filename=filename)


def remove_map_assets(project_dir: Path, map_id: str) -> None:
    image_assets.remove_asset_dir(maps_root(project_dir), map_id)


def remap_map_asset_dirs(project_dir: Path, id_map: dict[str, str]) -> None:
    """Rename map asset folders after DB id remapping on package import."""
    root = maps_root(project_dir)
    for old_id, new_id in id_map.items():
        if old_id == new_id:
            continue
        src = root / old_id
        if not src.is_dir():
            continue
        dest = root / new_id
        if dest.exists():
            image_assets.remove_asset_dir(root, new_id)
        src.rename(dest)
