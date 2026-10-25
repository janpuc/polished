"""Browse list with filters, and the shade detail page (DESIGN 6, 13.2)."""

import sqlite3
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse

from .. import bottles, shades, wheels, wishlist
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
    owned: str = "",
    page: int = 1,
):
    query = shades.ShadeQuery.from_params(q, finish, color, collection, kind, status, sort, owned)
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


@router.get("/new")
def new_shade_form(request: Request, title: str = ""):
    """Declared before `/{shade_id}`, which would otherwise try to read "new" as a number."""
    return render(
        request,
        "shade_new.html",
        {"values": {"title": title.strip()[:100], "kind": "polish"}, "errors": {}},
    )


@router.post("")
def create_shade(
    request: Request,
    conn: Conn,
    title: Annotated[str, Form()] = "",
    kind: Annotated[str, Form()] = "polish",
):
    """A shade added by hand, for a gifted bottle that is not in the catalog."""
    errors = {}
    if not title.strip():
        errors["title"] = "Give the shade a name."
    if kind not in shades.MANUAL_KINDS:
        errors["kind"] = "Pick polish, topper or base coat."
    if errors:
        values = {"title": title.strip()[:100], "kind": kind}
        return render(request, "shade_new.html", {"values": values, "errors": errors}, 422)
    shade_id = shades.create_manual(conn, title[:100], kind)
    return RedirectResponse(f"/shades/{shade_id}", status_code=302)


def _detail_context(conn: sqlite3.Connection, shade: dict) -> dict:
    return {
        "shade": shade,
        "bottles": bottles.for_shade(conn, shade["id"]),
        "wish": wishlist.for_shade(conn, shade["id"]),
        "swatched_on": wheels.swatched_on(conn, shade["id"]),
        "ctx": "shade",
    }


@router.get("/{shade_id}")
def detail(request: Request, conn: Conn, shade_id: int):
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        return render(request, "not_found.html", status_code=404)
    return render(request, "shade_detail.html", _detail_context(conn, shade))


@router.post("/{shade_id}/tip-colour")
def set_tip_colour(
    request: Request,
    conn: Conn,
    shade_id: int,
    hex: Annotated[str, Form()] = "",
    reset: Annotated[str, Form()] = "",
):
    """The household's own colour for this shade's nail tip, or Reset to the one read from its
    photos."""
    try:
        found = shades.set_tip_colour(conn, shade_id, None if reset else hex)
    except ValueError as exc:
        shade = shades.get_shade(conn, shade_id)
        if shade is None:
            return render(request, "not_found.html", status_code=404)
        context = {**_detail_context(conn, shade), "tip_error": str(exc)}
        return render(request, "shade_detail.html", context, status_code=422)
    if not found:
        return render(request, "not_found.html", status_code=404)
    return RedirectResponse(f"/shades/{shade_id}", status_code=303)
