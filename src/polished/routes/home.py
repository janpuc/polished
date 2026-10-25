"""Home and the typeahead behind its search field (DESIGN 13.2)."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .. import bottles, identifiers, shades, wishlist
from ..db import get_conn
from ..gtin import is_numeric
from ..web import render

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


@router.get("/")
def home(request: Request, conn: Conn):
    total = conn.execute("select count(*) from shade").fetchone()[0]
    context = {
        "shade_count": total,
        "counts": bottles.counts(conn),
        "wishlist": wishlist.summary(wishlist.items(conn)),
        "recent": bottles.recent(conn),
    }
    return render(request, "home.html", context)


@router.get("/wheels")
def wheels_placeholder(request: Request):
    """The Wheels tab until the wheel pages (DESIGN 9) exist; routes/wheels.py replaces it."""
    return render(request, "wheels.html")


@router.get("/search")
def search(
    request: Request,
    conn: Conn,
    q: str = "",
    ctx: Annotated[Literal["home", "learn"], Query()] = "home",
    kind: str = "",
    value: str = "",
):
    """Rows only, for every request: the page that asked is already on screen. `ctx` decides
    what tapping a row does: `home` opens the shade, `learn` teaches it the code in `kind` and
    `value` (a gtin or a P code, DESIGN 7.2)."""
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
