"""Tests for shared project archive helpers."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from project_archive import (  # noqa: E402
    is_safe_zip_member,
    iter_project_archive_files,
    safe_extract_zip,
)

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_iter_project_archive_files_includes_assets(tmp_path):
    project = tmp_path / "p"
    (project / "outputs" / "state").mkdir(parents=True)
    (project / "outputs" / "state" / "story_state.json").write_text("{}", encoding="utf-8")
    portrait = project / "assets" / "portraits" / "char_a" / "face.png"
    portrait.parent.mkdir(parents=True)
    portrait.write_bytes(_TINY_PNG)
    map_img = project / "assets" / "maps" / "map1" / "world.png"
    map_img.parent.mkdir(parents=True)
    map_img.write_bytes(_TINY_PNG)

    names = {arc for _path, arc in iter_project_archive_files(project)}
    assert "outputs/state/story_state.json" in names
    assert "assets/portraits/char_a/face.png" in names
    assert "assets/maps/map1/world.png" in names


@pytest.mark.parametrize(
    "member,expected",
    [
        ("outputs/state/story_state.json", True),
        ("assets/maps/map1/world.png", True),
        ("assets/portraits/char_a/face.png", True),
        ("db_export.json", True),
        ("package_manifest.json", True),
        ("../etc/passwd", False),
        ("assets/maps/../escape.png", False),
        ("assets/other/secret.png", False),
        ("assets/maps/evil/../face.png", False),
    ],
)
def test_is_safe_zip_member(member, expected):
    assert is_safe_zip_member(member) is expected


def test_safe_extract_zip_skips_traversal(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("outputs/state/story_state.json", "{}")
        zf.writestr("assets/portraits/char_a/ok.png", _TINY_PNG)
        zf.writestr("../escape.txt", "bad")
        zf.writestr("assets/maps/../../evil.png", _TINY_PNG)

    extract = tmp_path / "extract"
    with zipfile.ZipFile(io.BytesIO(buf.getvalue()), "r") as zf:
        safe_extract_zip(zf, extract)

    assert (extract / "outputs" / "state" / "story_state.json").exists()
    assert (extract / "assets" / "portraits" / "char_a" / "ok.png").exists()
    assert not (tmp_path / "escape.txt").exists()
    assert not list(extract.rglob("evil.png"))
