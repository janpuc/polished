"""The /sync page: recent runs, counts, Sync now (DESIGN 13.2)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from starlette.background import BackgroundTask

from ..catalog.sync import RunRefused, SyncRunner, cooldown_remaining_s, parse_time, running_run
from ..db import connect, get_conn
from ..web import render

router = APIRouter(prefix="/sync")

RUNS_SHOWN = 10

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _run_view(row: sqlite3.Row, runner: SyncRunner) -> dict:
    run = dict(row)
    run["started_local"] = (
        parse_time(row["started_at"]).astimezone(runner.tz).strftime("%d %b %H:%M")
    )
    return run


def _status_context(conn: sqlite3.Connection, runner: SyncRunner, error: str | None = None) -> dict:
    now = runner.now()
    rows = conn.execute("select * from sync_run order by id desc limit ?", (RUNS_SHOWN,)).fetchall()
    return {
        "runs": [_run_view(row, runner) for row in rows],
        "running": runner.running or running_run(conn, now) is not None,
        "cooldown_min": -(-cooldown_remaining_s(conn, runner.settings, now) // 60),
        "error": error,
    }


def _respond(
    request: Request, runner: SyncRunner, status_code: int = 200, error: str | None = None
) -> Response:
    """The status box for HTMX requests, the whole page otherwise."""
    template = "_sync_status.html" if request.headers.get("hx-request") == "true" else "sync.html"
    conn = connect(runner.settings.db_path)
    try:
        return render(request, template, _status_context(conn, runner, error), status_code)
    finally:
        conn.close()


@router.get("")
def sync_page(request: Request, conn: Conn):
    return render(request, "sync.html", _status_context(conn, request.app.state.sync_runner))


@router.get("/status")
def sync_status(request: Request, conn: Conn):
    return render(
        request, "_sync_status.html", _status_context(conn, request.app.state.sync_runner)
    )


@router.post("/run")
async def sync_run(request: Request):
    """Starts a manual run in the background: 409 while one is running, 429 in the cooldown."""
    runner: SyncRunner = request.app.state.sync_runner
    hx = request.headers.get("hx-request") == "true"
    try:
        run_id = await runner.begin("manual")
    except RunRefused as exc:
        return _respond(request, runner, exc.status_code, str(exc))
    response = _respond(request, runner) if hx else RedirectResponse("/sync", status_code=303)
    response.background = BackgroundTask(runner.execute, run_id)
    return response
