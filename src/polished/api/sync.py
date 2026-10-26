"""GET /sync: the catalog sync's state, and POST /sync/run, the only call that reaches the shop."""

from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

from ..catalog.sync import RunRefused, cooldown_remaining_s, format_time, running_run
from . import schemas
from .errors import ApiError
from .routing import ApiRoute, Conn

router = APIRouter(prefix="/sync", route_class=ApiRoute, tags=["sync"])

RUNS_SHOWN = 10


@router.get("", response_model=schemas.Sync, summary="Sync status")
def sync_status(request: Request, conn: Conn):
    runner = request.app.state.sync_runner
    now = runner.now()
    runs = [
        schemas.SyncRun(**dict(row))
        for row in conn.execute("select * from sync_run order by id desc limit ?", (RUNS_SHOWN,))
    ]
    wait = cooldown_remaining_s(conn, runner.settings, now)
    return schemas.Sync(
        running=runner.running or running_run(conn, now) is not None,
        last=runs[0] if runs else None,
        runs=runs,
        cooldown_until=format_time(now + timedelta(seconds=wait)) if wait else None,
    )


@router.post(
    "/run",
    status_code=202,
    response_model=schemas.SyncStarted,
    summary="Sync now",
    responses={
        409: {"description": "`sync_running`: a run is already going."},
        429: {"description": "`cooldown`: the last run started too recently; see `retry_after_s`."},
    },
)
async def sync_run(request: Request, conn: Conn):
    """Starts a manual run in the background and answers at once; poll `GET /sync` for the end.
    The run fetches the shop's `products.json` (three requests, one a second) and waits out the
    cooldown between manual runs."""
    runner = request.app.state.sync_runner
    try:
        run_id = await runner.begin("manual")
    except RunRefused as exc:
        if exc.status_code == 429:
            wait = max(1, cooldown_remaining_s(conn, runner.settings, runner.now()))
            raise ApiError(
                429, "cooldown", str(exc), retry_after_s=wait, headers={"Retry-After": str(wait)}
            ) from None
        raise ApiError(409, "sync_running", str(exc)) from None
    return JSONResponse(
        {"run_id": run_id}, status_code=202, background=BackgroundTask(runner.execute, run_id)
    )
