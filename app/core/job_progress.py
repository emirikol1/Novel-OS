"""Helpers for reporting long-running background job progress."""

from __future__ import annotations

from collections import deque
import time
from typing import Deque

from job_control import update_job_progress


class RollingJobProgress:
    """Track sequential work and estimate remaining time from recent completions."""

    def __init__(self, *, total: int, unit: str) -> None:
        self.total = max(0, int(total))
        self.unit = unit
        self.completed = 0
        self.skipped = 0
        self.failed = 0
        self._started = time.monotonic()
        self._current_started: float | None = None
        self._durations: Deque[float] = deque(maxlen=3)

    def report(self, current: str = "") -> None:
        avg = (
            sum(self._durations) / len(self._durations)
            if self._durations
            else None
        )
        remaining_items = max(0, self.total - self.completed - self.skipped - self.failed)
        update_job_progress(
            total=self.total,
            completed=self.completed,
            skipped=self.skipped,
            failed=self.failed,
            current=current,
            unit=self.unit,
            average_seconds=avg,
            elapsed_seconds=max(0.0, time.monotonic() - self._started),
            remaining_seconds=(avg * remaining_items) if avg is not None else None,
        )

    def start(self, current: str) -> None:
        self._current_started = time.monotonic()
        self.report(current)

    def complete(self, current: str = "") -> None:
        if self._current_started is not None:
            self._durations.append(max(0.0, time.monotonic() - self._current_started))
            self._current_started = None
        self.completed += 1
        self.report(current)

    def skip(self, current: str = "") -> None:
        self._current_started = None
        self.skipped += 1
        self.report(current)

    def fail(self, current: str = "") -> None:
        self._current_started = None
        self.failed += 1
        self.report(current)
