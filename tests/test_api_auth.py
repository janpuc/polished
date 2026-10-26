"""The Bearer gate, the app's PKCE sign-in and the device list (docs/NATIVE.md 2.4 and 3)."""

import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import make_client, make_settings, oidc_settings, session_cookie
from starlette.testclient import TestClient
from test_api_support import DEV_TOKEN, LOOPBACK, make_api

from polished import auth as web_auth
from polished.api import auth as tokens
from polished.server import create_app

pytest_plugins = ["test_api_support"]

VERIFIER = "v" * 43
CHALLENGE = tokens.challenge_for(VERIFIER)


def mint(api, verifier=VERIFIER, sub="u1", name="Rae Example", device="Rae's iPhone"):
    conn = api.conn()
    try:
        return tokens.mint_login_code(conn, sub, name, tokens.challenge_for(verifier), device)
    finally:
        conn.close()


def exchange(api, code, verifier=VERIFIER, device_name="Rae's iPhone", **extra):
    body = {
        "code": code,
        "verifier": verifier,
        "device_name": device_name,
        "platform": "ios",
        "app_version": "1.0.0",
    } | extra
    return api.client.post("/api/v1/auth/exchange", json=body, headers={"Authorization": ""})


def sign_in(api, **kwargs) -> str:
    response = exchange(api, mint(api, **kwargs), device_name=kwargs.get("device", "Rae's iPhone"))
    assert response.status_code == 200, response.text
    return response.json()["token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- the gate ------------------------------------------------------------------------------


def test_challenge_is_base64url_sha256_without_padding():
    digest = hashlib.sha256(b"abc").digest()
    assert tokens.challenge_for("abc") == base64.urlsafe_b64encode(digest).decode().rstrip("=")
    assert tokens.CHALLENGE.fullmatch(CHALLENGE)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer nope"},
        {"Authorization": "Basic Zm9vOmJhcg=="},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
    ],
)
def test_missing_or_unknown_token_is_a_401_in_json(bare_client, headers):
    response = bare_client.get("/api/v1/home", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-polished-api"] == "1"
    assert "location" not in response.headers


def test_unauthorized_never_redirects_in_oidc_mode(tmp_path):
    client = make_client(oidc_settings(tmp_path))
    for method, path in (
        ("GET", "/api/v1/home"),
        ("POST", "/api/v1/auth/revoke"),
        ("GET", "/api/v1/nothing"),
    ):
        response = client.request(method, path)
        assert response.status_code == 401, (method, path)
        assert response.json() == {"error": {"code": "unauthorized", "message": "Sign in again."}}


def test_a_web_session_cookie_is_ignored_under_api(tmp_path):
    settings = oidc_settings(tmp_path)
    client = make_client(settings)
    client.cookies.set(
        web_auth.SESSION_COOKIE,
        session_cookie(settings, {"sub": "u1", "name": "Rae", "iat": 9e12, "seen": 9e12}),
        domain="polished.example.test",
    )
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/me").status_code == 401


def test_auth_mode_none_does_not_open_the_api(tmp_path):
    client = make_client(make_settings(tmp_path))
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/me").status_code == 401


def test_every_answer_has_the_api_header_and_errors_have_the_error_shape(api):
    for path, status, code in (
        ("/api/v1/me", 200, None),
        ("/api/v1/shades/999999", 404, "not_found"),
        ("/api/v1/nothing-here", 404, "not_found"),
        ("/api/v1/shades?page=x", 422, "validation"),
    ):
        response = api.get(path)
        assert response.status_code == status, path
        assert response.headers["x-polished-api"] == "1"
        if code:
            assert response.json()["error"]["code"] == code
    assert "x-polished-api" not in api.get("/healthz").headers


def test_validation_error_names_the_field(api):
    error = api.get("/api/v1/shades?page=x").json()["error"]
    assert error["field"] == "page"
    assert error["message"]


def test_a_post_without_a_token_is_a_401_not_an_origin_403(bare_client):
    response = bare_client.post("/api/v1/auth/revoke")
    assert response.status_code == 401


def test_web_posts_still_need_an_origin(api, bare_client):
    assert bare_client.post("/bottles/1/delete").status_code == 403


# --- the browser half ----------------------------------------------------------------------


def test_app_start_keeps_the_challenge_and_goes_to_login(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    response = client.get(
        "/auth/app/start", params={"challenge": CHALLENGE, "device": " Rae's  iPhone "}
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login?next=%2Fauth%2Fapp%2Ffinish"


@pytest.mark.parametrize("challenge", ["", "short", "!" * 43, "a" * 44])
def test_app_start_refuses_a_bad_challenge(tmp_path, challenge):
    client = make_client(make_settings(tmp_path))
    response = client.get("/auth/app/start", params={"challenge": challenge})
    assert response.status_code == 400


def test_app_finish_without_start_is_refused(tmp_path):
    client = make_client(make_settings(tmp_path))
    assert client.get("/auth/app/finish").status_code == 400


def test_app_sign_in_end_to_end_in_none_mode(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    start = client.get("/auth/app/start", params={"challenge": CHALLENGE, "device": "Rae's iPhone"})
    assert client.get(start.headers["location"]).headers["location"] == "/auth/app/finish"
    finish = client.get("/auth/app/finish")
    assert finish.status_code == 302
    assert finish.headers["cache-control"] == "no-store"
    location = urlsplit(finish.headers["location"])
    assert (location.scheme, location.netloc, location.path) == ("polished", "auth", "")
    code = parse_qs(location.query)["code"][0]
    # The code is used by the app, once.
    exchanged = client.post(
        "/api/v1/auth/exchange", json={"code": code, "verifier": VERIFIER, "platform": "ios"}
    )
    assert exchanged.status_code == 200
    body = exchanged.json()
    assert body["user"] == {"sub": "dev", "name": "Dev"}
    me = client.get("/api/v1/me", headers=bearer(body["token"]))
    assert me.status_code == 200
    assert client.get("/auth/app/finish").status_code == 400  # app_login was used up


def test_app_login_survives_the_oidc_callback(tmp_path, monkeypatch):
    """The callback rewrites the whole session; the challenge must come out the other side."""
    from test_auth import FakeOidc

    settings = oidc_settings(tmp_path)
    client = make_client(settings)
    client.get("/auth/app/start", params={"challenge": CHALLENGE, "device": "Rae's iPhone"})
    client.app.state.oidc = FakeOidc(
        token_claims={"sub": "u1", "name": "Rae", "groups": ["ID-Users"]}
    )
    callback = client.get("/auth/callback", params={"code": "c", "state": "s"})
    assert callback.status_code == 302
    finish = client.get("/auth/app/finish")
    assert finish.status_code == 302
    assert finish.headers["location"].startswith("polished://auth?code=")


def test_app_finish_needs_a_session_in_oidc_mode(tmp_path):
    client = make_client(oidc_settings(tmp_path))
    response = client.get("/auth/app/finish")
    assert response.status_code == 302
    assert response.headers["location"].startswith("/auth/login")


# --- exchange ------------------------------------------------------------------------------


def test_exchange_happy_path(api):
    code = mint(api)
    response = exchange(api, code)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "token_id", "user"}
    assert body["user"] == {"sub": "u1", "name": "Rae Example"}
    assert (
        api.get("/api/v1/me", headers=bearer(body["token"])).json()["user"]["first_name"] == "Rae"
    )
    # Only the hashes are stored.
    conn = api.conn()
    stored = conn.execute(
        "select token_hash, device_name, platform, app_version from api_token"
    ).fetchone()
    assert stored["token_hash"] == hashlib.sha256(body["token"].encode()).hexdigest()
    assert (stored["device_name"], stored["platform"], stored["app_version"]) == (
        "Rae's iPhone",
        "ios",
        "1.0.0",
    )
    assert (
        conn.execute("select code_hash from app_login_code").fetchone()[0]
        == hashlib.sha256(code.encode()).hexdigest()
    )
    conn.close()


def test_exchange_works_without_an_origin_or_a_token(api, bare_client):
    response = bare_client.post(
        "/api/v1/auth/exchange", json={"code": mint(api), "verifier": VERIFIER}
    )
    assert response.status_code == 200


def test_exchange_with_the_wrong_verifier_is_bad_code_and_burns_the_code(api):
    code = mint(api)
    bad = exchange(api, code, verifier="w" * 43)
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "bad_code"
    assert exchange(api, code).status_code == 400  # even the right verifier is too late now


def test_exchange_code_is_single_use(api):
    code = mint(api)
    assert exchange(api, code).status_code == 200
    again = exchange(api, code)
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "bad_code"


def test_exchange_code_expires_after_60_seconds(api):
    conn = api.conn()
    now = tokens.now()
    stale = tokens.mint_login_code(
        conn, "u1", "Rae", CHALLENGE, "iPhone", at=now - timedelta(seconds=61)
    )
    fresh = tokens.mint_login_code(
        conn, "u1", "Rae", CHALLENGE, "iPhone", at=now - timedelta(seconds=50)
    )
    conn.close()
    assert exchange(api, stale).json()["error"]["code"] == "bad_code"
    assert exchange(api, fresh).status_code == 200


def test_exchange_unknown_code(api):
    assert exchange(api, "never-minted").status_code == 400


def test_exchange_body_is_validated(api):
    response = api.client.post("/api/v1/auth/exchange", json={"verifier": VERIFIER})
    assert response.status_code == 422
    assert response.json()["error"]["field"] == "code"


def test_each_code_binds_its_own_challenge_and_user(api):
    a, b = mint(api, "a" * 43, sub="ua", name="Ann"), mint(api, "b" * 43, sub="ub", name="Bo")
    assert exchange(api, a, verifier="b" * 43).status_code == 400
    assert exchange(api, b, verifier="b" * 43).json()["user"] == {"sub": "ub", "name": "Bo"}


def test_old_login_codes_are_dropped_when_a_new_one_is_made(api):
    conn = api.conn()
    now = tokens.now()
    tokens.mint_login_code(conn, "u1", "Rae", CHALLENGE, "iPhone", at=now - timedelta(days=3))
    tokens.mint_login_code(conn, "u1", "Rae", CHALLENGE, "iPhone", at=now)
    assert conn.execute("select count(*) from app_login_code").fetchone()[0] == 1
    conn.close()


# --- revoke and devices --------------------------------------------------------------------


def test_revoke_signs_the_calling_device_out(api):
    token = sign_in(api)
    assert api.get("/api/v1/me", headers=bearer(token)).status_code == 200
    assert api.client.post("/api/v1/auth/revoke", headers=bearer(token)).status_code == 204
    after = api.get("/api/v1/me", headers=bearer(token))
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "unauthorized"
    conn = api.conn()
    assert conn.execute("select revoked_at from api_token").fetchone()[0] is not None
    conn.close()


def test_devices_lists_your_live_tokens_and_marks_the_current_one(api):
    phone, ipad = sign_in(api, device="Rae's iPhone"), sign_in(api, device="Rae's iPad")
    sign_in(api, sub="someone-else", device="Not yours")
    items = api.get("/api/v1/auth/devices", headers=bearer(phone)).json()["items"]
    assert [(d["device_name"], d["current"]) for d in items] == [
        ("Rae's iPad", False),
        ("Rae's iPhone", True),
    ]
    assert set(items[0]) == {
        "id",
        "device_name",
        "platform",
        "created_at",
        "last_used_at",
        "current",
    }
    items = api.get("/api/v1/auth/devices", headers=bearer(ipad)).json()["items"]
    assert [d["current"] for d in items] == [True, False]


def test_delete_device_revokes_that_device_only(api):
    phone, ipad = sign_in(api, device="phone"), sign_in(api, device="ipad")
    devices = api.get("/api/v1/auth/devices", headers=bearer(phone)).json()["items"]
    ipad_id = next(d["id"] for d in devices if d["device_name"] == "ipad")
    assert (
        api.client.delete(f"/api/v1/auth/devices/{ipad_id}", headers=bearer(phone)).status_code
        == 204
    )
    assert api.get("/api/v1/me", headers=bearer(ipad)).status_code == 401
    assert api.get("/api/v1/me", headers=bearer(phone)).status_code == 200
    again = api.client.delete(f"/api/v1/auth/devices/{ipad_id}", headers=bearer(phone))
    assert again.status_code == 404
    assert again.json()["error"]["code"] == "not_found"


def test_a_device_of_another_user_cannot_be_deleted(api):
    mine = sign_in(api, sub="u1")
    other = sign_in(api, sub="u2", device="other")
    other_id = api.get("/api/v1/auth/devices", headers=bearer(other)).json()["items"][0]["id"]
    assert (
        api.client.delete(f"/api/v1/auth/devices/{other_id}", headers=bearer(mine)).status_code
        == 404
    )
    assert api.get("/api/v1/me", headers=bearer(other)).status_code == 200


def test_last_used_moves_at_most_once_a_minute(api):
    token = sign_in(api)
    conn = api.conn()

    def last_used():
        return conn.execute("select last_used_at from api_token").fetchone()[0]

    now = tokens.now()
    assert last_used() is None
    tokens.authenticate(conn, token, at=now)
    first = last_used()
    assert first is not None
    tokens.authenticate(conn, token, at=now + timedelta(seconds=30))
    assert last_used() == first
    tokens.authenticate(conn, token, at=now + timedelta(seconds=61))
    assert last_used() > first
    conn.close()


def test_token_is_stored_hashed_and_unknown_tokens_do_not_match(api):
    token = sign_in(api)
    conn = api.conn()
    assert (
        conn.execute("select count(*) from api_token where token_hash = ?", (token,)).fetchone()[0]
        == 0
    )
    assert tokens.authenticate(conn, token + "x") is None
    conn.close()


# --- the development token -----------------------------------------------------------------


def test_dev_token_works_in_none_mode_when_set(api):
    me = api.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user"] == {"sub": "dev", "name": "Dev", "first_name": "Dev"}
    assert api.get("/api/v1/me", headers=bearer(DEV_TOKEN + "x")).status_code == 401


def test_dev_token_is_off_when_unset(tmp_path, api_template):
    template, ids = api_template
    off = make_api(tmp_path, template, ids)
    off.settings.dev_token = None
    assert off.get("/api/v1/me", headers=bearer(DEV_TOKEN)).status_code == 401


def test_dev_token_cannot_be_configured_in_oidc_mode(tmp_path):
    with pytest.raises(ValueError, match="DEV_TOKEN is only allowed with POLISHED_AUTH_MODE=none"):
        oidc_settings(tmp_path, dev_token="x")


def test_dev_token_is_ignored_by_the_gate_outside_none_mode(tmp_path):
    """Belt and braces: even if a Settings object were built around the validator."""
    settings = oidc_settings(tmp_path)
    object.__setattr__(settings, "dev_token", type(settings.session_secret)("dev-token"))
    client = TestClient(
        create_app(settings),
        base_url=settings.public_url,
        headers=bearer("dev-token"),
        client=LOOPBACK,
    )
    from polished.migrate import migrate

    migrate(settings.db_path)
    assert client.get("/api/v1/me").status_code == 401


def test_dev_token_user_has_no_token_to_revoke(api):
    assert api.client.post("/api/v1/auth/revoke").status_code == 204
    assert api.get("/api/v1/me").status_code == 200
