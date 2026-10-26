"""Security headers, cache headers and the Origin check (DESIGN 8.3, 3.2).

Pure ASGI middleware, outermost first in server.create_app(): headers, then the Origin check.
"""

from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    "default-src 'self'; img-src 'self' https://cdn.shopify.com data:; "
    "script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; "
    "worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
VARY_HTML = ("HX-Request", "HX-History-Restore-Request")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
API_PREFIX = "/api/v1"
# The UI-test reset (a route that exists only in AUTH_MODE=none, from loopback)
# comes from XCUITest without an Origin; a request that does carry one (a web page) is checked.
TEST_RESET_PATH = "/__test/reset"


def is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


class SecurityHeadersMiddleware:
    """CSP, nosniff and referrer policy on every response; HTML is never cached or shared, and
    varies on the HTMX headers so Safari's back button never shows a partial."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = CSP
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
                if is_api_path(scope["path"]):
                    headers["X-Polished-Api"] = "1"
                    headers.setdefault("Cache-Control", "private, no-cache")
                    headers.append("Vary", "Authorization")
                if headers.get("content-type", "").startswith("text/html"):
                    if headers.get("cache-control") != "no-store":
                        headers["Cache-Control"] = "private, no-cache"
                    present = {v.strip().lower() for v in headers.get("vary", "").split(",")}
                    for name in VARY_HTML:
                        if name.lower() not in present:
                            headers.append("Vary", name)
            await send(message)

        await self.app(scope, receive, send_with_headers)


class OriginCheckMiddleware:
    """CSRF defence with SameSite=Lax: an unsafe method needs an Origin (else Referer) whose
    host equals the host of PUBLIC_URL. /api/v1 is exempt: its only credential is the Bearer
    header, which a browser never attaches by itself (cookies are ignored there, so there is
    nothing to forge), and a request without one should get the 401 JSON from the auth gate."""

    def __init__(self, app: ASGIApp, public_netloc: str):
        self.app = app
        self.public_netloc = public_netloc

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            headers = Headers(scope=scope)
            path = scope["path"]
            if is_api_path(path) or (path == TEST_RESET_PATH and "origin" not in headers):
                await self.app(scope, receive, send)
                return
            source = headers.get("origin") or headers.get("referer")
            if not source or urlsplit(source).netloc != self.public_netloc:
                response = PlainTextResponse("Forbidden: bad origin", status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
