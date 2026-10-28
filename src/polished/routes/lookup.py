"""Identifier lookup: the scan page, the resolver and the learned codes (DESIGN 7, 13.4).

`/lookup/resolve` and the POSTs answer with their fragment, with or without HX-Request, as
/search does: the page that asked is on screen, and plain `curl` can read the result."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from .. import identifiers
from ..db import get_conn, transaction
from ..web import render

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

VIAS = ("scan", "typed")


def _via(via: str) -> str:
    return via if via in VIAS else "typed"


def _result(request: Request, resolution: identifiers.Resolution, status_code: int = 200, **extra):
    return render(
        request, "_lookup_result.html", {"r": resolution, "saved": False, **extra}, status_code
    )


@router.get("/lookup")
def lookup(request: Request, conn: Conn, q: str = "", via: str = "typed", scan: int = 0):
    """The page. `q` makes it work without JavaScript (the field is a GET form) and is how the
    home search hands a number over; `scan=1` opens the camera as the page loads."""
    resolution = identifiers.resolve(conn, q, _via(via)) if q.strip() else None
    return render(request, "lookup.html", {"q": q.strip(), "r": resolution, "autoscan": bool(scan)})


@router.get("/lookup/resolve")
def resolve(request: Request, conn: Conn, q: str = "", via: str = "typed"):
    return _result(request, identifiers.resolve(conn, q, _via(via)))


@router.post("/identifiers")
def learn_identifier(
    request: Request,
    conn: Conn,
    kind: Annotated[str, Form()],
    value: Annotated[str, Form()],
    shade_id: Annotated[int, Form()],
):
    """One tap on a shade in the picker: remember the code, then show the shade with
    "+ Add bottle". A code that is already known keeps its shade and says so."""
    if kind not in identifiers.KINDS:
        raise HTTPException(422, "kind must be gtin")
    if conn.execute("select 1 from shade where id = ?", (shade_id,)).fetchone() is None:
        raise HTTPException(404, "No such shade")
    try:
        with transaction(conn):
            learned = identifiers.learn(conn, kind, value, shade_id)
    except ValueError:
        resolution = identifiers.Resolution("invalid_code", value, "typed")
        return _result(request, resolution, 422)
    resolution = identifiers.Resolution(
        "match",
        value,
        code=learned.value,
        kind=kind,
        shade=identifiers.result_shade(conn, learned.shade_id),
        identifier_id=learned.id,
    )
    kept_other = learned.shade_id != shade_id
    return _result(request, resolution, saved=learned.created, kept_other=kept_other)


@router.get("/identifiers")
def identifier_list(request: Request, conn: Conn):
    return render(request, "identifiers.html", {"items": identifiers.list_all(conn)})


@router.post("/identifiers/{identifier_id}/delete")
def delete_identifier(
    request: Request,
    conn: Conn,
    identifier_id: int,
    ctx: Annotated[str, Form()] = "list",
):
    """From the list: the row goes. From a lookup match ("This isn't it"): the result turns back
    into the unknown-barcode question for the same code."""
    row = identifiers.get(conn, identifier_id)
    if row is None:
        raise HTTPException(404, "No such identifier")
    identifiers.delete(conn, identifier_id)
    if ctx == "lookup" and row["kind"] == "gtin":
        return _result(
            request, identifiers.Resolution("unknown_code", row["value"], code=row["value"])
        )
    return HTMLResponse("")
