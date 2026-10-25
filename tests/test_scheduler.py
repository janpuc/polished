import asyncio
import random
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from conftest import make_client, make_settings

from polished.catalog.scheduler import (
    CATCHUP_DELAY_S,
    RETRY_DELAY_S,
    Scheduler,
    catchup_due,
    close_stale_runs,
    next_run_at,
)
from polished.catalog.sync import RunOutcome, RunRefused, SyncRunner, format_time
from polished.db import connect

WARSAW = ZoneInfo("Europe/Warsaw")
NOON = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


class NoJitter(random.Random):
    def uniform(self, a, b):
        return a


class MaxJitter(random.Random):
    def uniform(self, a, b):
        return b


def slot(after, **kwargs):
    return next_run_at(after, hour=6, jitter_min=30, tz=WARSAW, rng=NoJitter(), **kwargs)


def test_next_run_is_the_next_6am_in_the_household_timezone():
    # Warsaw is UTC+2 in July: 06:00 local is 04:00 UTC, tomorrow because noon UTC is past it
    assert slot(NOON) == datetime(2026, 7, 2, 4, 0, tzinfo=UTC)
    # before today's slot: today
    assert slot(datetime(2026, 7, 1, 1, 0, tzinfo=UTC)) == datetime(2026, 7, 1, 4, 0, tzinfo=UTC)


def test_next_run_follows_daylight_saving_time():
    # Warsaw is UTC+1 in winter: 06:00 local is 05:00 UTC
    assert slot(datetime(2026, 12, 1, 12, 0, tzinfo=UTC)) == datetime(2026, 12, 2, 5, 0, tzinfo=UTC)
    # the clocks go back on 2026-10-25; the slot after 11:00 local that day is 06:00 CET
    assert slot(datetime(2026, 10, 25, 10, 0, tzinfo=UTC)) == datetime(
        2026, 10, 26, 5, 0, tzinfo=UTC
    )


def test_next_run_honours_another_timezone_and_hour():
    result = next_run_at(
        NOON, hour=3, jitter_min=0, tz=ZoneInfo("America/New_York"), rng=NoJitter()
    )
    assert result == datetime(2026, 7, 2, 7, 0, tzinfo=UTC)  # 03:00 EDT


def test_jitter_stays_within_zero_to_thirty_minutes():
    base = slot(NOON)
    assert next_run_at(NOON, hour=6, jitter_min=30, tz=WARSAW, rng=MaxJitter()) == base + timedelta(
        minutes=30
    )
    rng = random.Random(7)
    for _ in range(200):
        delta = next_run_at(NOON, hour=6, jitter_min=30, tz=WARSAW, rng=rng) - base
        assert timedelta(0) <= delta <= timedelta(minutes=30)


def test_a_run_started_inside_the_jitter_window_does_not_schedule_itself_again_today():
    run_started = datetime(2026, 7, 2, 4, 20, tzinfo=UTC)  # 06:20 local, after the 06:00 slot
    assert slot(run_started) == datetime(2026, 7, 3, 4, 0, tzinfo=UTC)


def add_run(conn, started, status="ok"):
    conn.execute(
        "insert into sync_run (started_at, trigger, status) values (?, 'schedule', ?)",
        (format_time(started), status),
    )


def test_catchup_is_due_with_no_ok_run_in_30_hours(conn):
    now = NOON
    assert catchup_due(conn, now)
    add_run(conn, now - timedelta(hours=31))
    assert catchup_due(conn, now)
    add_run(conn, now - timedelta(hours=1), status="error")
    assert catchup_due(conn, now)
    add_run(conn, now - timedelta(hours=29))
    assert not catchup_due(conn, now)


def test_a_stale_running_row_is_closed_at_startup(conn):
    add_run(conn, NOON - timedelta(hours=2), status="running")
    add_run(conn, NOON - timedelta(minutes=5), status="running")
    assert close_stale_runs(conn, NOON) == 1
    rows = conn.execute("select status, error, finished_at from sync_run order by id").fetchall()
    assert (rows[0]["status"], rows[0]["error"]) == ("error", "interrupted")
    assert rows[0]["finished_at"] == format_time(NOON)
    assert rows[1]["status"] == "running"


def test_the_app_closes_stale_runs_when_it_starts(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    add_run(conn, datetime.now(UTC) - timedelta(hours=3), status="running")
    with client:
        pass
    assert conn.execute("select status from sync_run").fetchone()["status"] == "error"


def test_the_scheduler_task_runs_with_the_app_and_stops_with_it(tmp_path):
    settings = make_settings(tmp_path, sync_enabled=True)
    with make_client(settings) as client:
        assert client.get("/healthz").status_code == 200


async def test_single_flight_refuses_a_second_begin_until_the_first_ends(tmp_path, conn):
    settings = make_settings(tmp_path)
    runner = SyncRunner(settings)
    run_id = await runner.begin("manual")
    assert runner.running
    with pytest.raises(RunRefused) as refused:
        await runner.begin("schedule")
    assert refused.value.status_code == 409
    runner.lock.release()
    # the `running` row still blocks, e.g. a run in another process
    with pytest.raises(RunRefused) as refused:
        await runner.begin("schedule")
    assert refused.value.status_code == 409
    conn.execute("update sync_run set status = 'error' where id = ?", (run_id,))
    assert await runner.begin("schedule") > run_id


async def test_a_running_row_older_than_an_hour_does_not_block_a_new_run(tmp_path, conn):
    settings = make_settings(tmp_path)
    add_run(conn, datetime.now(UTC) - timedelta(hours=2), status="running")
    assert await SyncRunner(settings).begin("schedule")


class StubRunner:
    """Stands in for SyncRunner: records triggers, answers from a script."""

    def __init__(self, settings, outcomes=()):
        self.settings = settings
        self.tz = ZoneInfo(settings.timezone)
        self.outcomes = list(outcomes)
        self.triggers = []

    async def run(self, trigger):
        self.triggers.append(trigger)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return RunOutcome(1, "ok")


class Stop(Exception):
    pass


def scheduler_for(settings, outcomes=(), stop_after=10, now=NOON):
    runner = StubRunner(settings, outcomes)
    clock = SimpleNamespace(now=now, sleeps=[])

    async def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += timedelta(seconds=seconds)
        if len(clock.sleeps) >= stop_after:
            raise Stop

    scheduler = Scheduler(runner, sleep=sleep, now=lambda: clock.now, rng=NoJitter())
    return scheduler, runner, clock


async def test_the_scheduler_catches_up_after_60_seconds_then_waits_for_the_slot(tmp_path, conn):
    scheduler, runner, clock = scheduler_for(make_settings(tmp_path), stop_after=3)
    with pytest.raises(Stop):
        await scheduler.run_forever()
    assert runner.triggers == ["catchup", "schedule"]
    assert clock.sleeps[0] == CATCHUP_DELAY_S
    # NOON + 60 s, then to the next 06:00 Warsaw (04:00 UTC next day)
    assert datetime(2026, 7, 1, 12, 0, tzinfo=UTC) + timedelta(
        seconds=clock.sleeps[0] + clock.sleeps[1]
    ) == datetime(2026, 7, 2, 4, 0, tzinfo=UTC)


async def test_the_scheduler_skips_the_catchup_after_a_recent_ok_run(tmp_path, conn):
    add_run(conn, NOON - timedelta(hours=2))
    scheduler, runner, _ = scheduler_for(make_settings(tmp_path), stop_after=3)
    with pytest.raises(Stop):
        await scheduler.run_forever()
    assert runner.triggers == ["schedule"]


async def test_a_5xx_is_retried_once_an_hour_later(tmp_path, conn):
    add_run(conn, NOON - timedelta(hours=2))
    failed = RunOutcome(1, "error", "page 1: HTTP 503", retryable=True)
    scheduler, runner, clock = scheduler_for(
        make_settings(tmp_path), [failed, failed], stop_after=4
    )
    with pytest.raises(Stop):
        await scheduler.run_forever()
    assert runner.triggers == ["schedule", "schedule"]
    assert clock.sleeps[2] == RETRY_DELAY_S


async def test_a_429_is_not_retried_the_same_day(tmp_path, conn):
    add_run(conn, NOON - timedelta(hours=2))
    throttled = RunOutcome(1, "error", "page 1: HTTP 429", retryable=False)
    scheduler, runner, clock = scheduler_for(make_settings(tmp_path), [throttled], stop_after=4)
    with pytest.raises(Stop):
        await scheduler.run_forever()
    assert runner.triggers == ["schedule", "schedule"]  # the second is the next day's slot
    assert RETRY_DELAY_S not in clock.sleeps
    assert clock.sleeps[2] > 20 * 3600


async def test_a_refused_run_is_skipped_not_fatal(tmp_path, conn):
    scheduler, runner, _ = scheduler_for(
        make_settings(tmp_path), [RunRefused(409, "already running")], stop_after=3
    )
    with pytest.raises(Stop):
        await scheduler.run_forever()
    assert runner.triggers == ["catchup", "schedule"]


async def test_cancelling_the_scheduler_task_is_clean(tmp_path, conn):
    settings = make_settings(tmp_path)
    task = asyncio.create_task(Scheduler(SyncRunner(settings)).run_forever())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
