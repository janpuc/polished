"""POST /sync/run, POST /wear/{id} with the home pick, and that no write works without a Bearer."""

from datetime import UTC, datetime

import pytest
from conftest import FakeClock, load_feed, make_client, oidc_settings, session_cookie
from test_api_support import TODAY, assert_error, make_api

from polished import auth as web_auth
from polished.catalog.sync import SyncRunner, format_time

pytest_plugins = ["test_api_support"]


# --- sync ----------------------------------------------------------------------------------


def store_runner(settings, status: int = 200) -> SyncRunner:
    import httpx

    def handler(request):
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, json={"products": load_feed()})

    clock = FakeClock()
    return SyncRunner(
        settings, transport=httpx.MockTransport(handler), clock=clock, sleep=clock.sleep
    )


@pytest.fixture
def sync_api(tmp_path, api_template, frozen_today):
    template, ids = api_template
    api = make_api(tmp_path, template, ids, sync_manual_cooldown_s=3600)
    conn = api.conn()
    conn.execute("delete from sync_run")  # the household's recorded run must not start a cooldown
    conn.close()
    api.client.app.state.sync_runner = store_runner(api.settings)
    return api


def test_sync_run_starts_a_run_and_answers_202_with_its_id(sync_api):
    response = sync_api.client.post("/api/v1/sync/run")
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"run_id"} and isinstance(body["run_id"], int)
    # The run was handed to the mock shop (the tests allow no other); it finished before the
    # test client returned.
    run = sync_api.rows("select * from sync_run where id = ?", body["run_id"])[0]
    assert (run["trigger"], run["status"], run["products_seen"]) == ("manual", "ok", 16)
    status = sync_api.get("/api/v1/sync").json()
    assert status["running"] is False and status["last"]["id"] == body["run_id"]


def test_a_second_run_inside_the_cooldown_is_429_with_retry_after_s(sync_api):
    sync_api.client.post("/api/v1/sync/run")
    response = sync_api.client.post("/api/v1/sync/run")
    error = assert_error(response, 429, "cooldown")
    assert 0 < error["retry_after_s"] <= 3600
    assert response.headers["retry-after"] == str(error["retry_after_s"])
    assert sync_api.count("sync_run") == 1


def test_a_run_while_another_is_going_is_409_sync_running(sync_api):
    conn = sync_api.conn()
    conn.execute(
        "insert into sync_run (started_at, trigger, status) values (?, 'schedule', 'running')",
        (format_time(datetime.now(UTC)),),
    )
    conn.close()
    assert_error(sync_api.client.post("/api/v1/sync/run"), 409, "sync_running")
    assert sync_api.count("sync_run") == 1  # only the one inserted above


def test_a_run_while_the_runner_holds_its_lock_is_409(sync_api):
    runner = sync_api.client.app.state.sync_runner
    runner.lock = _Locked()
    assert_error(sync_api.client.post("/api/v1/sync/run"), 409, "sync_running")


class _Locked:
    def locked(self):
        return True


def test_a_shop_that_errors_leaves_a_failed_run_and_the_catalog_alone(sync_api):
    sync_api.client.app.state.sync_runner = store_runner(sync_api.settings, status=503)
    shades = sync_api.count("shade")
    response = sync_api.client.post("/api/v1/sync/run")
    assert response.status_code == 202  # started; the outcome is in GET /sync
    last = sync_api.get("/api/v1/sync").json()["last"]
    assert last["status"] == "error" and last["error"]
    assert sync_api.count("shade") == shades


# --- wear ----------------------------------------------------------------------------------


def home_wear(api, query: str = "") -> dict:
    return api.get(f"/api/v1/home{query}").json()["wear"]


def test_wear_records_today(api):
    shade_id = api.shade("Thirst Trap")
    response = api.client.post(f"/api/v1/wear/{shade_id}")
    assert response.status_code == 200
    assert response.json() == {"worn_on": TODAY}
    assert api.rows("select shade_id, worn_on from wear") == [
        {"shade_id": shade_id, "worn_on": TODAY}
    ]


def test_wearing_twice_in_a_day_is_one_wearing(api):
    shade_id = api.shade("Thirst Trap")
    for _ in range(3):
        assert api.client.post(f"/api/v1/wear/{shade_id}").json() == {"worn_on": TODAY}
    assert api.count("wear") == 1


def test_wear_of_an_unknown_shade_is_a_404(api):
    assert_error(api.client.post("/api/v1/wear/999999"), 404, "not_found")
    assert api.count("wear") == 0


def test_a_day_is_the_households_not_utc(tmp_path, api_template, frozen_today):
    template, ids = api_template
    api = make_api(tmp_path, template, ids, timezone="Pacific/Auckland")  # 05:30 on the 27th
    body = api.client.post(f"/api/v1/wear/{api.shade('Thirst Trap')}").json()
    assert body == {"worn_on": "2026-10-27"}
    assert api.get("/api/v1/home").json()["date"] == "2026-10-27"


def test_home_shows_a_pick_that_holds_all_day(api):
    first = home_wear(api)
    assert set(first) == {"shade", "bottle", "worn_today"}
    assert first["worn_today"] is False
    assert first["shade"]["owned_count"] > 0
    assert first["bottle"]["shade_id"] == first["shade"]["id"]
    assert first["bottle"]["archived"] is False and first["bottle"]["state"] != "empty"
    assert [home_wear(api) for _ in range(5)] == [first] * 5


def test_i_wore_this_marks_the_pick_worn_today(api):
    pick = home_wear(api)["shade"]["id"]
    api.client.post(f"/api/v1/wear/{pick}")
    after = home_wear(api)
    assert after["shade"]["id"] == pick and after["worn_today"] is True


def test_wearing_another_shade_makes_it_the_one_shown(api):
    pick = home_wear(api)["shade"]["id"]
    other = next(
        s["id"] for s in api.get("/api/v1/shades?owned=owned").json()["items"] if s["id"] != pick
    )
    api.client.post(f"/api/v1/wear/{other}")
    shown = home_wear(api)
    assert shown["shade"]["id"] == other and shown["worn_today"] is True


def test_another_is_a_different_owned_shade_every_time(api):
    pick = home_wear(api)
    seen = set()
    for _ in range(25):
        other = home_wear(api, "?another=1")
        assert other["shade"]["id"] != pick["shade"]["id"]
        assert other["worn_today"] is False and other["bottle"]["shade_id"] == other["shade"]["id"]
        seen.add(other["shade"]["id"])
    assert len(seen) >= 2  # four shades are owned
    assert home_wear(api) == pick  # asking for another does not move today's pick


def test_another_after_wearing_the_pick_leaves_it_worn(api):
    pick = home_wear(api)["shade"]["id"]
    api.client.post(f"/api/v1/wear/{pick}")
    other = home_wear(api, "?another=1")
    assert other["shade"]["id"] != pick
    assert home_wear(api)["shade"]["id"] == pick


def test_home_has_no_wear_when_nothing_is_owned(api):
    conn = api.conn()
    conn.execute("update bottle set archived = 1")
    conn.close()
    assert home_wear(api) is None
    assert home_wear(api, "?another=1") is None


# --- every write needs a Bearer token ------------------------------------------------------

WRITES = [
    ("POST", "/api/v1/shades", {"title": "X", "kind": "polish"}),
    ("PUT", "/api/v1/shades/1/tip-colour", {"hex": "#aa00cc"}),
    ("POST", "/api/v1/shades/1/bottles", {}),
    ("PATCH", "/api/v1/bottles/1", {"state": "low"}),
    ("DELETE", "/api/v1/bottles/1", None),
    ("PUT", "/api/v1/shades/1/wishlist", {"priority": 1}),
    ("PATCH", "/api/v1/wishlist/1", {"priority": 3}),
    ("DELETE", "/api/v1/wishlist/1", None),
    ("POST", "/api/v1/wishlist/bought", {"items": [{"id": 1}]}),
    ("POST", "/api/v1/identifiers", {"kind": "gtin", "value": "5901234123457", "shade_id": 1}),
    ("DELETE", "/api/v1/identifiers/1", None),
    ("POST", "/api/v1/wheels", {"name": "X"}),
    ("PATCH", "/api/v1/wheels/1", {"name": "X"}),
    ("DELETE", "/api/v1/wheels/1", None),
    ("POST", "/api/v1/wheels/1/slug/regenerate", None),
    ("POST", "/api/v1/wheels/1/slug/take", {"from_wheel_id": 2}),
    ("POST", "/api/v1/wheels/1/slots/1/draft", None),
    ("DELETE", "/api/v1/wheels/1/slots/12", None),
    ("POST", "/api/v1/stacks/3/layers", {"shade_id": 1}),
    ("PATCH", "/api/v1/stacks/3/layers/4", {"coats_delta": 1}),
    ("DELETE", "/api/v1/stacks/3/layers/4", None),
    ("POST", "/api/v1/stacks/3/template", {"kind": "over_black"}),
    ("POST", "/api/v1/stacks/3/save", {}),
    ("POST", "/api/v1/stacks/3/cancel", None),
    ("POST", "/api/v1/sync/run", None),
    ("POST", "/api/v1/wear/1", None),
]


def tables(path) -> list:
    import sqlite3

    conn = sqlite3.connect(path)
    try:
        names = [r[0] for r in conn.execute("select name from sqlite_master where type = 'table'")]
        return [
            (name, conn.execute(f"select * from [{name}] order by 1").fetchall())
            for name in sorted(names)
        ]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("method", "path", "body"), WRITES, ids=lambda v: v if isinstance(v, str) else ""
)
def test_a_write_without_a_token_is_a_401_and_changes_nothing(api, bare_client, method, path, body):
    before = tables(api.settings.db_path)
    response = bare_client.request(method, path, json=body)
    assert_error(response, 401, "unauthorized")
    assert tables(api.settings.db_path) == before


@pytest.mark.parametrize(
    ("method", "path", "body"), WRITES, ids=lambda v: v if isinstance(v, str) else ""
)
def test_a_write_with_only_a_session_cookie_is_a_401(tmp_path, method, path, body):
    settings = oidc_settings(tmp_path)
    client = make_client(settings)  # sends the Origin a browser would
    client.cookies.set(
        web_auth.SESSION_COOKIE,
        session_cookie(settings, {"sub": "u1", "name": "Rae", "iat": 9e12, "seen": 9e12}),
        domain="polished.example.test",
    )
    assert client.get("/").status_code == 200  # the cookie is a good one for the web
    assert_error(client.request(method, path, json=body), 401, "unauthorized")


def test_a_write_with_a_wrong_token_is_a_401(api, bare_client):
    response = bare_client.post(
        "/api/v1/wheels", json={"name": "X"}, headers={"Authorization": "Bearer nope"}
    )
    assert_error(response, 401, "unauthorized")
    assert api.count("wheel") == 2


def test_the_writes_cover_every_post_put_patch_and_delete_of_the_spec():
    """A new write endpoint must be listed above (and so tested for the token)."""
    import yaml
    from test_api_spec import SPEC

    spec = yaml.safe_load(SPEC.read_text())
    unsafe = {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        if path.startswith("/api/v1/")
        for method in item
        if method != "get"
    }
    public = {
        ("POST", "/api/v1/auth/exchange"),
        ("POST", "/api/v1/auth/revoke"),
        ("DELETE", "/api/v1/auth/devices/{device_id}"),
    }
    import re

    listed = {(m, re.sub(r"/\d+", "/{}", p)) for m, p, _ in WRITES}
    wanted = {(m, re.sub(r"\{[^}]+\}", "{}", p)) for m, p in unsafe - public}
    assert listed == wanted
