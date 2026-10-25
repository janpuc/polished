"""Home and the typeahead behind its search field (DESIGN 13.2)."""

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request

from .. import bottles, shades, wishlist
from ..db import get_conn
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


@router.get("/search")
def search(
    request: Request,
    conn: Conn,
    q: str = "",
    ctx: Annotated[Literal["home"], Query()] = "home",
):
    """Rows only, for every request: the page that asked is already on screen. `ctx` decides
    what tapping a row does; stage 3 has only `home` (open the shade)."""
    result = shades.search(conn, q) if shades.tokens(q) else None
    return render(request, "_search_results.html", {"result": result, "q": q.strip(), "ctx": ctx})
