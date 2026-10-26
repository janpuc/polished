"""The routes around /api/v1: universal links (AASA), the UI-test reset, the migration."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from conftest import make_client, make_settings, oidc_settings
from pydantic import ValidationError
from starlette.testclient import TestClient
from test_api_support import LOOPBACK, make_api

from polished.migrate import MIGRATIONS, migrate
from polished.server import create_app

pytest_plugins = ["test_api_support"]

TEAM = "RW5T9P5A59"
AASA = "/.well-known/apple-app-site-association"
REAL_DEV_DB = Path.home() / ".cache/polished/overhaul-dev4/polished.db"


# --- apple-app-site-association ------------------------------------------------------------


def test_aasa_is_public_json_without_a_redirect(tmp_path):
    client = make_client(oidc_settings(tmp_path, apple_team_id=TEAM))
    response = client.get(AASA)  # nobody is signed in
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "applinks": {
            "details": [
                {
                    "appIDs": [f"{TEAM}.com.janpuc.polished"],
                    "components": [
                        {"/": "/w/*"},
                        {"/": "/shades/new", "exclude": True},
                        {"/": "/shades/*"},
                    ],
                }
            ]
        },
        # The app's sign-in callback (an https address ASWebAuthenticationSession claims) needs this.
        "webcredentials": {"apps": [f"{TEAM}.com.janpuc.polished"]},
    }


def test_aasa_does_not_open_the_sign_in_in_the_app(tmp_path):
    """A tapped /auth/* link must stay in the browser: applinks lists only /w/* and /shades/*."""
    client = make_client(make_settings(tmp_path, apple_team_id=TEAM))
    aasa = client.get(AASA).json()
    assert set(aasa) == {"applinks", "webcredentials"}
    paths = [c["/"] for d in aasa["applinks"]["details"] for c in d["components"]]
    assert paths == ["/w/*", "/shades/new", "/shades/*"]
    assert not any(
        p.startswith("/auth") or p == "*" or p.endswith("/*") and p[:-2] == "" for p in paths
    )
    assert aasa["webcredentials"] == {"apps": [f"{TEAM}.com.janpuc.polished"]}


def test_aasa_excludes_new_shades_before_the_shades_wildcard(tmp_path):
    client = make_client(make_settings(tmp_path, apple_team_id=TEAM))
    components = client.get(AASA).json()["applinks"]["details"][0]["components"]
    paths = [c["/"] for c in components]
    assert paths.index("/shades/new") < paths.index("/shades/*")
    assert components[paths.index("/shades/new")]["exclude"] is True


@pytest.mark.parametrize("make", [make_settings, oidc_settings])
def test_aasa_is_off_without_a_team_id(tmp_path, make):
    client = make_client(make(tmp_path))
    response = client.get(AASA)
    assert response.status_code == 404
    assert "location" not in response.headers


def test_team_id_must_look_like_one(tmp_path):
    for bad in ("rw5t9p5a59", "RW5T9P5A5", "RW5T9P5A59X", "RW5T 9P5A59"):
        with pytest.raises(ValidationError, match="Apple team ID"):
            make_settings(tmp_path, apple_team_id=bad)
    assert make_settings(tmp_path, apple_team_id=" RW5T9P5A59 ").apple_team_id == TEAM
    assert make_settings(tmp_path, apple_team_id="").apple_team_id == ""


def test_team_id_comes_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("POLISHED_APPLE_TEAM_ID", TEAM)
    assert make_settings(tmp_path).apple_team_id == TEAM


# --- /__test/reset -------------------------------------------------------------------------


def reset_api(tmp_path, api_template, **overrides):
    template, ids = api_template
    # The "template" for the reset is a second copy, so the live copy can be changed freely.
    spare = tmp_path / "reset-template.db"
    shutil.copy(template, spare)
    overrides.setdefault("test_reset_from", str(spare))
    return make_api(tmp_path, template, ids, **overrides)


def bottle_count(api) -> int:
    conn = api.conn()
    try:
        return conn.execute("select count(*) from bottle").fetchone()[0]
    finally:
        conn.close()


def test_reset_restores_the_template(tmp_path, api_template):
    api = reset_api(tmp_path, api_template)
    before = bottle_count(api)
    conn = api.conn()
    conn.execute("delete from bottle")
    conn.execute("insert into wheel (slug, name) values ('zzzzzz', 'Scratch')")
    conn.close()
    assert bottle_count(api) == 0
    response = api.client.post("/__test/reset", headers={"Authorization": ""})
    assert response.status_code == 200
    assert response.json() == {"reset": True}
    assert bottle_count(api) == before
    conn = api.conn()
    assert conn.execute("select count(*) from wheel where slug = 'zzzzzz'").fetchone()[0] == 0
    assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert conn.execute("pragma journal_mode").fetchone()[0] == "wal"
    conn.close()
    assert api.get("/api/v1/bottles").status_code == 200  # the app keeps serving


def test_reset_works_while_another_connection_is_open(tmp_path, api_template):
    api = reset_api(tmp_path, api_template)
    reader = api.conn()
    reader.execute("select count(*) from shade").fetchone()
    assert api.client.post("/__test/reset").status_code == 200
    assert reader.execute("select count(*) from bottle").fetchone()[0] == bottle_count(api)
    reader.close()


def test_reset_needs_no_token_and_no_origin(tmp_path, api_template):
    api = reset_api(tmp_path, api_template)
    bare = TestClient(api.client.app, client=LOOPBACK, base_url=api.settings.public_url)
    assert bare.post("/__test/reset").status_code == 200


def test_reset_refuses_a_web_page_that_names_an_origin(tmp_path, api_template):
    api = reset_api(tmp_path, api_template)
    response = api.client.post("/__test/reset", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["10.1.2.3", "192.168.0.7", "testclient", "::ffff:127.0.0.1"])
def test_reset_is_404_away_from_loopback(tmp_path, api_template, host):
    api = reset_api(tmp_path, api_template)
    client = TestClient(api.client.app, client=(host, 1234), base_url=api.settings.public_url)
    response = client.post("/__test/reset")
    assert response.status_code == 404
    assert bottle_count(api) > 0


def test_reset_is_404_when_no_template_is_configured(tmp_path, api_template):
    template, ids = api_template
    api = make_api(tmp_path, template, ids)
    for path in ("/__test/reset",):
        assert api.client.post(path).status_code == 404


def test_reset_cannot_be_configured_in_oidc_mode(tmp_path):
    with pytest.raises(ValidationError, match="TEST_RESET_FROM is only allowed"):
        oidc_settings(tmp_path, test_reset_from="/tmp/x.db")


def test_reset_with_a_missing_template_is_a_server_error_in_json(tmp_path, api_template):
    api = reset_api(tmp_path, api_template, test_reset_from=str(tmp_path / "nope.db"))
    response = api.client.post("/__test/reset")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "server_error"
    assert bottle_count(api) > 0


def test_reset_refuses_to_copy_the_live_database_onto_itself(tmp_path, api_template):
    template, ids = api_template
    api = make_api(tmp_path, template, ids, test_reset_from=str(tmp_path / "polished.db"))
    response = api.client.post("/__test/reset")
    assert response.status_code == 500
    assert "live database" in response.json()["error"]["message"]
    assert bottle_count(api) > 0


def test_reset_route_does_not_exist_unless_enabled(tmp_path):
    client = TestClient(create_app(make_settings(tmp_path)), client=LOOPBACK)
    assert client.post("/__test/reset").status_code == 404


# --- 008_api_tokens.sql --------------------------------------------------------------------


def migrations_below(tmp_path: Path, version: int) -> Path:
    directory = tmp_path / f"migrations-below-{version}"
    directory.mkdir()
    for path in MIGRATIONS.iterdir():
        if path.name.endswith(".sql") and int(path.name[:3]) < version:
            (directory / path.name).write_text(path.read_text())
    return directory


def test_008_adds_two_tables_and_leaves_the_data_alone(tmp_path):
    db = str(tmp_path / "live.db")
    assert migrate(db, migrations_below(tmp_path, 8))[-1] == "007_release_sheet.sql"
    conn = sqlite3.connect(db)
    conn.execute("insert into shade (title, search_text, kind) values ('Old', 'old', 'polish')")
    conn.execute("insert into bottle (shade_id, state) values (1, 'half')")
    conn.execute("insert into wheel (slug, name) values ('abcdef', 'Holos')")
    conn.commit()
    conn.close()

    below_9 = migrations_below(tmp_path, 9)
    assert migrate(db, below_9) == ["008_api_tokens.sql"]
    assert migrate(db, below_9) == []  # idempotent

    conn = sqlite3.connect(db)
    assert conn.execute("select max(version) from schema_version").fetchone()[0] == 8
    assert conn.execute("select state from bottle").fetchall() == [("half",)]
    assert conn.execute("select name from wheel").fetchall() == [("Holos",)]
    columns = {r[1] for r in conn.execute("pragma table_info(api_token)")}
    assert columns == {
        "id", "user_sub", "user_name", "device_name", "platform", "app_version", "token_hash",
        "created_at", "last_used_at", "revoked_at",
    }  # fmt: skip
    columns = {r[1] for r in conn.execute("pragma table_info(app_login_code)")}
    assert columns == {
        "code_hash", "user_sub", "user_name", "challenge", "device_name", "expires_at", "used_at",
    }  # fmt: skip
    assert conn.execute("pragma foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        for _ in range(2):
            conn.execute(
                "insert into api_token (user_sub, user_name, device_name, platform, token_hash)"
                " values ('u', 'U', 'd', 'ios', 'same')"
            )
    conn.close()


def test_009_adds_the_wear_log_and_leaves_the_data_alone(tmp_path):
    db = str(tmp_path / "live.db")
    assert migrate(db, migrations_below(tmp_path, 9))[-1] == "008_api_tokens.sql"
    conn = sqlite3.connect(db)
    conn.execute("insert into shade (title, search_text, kind) values ('Old', 'old', 'polish')")
    conn.execute("insert into bottle (shade_id, state) values (1, 'half')")
    conn.commit()
    conn.close()

    assert migrate(db) == ["009_wear.sql"]
    assert migrate(db) == []  # idempotent

    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("pragma foreign_keys = on")
    assert conn.execute("select max(version) from schema_version").fetchone()[0] == 9
    assert conn.execute("select state from bottle").fetchall() == [("half",)]
    columns = [r[1] for r in conn.execute("pragma table_info(wear)")]
    assert columns == ["id", "shade_id", "worn_on", "created_at"]
    conn.execute("insert into wear (shade_id, worn_on) values (1, '2026-10-26')")
    with pytest.raises(sqlite3.IntegrityError):  # one row per shade per day
        conn.execute("insert into wear (shade_id, worn_on) values (1, '2026-10-26')")
    conn.execute("insert into wear (shade_id, worn_on) values (1, '2026-10-27')")
    with pytest.raises(sqlite3.IntegrityError):  # a shade that exists
        conn.execute("insert into wear (shade_id, worn_on) values (99, '2026-10-26')")
    with pytest.raises(sqlite3.IntegrityError):  # a date
        conn.execute("insert into wear (shade_id, worn_on) values (1, 'today')")
    conn.close()


@pytest.mark.skipif(not REAL_DEV_DB.exists(), reason="no local dev database to copy")
def test_008_applies_to_a_copy_of_a_realistic_database(tmp_path):
    copy = tmp_path / "dev-copy.db"
    source = sqlite3.connect(f"file:{REAL_DEV_DB}?mode=ro", uri=True)
    destination = sqlite3.connect(copy)
    source.backup(
        destination
    )  # a consistent copy, even with a live -wal; the original is untouched
    destination.close()
    source.close()

    def counts(path) -> dict:
        conn = sqlite3.connect(path)
        try:
            return {
                t: conn.execute(f"select count(*) from {t}").fetchone()[0]
                for t in ("shade", "bottle", "wheel", "wishlist_item", "stack_layer")
            }
        finally:
            conn.close()

    before = counts(copy)
    applied = migrate(str(copy))
    assert "008_api_tokens.sql" in applied
    assert counts(copy) == before
    conn = sqlite3.connect(copy)
    assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert conn.execute("select count(*) from api_token").fetchone()[0] == 0
    conn.close()
