"""Browse list with filters, and the shade detail page (DESIGN 6, 13.2)."""

import sqlite3
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request

from .. import shades
from ..db import get_conn
from ..web import render

router = APIRouter(prefix="/shades")

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


@router.get("")
def browse(
    request: Request,
    conn: Conn,
    *,
    q: str = "",
    finish: Annotated[list[str], Query(default_factory=list)],
    color: Annotated[list[str], Query(default_factory=list)],
    collection: str = "",
    kind: str = "",
    status: str = "",
    sort: str = "name",
    page: int = 1,
):
    query = shades.ShadeQuery.from_params(q, finish, color, collection, kind, status, sort)
    result = shades.list_shades(conn, query, page)
    more_url = "/shades?" + urlencode(query.params(result.page + 1)) if result.has_more else None
    context = {
        "query": query,
        "result": result,
        "more_url": more_url,
        "facets": shades.facets(conn),
        "kinds": shades.KINDS,
        "statuses": shades.STATUSES,
    }
    return render(request, "shades.html", context, partial="_shade_rows.html")


@router.get("/{shade_id}")
def detail(request: Request, conn: Conn, shade_id: int):
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        return render(request, "not_found.html", status_code=404)
    return render(request, "shade_detail.html", {"shade": shade})
