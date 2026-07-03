"""Tests for mine preview UI summaries."""

from mine_preview_ui import build_mine_preview_ui


def test_plot_preview_splits_apply_and_skip():
    parsed = {
        "plot_events": ["Jack falls on the hill", "Jill follows", "They head home"],
        "subplot_beats": ["Fetch a Pail of Water | Jack slips"],
        "plot_lifespan_updates": ["Wrong Node | 1 | 1"],
    }
    technical = [
        "[mine_plots] no plot thread for subplot beat (19 chars, ~2 words)",
        "[mine_plots] unknown graph node for lifespan update (10 chars, ~2 words)",
        "[mine_plots] plot event: +3 new",
    ]
    ui = build_mine_preview_ui("plots", parsed, technical)
    assert ui["can_apply"] is True
    assert len(ui["will_apply"]) == 1
    assert "plot-event" in ui["will_apply"][0].lower()
    assert len(ui["skipped"]) == 2
    assert len(ui["proposed"]) >= 3
    assert "Story Graph" in ui["advice"]


def test_all_skipped_cannot_apply():
    technical = [
        "[mine_plots] no plot thread for subplot beat (x)",
        "[mine_plots] unknown graph node for lifespan update (y)",
    ]
    ui = build_mine_preview_ui("plots", {"subplot_beats": ["A | b"]}, technical)
    assert ui["can_apply"] is False
    assert "Discard" in ui["advice"]
