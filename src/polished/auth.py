"""Pocket ID sign-in with authlib, the session, and the deny-by-default gate (DESIGN 8)."""

import asyncio
import hmac
import logging
import time
from urllib.parse import quote, urlsplit

import httpx
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from joserfc.errors import JoseError
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .api import auth as api_tokens
from .config import Settings
from .db import connect
from .security import is_api_path
from .web import render

log = logging.getLogger("polished.auth")

SESSION_COOKIE = "polished_session"
SEEN_REFRESH_S = 86400
SCOPE = "openid profile email groups"
DEV_USER = {"sub": "dev", "name": "Dev"}
PUBLIC_PATHS = frozenset(
    {
        "/healthz",
        "/manifest.webmanifest",
        "/sw.js",
        "/offline",
        "/auth/login",
        "/auth/callback",
        "/auth/logout",
        "/auth/signed-out",
        "/auth/app/start",
        # The app's universal links fetch this unsigned; the route exists only when
        # POLISHED_APPLE_TEAM_ID is set, and the reset only in AUTH_MODE=none (both 404 otherwise).
        "/.well-known/apple-app-site-association",
        "/__test/reset",
    }
)
# /api/v1 takes a Bearer token and nothing else; the exchange is how the app gets its first one.
API_PUBLIC_PATHS = frozenset({"/api/v1/auth/exchange"})
APP_LOGIN_MAX_AGE_S = 600
APP_FINISH_PATH = "/auth/app/finish"
APP_CALLBACK = "polished://auth"
PUBLIC_PREFIXES = ("/static/",)

router = APIRouter(prefix="/auth")


def safe_next(value: str | None) -> str:
    """The post-login target: a local path starting with a single "/", else "/"."""
    if (
        not value
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return "/"
    return value


def login_url(next_path: str) -> str:
    return f"/auth/login?next={quote(next_path, safe='')}"


def build_oidc_client(settings: Settings):
    """The Pocket ID client. Registering does not contact the issuer: authlib reads the
    discovery document at the first login."""
    oauth = OAuth()
    oauth.register(
        name="pocketid",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        server_metadata_url=f"{settings.oidc_issuer}/.well-known/openid-configuration",
        client_kwargs={"scope": SCOPE, "code_challenge_method": "S256"},
    )
    return oauth.pocketid


def bearer_token(request: StarletteRequest) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


def unauthorized_json() -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "unauthorized", "message": "Sign in again."}},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthGateMiddleware:
    """Deny by default. Everything outside PUBLIC_PATHS needs a valid session, or the dev user
    in AUTH_MODE=none. Sits inside SessionMiddleware. /api/v1 is the exception: there the cookie
    is ignored, a Bearer token (or, in AUTH_MODE=none, POLISHED_DEV_TOKEN) is required, and the
    answer to anything else is a 401 in JSON, never a redirect."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = StarletteRequest(scope, receive)
        path = request.url.path
        if is_api_path(path):
            await self._api(request, scope, receive, send)
            return
        user = self._user(request)
        if user is not None:
            request.state.user = user
        if user is not None or path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return
        await self._deny(request)(scope, receive, send)

    async def _api(self, request: StarletteRequest, scope: Scope, receive: Receive, send: Send):
        if request.url.path not in API_PUBLIC_PATHS:
            user = await self._token_user(request)
            if user is None:
                await unauthorized_json()(scope, receive, send)
                return
            request.state.user = user
        await self.app(scope, receive, send)

    async def _token_user(self, request: StarletteRequest) -> dict | None:
        token = bearer_token(request)
        if token is None:
            return None
        dev_token = self.settings.dev_token
        # Settings refuse a dev token outside AUTH_MODE=none (loopback only); checked again here.
        if (
            dev_token is not None
            and self.settings.auth_mode == "none"
            and hmac.compare_digest(token.encode(), dev_token.get_secret_value().encode())
        ):
            return {**DEV_USER, "token_id": None}
        return await asyncio.to_thread(self._lookup_token, token)

    def _lookup_token(self, token: str) -> dict | None:
        conn = connect(self.settings.db_path)
        try:
            return api_tokens.authenticate(conn, token)
        finally:
            conn.close()

    def _user(self, request: StarletteRequest) -> dict | None:
        if self.settings.auth_mode == "none":
            return DEV_USER
        session = request.session
        sub = session.get("sub")
        if not sub:
            return None
        now = time.time()
        iat = session.get("iat")
        if not isinstance(iat, int | float) or now - iat > self.settings.session_max_days * 86400:
            session.clear()
            return None
        seen = session.get("seen")
        if not isinstance(seen, int | float) or now - seen > SEEN_REFRESH_S:
            session["seen"] = int(now)
        return {"sub": sub, "name": session.get("name") or sub}

    @staticmethod
    def _deny(request: StarletteRequest) -> Response:
        if request.headers.get("hx-request") == "true":
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"HX-Redirect": login_url(_htmx_current_path(request))},
            )
        if request.method in ("GET", "HEAD"):
            target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            return RedirectResponse(login_url(target), status_code=302)
        return PlainTextResponse("Unauthorized", status_code=401)


def _htmx_current_path(request: StarletteRequest) -> str:
    """The page the HTMX request came from (HX-Current-URL), else the requested path."""
    current = request.headers.get("hx-current-url")
    if current:
        parts = urlsplit(current)
        if parts.netloc == request.url.netloc:
            return safe_next(parts.path + (f"?{parts.query}" if parts.query else ""))
    return safe_next(request.url.path + (f"?{request.url.query}" if request.url.query else ""))


class SignInRefused(Exception):
    """The identity provider's answer can't be trusted as a sign-in."""


def _audience_includes(aud, client_id: str | None) -> bool:
    """authlib only checks `azp` against the client id, so `aud` is checked here."""
    if isinstance(aud, str):
        aud = [aud]
    return bool(client_id) and isinstance(aud, list) and client_id in aud


def _message_page(request: Request, status_code: int, heading: str, message: str) -> Response:
    return render(
        request,
        "forbidden.html",
        {"heading": heading, "message": message},
        status_code=status_code,
    )


@router.get("/login")
async def login(request: Request, next: str | None = None):
    target = safe_next(next)
    settings: Settings = request.app.state.settings
    if settings.auth_mode == "none":
        return RedirectResponse(target, status_code=302)
    request.session["login_next"] = target
    try:
        return await request.app.state.oidc.authorize_redirect(
            request, f"{settings.public_url}/auth/callback"
        )
    except httpx.HTTPError:
        log.exception("OIDC discovery failed")
        return _message_page(
            request,
            502,
            "Sign-in is unavailable",
            "The login service did not answer. Try again later.",
        )


@router.get("/callback")
async def callback(request: Request):
    settings: Settings = request.app.state.settings
    if settings.auth_mode == "none":
        return RedirectResponse("/", status_code=302)
    oidc = request.app.state.oidc
    try:
        token = await oidc.authorize_access_token(request)
        # Only a validated ID token (signature, iss, exp, nonce) identifies the user.
        id_claims = token.get("userinfo")
        if not id_claims or not id_claims.get("sub"):
            raise SignInRefused("no validated ID token")
        if not _audience_includes(id_claims.get("aud"), settings.oidc_client_id):
            raise SignInRefused("ID token audience does not include this client")
        claims = dict(id_claims)
        if "groups" not in claims:
            userinfo = dict(await oidc.userinfo(token=token))
            if userinfo.get("sub") != claims["sub"]:
                raise SignInRefused("userinfo sub differs from the ID token sub")
            userinfo.pop("sub")
            claims = userinfo | claims
    except (OAuthError, JoseError, SignInRefused) as exc:
        log.warning("OIDC callback failed: %s: %s", type(exc).__name__, exc)
        request.session.pop("login_next", None)
        return _message_page(
            request, 400, "Sign-in failed", "The sign-in did not complete. Try again."
        )
    except httpx.HTTPError:
        log.exception("OIDC token exchange failed")
        return _message_page(
            request,
            502,
            "Sign-in is unavailable",
            "The login service did not answer. Try again later.",
        )

    groups = claims.get("groups") or []
    if isinstance(groups, str):
        groups = [groups]
    sub = claims.get("sub")
    if not sub or not settings.allowed_groups.intersection(groups):
        request.session.clear()
        log.warning("sign-in refused for %s: no allowed group", sub)
        return _message_page(
            request,
            403,
            "This account isn't allowed here",
            "Ask the owner to add it to an allowed group.",
        )

    target = safe_next(request.session.pop("login_next", None))
    app_login = request.session.get("app_login")
    now = int(time.time())
    request.session.clear()
    if app_login:
        request.session["app_login"] = app_login
    request.session.update(
        {
            "sub": sub,
            "name": claims.get("name")
            or claims.get("preferred_username")
            or claims.get("email")
            or sub,
            "iat": now,
            "seen": now,
        }
    )
    return RedirectResponse(target, status_code=302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/auth/signed-out", status_code=302)


@router.get("/signed-out")
def signed_out(request: Request):
    return render(request, "signed_out.html")


@router.get("/app/start")
def app_start(request: Request, challenge: str = "", device: str = ""):
    """The native app opens this in ASWebAuthenticationSession (docs/NATIVE.md 2.4): remember its
    PKCE challenge in the web session, then sign in as usual and come back to /auth/app/finish."""
    if not api_tokens.CHALLENGE.fullmatch(challenge):
        return _message_page(
            request, 400, "Sign-in can't start", "Open Polished on your phone and try again."
        )
    request.session["app_login"] = {
        "challenge": challenge,
        "device": api_tokens.clean_device_name(device),
        "iat": int(time.time()),
    }
    return RedirectResponse(login_url(APP_FINISH_PATH), status_code=302)


@router.get("/app/finish")
def app_finish(request: Request):
    """Signed in (the gate sends everyone else to log in first): hand the app a one-time code."""
    pending = request.session.pop("app_login", None)
    iat = pending.get("iat") if isinstance(pending, dict) else None
    if not isinstance(iat, int | float) or time.time() - iat > APP_LOGIN_MAX_AGE_S:
        return _message_page(
            request, 400, "Sign-in can't finish", "Open Polished on your phone and try again."
        )
    user = request.state.user
    settings: Settings = request.app.state.settings
    conn = connect(settings.db_path)
    try:
        code = api_tokens.mint_login_code(
            conn, user["sub"], user["name"], pending["challenge"], pending["device"]
        )
    finally:
        conn.close()
    return RedirectResponse(
        f"{APP_CALLBACK}?code={code}", status_code=302, headers={"Cache-Control": "no-store"}
    )
