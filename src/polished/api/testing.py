"""POST /__test/reset: puts a template database back, for the app's UI tests (NATIVE.md 6.2).

Registered only when POLISHED_AUTH_MODE=none and POLISHED_TEST_RESET_FROM is set (Settings refuse
the variable in oidc mode); it still answers 404 to anyone who is not on loopback."""

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import connect
from .errors import ApiError, not_found
from .routing import operation_id

router = APIRouter(generate_unique_id_function=operation_id, tags=["testing"])

LOOPBACK = ("127.0.0.1", "::1")


def restore(template: str, db_path: str) -> None:
    """Copies the template over the live database with SQLite's backup API, which takes the write
    lock and leaves other connections consistent (a file copy under a WAL would not)."""
    source = sqlite3.connect(f"{Path(template).resolve().as_uri()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(db_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    live = connect(db_path)
    try:
        live.execute("pragma wal_checkpoint(truncate)")
    finally:
        live.close()


@router.post(
    "/__test/reset",
    summary="Restore the template database (UI tests only)",
    responses={404: {"description": "Not enabled, or not called from loopback."}},
)
def test_reset(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    client = request.client.host if request.client else ""
    if settings.auth_mode != "none" or not settings.test_reset_from or client not in LOOPBACK:
        raise not_found()
    template = Path(settings.test_reset_from)
    if not template.is_file():
        raise ApiError(500, "server_error", "POLISHED_TEST_RESET_FROM is not a file.")
    if template.samefile(settings.db_path):
        raise ApiError(500, "server_error", "POLISHED_TEST_RESET_FROM is the live database.")
    restore(settings.test_reset_from, settings.db_path)
    return JSONResponse({"reset": True})
