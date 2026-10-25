"""Bottles: the list, the add and edit sheet, state changes (DESIGN 13.3).

Every route here answers with its fragment, with or without HX-Request, as /search does: the
page that asked is already on screen, and plain `curl` can read the result. Cards and the
bottle list carry an out-of-band copy of the shade page's action bar (`ctx=shade`), because
adding, emptying or deleting a bottle changes whether the shade is owned.
"""

import sqlite3
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from starlette.responses import Response

from .. import bottles, identifiers, shades, wishlist
from ..db import get_conn, transaction
from ..web import render

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

SHEET_CLOSE = {"HX-Trigger": "sheetClose"}
# Where a new bottle was started: on the shade page, or on /lookup after a scan or a typed code.
NEW_CONTEXTS = ("shade", "lookup")
# A form that fails validation goes back into the sheet it came from.
SHEET_RETARGET = {"HX-Retarget": "#sheet-body", "HX-Reswap": "innerHTML"}


def today(request: Request) -> str:
    return datetime.now(ZoneInfo(request.app.state.settings.timezone)).date().isoformat()


def actions_context(conn: sqlite3.Connection, shade_id: int) -> dict:
    """What the shade page's action bar (`_shade_actions.html`) shows."""
    return {"shade": shades.get_shade(conn, shade_id), "wish": wishlist.for_shade(conn, shade_id)}


def form_code(code: str) -> str:
    """The P prefix is left off a plain "P259" so the numeric keypad can edit it."""
    return code[1:] if code[:1] == "P" and code[1:].isdigit() else code


def form_values(bottle: dict | None, default_bought_on: str = "") -> dict[str, str]:
    """A bottle (or the new-bottle defaults) as the strings the form fields hold."""
    if bottle is None:
        return {"state": "full", "bought_on": default_bought_on}
    cents = bottle["price_paid_cents"]
    return {
        "state": bottle["state"],
        "printed_code": form_code(bottle["printed_code"] or ""),
        "bought_on": bottle["bought_on"] or "",
        "price_paid": f"{cents // 100}.{cents % 100:02d}" if cents is not None else "",
        "opened_on": bottle["opened_on"] or "",
        "notes": bottle["notes"] or "",
    }


def _conflict_notice(
    conn: sqlite3.Connection, learned: identifiers.Learned | None, shade_id: int
) -> str | None:
    """A P code that already points at another shade keeps that mapping (DESIGN 7.2); the bottle
    is saved with the code anyway, and this is the sentence that says so."""
    if learned is None or learned.shade_id == shade_id:
        return None
    other = shades.get_shade(conn, learned.shade_id)
    return f"{learned.value} was {other['title']} before. The bottle is saved; the old match stays."


def _require_shade(conn: sqlite3.Connection, shade_id: int) -> None:
    if conn.execute("select 1 from shade where id = ?", (shade_id,)).fetchone() is None:
        raise HTTPException(404, "No such shade")


def _require_bottle(conn: sqlite3.Connection, bottle_id: int) -> dict:
    bottle = bottles.get(conn, bottle_id)
    if bottle is None:
        raise HTTPException(404, "No such bottle")
    return bottle


def _form(
    request: Request,
    *,
    shade_id: int,
    title: str,
    bottle: dict | None,
    values: dict[str, str],
    errors: dict[str, str] | None = None,
    ctx: str = "shade",
    status_code: int = 200,
) -> Response:
    response = render(
        request,
        "_bottle_form.html",
        {
            "shade_id": shade_id,
            "shade_title": title,
            "bottle": bottle,
            "values": values,
            "errors": errors or {},
            "ctx": ctx,
            "states": bottles.STATE_LABELS,
        },
        status_code,
    )
    if errors:
        response.headers.update(SHEET_RETARGET)
    return response


def _card(request: Request, conn: sqlite3.Connection, bottle_id: int, ctx: str) -> Response:
    bottle = _require_bottle(conn, bottle_id)
    context = {"bottle": bottle, "ctx": ctx, "oob_actions": ctx == "shade"}
    if ctx == "shade":
        context |= actions_context(conn, bottle["shade_id"])
    return render(request, "_bottle_swap.html", context)


@router.get("/bottles")
def bottle_list(request: Request, conn: Conn, state: str = "", archived: int = 0):
    state = state if state in bottles.STATES else ""
    context = {
        "groups": bottles.list_groups(conn, state, bool(archived)),
        "state": state,
        "archived": bool(archived),
        "states": bottles.STATE_LABELS,
        "counts": bottles.counts(conn),
        "ctx": "list",
    }
    return render(request, "bottles.html", context, partial="_bottle_groups.html")


@router.get("/shades/{shade_id}/bottles/new")
def new_bottle_sheet(
    request: Request, conn: Conn, shade_id: int, ctx: str = "shade", printed_code: str = ""
):
    """`printed_code` pre-fills the P code field after a lookup (it is stored on save, not here)."""
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        raise HTTPException(404, "No such shade")
    values = form_values(None, today(request))
    code = bottles.clean_printed_code(printed_code)
    if code:
        values["printed_code"] = form_code(code)
    return _form(
        request,
        shade_id=shade_id,
        title=shade["title"],
        bottle=None,
        values=values,
        ctx=ctx if ctx in NEW_CONTEXTS else "shade",
    )


@router.post("/shades/{shade_id}/bottles")
def create_bottle(
    request: Request,
    conn: Conn,
    shade_id: int,
    state: Annotated[str, Form()] = "full",
    printed_code: Annotated[str, Form()] = "",
    bought_on: Annotated[str, Form()] = "",
    price_paid: Annotated[str, Form()] = "",
    opened_on: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    ctx: Annotated[str, Form()] = "shade",
):
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        raise HTTPException(404, "No such shade")
    ctx = ctx if ctx in NEW_CONTEXTS else "shade"
    raw = {
        "state": state,
        "printed_code": printed_code,
        "bought_on": bought_on,
        "price_paid": price_paid,
        "opened_on": opened_on,
        "notes": notes,
    }
    values, errors = bottles.parse_input(**raw)
    if errors:
        return _form(
            request,
            shade_id=shade_id,
            title=shade["title"],
            bottle=None,
            values=raw,
            errors=errors,
            ctx=ctx,
            status_code=422,
        )
    with transaction(conn):
        bottle_id = bottles.add(conn, shade_id, values)
        learned = identifiers.learn_printed(conn, shade_id, values.printed_code)
    notice = _conflict_notice(conn, learned, shade_id)
    if ctx == "lookup":
        response = render(
            request,
            "_lookup_added.html",
            {"bottle": bottles.get(conn, bottle_id), "shade": shade, "notice": notice},
        )
    else:
        response = render(
            request,
            "_bottles.html",
            {
                "bottles": bottles.for_shade(conn, shade_id),
                "ctx": "shade",
                "oob_actions": True,
                "notice": notice,
                **actions_context(conn, shade_id),
            },
        )
    response.headers.update(SHEET_CLOSE)
    return response


@router.get("/bottles/{bottle_id}/edit")
def edit_bottle_sheet(request: Request, conn: Conn, bottle_id: int, ctx: str = "shade"):
    bottle = _require_bottle(conn, bottle_id)
    return _form(
        request,
        shade_id=bottle["shade_id"],
        title=bottle["title"],
        bottle=bottle,
        values=form_values(bottle),
        ctx=ctx,
    )


@router.post("/bottles/{bottle_id}")
def update_bottle(
    request: Request,
    conn: Conn,
    bottle_id: int,
    state: Annotated[str, Form()] = "full",
    printed_code: Annotated[str, Form()] = "",
    bought_on: Annotated[str, Form()] = "",
    price_paid: Annotated[str, Form()] = "",
    opened_on: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
    ctx: Annotated[str, Form()] = "shade",
):
    bottle = _require_bottle(conn, bottle_id)
    raw = {
        "state": state,
        "printed_code": printed_code,
        "bought_on": bought_on,
        "price_paid": price_paid,
        "opened_on": opened_on,
        "notes": notes,
    }
    values, errors = bottles.parse_input(**raw)
    if errors:
        return _form(
            request,
            shade_id=bottle["shade_id"],
            title=bottle["title"],
            bottle=bottle,
            values=raw,
            errors=errors,
            ctx=ctx,
            status_code=422,
        )
    bottles.update(conn, bottle_id, values)
    response = _card(request, conn, bottle_id, ctx)
    response.headers.update(SHEET_CLOSE)
    return response


@router.post("/bottles/{bottle_id}/state")
def set_state(
    request: Request,
    conn: Conn,
    bottle_id: int,
    state: Annotated[str, Form()],
    ctx: Annotated[str, Form()] = "shade",
):
    _require_bottle(conn, bottle_id)
    if state not in bottles.STATES:
        raise HTTPException(422, "state must be full, half, low or empty")
    bottles.set_state(conn, bottle_id, state)
    return _card(request, conn, bottle_id, ctx)


@router.post("/bottles/{bottle_id}/archive")
def archive_bottle(
    request: Request,
    conn: Conn,
    bottle_id: int,
    archived: Annotated[int, Form()] = 1,
    ctx: Annotated[str, Form()] = "shade",
):
    _require_bottle(conn, bottle_id)
    bottles.set_archived(conn, bottle_id, bool(archived))
    return _card(request, conn, bottle_id, ctx)


@router.post("/bottles/{bottle_id}/delete")
def delete_bottle(
    request: Request,
    conn: Conn,
    bottle_id: int,
    ctx: Annotated[str, Form()] = "shade",
):
    bottle = _require_bottle(conn, bottle_id)
    bottles.delete(conn, bottle_id)
    context = {"oob_actions": ctx == "shade"}
    if ctx == "shade":
        context |= actions_context(conn, bottle["shade_id"])
    response = render(request, "_oob_actions.html", context)
    response.headers.update(SHEET_CLOSE)
    return response
