"""GET /sync: the catalog sync's state. (POST /sync/run comes with the write endpoints.)"""

from datetime import timedelta

from fastapi import APIRouter, Request

from ..catalog.sync import cooldown_remaining_s, format_time, running_run
from . import schemas
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
