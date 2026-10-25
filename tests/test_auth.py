import html
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from authlib.integrations.base_client import OAuthError
from conftest import OIDC_URL, make_client, oidc_settings, read_session, session_cookie
from joserfc import jwt
from joserfc.jwk import RSAKey

from polished.auth import SESSION_COOKIE, login_url, safe_next

DAY = 86400


class FakeOidc:
    """Stands in for the authlib client in the callback: no network."""

    def __init__(self, userinfo=None, token_claims=None, error=None):
        self.token_claims = token_claims if token_claims is not None else {}
        self.userinfo_claims = userinfo or {}
        self.error = error
        self.userinfo_calls = 0

    async def authorize_access_token(self, request):
        if self.error:
            raise self.error
        return {"access_token": "t", "userinfo": {"aud": "client-id"} | self.token_claims}

    async def userinfo(self, token):
        self.userinfo_calls += 1
        return self.userinfo_claims


def signed_in(settings, client, **session):
    now = time.time()
    data = {"sub": "u1", "name": "Rae", "iat": now, "seen": now} | session
    client.cookies.set(
        SESSION_COOKIE, session_cookie(settings, data), domain="polished.example.test"
    )
    return client


def current_session(settings, response_or_client):
    cookie = (
        response_or_client.cookies.get(SESSION_COOKIE)
        if hasattr(response_or_client, "cookies")
        else None
    )
    return read_session(settings, cookie) if cookie else {}


# --- deny by default -------------------------------------------------------------------


def test_signed_out_get_redirects_to_login_with_next(oidc_client):
    response = oidc_client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login?next=%2F"


def test_signed_out_get_keeps_path_and_query_in_next(oidc_client):
    response = oidc_client.get("/shades?q=a b&finish=holo")
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/auth/login?next=")
    assert parse_qs(urlsplit(location).query)["next"] == ["/shades?q=a%20b&finish=holo"]


def test_signed_out_htmx_request_gets_401_with_hx_redirect(oidc_client):
    response = oidc_client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 401
    assert response.headers["hx-redirect"] == "/auth/login?next=%2F"
    assert "location" not in response.headers


def test_htmx_hx_redirect_returns_to_the_page_the_request_came_from(oidc_client):
    response = oidc_client.get(
        "/search?q=a",
        headers={"HX-Request": "true", "HX-Current-URL": f"{OIDC_URL}/shades?finish=holo"},
    )
    assert response.status_code == 401
    assert response.headers["hx-redirect"] == login_url("/shades?finish=holo")


def test_htmx_current_url_on_another_host_is_ignored(oidc_client):
    response = oidc_client.get(
        "/search", headers={"HX-Request": "true", "HX-Current-URL": "https://evil.example/x"}
    )
    assert response.headers["hx-redirect"] == login_url("/search")


def test_signed_out_post_gets_plain_401_never_a_redirect(oidc_client):
    response = oidc_client.post("/anything")
    assert response.status_code == 401
    assert "location" not in response.headers
    assert "hx-redirect" not in response.headers


def test_unknown_paths_answer_like_known_ones(oidc_client):
    known = oidc_client.get("/")
    for path in ("/nope", "/w/abc123", "/wheels/1"):
        response = oidc_client.get(path)
        assert response.status_code == known.status_code == 302
        assert response.headers["location"] == login_url(path)


@pytest.mark.parametrize("path", ["/healthz", "/static/css/app.css", "/auth/signed-out"])
def test_public_paths_are_open_when_signed_out(oidc_client, path):
    assert oidc_client.get(path).status_code == 200


def test_public_list_does_not_include_lookalikes(oidc_client):
    for path in ("/healthz/x", "/staticfoo", "/auth/other", "/offlines"):
        assert oidc_client.get(path).status_code == 302


def test_auth_none_lets_the_dev_user_in(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Dev" in response.text


def test_a_valid_session_passes_the_gate(oidc_app_settings, oidc_client):
    signed_in(oidc_app_settings, oidc_client)
    response = oidc_client.get("/")
    assert response.status_code == 200
    assert "Rae" in response.text


def test_a_session_cookie_with_a_bad_signature_is_ignored(oidc_client):
    oidc_client.cookies.set(SESSION_COOKIE, "garbage.value.here", domain="polished.example.test")
    assert oidc_client.get("/").status_code == 302


def test_session_cookie_attributes(oidc_app_settings, oidc_client):
    signed_in(oidc_app_settings, oidc_client, seen=time.time() - 2 * DAY)
    cookie = oidc_client.get("/").headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert f"max-age={30 * DAY}" in cookie


# --- next -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "evil",
        "//evil.example",
        "///evil.example",
        "https://evil.example/x",
        "http:evil",
        "/\\evil.example",
        "/ok\r\nSet-Cookie: x=y",
        "javascript:alert(1)",
    ],
)
def test_next_is_rejected_unless_it_starts_with_a_single_slash(value):
    assert safe_next(value) == "/"


@pytest.mark.parametrize("value", ["/", "/shades", "/shades?q=a&b=c", "/w/k3m9xq", "/a/b#c"])
def test_next_is_kept_when_it_is_a_local_path(value):
    assert safe_next(value) == value


def test_login_in_auth_none_mode_goes_straight_to_next(client):
    assert client.get("/auth/login?next=/shades").headers["location"] == "/shades"
    assert client.get("/auth/login?next=//evil.example").headers["location"] == "/"


METADATA = {
    "_loaded_at": 1,
    "issuer": "https://id.example.test",
    "authorization_endpoint": "https://id.example.test/authorize",
    "token_endpoint": "https://id.example.test/api/oidc/token",
    "jwks_uri": "https://id.example.test/.well-known/jwks.json",
    "userinfo_endpoint": "https://id.example.test/api/oidc/userinfo",
}


def test_login_redirects_to_the_issuer_with_pkce_state_and_nonce(oidc_app_settings, oidc_client):
    oidc_client.app.state.oidc.server_metadata = dict(METADATA)
    response = oidc_client.get("/auth/login?next=/w/k3m9xq")
    assert response.status_code == 302
    url = urlsplit(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == METADATA["authorization_endpoint"]
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert query["response_type"] == "code"
    assert query["client_id"] == "client-id"
    assert query["redirect_uri"] == f"{OIDC_URL}/auth/callback"
    assert query["scope"] == "openid profile email groups"
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"] and query["state"] and query["nonce"]
    assert current_session(oidc_app_settings, oidc_client)["login_next"] == "/w/k3m9xq"


def test_login_stores_only_a_safe_next(oidc_app_settings, oidc_client):
    oidc_client.app.state.oidc.server_metadata = dict(METADATA)
    oidc_client.get("/auth/login?next=//evil.example")
    assert current_session(oidc_app_settings, oidc_client)["login_next"] == "/"


def test_the_app_starts_in_oidc_mode_without_reaching_the_issuer(oidc_client):
    """Discovery is lazy: building the app made no request (the test network guard is on)."""
    assert oidc_client.get("/healthz").status_code == 200
    assert not oidc_client.app.state.oidc.server_metadata.get("_loaded_at")


# --- callback: groups -----------------------------------------------------------------


def callback(settings, client, oidc, *, next_path="/w/k3m9xq"):
    client.app.state.oidc = oidc
    client.cookies.set(
        SESSION_COOKIE,
        session_cookie(settings, {"login_next": next_path}),
        domain="polished.example.test",
    )
    return client.get("/auth/callback?code=c&state=s")


@pytest.mark.parametrize("group", ["ID-Users", "ID-Admin"])
def test_an_allowed_group_signs_in_and_returns_to_next(oidc_app_settings, oidc_client, group):
    oidc = FakeOidc(token_claims={"sub": "u1", "name": "Rae", "groups": ["x", group]})
    response = callback(oidc_app_settings, oidc_client, oidc)
    assert response.status_code == 302
    assert response.headers["location"] == "/w/k3m9xq"
    session = current_session(oidc_app_settings, oidc_client)
    assert session["sub"] == "u1" and session["name"] == "Rae"
    assert abs(session["iat"] - time.time()) < 5 and session["seen"] == session["iat"]
    assert "login_next" not in session
    assert oidc.userinfo_calls == 0
    assert oidc_client.get("/").status_code == 200


def test_a_group_outside_the_allowed_list_is_403_and_creates_no_session(
    oidc_app_settings, oidc_client
):
    oidc = FakeOidc(token_claims={"sub": "u2", "name": "Sam", "groups": ["Other", "id-users"]})
    response = callback(oidc_app_settings, oidc_client, oidc)
    assert response.status_code == 403
    assert "isn't allowed here" in html.unescape(response.text)
    assert "sub" not in current_session(oidc_app_settings, oidc_client)
    assert oidc_client.get("/").status_code == 302


def test_no_groups_at_all_is_403(oidc_app_settings, oidc_client):
    oidc = FakeOidc(token_claims={"sub": "u2"}, userinfo={"sub": "u2"})
    assert callback(oidc_app_settings, oidc_client, oidc).status_code == 403
    assert "sub" not in current_session(oidc_app_settings, oidc_client)


def test_groups_missing_from_the_id_token_are_read_from_userinfo(oidc_app_settings, oidc_client):
    oidc = FakeOidc(
        token_claims={"sub": "u1", "name": "Rae"}, userinfo={"sub": "u1", "groups": ["ID-Admin"]}
    )
    response = callback(oidc_app_settings, oidc_client, oidc)
    assert response.status_code == 302
    assert oidc.userinfo_calls == 1


def test_allowed_groups_come_from_settings(tmp_path):
    settings = oidc_settings(tmp_path, oidc_allowed_groups="Polish")
    client = make_client(settings)
    ok = callback(settings, client, FakeOidc(token_claims={"sub": "u", "groups": ["Polish"]}))
    assert ok.status_code == 302
    client = make_client(settings)
    denied = callback(settings, client, FakeOidc(token_claims={"sub": "u", "groups": ["ID-Users"]}))
    assert denied.status_code == 403


def test_a_failed_token_exchange_is_a_400_page_without_a_session(oidc_app_settings, oidc_client):
    oidc = FakeOidc(error=OAuthError(error="mismatching_state"))
    response = callback(oidc_app_settings, oidc_client, oidc)
    assert response.status_code == 400
    assert "sub" not in current_session(oidc_app_settings, oidc_client)


def test_a_callback_next_that_is_not_local_falls_back_to_home(oidc_app_settings, oidc_client):
    oidc = FakeOidc(token_claims={"sub": "u1", "groups": ["ID-Users"]})
    response = callback(oidc_app_settings, oidc_client, oidc, next_path="//evil.example")
    assert response.headers["location"] == "/"


# --- logout ---------------------------------------------------------------------------


def test_logout_clears_the_session_and_lands_on_the_signed_out_page(oidc_app_settings, oidc_client):
    signed_in(oidc_app_settings, oidc_client)
    response = oidc_client.post("/auth/logout")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/signed-out"
    assert oidc_client.get("/").status_code == 302
    page = oidc_client.get("/auth/signed-out")
    assert "Sign in again" in page.text and 'href="/auth/login"' in page.text


def test_logout_needs_the_origin_header(oidc_client):
    assert oidc_client.post("/auth/logout", headers={"Origin": ""}).status_code == 403


# --- rolling seen and the absolute cap ---------------------------------------------------


def test_seen_older_than_a_day_is_rewritten(oidc_app_settings, oidc_client):
    old = time.time() - 2 * DAY
    signed_in(oidc_app_settings, oidc_client, seen=old)
    response = oidc_client.get("/")
    assert response.status_code == 200
    session = read_session(oidc_app_settings, oidc_client.cookies.get(SESSION_COOKIE))
    assert session["seen"] > old + DAY
    assert abs(session["seen"] - time.time()) < 5


def test_seen_within_a_day_is_left_alone(oidc_app_settings, oidc_client):
    recent = int(time.time() - DAY / 2)
    signed_in(oidc_app_settings, oidc_client, seen=recent)
    oidc_client.get("/")
    session = read_session(oidc_app_settings, oidc_client.cookies.get(SESSION_COOKIE))
    assert session["seen"] == recent


def test_iat_older_than_the_absolute_cap_forces_a_new_login(oidc_app_settings, oidc_client):
    signed_in(oidc_app_settings, oidc_client, iat=time.time() - 91 * DAY)
    response = oidc_client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login?next=%2F"
    assert oidc_client.cookies.get(SESSION_COOKIE) is None  # the stale cookie was cleared


def test_iat_inside_the_cap_stays_signed_in(oidc_app_settings, oidc_client):
    signed_in(oidc_app_settings, oidc_client, iat=time.time() - 89 * DAY)
    assert oidc_client.get("/").status_code == 200


def test_the_cap_follows_session_max_days(tmp_path):
    settings = oidc_settings(tmp_path, session_days=7, session_max_days=10)
    client = make_client(settings)
    signed_in(settings, client, iat=time.time() - 11 * DAY)
    assert client.get("/").status_code == 302


def test_a_session_without_iat_is_not_trusted(oidc_app_settings, oidc_client):
    oidc_client.cookies.set(
        SESSION_COOKIE,
        session_cookie(oidc_app_settings, {"sub": "u1", "seen": time.time()}),
        domain="polished.example.test",
    )
    assert oidc_client.get("/").status_code == 302


# --- callback: real ID tokens ---------------------------------------------------------------

ISSUER = METADATA["issuer"]
SIGNING_KEY = RSAKey.generate_key(2048, {"kid": "k1", "use": "sig"}, auto_kid=False)
OTHER_KEY = RSAKey.generate_key(2048, {"kid": "k1", "use": "sig"}, auto_kid=False)


class IdentityProvider:
    """Token and userinfo endpoints behind an httpx.MockTransport; ID tokens are really signed."""

    def __init__(self):
        self.userinfo = {"sub": "u1", "groups": ["ID-Users"]}
        self.id_token_claims = {}
        self.key = SIGNING_KEY
        self.nonce = None
        self.send_id_token = True
        self.userinfo_calls = 0

    def id_token(self):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "u1",
            "aud": "client-id",
            "iat": now,
            "exp": now + 600,
            "nonce": self.nonce,
            "name": "Rae",
            "groups": ["ID-Users"],
        } | self.id_token_claims
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode({"alg": "RS256", "kid": "k1"}, claims, self.key)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            body = {"access_token": "at", "token_type": "Bearer", "expires_in": 600}
            if self.send_id_token:
                body["id_token"] = self.id_token()
            return httpx.Response(200, json=body)
        if request.url.path.endswith("/userinfo"):
            self.userinfo_calls += 1
            return httpx.Response(200, json=self.userinfo)
        return httpx.Response(404)


def real_callback(settings, client, idp, *, nonce_override=None):
    """Log in (which stores state and nonce in the session), then return from the issuer."""
    oidc = client.app.state.oidc
    oidc.server_metadata = dict(METADATA) | {"jwks": {"keys": [SIGNING_KEY.as_dict(private=False)]}}
    oidc.client_kwargs["transport"] = httpx.MockTransport(idp.handle)
    query = parse_qs(urlsplit(client.get("/auth/login?next=/w/k3m9xq").headers["location"]).query)
    idp.nonce = nonce_override or query["nonce"][0]
    return client.get(f"/auth/callback?code=c&state={query['state'][0]}")


def assert_refused(response, settings, client):
    assert response.status_code == 400
    assert "Sign-in failed" in html.unescape(response.text)
    session = current_session(settings, client)
    assert "sub" not in session and "login_next" not in session


def test_a_validly_signed_id_token_signs_in(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    response = real_callback(oidc_app_settings, oidc_client, idp)
    assert response.status_code == 302
    assert response.headers["location"] == "/w/k3m9xq"
    assert current_session(oidc_app_settings, oidc_client)["sub"] == "u1"
    assert idp.userinfo_calls == 0


def test_an_audience_for_another_client_is_refused_even_with_our_azp(
    oidc_app_settings, oidc_client
):
    idp = IdentityProvider()
    idp.id_token_claims = {"aud": "other-client", "azp": "client-id"}
    assert_refused(
        real_callback(oidc_app_settings, oidc_client, idp), oidc_app_settings, oidc_client
    )


def test_an_audience_list_containing_our_client_is_accepted(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.id_token_claims = {"aud": ["other-client", "client-id"], "azp": "client-id"}
    assert real_callback(oidc_app_settings, oidc_client, idp).status_code == 302


def test_a_token_response_without_an_id_token_is_refused(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.send_id_token = False
    response = real_callback(oidc_app_settings, oidc_client, idp)
    assert_refused(response, oidc_app_settings, oidc_client)
    assert idp.userinfo_calls == 0


def test_userinfo_with_a_different_sub_is_refused(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.id_token_claims = {"groups": None}
    idp.userinfo = {"sub": "someone-else", "groups": ["ID-Admin"]}
    response = real_callback(oidc_app_settings, oidc_client, idp)
    assert_refused(response, oidc_app_settings, oidc_client)
    assert idp.userinfo_calls == 1


def test_userinfo_without_a_sub_is_refused(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.id_token_claims = {"groups": None}
    idp.userinfo = {"groups": ["ID-Admin"]}
    assert_refused(
        real_callback(oidc_app_settings, oidc_client, idp), oidc_app_settings, oidc_client
    )


def test_groups_come_from_userinfo_when_the_sub_matches(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.id_token_claims = {"groups": None}
    idp.userinfo = {"sub": "u1", "groups": ["ID-Admin"], "name": "Not Rae"}
    response = real_callback(oidc_app_settings, oidc_client, idp)
    assert response.status_code == 302
    session = current_session(oidc_app_settings, oidc_client)
    assert session["sub"] == "u1" and session["name"] == "Rae"
    assert idp.userinfo_calls == 1


def test_an_expired_id_token_is_a_400_not_a_500(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    past = int(time.time()) - 7200
    idp.id_token_claims = {"iat": past - 600, "exp": past}
    assert_refused(
        real_callback(oidc_app_settings, oidc_client, idp), oidc_app_settings, oidc_client
    )


def test_an_id_token_with_a_bad_signature_is_a_400_not_a_500(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.key = OTHER_KEY
    assert_refused(
        real_callback(oidc_app_settings, oidc_client, idp), oidc_app_settings, oidc_client
    )


def test_an_id_token_with_the_wrong_nonce_is_a_400_not_a_500(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    response = real_callback(oidc_app_settings, oidc_client, idp, nonce_override="not-ours")
    assert_refused(response, oidc_app_settings, oidc_client)


def test_an_id_token_from_another_issuer_is_a_400(oidc_app_settings, oidc_client):
    idp = IdentityProvider()
    idp.id_token_claims = {"iss": "https://evil.example"}
    assert_refused(
        real_callback(oidc_app_settings, oidc_client, idp), oidc_app_settings, oidc_client
    )
