import sqlite3

import pytest
from shade_data import made_from, seed, shade_id

from polished import shades, wishlist

STORE = "https://holotaco.com"
LAST_STOCK = made_from(
    "thirst-trap", 1, "Last Stock", tags=["collection:retirement"], available=True
)


@pytest.fixture
def catalog(conn):
    seed(conn, [LAST_STOCK])
    return conn


def wish(conn, handle, priority=2) -> int:
    return wishlist.add(conn, shade_id(conn, handle), priority)


@pytest.fixture
def mixed(catalog):
    """Buyable, sold out, retired and unavailable, retired with last stock, no longer listed and
    manual shades, added in this order."""
    manual = shades.create_manual(catalog, "Gifted Glow", "polish")
    catalog.execute(
        "update product set missing_since = '2026-10-01T00:00:00Z' where handle = 'aurora-unicorn-skin'"
    )
    wish(catalog, "thirst-trap", 2)
    wish(catalog, "peely-base", 1)
    wish(catalog, "rest-in-peach", 3)
    wish(catalog, "gold-play-button", 1)
    wish(catalog, "hit-the-lights", 2)
    wish(catalog, "last-stock", 2)
    wish(catalog, "aurora-unicorn-skin", 1)
    wishlist.add(catalog, manual, 1)
    return catalog


def test_there_is_one_row_per_shade(catalog):
    shade = shade_id(catalog, "thirst-trap")
    first = wishlist.add(catalog, shade, 1)
    again = wishlist.add(catalog, shade, 3)
    assert first == again
    rows = catalog.execute("select * from wishlist_item").fetchall()
    assert len(rows) == 1 and rows[0]["priority"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        catalog.execute("insert into wishlist_item (shade_id) values (?)", (shade,))


def test_the_default_priority_is_2(catalog):
    item = catalog.execute(
        "insert into wishlist_item (shade_id) values (?)", (shade_id(catalog, "thirst-trap"),)
    ).lastrowid
    assert wishlist.get(catalog, item)["priority"] == 2
    assert wishlist.get(catalog, item)["added_on"]


@pytest.mark.parametrize("priority", [0, 4, -1])
def test_priority_is_bounded_to_1_to_3(catalog, priority):
    shade = shade_id(catalog, "thirst-trap")
    with pytest.raises(ValueError):
        wishlist.add(catalog, shade, priority)
    item = wishlist.add(catalog, shade)
    with pytest.raises(ValueError):
        wishlist.update(catalog, item, priority, None)
    with pytest.raises(sqlite3.IntegrityError):
        catalog.execute("update wishlist_item set priority = ?", (priority,))


def test_update_sets_priority_and_a_trimmed_note(catalog):
    item = wish(catalog, "thirst-trap")
    wishlist.update(catalog, item, 1, "  for the wedding  ")
    row = wishlist.get(catalog, item)
    assert (row["priority"], row["note"]) == (1, "for the wedding")
    wishlist.update(catalog, item, 3, "   ")
    assert wishlist.get(catalog, item)["note"] is None


def test_remove_and_lookup_by_shade(catalog):
    item = wish(catalog, "thirst-trap")
    assert wishlist.for_shade(catalog, shade_id(catalog, "thirst-trap"))["id"] == item
    wishlist.remove(catalog, item)
    assert wishlist.get(catalog, item) is None
    assert wishlist.for_shade(catalog, shade_id(catalog, "thirst-trap")) is None


def test_items_are_ordered_by_priority_then_age_and_grouped(mixed):
    rows = wishlist.items(mixed)
    assert [(r["priority"], r["title"]) for r in rows] == [
        (1, "Peely Base"),
        (1, "Gold Play Button"),
        (1, "Aurora Unicorn Skin™"),
        (1, "Gifted Glow"),
        (2, "Thirst Trap"),
        (2, "Hit The Lights"),
        (2, "Last Stock"),
        (3, "Rest In Peach"),
    ]
    groups = wishlist.groups(rows)
    assert [(g["priority"], len(g["rows"])) for g in groups] == [(1, 4), (2, 3), (3, 1)]
    assert [g["label"] for g in groups] == ["Want most", "Would like", "Maybe one day"]
    assert wishlist.groups([]) == []


def test_totals_count_all_items_and_the_buyable_ones_separately(mixed):
    assert wishlist.summary(wishlist.items(mixed)) == {
        "count": 8,
        "total_cents": 10250,
        "buyable_count": 4,
        "buyable_cents": 5800,
    }
    assert wishlist.summary([]) == {
        "count": 0,
        "total_cents": 0,
        "buyable_count": 0,
        "buyable_cents": 0,
    }


def test_the_permalink_is_exact_and_lists_buyable_items_only(mixed):
    cart = wishlist.cart(wishlist.items(mixed), STORE)
    # Priority 1 first, then 2, then 3, oldest first inside a priority. Left out: Gold Play
    # Button (retired, unavailable), Hit The Lights (sold out), Aurora Unicorn Skin (no longer
    # listed) and Gifted Glow (manual, no variant).
    assert cart.url == (
        "https://holotaco.com/cart/30936560795738:1,42093180747866:1,6000000001:1,40243922305114:1"
    )
    assert [i["title"] for i in cart.items] == [
        "Peely Base",
        "Thirst Trap",
        "Last Stock",
        "Rest In Peach",
    ]
    assert (cart.total_cents, cart.skipped, cart.max_priority) == (5800, 4, 3)
    assert cart.names == "Peely Base\nThirst Trap\nLast Stock\nRest In Peach"


def test_retired_with_last_stock_is_buyable_and_retired_unavailable_is_not(mixed):
    by_title = {r["title"]: r for r in wishlist.items(mixed)}
    assert by_title["Last Stock"]["status"].label == "Retired, last stock"
    assert by_title["Last Stock"]["buyable"]
    assert not by_title["Gold Play Button"]["buyable"]
    assert by_title["Aurora Unicorn Skin™"]["status"].key == "missing"
    assert by_title["Gifted Glow"]["status"] is None and not by_title["Gifted Glow"]["buyable"]


def test_max_priority_limits_the_permalink(mixed):
    rows = wishlist.items(mixed)
    one = wishlist.cart(rows, STORE, 1)
    assert one.url == "https://holotaco.com/cart/30936560795738:1"
    assert (one.max_priority, one.skipped, one.total_cents) == (1, 3, 1350)
    two = wishlist.cart(rows, STORE, 2)
    assert two.url == "https://holotaco.com/cart/30936560795738:1,42093180747866:1,6000000001:1"
    assert two.skipped == 4
    # An out-of-range value means everything.
    assert wishlist.cart(rows, STORE, 9).url == wishlist.cart(rows, STORE, 3).url
    assert wishlist.cart(rows, STORE, 0).max_priority == 3


def test_nothing_buyable_gives_no_permalink(catalog):
    wish(catalog, "gold-play-button")
    wish(catalog, "hit-the-lights")
    cart = wishlist.cart(wishlist.items(catalog), STORE)
    assert cart.url is None and cart.items == [] and cart.skipped == 2
    assert wishlist.cart([], STORE).url is None


def test_the_permalink_uses_the_configured_store(mixed):
    cart = wishlist.cart(wishlist.items(mixed), "https://shop.example", 1)
    assert cart.url == "https://shop.example/cart/30936560795738:1"
