"""Request-scoped batch id so related background jobs cancel together."""

from __future__ import annotations

from contextvars import ContextVar

_job_batch_id: ContextVar[str | None] = ContextVar("job_batch_id", default=None)


def get_job_batch_id() -> str | None:
    return _job_batch_id.get()


def set_job_batch_id(batch_id: str | None):
    return _job_batch_id.set(batch_id)


def reset_job_batch_id(token) -> None:
    _job_batch_id.reset(token)
