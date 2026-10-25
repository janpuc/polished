from datetime import UTC, datetime, timedelta

import httpx
from conftest import FakeClock, load_feed, make_client, make_settings, oidc_settings

from polished.catalog.sync import SyncRunner, format_time
from polished.db import connect

HX = {"HX-Request": "true"}


def store(status=200):
    def handler(request):
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"products": load_feed()})

    return httpx.MockTransport(handler)


def client_with_store(tmp_path, status=200, **overrides):
    settings = make_settings(tmp_path, **overrides)
    client = make_client(settings)
    clock = FakeClock()
    client.app.state.sync_runner = SyncRunner(
        settings, transport=store(status), clock=clock, sleep=clock.sleep
    )
    return client, settings


def add_run(settings, started, status="ok", trigger="schedule"):
    conn = connect(settings.db_path)
    conn.execute(
        "insert into sync_run (started_at, trigger, status, products_seen, new_shades)"
        " values (?, ?, ?, 526, 372)",
        (format_time(started), trigger, status),
    )
    conn.close()


def test_the_sync_page_with_no_runs(client):
    response = client.get("/sync")
    assert response.status_code == 200
    assert "No sync has run yet." in response.text
    assert "Sync now" in response.text
    assert 'hx-trigger="every 2s"' not in response.text


def test_the_sync_page_lists_the_runs_with_counts(tmp_path):
    client, settings = client_with_store(tmp_path, sync_manual_cooldown_s=0)
    add_run(settings, datetime(2026, 10, 24, 4, 12, tzinfo=UTC))  # 06:12 in Warsaw (CEST)
    html = client.get("/sync").text
    assert "24 Oct 06:12" in html
    assert "526 products" in html
    assert "372 new" in html
    assert "schedule" in html


def test_the_status_box_polls_every_2s_only_while_a_run_is_going(tmp_path):
    client, settings = client_with_store(tmp_path, sync_manual_cooldown_s=0)
    assert 'hx-trigger="every 2s"' not in client.get("/sync/status").text
    add_run(settings, datetime.now(UTC), status="running")
    html = client.get("/sync/status").text
    assert 'hx-trigger="every 2s"' in html
    assert "A sync is running" in html
    assert "<html" not in html  # a partial


def test_post_sync_run_starts_a_run_through_the_mock_store(tmp_path):
    client, settings = client_with_store(tmp_path)
    response = client.post("/sync/run", headers=HX)
    assert response.status_code == 200
    assert 'id="sync-status"' in response.text
    conn = connect(settings.db_path)
    run = conn.execute("select * from sync_run").fetchone()
    assert (run["trigger"], run["status"], run["products_seen"]) == ("manual", "ok", 16)
    assert conn.execute("select count(*) from shade").fetchone()[0] == 9
    assert "9 new" in client.get("/sync").text


def test_post_sync_run_without_htmx_redirects_back_to_the_page(tmp_path):
    client, settings = client_with_store(tmp_path)
    response = client.post("/sync/run")
    assert (response.status_code, response.headers["location"]) == (303, "/sync")
    conn = connect(settings.db_path)
    assert conn.execute("select status from sync_run").fetchone()["status"] == "ok"


def test_a_manual_run_is_refused_with_409_while_one_is_running(tmp_path):
    client, settings = client_with_store(tmp_path, sync_manual_cooldown_s=0)
    add_run(settings, datetime.now(UTC), status="running", trigger="schedule")
    response = client.post("/sync/run", headers=HX)
    assert response.status_code == 409
    assert "already running" in response.text
    conn = connect(settings.db_path)
    assert conn.execute("select count(*) from sync_run").fetchone()[0] == 1
    assert conn.execute("select count(*) from product").fetchone()[0] == 0


def test_a_manual_run_inside_the_cooldown_is_refused_with_429(tmp_path):
    client, settings = client_with_store(tmp_path)
    add_run(settings, datetime.now(UTC) - timedelta(minutes=10))
    response = client.post("/sync/run", headers=HX)
    assert response.status_code == 429
    assert "try again in" in response.text
    conn = connect(settings.db_path)
    assert conn.execute("select count(*) from sync_run").fetchone()[0] == 1


def test_the_button_is_disabled_inside_the_cooldown_and_back_after_it(tmp_path):
    (tmp_path / "inside").mkdir()
    (tmp_path / "after").mkdir()
    inside, settings = client_with_store(tmp_path / "inside")
    add_run(settings, datetime.now(UTC) - timedelta(minutes=10))
    assert "disabled" in inside.get("/sync").text
    after, settings = client_with_store(tmp_path / "after")
    add_run(settings, datetime.now(UTC) - timedelta(hours=2))
    assert "disabled" not in after.get("/sync").text
    assert after.post("/sync/run", headers=HX).status_code == 200


def test_a_failed_run_shows_its_error_on_the_page(tmp_path):
    client, settings = client_with_store(tmp_path, status=429)
    assert client.post("/sync/run", headers=HX).status_code == 200
    html = client.get("/sync").text
    assert "HTTP 429" in html
    conn = connect(settings.db_path)
    assert conn.execute("select count(*) from product").fetchone()[0] == 0


def test_sync_routes_need_a_session(tmp_path):
    settings = oidc_settings(tmp_path)
    client = make_client(settings)
    assert client.get("/sync").status_code == 302
    assert client.get("/sync/status", headers=HX).status_code == 401
    assert client.post("/sync/run").status_code == 401


def test_post_sync_run_needs_a_matching_origin(client):
    assert client.post("/sync/run", headers={"Origin": "https://evil.example"}).status_code == 403
