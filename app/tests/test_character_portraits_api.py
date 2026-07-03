import json
from pathlib import Path

import pytest

from api import portrait_assets
from tests.test_api import _client, _seed_project

# Minimal 1x1 PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_portrait_image_path_safety(tmp_path):
    project_dir = tmp_path / "p"
    project_dir.mkdir()
    character_id = "char_001"
    filename = portrait_assets.store_portrait_image(project_dir, character_id, _TINY_PNG)
    path = portrait_assets.resolve_portrait_image_path(project_dir, character_id, filename)
    assert path.is_file()

    with pytest.raises(portrait_assets.PortraitAssetError):
        portrait_assets.resolve_portrait_image_path(project_dir, character_id, "../escape.png")

    with pytest.raises(portrait_assets.PortraitAssetError):
        portrait_assets.resolve_portrait_image_path(project_dir, character_id, "/etc/passwd")

    with pytest.raises(portrait_assets.PortraitAssetError):
        portrait_assets.store_portrait_image(project_dir, "../evil", _TINY_PNG)


def test_character_portrait_upload_remove_serve(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"},
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    detail = c.get("/api/projects/p/characters/char_001").json()
    assert detail["portrait_url"] is None

    upload = c.post(
        "/api/projects/p/characters/char_001/portrait",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["portrait_url"] == "/api/projects/p/characters/char_001/portrait"

    image = c.get("/api/projects/p/characters/char_001/portrait")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/")

    listed = c.get("/api/projects/p/characters").json()
    assert listed[0]["portrait_url"] == "/api/projects/p/characters/char_001/portrait"

    saved = json.loads(sf.read_text())
    assert saved["characters"]["char_001"]["portrait_filename"]
    assert "portrait_filename" not in body

    replace = c.post(
        "/api/projects/p/characters/char_001/portrait",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    )
    assert replace.status_code == 200
    old_filename = saved["characters"]["char_001"]["portrait_filename"]
    new_filename = json.loads(sf.read_text())["characters"]["char_001"]["portrait_filename"]
    assert new_filename != old_filename

    removed = c.delete("/api/projects/p/characters/char_001/portrait")
    assert removed.status_code == 200
    assert removed.json()["portrait_url"] is None
    assert json.loads(sf.read_text())["characters"]["char_001"].get("portrait_filename", "") == ""

    assert c.get("/api/projects/p/characters/char_001/portrait").status_code == 404


def test_character_portrait_upload_rejects_invalid_bytes(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"},
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    bad = c.post(
        "/api/projects/p/characters/char_001/portrait",
        content=b"not an image",
        headers={"Content-Type": "text/plain"},
    )
    assert bad.status_code == 400


def test_delete_character_removes_portrait_assets(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"},
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    c.post(
        "/api/projects/p/characters/char_001/portrait",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    )
    assert (tmp_path / "p" / "assets" / "portraits" / "char_001").is_dir()

    assert c.delete("/api/projects/p/characters/char_001").status_code == 204
    assert not (tmp_path / "p" / "assets" / "portraits" / "char_001").exists()
