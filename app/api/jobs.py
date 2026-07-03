"""In-memory background job runner for long agent phases.

Agent phases (write/edit/validate…) call the LLM and take 30–90s, so they must
never run inline in a request. We run them on a daemon thread and expose status
for the UI to poll. LLM concurrency is capped separately by ``llm_queue``.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobCancelledError(Exception):
    """Raised when a background job is cancelled cooperatively."""


class JobRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._groups: dict[str, set[str]] = {}
        self._job_to_group: dict[str, str] = {}
        self._lock = threading.Lock()
        self._shutting_down = False

    def _is_cancelled_unlocked(self, job_id: str) -> bool:
        event = self._cancel_events.get(job_id)
        return event.is_set() if event is not None else False

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._is_cancelled_unlocked(job_id)

    def batch_id_for_job(self, job_id: str) -> str | None:
        with self._lock:
            return self._job_to_group.get(job_id)

    def running_jobs_in_batch(self, batch_id: str) -> list[str]:
        with self._lock:
            return [
                jid for jid in self._groups.get(batch_id, set())
                if self._jobs.get(jid, {}).get("status") == "running"
            ]

    def batch_size(self, batch_id: str) -> int:
        with self._lock:
            return len(self._groups.get(batch_id, set()))

    def _register_group_unlocked(self, job_id: str, batch_id: str) -> None:
        self._job_to_group[job_id] = batch_id
        self._groups.setdefault(batch_id, set()).add(job_id)

    def submit(self, kind: str, fn: Callable[[], None], meta: Optional[dict] = None) -> str:
        from job_batch import get_job_batch_id  # noqa: WPS433

        job_id = uuid.uuid4().hex
        meta = dict(meta or {})
        batch_id = (meta.get("batch_id") or get_job_batch_id() or "").strip() or None
        if batch_id:
            meta["batch_id"] = batch_id

        with self._lock:
            if self._shutting_down:
                raise RuntimeError("Novel OS is restarting — new jobs are not accepted")
            self._jobs[job_id] = {
                "job_id": job_id,
                "kind": kind,
                "status": "running",
                "error": None,
                "started_at": _now(),
                "finished_at": None,
                **meta,
            }
            self._cancel_events[job_id] = threading.Event()
            if batch_id:
                self._register_group_unlocked(job_id, batch_id)

        def run() -> None:
            from llm_call_context import format_llm_job_label, llm_job_context  # noqa: WPS433
            from llm_queue import QueueCancelledError  # noqa: WPS433

            with self._lock:
                started_at = self._jobs.get(job_id, {}).get("started_at")
            job_label = format_llm_job_label(kind, meta, started_at=started_at)
            ctx_meta = {**(meta or {}), "kind": kind, "job_id": job_id}
            try:
                if self.is_cancelled(job_id):
                    raise JobCancelledError("Cancelled")
                with llm_job_context(job_label, meta=ctx_meta):
                    fn()
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job and job["status"] == "running":
                        if self._is_cancelled_unlocked(job_id):
                            self._update_unlocked(job_id, status="error", error="Cancelled")
                        else:
                            self._update_unlocked(job_id, status="done")
            except JobCancelledError:
                self._update(job_id, status="error", error="Cancelled")
            except QueueCancelledError:
                self._update(job_id, status="error", error="Cancelled")
            except Exception as e:  # noqa: BLE001 - surface any agent failure to the UI
                if self.is_cancelled(job_id) or "Cancelled" in str(e):
                    self._update(job_id, status="error", error="Cancelled")
                else:
                    err = f"{type(e).__name__}: {e}"
                    self._update(job_id, status="error", error=err)
                    from log_redaction import safe_log  # noqa: WPS433

                    safe_log(f"Job {kind} failed: {err}")

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def _cancel_one(self, job_id: str, reason: str = "Cancelled") -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.get("status") != "running":
                return False
            event = self._cancel_events.get(job_id)
            if event is not None:
                event.set()
            job["status"] = "error"
            job["error"] = reason
            job["finished_at"] = _now()

        from llm_queue import get_llm_queue  # noqa: WPS433

        get_llm_queue().cancel_for_job(job_id)
        return True

    def cancel(self, job_id: str, reason: str = "Cancelled") -> dict:
        """Cancel a job and every sibling in the same batch (if any)."""
        batch_id = self.batch_id_for_job(job_id)
        with self._lock:
            if batch_id:
                targets = list(self._groups.get(batch_id, {job_id}))
            else:
                targets = [job_id]

        cancelled = 0
        for target_id in targets:
            if self._cancel_one(target_id, reason):
                cancelled += 1

        job = self.get(job_id)
        return {
            "job": job,
            "cancelled_jobs": cancelled,
            "batch_id": batch_id,
            "batch_size": self.batch_size(batch_id) if batch_id else cancelled,
        }

    def _update_unlocked(self, job_id: str, **fields) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.update(fields)
            job["finished_at"] = _now()

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            self._update_unlocked(job_id, **fields)

    def flush(self, reason: str = "Cancelled by restart", reject_new: bool = False) -> int:
        """Mark in-flight jobs failed; optionally reject new submissions for restart."""
        with self._lock:
            if reject_new:
                self._shutting_down = True
            count = 0
            for job_id, job in self._jobs.items():
                if job["status"] == "running":
                    event = self._cancel_events.get(job_id)
                    if event is not None:
                        event.set()
                    job["status"] = "error"
                    job["error"] = reason
                    job["finished_at"] = _now()
                    count += 1
            return count

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_running(self) -> list[dict]:
        from llm_call_context import format_llm_job_label, screen_for_kind  # noqa: WPS433

        _meta_keys = frozenset({
            "job_id", "kind", "status", "error", "started_at", "finished_at",
        })
        with self._lock:
            rows: list[dict] = []
            for job in self._jobs.values():
                if job.get("status") != "running":
                    continue
                meta = {k: v for k, v in job.items() if k not in _meta_keys}
                kind = str(job.get("kind", ""))
                batch_id = job.get("batch_id")
                rows.append({
                    "job_id": job["job_id"],
                    "kind": kind,
                    "label": format_llm_job_label(
                        kind, meta, started_at=job.get("started_at"),
                    ),
                    "started_at": job.get("started_at") or _now(),
                    "project_id": job.get("project_id"),
                    "chapter": job.get("chapter"),
                    "screen": screen_for_kind(kind, meta),
                    "batch_id": batch_id,
                    "batch_size": len(self._groups.get(batch_id, set())) if batch_id else 1,
                })
            rows.sort(key=lambda r: r["started_at"])
            return rows


# Process-wide singleton.
runner = JobRunner()
