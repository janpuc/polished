"""The wishlist: GET /wishlist, and the writes (add, change, remove, mark as bought)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from .. import bottles, wishlist
from . import rows, schemas
from .bottles import MAX_PRICE_CENTS, PRICE_MESSAGE, shade_or_404
from .errors import invalid, not_found
from .routing import ApiRoute, AppSettings, Conn, household_today

router = APIRouter(route_class=ApiRoute, tags=["wishlist"])

PRIORITY_MESSAGE = "Priority must be 1, 2 or 3."


def wishlist_item(conn, item: dict) -> schemas.WishlistItem:
    shade = rows.rows_by_id(conn, [item["shade_id"]])[item["shade_id"]]
    return schemas.WishlistItem(
        id=item["id"],
        shade=shade,
        priority=item["priority"],
        note=item["note"],
        added_on=item["added_on"],
        buyable=item["buyable"],
    )


def wishlist_response(conn, settings, max_priority: int = 3) -> schemas.Wishlist:
    items = wishlist.items(conn)
    cart = wishlist.cart(items, settings.store_url, max_priority)
    shade_rows = rows.rows_by_id(conn, [i["shade_id"] for i in items])
    return schemas.Wishlist(
        items=[
            schemas.WishlistItem(
                id=i["id"],
                shade=shade_rows[i["shade_id"]],
                priority=i["priority"],
                note=i["note"],
                added_on=i["added_on"],
                buyable=i["buyable"],
            )
            for i in items
        ],
        summary=wishlist.summary(items),
        cart=schemas.Cart(
            url=cart.url,
            total_cents=cart.total_cents,
            count=len(cart.items),
            skipped=cart.skipped,
            names=[i["title"] for i in cart.items],
        ),
    )


def item_or_404(conn, item_id: int) -> dict:
    item = wishlist.get(conn, item_id)
    if item is None:
        raise not_found("No such wishlist item.")
    return item


@router.get("/wishlist", response_model=schemas.Wishlist, summary="The wishlist and its cart link")
def wishlist_body(
    conn: Conn, settings: AppSettings, max_priority: Annotated[int, Query(ge=1, le=3)] = 3
):
    """Items by priority (1 first), the totals, and the shop's cart permalink for the buyable
    items up to `max_priority`."""
    return wishlist_response(conn, settings, max_priority)


@router.put(
    "/shades/{shade_id}/wishlist",
    response_model=schemas.WishlistItem,
    summary="Put a shade on the wishlist",
    responses={404: {"description": "`not_found`: no such shade."}},
)
def add_to_wishlist(conn: Conn, shade_id: int, body: schemas.WishlistAdd):
    """Idempotent: a shade already on the list keeps its row, priority and note."""
    shade_or_404(conn, shade_id)
    if body.priority not in wishlist.PRIORITIES:
        raise invalid({"priority": PRIORITY_MESSAGE})
    item_id = wishlist.add(conn, shade_id, body.priority)
    return wishlist_item(conn, wishlist.get(conn, item_id))


@router.patch(
    "/wishlist/{item_id}",
    response_model=schemas.Wishlist,
    summary="Change an item's priority or note",
    responses={404: {"description": "`not_found`"}, 422: {"description": "`validation`"}},
)
def edit_wishlist_item(
    conn: Conn, settings: AppSettings, item_id: int, body: schemas.WishlistPatch
):
    """Fields left out stay as they are; an empty or `null` note clears it. Answers the whole
    wishlist, which is what changed."""
    item = item_or_404(conn, item_id)
    sent = body.model_fields_set
    priority = body.priority if "priority" in sent else item["priority"]
    if priority not in wishlist.PRIORITIES:
        raise invalid({"priority": PRIORITY_MESSAGE})
    wishlist.update(conn, item_id, priority, body.note if "note" in sent else item["note"])
    return wishlist_response(conn, settings)


@router.delete(
    "/wishlist/{item_id}",
    status_code=204,
    summary="Take an item off the wishlist",
    responses={404: {"description": "`not_found`"}},
)
def remove_wishlist_item(conn: Conn, item_id: int) -> Response:
    item_or_404(conn, item_id)
    wishlist.remove(conn, item_id)
    return Response(status_code=204)


@router.post(
    "/wishlist/bought",
    response_model=schemas.Bought,
    summary="I bought these",
    responses={
        404: {"description": "`not_found`: an item is not on the wishlist. Nothing changed."},
        422: {"description": "`validation`. Nothing changed."},
    },
)
def mark_bought(conn: Conn, settings: AppSettings, body: schemas.BoughtRequest):
    """One full bottle per item, bought on one date, with the price paid (or none), and the items
    leave the wishlist, all in one transaction: if anything is wrong nothing changes."""
    ids = [item.id for item in body.items]
    known = {i["id"] for i in wishlist.items(conn)}
    if not known.issuperset(ids):
        raise not_found("No such wishlist item.")
    errors = {}
    if not ids:
        errors["items"] = "Tick the shades you bought."
    elif len(set(ids)) != len(ids):
        errors["items"] = "An item was listed twice."
    for position, item in enumerate(body.items):
        if item.price_cents is not None and not 0 <= item.price_cents <= MAX_PRICE_CENTS:
            errors[f"items.{position}.price_cents"] = PRICE_MESSAGE
    today = household_today(settings)
    bought_on = (body.bought_on or "").strip() or today.isoformat()
    try:
        if date.fromisoformat(bought_on) > today:
            errors["bought_on"] = bottles.FUTURE_DATE
        bought_on = date.fromisoformat(bought_on).isoformat()
    except ValueError:
        errors["bought_on"] = "Use a date like 2026-10-25."
    if errors:
        raise invalid(errors)
    try:
        new_ids = wishlist.mark_bought(
            conn, [(item.id, item.price_cents) for item in body.items], bought_on
        )
    except LookupError:
        raise not_found("No such wishlist item.") from None
    return schemas.Bought(
        bottles=[rows.bottle(bottles.get(conn, i)) for i in new_ids],
        wishlist=wishlist_response(conn, settings),
    )
