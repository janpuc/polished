"""The wishlist and its cart permalink (DESIGN 13.3). Like the bottle routes, every route answers
with its fragment, with or without HX-Request."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from starlette.responses import Response

from .. import bottles, shades, wishlist
from ..db import get_conn
from ..web import render
from .bottles import SHEET_CLOSE, SHEET_RETARGET, actions_context, today

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _cart_context(request: Request, rows: list[dict], max_priority: int) -> dict:
    return {"cart": wishlist.cart(rows, request.app.state.settings.store_url, max_priority)}


def _page_context(request: Request, conn: sqlite3.Connection, bought: int = 0) -> dict:
    rows = wishlist.items(conn)
    return {
        "bought": bought,
        "groups": wishlist.groups(rows),
        "summary": wishlist.summary(rows),
        "priorities": wishlist.PRIORITY_LABELS,
        **_cart_context(request, rows, max(wishlist.PRIORITIES)),
    }


def _require_item(conn: sqlite3.Connection, item_id: int) -> dict:
    item = wishlist.get(conn, item_id)
    if item is None:
        raise HTTPException(404, "No such wishlist item")
    return item


@router.get("/wishlist")
def wishlist_page(request: Request, conn: Conn):
    return render(request, "wishlist.html", _page_context(request, conn))


@router.get("/wishlist/cart")
def cart_box(request: Request, conn: Conn, max_priority: int = max(wishlist.PRIORITIES)):
    return render(
        request, "_cart_box.html", _cart_context(request, wishlist.items(conn), max_priority)
    )


def price_field(cents: int | None) -> str:
    return f"{cents // 100}.{cents % 100:02d}" if cents is not None else ""


def _bought_sheet(
    request: Request,
    conn: sqlite3.Connection,
    *,
    checked: set[int],
    prices: dict[int, str],
    bought_on: str,
    errors: dict[str, str] | None = None,
    price_errors: dict[int, str] | None = None,
    status_code: int = 200,
) -> Response:
    rows = wishlist.items(conn)
    for item in rows:
        item["checked"] = item["id"] in checked
        item["price_field"] = prices.get(item["id"], price_field(item["price_cents"]))
    response = render(
        request,
        "_bought_sheet.html",
        {
            "rows": rows,
            "bought_on": bought_on,
            "errors": errors or {},
            "price_errors": price_errors or {},
        },
        status_code,
    )
    if errors or price_errors:
        response.headers.update(SHEET_RETARGET)
    return response


@router.get("/wishlist/bought")
def bought_sheet(request: Request, conn: Conn, max_priority: int = max(wishlist.PRIORITIES)):
    """The "I bought these" sheet: the items the checkout box includes, and are buyable, ticked."""
    if max_priority not in wishlist.PRIORITIES:
        max_priority = max(wishlist.PRIORITIES)
    checked = {
        i["id"] for i in wishlist.items(conn) if i["buyable"] and i["priority"] <= max_priority
    }
    return _bought_sheet(request, conn, checked=checked, prices={}, bought_on=today(request))


@router.post("/wishlist/bought")
async def mark_bought(request: Request, conn: Conn):
    """One bottle per ticked item (`item` = item ids, `price-<id>` = price paid), one date for
    all; the items leave the wishlist in the same transaction. The fields are read from the raw
    form because their names carry the item id."""
    form = await request.form()
    try:
        item_ids = [int(v) for v in form.getlist("item")]
    except ValueError:
        raise HTTPException(422, "item must be a wishlist item id") from None
    known = {i["id"] for i in wishlist.items(conn)}
    if not known.issuperset(item_ids):
        raise HTTPException(404, "No such wishlist item")
    bought_on = str(form.get("bought_on", "")).strip()
    prices = {i: str(form.get(f"price-{i}", "")) for i in known}
    errors: dict[str, str] = {}
    price_errors: dict[int, str] = {}
    cents: dict[int, int | None] = {}
    for item_id in item_ids:
        try:
            cents[item_id] = bottles.parse_price(prices[item_id])
        except ValueError:
            price_errors[item_id] = "Use an amount like 15.50."
    try:
        date.fromisoformat(bought_on)
    except ValueError:
        errors["bought_on"] = "Use a date like 2026-10-25."
    if not item_ids:
        errors["none_ticked"] = "Tick the shades you bought."
    if errors or price_errors:
        return _bought_sheet(
            request,
            conn,
            checked=set(item_ids),
            prices=prices,
            bought_on=bought_on,
            errors=errors,
            price_errors=price_errors,
            status_code=422,
        )
    new_ids = wishlist.mark_bought(
        conn, [(i, cents[i]) for i in dict.fromkeys(item_ids)], bought_on
    )
    response = render(request, "_wishlist.html", _page_context(request, conn, len(new_ids)))
    response.headers.update(SHEET_CLOSE)
    return response


@router.post("/shades/{shade_id}/wishlist")
def add_to_wishlist(
    request: Request, conn: Conn, shade_id: int, priority: Annotated[int, Form()] = 2
):
    if shades.get_shade(conn, shade_id) is None:
        raise HTTPException(404, "No such shade")
    if priority not in wishlist.PRIORITIES:
        raise HTTPException(422, "priority must be 1, 2 or 3")
    wishlist.add(conn, shade_id, priority)
    return render(request, "_shade_actions.html", actions_context(conn, shade_id))


@router.get("/wishlist/{item_id}/edit")
def edit_item_sheet(request: Request, conn: Conn, item_id: int):
    """The row's sheet: the note, and Remove."""
    item = _require_item(conn, item_id)
    return render(
        request,
        "_wishlist_sheet.html",
        {"item": item, "priority_label": wishlist.PRIORITY_LABELS[item["priority"]]},
    )


@router.post("/wishlist/{item_id}")
def update_item(
    request: Request,
    conn: Conn,
    item_id: int,
    priority: Annotated[int, Form()],
    note: Annotated[str, Form()] = "",
):
    """The row's sheet: priority and note together (an empty note clears it)."""
    _require_item(conn, item_id)
    if priority not in wishlist.PRIORITIES:
        raise HTTPException(422, "priority must be 1, 2 or 3")
    wishlist.update(conn, item_id, priority, note)
    response = render(request, "_wishlist.html", _page_context(request, conn))
    response.headers.update(SHEET_CLOSE)
    return response


@router.post("/wishlist/{item_id}/priority")
def set_priority(request: Request, conn: Conn, item_id: int, priority: Annotated[int, Form()]):
    """The priority menu of a row: the priority alone, the note stays."""
    item = _require_item(conn, item_id)
    if priority not in wishlist.PRIORITIES:
        raise HTTPException(422, "priority must be 1, 2 or 3")
    wishlist.update(conn, item_id, priority, item["note"])
    return render(request, "_wishlist.html", _page_context(request, conn))


@router.post("/wishlist/{item_id}/delete")
def delete_item(
    request: Request,
    conn: Conn,
    item_id: int,
    ctx: Annotated[str, Form()] = "list",
):
    item = _require_item(conn, item_id)
    wishlist.remove(conn, item_id)
    if ctx == "shade":
        return render(request, "_shade_actions.html", actions_context(conn, item["shade_id"]))
    response = render(request, "_wishlist.html", _page_context(request, conn))
    response.headers.update(SHEET_CLOSE)
    return response
