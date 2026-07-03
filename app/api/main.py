import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from . import db
from .routes import router, get_service
from .services import ProjectService

_CORE = Path(__file__).resolve().parent.parent / "core"


def _ensure_runtime_paths() -> None:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from runtime_paths import ensure_runtime_paths  # noqa: WPS433

    ensure_runtime_paths()


class JobBatchMiddleware(BaseHTTPMiddleware):
    """Attach X-Job-Batch header to context so related submits share a cancel group."""

    async def dispatch(self, request, call_next):
        _ensure_runtime_paths()
        from job_batch import reset_job_batch_id, set_job_batch_id  # noqa: WPS433

        batch = (request.headers.get("X-Job-Batch") or "").strip() or None
        token = set_job_batch_id(batch)
        try:
            return await call_next(request)
        finally:
            reset_job_batch_id(token)


def create_app(projects_root: Optional[Path] = None, db_url: Optional[str] = None) -> FastAPI:
    _ensure_runtime_paths()
    from log_redaction import configure_sanitized_logging  # noqa: WPS433
    from version import APP_VERSION  # noqa: WPS433

    configure_sanitized_logging()
    db.configure(db_url or os.environ.get("NOVEL_OS_DB") or "sqlite:///./novel_os.db")

    app = FastAPI(title="Novel OS API", version=APP_VERSION)
    app.add_middleware(JobBatchMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if projects_root is not None:
        app.dependency_overrides[get_service] = lambda: ProjectService(projects_root)
    return app


app = create_app()
