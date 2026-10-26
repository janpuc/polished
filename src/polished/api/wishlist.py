"""GET /wishlist."""

from typing import Annotated

from fastapi import APIRouter, Query

from .. import wishlist
from . import rows, schemas
from .routing import ApiRoute, AppSettings, Conn

router = APIRouter(prefix="/wishlist", route_class=ApiRoute, tags=["wishlist"])


@router.get("", response_model=schemas.Wishlist, summary="The wishlist and its cart link")
def wishlist_body(
    conn: Conn, settings: AppSettings, max_priority: Annotated[int, Query(ge=1, le=3)] = 3
):
    """Items by priority (1 first), the totals, and the shop's cart permalink for the buyable
    items up to `max_priority`."""
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
