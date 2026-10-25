"""The wishlist: one row per shade, a priority, totals and the Shopify cart permalink
(DESIGN 4.2, 13.3)."""

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from . import bottles
from .db import atomic
from .shades import status
from .tips import TIP_FIELDS

PRIORITIES = (1, 2, 3)
PRIORITY_LABELS = {1: "Want most", 2: "Would like", 3: "Maybe one day"}
NOTE_LIMIT = 200

# wishlist_item w join shade s left join product p: what a wishlist row shows and the cart needs.
_SELECT = (
    "select w.id, w.shade_id, w.priority, w.note, w.added_on, s.title, s.hero_image_url,"
    " s.source, s.price_cents, s.available, s.retired, s.retiring, p.missing_since,"
    f" p.variant_id, ss.owned_count, {TIP_FIELDS}"
    " from wishlist_item w join shade s on s.id = w.shade_id"
    " left join product p on p.id = s.product_id"
    " join shade_status ss on ss.shade_id = s.id"
)
_ORDER = " order by w.priority, w.id"


def add(conn: sqlite3.Connection, shade_id: int, priority: int = 2) -> int:
    """Wishlists the shade; a shade already on the list keeps its row and priority.
    Returns the item id."""
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be 1 to 3, got {priority!r}")
    conn.execute(
        "insert into wishlist_item (shade_id, priority) values (?, ?)"
        " on conflict (shade_id) do nothing",
        (shade_id, priority),
    )
    row = conn.execute("select id from wishlist_item where shade_id = ?", (shade_id,)).fetchone()
    return row["id"]


def update(conn: sqlite3.Connection, item_id: int, priority: int, note: str | None) -> None:
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be 1 to 3, got {priority!r}")
    conn.execute(
        "update wishlist_item set priority = ?, note = ? where id = ?",
        (priority, (note or "").strip()[:NOTE_LIMIT] or None, item_id),
    )


def remove(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute("delete from wishlist_item where id = ?", (item_id,))


def _view(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["status"] = status(item)
    # A manual shade has no listing; a product that left the feed cannot be bought either.
    item["buyable"] = bool(item["status"] and item["status"].buyable)
    return item


def get(conn: sqlite3.Connection, item_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} where w.id = ?", (item_id,)).fetchone()
    return _view(row) if row else None


def for_shade(conn: sqlite3.Connection, shade_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} where w.shade_id = ?", (shade_id,)).fetchone()
    return _view(row) if row else None


def items(conn: sqlite3.Connection) -> list[dict]:
    """Every item, priority 1 first, oldest first inside a priority."""
    return [_view(r) for r in conn.execute(_SELECT + _ORDER)]


def groups(wishlist: list[dict]) -> list[dict]:
    """The items as the priority groups; an empty group is left out."""
    return [
        {"priority": p, "label": PRIORITY_LABELS[p], "rows": rows}
        for p in PRIORITIES
        if (rows := [i for i in wishlist if i["priority"] == p])
    ]


def summary(wishlist: list[dict]) -> dict[str, int]:
    """Counts and prices: the total of every priced item, and of the buyable ones."""
    return {
        "count": len(wishlist),
        "total_cents": sum(i["price_cents"] or 0 for i in wishlist),
        "buyable_count": sum(i["buyable"] for i in wishlist),
        "buyable_cents": sum(i["price_cents"] or 0 for i in wishlist if i["buyable"]),
    }


@dataclass
class Cart:
    max_priority: int
    items: list[dict] = field(default_factory=list)
    url: str | None = None  # None when nothing is buyable
    total_cents: int = 0
    skipped: int = 0  # items up to max_priority that cannot be bought now

    @property
    def names(self) -> str:
        """The "Copy the list" text: one title per line, for ordering by hand."""
        return "\n".join(item["title"] for item in self.items)


def cart(wishlist: list[dict], store_url: str, max_priority: int = PRIORITIES[-1]) -> Cart:
    """Cart permalink `<store>/cart/<variant_id>:1,<variant_id>:1,…` for the buyable items with a
    priority up to `max_priority`, in list order. Sold-out, retired-unavailable, no-longer-listed
    and manual shades are left out, so the permalink never carries a variant that cannot be
    bought. An out-of-range `max_priority` means all priorities."""
    if max_priority not in PRIORITIES:
        max_priority = PRIORITIES[-1]
    wanted = [i for i in wishlist if i["priority"] <= max_priority]
    buyable = [i for i in wanted if i["buyable"]]
    url = None
    if buyable:
        url = f"{store_url}/cart/" + ",".join(f"{i['variant_id']}:1" for i in buyable)
    return Cart(
        max_priority=max_priority,
        items=buyable,
        url=url,
        total_cents=sum(i["price_cents"] or 0 for i in buyable),
        skipped=len(wanted) - len(buyable),
    )


def mark_bought(
    conn: sqlite3.Connection, items: list[tuple[int, int | None]], bought_on: str
) -> list[int]:
    """Turns wishlist items into bottles: for each (item id, price paid in cents or None) one full
    bottle of the item's shade bought on `bought_on` (an ISO date), and the item is removed, all or
    nothing. Returns the new bottle ids in the order given. Raises LookupError for an unknown item,
    ValueError for no items, a repeated item or a date that is not YYYY-MM-DD; nothing is written
    then."""
    date.fromisoformat(bought_on)
    if not items:
        raise ValueError("no items")
    ids = [item_id for item_id, _ in items]
    if len(set(ids)) != len(ids):
        raise ValueError("an item was listed twice")
    with atomic(conn):
        shade_ids = {}
        for item_id in ids:
            row = conn.execute(
                "select shade_id from wishlist_item where id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"no wishlist item {item_id}")
            shade_ids[item_id] = row["shade_id"]
        new_ids = []
        for item_id, price_cents in items:
            values = bottles.BottleInput(bought_on=bought_on, price_paid_cents=price_cents)
            new_ids.append(bottles.add(conn, shade_ids[item_id], values))
            remove(conn, item_id)
    return new_ids
