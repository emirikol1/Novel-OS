"""Runtime import path setup."""

from __future__ import annotations

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from runtime_paths import ensure_runtime_paths  # noqa: E402


def test_ensure_runtime_paths_allows_jobs_import_from_core():
    api = Path(__file__).resolve().parent.parent / "api"
    sys.path[:] = [p for p in sys.path if p not in {str(CORE), str(api)}]
    sys.path.insert(0, str(CORE))

    ensure_runtime_paths()

    from jobs import runner  # noqa: WPS433

    assert runner is not None
