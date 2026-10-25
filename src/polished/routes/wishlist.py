"""The wishlist and its cart permalink (DESIGN 13.3). Like the bottle routes, every route answers
with its fragment, with or without HX-Request."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from .. import shades, wishlist
from ..db import get_conn
from ..web import render
from .bottles import actions_context

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _cart_context(request: Request, rows: list[dict], max_priority: int) -> dict:
    return {"cart": wishlist.cart(rows, request.app.state.settings.store_url, max_priority)}


def _page_context(request: Request, conn: sqlite3.Connection) -> dict:
    rows = wishlist.items(conn)
    return {
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


@router.post("/wishlist/{item_id}")
def update_item(
    request: Request,
    conn: Conn,
    item_id: int,
    priority: Annotated[int, Form()],
    note: Annotated[str, Form()] = "",
):
    _require_item(conn, item_id)
    if priority not in wishlist.PRIORITIES:
        raise HTTPException(422, "priority must be 1, 2 or 3")
    wishlist.update(conn, item_id, priority, note)
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
    return render(request, "_wishlist.html", _page_context(request, conn))
