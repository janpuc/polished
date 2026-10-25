"""When syncs run: a daily slot with jitter, a catch-up after a restart, one retry after a 5xx
(DESIGN 5.1). The loop lives in the app's lifespan; the pieces are plain functions."""

import asyncio
import logging
import random
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..config import Settings
from ..db import connect
from .fetch import Sleep
from .sync import STALE_RUNNING_S, RunRefused, SyncRunner, format_time, utc_now

log = logging.getLogger("polished.sync")

CATCHUP_DELAY_S = 60
CATCHUP_AFTER_H = 30  # no ok run for this long: sync once at startup
RETRY_DELAY_S = 3600


def next_run_at(
    after: datetime, *, hour: int, jitter_min: int, tz: ZoneInfo, rng: random.Random | None = None
) -> datetime:
    """The next `hour`:00 local time after `after`, plus 0 to `jitter_min` minutes; UTC."""
    rng = rng or random
    local = after.astimezone(tz)
    slot = datetime.combine(local.date(), time(hour), tzinfo=tz)
    if slot <= local:
        slot = datetime.combine(local.date() + timedelta(days=1), time(hour), tzinfo=tz)
    jitter = rng.uniform(0, jitter_min * 60)
    return (slot.astimezone(UTC)) + timedelta(seconds=jitter)


def catchup_due(conn: sqlite3.Connection, now: datetime) -> bool:
    """True when there is no ok run in the last CATCHUP_AFTER_H hours (or none at all)."""
    cutoff = format_time(now - timedelta(hours=CATCHUP_AFTER_H))
    row = conn.execute(
        "select 1 from sync_run where status = 'ok' and started_at > ? limit 1", (cutoff,)
    ).fetchone()
    return row is None


def close_stale_runs(conn: sqlite3.Connection, now: datetime) -> int:
    """Closes `running` rows older than STALE_RUNNING_S as `error: interrupted`; returns how many."""
    cutoff = format_time(now - timedelta(seconds=STALE_RUNNING_S))
    return conn.execute(
        "update sync_run set status = 'error', error = 'interrupted', finished_at = ?"
        " where status = 'running' and started_at <= ?",
        (format_time(now), cutoff),
    ).rowcount


def close_stale_runs_at_startup(settings: Settings, now: datetime) -> None:
    """Startup housekeeping; a database that was never migrated is left for healthz to report."""
    try:
        conn = connect(settings.db_path)
        try:
            closed = close_stale_runs(conn, now)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        log.warning("could not close stale sync runs: %s", exc)
        return
    if closed:
        log.warning("closed %d interrupted sync run(s)", closed)


class Scheduler:
    """Runs the catch-up check once, then the daily slot forever."""

    def __init__(
        self,
        runner: SyncRunner,
        *,
        sleep: Sleep = asyncio.sleep,
        now: Callable[[], datetime] = utc_now,
        rng: random.Random | None = None,
    ):
        self.runner = runner
        self.settings = runner.settings
        self.sleep = sleep
        self.now = now
        self.rng = rng

    async def run_forever(self) -> None:
        await self.sleep(CATCHUP_DELAY_S)
        if await asyncio.to_thread(self._catchup_due):
            await self._run("catchup")
        while True:
            await self.sleep_until_next_slot()
            outcome = await self._run("schedule")
            if outcome is not None and outcome.retryable:
                log.info("retrying once in %d s", RETRY_DELAY_S)
                await self.sleep(RETRY_DELAY_S)
                await self._run("schedule")

    async def sleep_until_next_slot(self) -> None:
        target = next_run_at(
            self.now(),
            hour=self.settings.sync_hour,
            jitter_min=self.settings.sync_jitter_min,
            tz=self.runner.tz,
            rng=self.rng,
        )
        log.info("next sync at %s", format_time(target))
        await self.sleep(max(0.0, (target - self.now()).total_seconds()))

    def _catchup_due(self) -> bool:
        conn = connect(self.settings.db_path)
        try:
            return catchup_due(conn, self.now())
        finally:
            conn.close()

    async def _run(self, trigger: str):
        try:
            return await self.runner.run(trigger)
        except RunRefused as exc:
            log.info("%s sync skipped: %s", trigger, exc)
        except sqlite3.Error:
            log.exception("%s sync could not start", trigger)
        return None
