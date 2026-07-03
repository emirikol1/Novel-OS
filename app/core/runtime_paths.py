"""Ensure core/ and api/ are on sys.path for cross-layer imports (e.g. jobs from core)."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent.parent
_API = _APP_ROOT / "api"
_CORE = _APP_ROOT / "core"


def ensure_runtime_paths() -> None:
    for path in (_CORE, _API):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)
