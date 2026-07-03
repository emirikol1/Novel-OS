"""Tests for background job runner."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from jobs import JobRunner


def test_list_running_includes_label_and_meta():
    runner = JobRunner()
    started = threading.Event()

    def work():
        started.wait(timeout=2)

    job_id = runner.submit(
        "mine_plots",
        work,
        meta={"project_id": "demo-project", "chapter": 3},
    )
    time.sleep(0.05)
    running = runner.list_running()
    assert len(running) == 1
    row = running[0]
    assert row["job_id"] == job_id
    assert row["screen"] == "Chapter"
    assert row["project_id"] == "demo-project"
    assert row["chapter"] == 3
    assert "demo-project" in row["label"]
    assert "Ch.3" in row["label"]
    assert "Mine plot threads" in row["label"]
    started.set()


def test_cancel_running_job_marks_error():
    runner = JobRunner()
    done = threading.Event()

    def work():
        time.sleep(0.2)
        done.set()

    job_id = runner.submit("write", work, meta={"project_id": "demo"})
    time.sleep(0.05)
    assert runner.cancel(job_id)["cancelled_jobs"] == 1
    job = runner.get(job_id)
    assert job is not None
    assert job["status"] == "error"
    assert job["error"] == "Cancelled"
    done.wait(timeout=2)


def test_cancel_batch_cancels_all_sibling_jobs():
    runner = JobRunner()
    from job_batch import reset_job_batch_id, set_job_batch_id  # noqa: E402

    started = threading.Event()
    hold = threading.Event()

    def work():
        started.set()
        hold.wait(timeout=3)

    token = set_job_batch_id("batch-test-001")
    try:
        job_a = runner.submit("write", work, meta={"project_id": "demo"})
        job_b = runner.submit("edit", work, meta={"project_id": "demo"})
    finally:
        reset_job_batch_id(token)

    started.wait(timeout=2)
    result = runner.cancel(job_a)
    assert result["cancelled_jobs"] == 2
    assert runner.get(job_a)["status"] == "error"
    assert runner.get(job_b)["status"] == "error"
    hold.set()
