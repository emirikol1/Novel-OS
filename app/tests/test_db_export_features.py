"""DB export/import round trip for Features 14–16."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import api.db as dbmod  # noqa: E402


@pytest.fixture(autouse=True)
def _db(tmp_path):
    dbmod.configure(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    dbmod._clear_all()
    yield


def _seed_db_project(root: Path, project_id: str) -> None:
    state_dir = root / project_id / "outputs" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "story_state.json").write_text(
        json.dumps({"metadata": {"title": "T", "genre": "G"}, "chapters": {}}),
        encoding="utf-8",
    )
    dbmod.ingest_project(root, project_id)


def test_export_import_research_maps_and_pins_roundtrip(tmp_path):
    _seed_db_project(tmp_path, "p")
    spark = dbmod.research_spark_create(
        "p", title="Note", body="Body", tags=["tag"], kind="note",
    )
    pmap = dbmod.project_map_create("p", name="World")
    dbmod.project_map_set_image("p", pmap.id, "world.png")
    pin = dbmod.map_pin_create("p", pmap.id, label="City", x=0.1, y=0.2)

    exported = dbmod.export_project_data("p")
    assert len(exported["research_sparks"]) == 1
    assert exported["research_sparks"][0]["title"] == "Note"
    assert len(exported["project_maps"]) == 1
    assert exported["project_maps"][0]["image_filename"] == "world.png"
    assert len(exported["map_pins"]) == 1
    assert exported["map_pins"][0]["label"] == "City"

    dbmod.import_project_data("p", exported)
    again = dbmod.export_project_data("p")
    assert again["research_sparks"][0]["id"] == spark.id
    assert again["project_maps"][0]["id"] == pmap.id
    assert again["map_pins"][0]["map_id"] == pmap.id
    assert again["map_pins"][0]["id"] == pin.id


def test_import_remaps_map_pin_map_id_on_package_import(tmp_path):
    _seed_db_project(tmp_path, "src")
    pmap = dbmod.project_map_create("src", name="World")
    dbmod.map_pin_create("src", pmap.id, label="Pin", x=0.5, y=0.5)
    exported = dbmod.export_project_data("src")

    _seed_db_project(tmp_path, "dest")
    remap = dbmod.import_project_data(
        "dest", exported, allow_id_mismatch=True, remap_ids=True,
    )
    assert pmap.id in remap
    new_map_id = remap[pmap.id]
    pins = dbmod.map_pins_list("dest", new_map_id)
    assert len(pins) == 1
    assert pins[0].map_id == new_map_id
