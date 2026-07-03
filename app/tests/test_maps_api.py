import json
from pathlib import Path

import pytest

from api import map_assets
from tests.test_api import _client, _seed_project

# Minimal 1x1 PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_map_image_path_safety(tmp_path):
    project_dir = tmp_path / "p"
    project_dir.mkdir()
    map_id = "abc123"
    filename = map_assets.store_map_image(project_dir, map_id, _TINY_PNG)
    path = map_assets.resolve_map_image_path(project_dir, map_id, filename)
    assert path.is_file()

    with pytest.raises(map_assets.MapAssetError):
        map_assets.resolve_map_image_path(project_dir, map_id, "../escape.png")

    with pytest.raises(map_assets.MapAssetError):
        map_assets.resolve_map_image_path(project_dir, map_id, "/etc/passwd")

    with pytest.raises(map_assets.MapAssetError):
        map_assets.store_map_image(project_dir, "../evil", _TINY_PNG)


def test_maps_and_pins_crud(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    c = _client(tmp_path)

    assert c.get("/api/projects/p/maps").json() == []

    created = c.post("/api/projects/p/maps", json={"name": "World Map"})
    assert created.status_code == 201
    map_body = created.json()
    map_id = map_body["id"]
    assert map_body["name"] == "World Map"
    assert map_body["pin_count"] == 0

    upload = c.post(
        f"/api/projects/p/maps/{map_id}/image",
        content=_TINY_PNG,
        headers={"Content-Type": "image/png"},
    )
    assert upload.status_code == 200
    assert upload.json()["image_url"] == f"/api/projects/p/maps/{map_id}/image"

    image = c.get(f"/api/projects/p/maps/{map_id}/image")
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/")

    pin = c.post(
        f"/api/projects/p/maps/{map_id}/pins",
        json={
            "label": "Harbor",
            "x": 0.25,
            "y": 0.75,
            "lore_section": "setting_summary",
            "lore_label": "Old Harbor",
            "notes": "Dock district",
        },
    )
    assert pin.status_code == 201
    pin_id = pin.json()["id"]
    assert pin.json()["x"] == 0.25

    detail = c.get(f"/api/projects/p/maps/{map_id}").json()
    assert len(detail["pins"]) == 1
    assert detail["pins"][0]["lore_label"] == "Old Harbor"

    patched = c.patch(
        f"/api/projects/p/maps/{map_id}/pins/{pin_id}",
        json={"label": "Harbor District", "x": 1.5, "y": -0.2},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Harbor District"
    assert patched.json()["x"] == 1.0
    assert patched.json()["y"] == 0.0

    assert c.delete(f"/api/projects/p/maps/{map_id}/pins/{pin_id}").status_code == 204
    assert c.get(f"/api/projects/p/maps/{map_id}/pins").json() == []

    assert c.delete(f"/api/projects/p/maps/{map_id}").status_code == 204
    assert c.get("/api/projects/p/maps").json() == []

    saved = json.loads(sf.read_text())
    assert "maps" not in saved
    assert not (tmp_path / "p" / "assets" / "maps" / map_id).exists()


def test_map_upload_rejects_invalid_bytes(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    map_id = c.post("/api/projects/p/maps", json={"name": "X"}).json()["id"]
    bad = c.post(
        f"/api/projects/p/maps/{map_id}/image",
        content=b"not an image",
        headers={"Content-Type": "text/plain"},
    )
    assert bad.status_code == 400


def test_map_pin_requires_label(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    map_id = c.post("/api/projects/p/maps", json={"name": "X"}).json()["id"]
    resp = c.post(
        f"/api/projects/p/maps/{map_id}/pins",
        json={"label": "", "x": 0.5, "y": 0.5},
    )
    assert resp.status_code == 400
