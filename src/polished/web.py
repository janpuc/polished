"""Jinja environment, page rendering (DESIGN 3.2) and template filters."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"


def _context(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "user": getattr(request.state, "user", None),
        "version": settings.version,
        "store_url": settings.store_url,
    }


def money(cents: int | None) -> str:
    """1550 -> "$15.50"; empty for a missing price."""
    if cents is None:
        return ""
    return f"${cents // 100}.{cents % 100:02d}"


def thumb(url: str | None, width: int) -> str:
    """Shopify's image CDN resizes by query parameter, so no image is ever proxied or stored."""
    if not url:
        return ""
    return f"{url}{'&' if '?' in url else '?'}width={width}"


def label(value: str) -> str:
    """A tag value as shown to people: "rose-gold" -> "Rose gold"."""
    text = value.replace("-", " ").strip()
    return text[:1].upper() + text[1:]


templates = Jinja2Templates(directory=PACKAGE_DIR / "templates", context_processors=[_context])
templates.env.filters.update(money=money, thumb=thumb, label=label)


def is_partial_request(request: Request) -> bool:
    """HTMX asked for a fragment. A history restore (back button after a reload) needs the whole
    page, which is why historyCacheSize is 0 and the two headers are in Vary."""
    return (
        request.headers.get("hx-request") == "true"
        and "hx-history-restore-request" not in request.headers
    )


def render(
    request: Request,
    page: str,
    context: dict | None = None,
    status_code: int = 200,
    partial: str | None = None,
) -> Response:
    """The `partial` template for a fragment request, otherwise the full `page`. Templates see
    `is_partial`, which lets a fragment carry out-of-band updates the full page does not need."""
    use_partial = partial is not None and is_partial_request(request)
    values = {**(context or {}), "is_partial": use_partial}
    return templates.TemplateResponse(
        request, partial if use_partial else page, values, status_code=status_code
    )
