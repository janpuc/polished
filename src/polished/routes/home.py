"""Home and the typeahead behind its search field (DESIGN 13.2)."""

import sqlite3
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import bottles, identifiers, shades, wheels, wishlist
from ..db import get_conn
from ..gtin import is_numeric
from ..web import clear_arrival, pop_arrival, render
from . import _builder as builder
from . import wear as wear_routes

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def greeting(now: datetime) -> str:
    """ "Good morning", "Good afternoon" or "Good evening" by the local hour."""
    part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
    return f"Good {part}"


def first_name(user: dict | None) -> str:
    """The first word of the signed-in name (the part before an @ when the name is an address)."""
    words = (user or {}).get("name", "").split("@")[0].split()
    return words[0] if words else ""


RACK_SIZE = 6


@router.get("/")
def home(request: Request, conn: Conn, another: int = 0, shown: int | None = None):
    """The shelf (docs/VISUAL.md section 6): what to wear today, the bottles added last, the wheel
    worked on last and the collection in numbers. `another` (and `shown`, the shade on screen) is
    the hero's "Another" for a browser without htmx."""
    now = datetime.now(ZoneInfo(request.app.state.settings.timezone))
    today = wear_routes.household_today(request)
    total = conn.execute("select count(*) from shade").fetchone()[0]
    wheel = wheels.most_recent(conn)
    recent = bottles.recent(conn, RACK_SIZE)
    arrived = pop_arrival(request)
    context = {
        "greeting": greeting(now),
        "first_name": first_name(getattr(request.state, "user", None)),
        "date_line": f"{now:%A} {now.day} {now:%B}",
        "shade_count": total,
        "counts": bottles.counts(conn),
        "wishlist": wishlist.summary(wishlist.items(conn)),
        "recent": recent,
        "arrived_bottle_id": arrived if recent and recent[0]["id"] == arrived else None,
        "wheel": wheel,
        "wheel_count": len(wheels.list_wheels(conn)),
        "tiles": wheels.slot_grid(conn, wheel) if wheel else wheels.unpainted_ring(),
        "arriving": bool(another),
    } | wear_routes.hero_context(conn, wear_routes.choose(conn, today, bool(another), shown), today)
    response = render(request, "home.html", context)
    if arrived is not None:
        clear_arrival(response)
    return response


@router.get("/more")
def more(request: Request):
    """What Home keeps out of the way: adding a shade by hand, catalog sync, learned codes and
    signing out."""
    return render(request, "more.html")


@router.get("/search")
def search(
    request: Request,
    conn: Conn,
    q: str = "",
    ctx: Annotated[Literal["home", "learn", "stack"], Query()] = "home",
    kind: str = "",
    value: str = "",
    stack_id: int | None = None,
    filter: str = "owned",
):
    """Rows only, for every request: the page that asked is already on screen. `ctx` decides
    what tapping a row does: `home` opens the shade, `learn` teaches it the code in `kind` and
    `value` (a gtin or a P code, DESIGN 7.2), `stack` adds it as a layer of the draft `stack_id`
    (DESIGN 10), narrowed by `filter` (owned, toppers or all)."""
    if ctx == "stack":
        if stack_id is None:
            raise HTTPException(422, "stack needs a stack_id")
        picked = builder.picker(conn, stack_id, q, filter)
        return render(request, "_picker_results.html", {"picker": picked})
    code = None
    if ctx == "learn":
        code = identifiers.normalise(kind, value)
        if code is None:
            raise HTTPException(422, "learn needs a kind (gtin or printed) and a valid value")
    result = shades.search(conn, q) if shades.tokens(q) else None
    context = {"result": result, "q": q.strip(), "ctx": ctx, "kind": kind, "value": code}
    # A number or a P code typed into the home search is offered to the resolver (DESIGN 7.2).
    stripped = q.strip()
    if (
        ctx == "home"
        and stripped
        and (is_numeric(stripped) or identifiers.normalise_printed(stripped))
    ):
        context["code_q"] = stripped
    return render(request, "_search_results.html", context)
