"""Cooperative cancel checks for long-running job work."""

from __future__ import annotations


def check_job_cancelled() -> None:
    """Raise JobCancelledError when the current background job was cancelled."""
    from llm_call_context import get_llm_job_meta  # noqa: WPS433
    from runtime_paths import ensure_runtime_paths  # noqa: WPS433

    meta = get_llm_job_meta()
    job_id = meta.get("job_id")
    if not job_id:
        return
    ensure_runtime_paths()
    from jobs import JobCancelledError, runner  # noqa: WPS433

    if runner.is_cancelled(str(job_id)):
        raise JobCancelledError("Cancelled")


def update_job_progress(**progress) -> None:
    """Attach progress metadata to the current background job, if any."""
    from llm_call_context import get_llm_job_meta  # noqa: WPS433
    from runtime_paths import ensure_runtime_paths  # noqa: WPS433

    meta = get_llm_job_meta()
    job_id = meta.get("job_id")
    if not job_id:
        return
    ensure_runtime_paths()
    from jobs import runner  # noqa: WPS433

    runner.update_progress(str(job_id), progress)
