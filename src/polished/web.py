"""Jinja environment, page rendering (DESIGN 3.2) and template filters."""

from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.responses import Response

from . import tips
from .bottles import is_owned

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"


def _context(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "user": getattr(request.state, "user", None),
        "today_iso": datetime.now(ZoneInfo(settings.timezone)).date().isoformat(),
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


def date_words(value: str | None, today: str) -> tuple[str, str]:
    """A date field's value in words, as (main, rest): ("Today", "26 Oct 2026"), ("Yesterday",
    "25 Oct 2026"), ("21 Jul 2026", "Tuesday") or ("", "") for no date. static/js/date.js draws
    the same words when the field changes."""
    try:
        parsed = date.fromisoformat(value or "")
        current = date.fromisoformat(today)
    except ValueError:
        return "", ""
    long = f"{parsed.day} {parsed:%b %Y}"
    if parsed == current:
        return "Today", long
    if parsed == current - timedelta(days=1):
        return "Yesterday", long
    return long, f"{parsed:%A}"


def marked(text: str, spans: list[tuple[int, int]] | None) -> str | Markup:
    """`text` with the character spans from search.marks() wrapped in <mark>. Everything outside
    the tags is escaped; with no spans the plain text is returned for the template to escape."""
    if not spans:
        return text
    out = Markup("")
    position = 0
    for start, end in spans:
        out += escape(text[position:start])
        out += Markup("<mark>{}</mark>").format(text[start:end])
        position = end
    return out + escape(text[position:])


templates = Jinja2Templates(directory=PACKAGE_DIR / "templates", context_processors=[_context])
templates.env.filters.update(
    money=money,
    thumb=thumb,
    label=label,
    words=words,
    day=day,
    date_words=date_words,
    marked=marked,
)
templates.env.globals.update(
    tip_shade_url=tips.shade_url, tip_stack_url=tips.stack_url, tip_hex=tips.effective_hex
)
templates.env.tests["owned_bottle"] = is_owned


FLASH_COOKIE = "polished_flash"
FLASH_SECONDS = 60


def set_flash(response: Response, text: str) -> None:
    """A line the next page shows once (a deleted wheel). It rides in a short-lived cookie that
    pop_flash() clears, so a reload does not repeat it."""
    response.set_cookie(
        FLASH_COOKIE, quote(text), max_age=FLASH_SECONDS, httponly=True, samesite="lax", path="/"
    )


def pop_flash(request: Request) -> str | None:
    """The flash line the request carries, if any. The response must call clear_flash()."""
    raw = request.cookies.get(FLASH_COOKIE)
    return unquote(raw) if raw else None


def clear_flash(response: Response) -> None:
    response.delete_cookie(FLASH_COOKIE, path="/")


ARRIVED_COOKIE = "polished_arrived"
ARRIVED_SECONDS = 600


def set_arrival(response: Response, bottle_id: int) -> None:
    """Remembers the bottle just added, so the next Home draws its tip arriving on the rack (the
    one authored moment, docs/VISUAL.md section 8). A cookie, like the flash line, so a reload does
    not replay it."""
    response.set_cookie(
        ARRIVED_COOKIE,
        str(bottle_id),
        max_age=ARRIVED_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def pop_arrival(request: Request) -> int | None:
    """The bottle id set_arrival() left, if any. The response must call clear_arrival()."""
    raw = request.cookies.get(ARRIVED_COOKIE, "")
    return int(raw) if raw.isdecimal() else None


def clear_arrival(response: Response) -> None:
    response.delete_cookie(ARRIVED_COOKIE, path="/")


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
