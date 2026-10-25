"""Jinja environment, page rendering (DESIGN 3.2) and template filters."""

from datetime import date
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from . import tips
from .bottles import is_owned

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


def thumb(url: str | None, width: int, height: int | None = None) -> str:
    """Shopify's image CDN resizes and crops by query parameter, so no image is ever proxied or
    stored. With a `height` the CDN returns a true centre crop of exactly that size, which keeps
    the bottle and discards most of the backdrop."""
    if not url:
        return ""
    size = f"width={width}" if height is None else f"width={width}&height={height}&crop=center"
    return f"{url}{'&' if '?' in url else '?'}{size}"


def label(value: str) -> str:
    """A tag value as shown to people: "rose-gold" -> "Rose gold"."""
    text = value.replace("-", " ").strip()
    return text[:1].upper() + text[1:]


def words(values: list[str]) -> str:
    """Tag values as one phrase: ["glitter", "rose-gold"] -> "Glitter, rose gold"."""
    return label(", ".join(v.replace("-", " ").strip() for v in values))


def day(value: str | None) -> str:
    """An ISO date as people say it: "2026-10-01" -> "1 Oct 2026"; anything else unchanged."""
    try:
        parsed = date.fromisoformat(value or "")
    except ValueError:
        return value or ""
    return f"{parsed.day} {parsed:%b %Y}"


templates = Jinja2Templates(directory=PACKAGE_DIR / "templates", context_processors=[_context])
templates.env.filters.update(money=money, thumb=thumb, label=label, words=words, day=day)
templates.env.globals.update(
    tip_shade_url=tips.shade_url, tip_stack_url=tips.stack_url, tip_hex=tips.effective_hex
)
templates.env.tests["owned_bottle"] = is_owned


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
