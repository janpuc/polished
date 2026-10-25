"""Pocket ID sign-in with authlib, the session, and the deny-by-default gate (DESIGN 8)."""

import logging
import time
from urllib.parse import quote, urlsplit

import httpx
from authlib.integrations.base_client import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from starlette.requests import Request as StarletteRequest
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings
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
    }
)
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


class AuthGateMiddleware:
    """Deny by default. Everything outside PUBLIC_PATHS needs a valid session, or the dev user
    in AUTH_MODE=none. Sits inside SessionMiddleware."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = StarletteRequest(scope, receive)
        user = self._user(request)
        if user is not None:
            request.state.user = user
        path = request.url.path
        if user is not None or path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return
        await self._deny(request)(scope, receive, send)

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
        claims = dict(token.get("userinfo") or {})
        if "groups" not in claims:
            claims.update(await oidc.userinfo(token=token))
    except OAuthError as exc:
        log.warning("OIDC callback failed: %s", exc)
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
    now = int(time.time())
    request.session.clear()
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
