"""Safe on-disk storage for character portrait images."""

from __future__ import annotations

from pathlib import Path

from . import image_assets

PortraitAssetError = image_assets.ImageAssetError


def portraits_root(project_dir: Path) -> Path:
    return project_dir / "assets" / "portraits"


def portrait_asset_dir(project_dir: Path, character_id: str) -> Path:
    return image_assets.asset_dir(portraits_root(project_dir), character_id)


def store_portrait_image(project_dir: Path, character_id: str, data: bytes) -> str:
    return image_assets.store_image(
        portraits_root(project_dir), character_id, data=data
    )


def resolve_portrait_image_path(project_dir: Path, character_id: str, filename: str) -> Path:
    return image_assets.resolve_image_path(
        portraits_root(project_dir), character_id, filename=filename
    )


def remove_portrait_image(project_dir: Path, character_id: str, filename: str) -> None:
    image_assets.remove_image(
        portraits_root(project_dir), character_id, filename=filename
    )


def remove_portrait_assets(project_dir: Path, character_id: str) -> None:
    image_assets.remove_asset_dir(portraits_root(project_dir), character_id)


def media_type_for_filename(filename: str) -> str:
    return image_assets.media_type_for_filename(filename)
