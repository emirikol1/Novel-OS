"""Chapter mining writes previews; apply/discard gates state changes."""

from __future__ import annotations

import json

from state_manager import StoryState, initialize_project


def test_mine_preview_apply_updates_state(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()

    feedback = tmp_path / "outputs" / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    parsed = {
        "plot_threads": ["Heist Arc | main | Vault job | Alice"],
        "subplot_threads": [],
        "subplot_beats": [],
        "resolved_subplots": [],
        "plot_events": [],
    }
    preview_path = feedback / "chapter_001_mine_plots_preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "chapter_number": 1,
                "kind": "plots",
                "stage_source": "draft",
                "source": "mine_plots",
                "parsed": parsed,
                "changes": ["preview line"],
                "report_path": str(feedback / "chapter_001_mine_plots_report.md"),
            },
        ),
        encoding="utf-8",
    )

    from api.services import ProjectService

    svc = ProjectService(tmp_path.parent)
    project_id = tmp_path.name
    result = svc.apply_chapter_mine_preview(project_id, 1, "plots")
    assert result.changes
    assert not preview_path.exists()

    final = StoryState(str(tmp_path))
    assert any(t.name == "Heist Arc" for t in final.plot_threads.values())


def test_mine_preview_discard(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()

    feedback = tmp_path / "outputs" / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    preview_path = feedback / "chapter_001_mine_plots_preview.json"
    preview_path.write_text("{}", encoding="utf-8")

    from api.services import ProjectService

    svc = ProjectService(tmp_path.parent)
    svc.discard_chapter_mine_preview(tmp_path.name, 1, "plots")
    assert not preview_path.exists()


def test_list_mine_previews(tmp_path):
    initialize_project(str(tmp_path), "Novel", "Drama")
    feedback = tmp_path / "outputs" / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    (feedback / "chapter_002_mine_characters_preview.json").write_text(
        json.dumps({"chapter_number": 2, "kind": "characters", "changes": ["a", "b"]}),
        encoding="utf-8",
    )

    from api.services import ProjectService

    svc = ProjectService(tmp_path.parent)
    rows = svc.list_chapter_mine_previews(tmp_path.name, kind="characters")
    assert len(rows) == 1
    assert rows[0].chapter_number == 2
    assert rows[0].change_count == 2
