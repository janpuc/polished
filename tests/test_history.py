import pytest
from shade_data import seed, shade_id

from polished import bottles, wishlist


@pytest.fixture
def catalog(conn):
    seed(conn)
    return conn


def buy(conn, handle, bought_on=None, price=None, state="full", archived=False, created=None):
    values = bottles.BottleInput(state=state, bought_on=bought_on, price_paid_cents=price)
    bottle_id = bottles.add(conn, shade_id(conn, handle), values)
    if archived:
        bottles.set_archived(conn, bottle_id, True)
    if created:
        conn.execute("update bottle set created_at = ? where id = ?", (created, bottle_id))
    return bottle_id


def test_no_bottles_is_no_history(catalog):
    assert bottles.history(catalog) == []


def test_bottles_group_by_year_and_month_newest_first(catalog):
    buy(catalog, "thirst-trap", "2025-12-30", 1550)
    buy(catalog, "peely-base", "2026-10-03", 1550)
    buy(catalog, "hit-the-lights", "2026-10-20", 1000)
    buy(catalog, "rest-in-peach", "2026-02-14", 1200)
    years = bottles.history(catalog)
    assert [y["year"] for y in years] == ["2026", "2025"]
    assert [m["label"] for m in years[0]["months"]] == ["October 2026", "February 2026"]
    october = years[0]["months"][0]
    assert [r["title"] for r in october["rows"]] == ["Hit The Lights", "Peely Base"]
    assert [m["label"] for m in years[1]["months"]] == ["December 2025"]


def test_totals_per_month_and_year(catalog):
    buy(catalog, "thirst-trap", "2026-10-03", 1550)
    buy(catalog, "peely-base", "2026-10-20", 1000)
    buy(catalog, "rest-in-peach", "2026-02-14", 1200)
    year = bottles.history(catalog)[0]
    assert (year["count"], year["total_cents"], year["unpriced"]) == (3, 3750, 0)
    october, february = year["months"]
    assert (october["count"], october["total_cents"]) == (2, 2550)
    assert (february["count"], february["total_cents"]) == (1, 1200)
    assert october["count_text"] == "2 bottles" and february["count_text"] == "1 bottle"


def test_a_bottle_without_a_price_is_counted_but_not_added(catalog):
    buy(catalog, "thirst-trap", "2026-10-03", 1550)
    buy(catalog, "peely-base", "2026-10-04", None)
    buy(catalog, "hit-the-lights", "2026-10-05", None)
    year = bottles.history(catalog)[0]
    month = year["months"][0]
    assert (month["count"], month["total_cents"], month["unpriced"]) == (3, 1550, 2)
    assert (year["count"], year["total_cents"], year["unpriced"]) == (3, 1550, 2)


def test_a_free_bottle_is_priced_at_zero(catalog):
    buy(catalog, "thirst-trap", "2026-10-03", 0)
    month = bottles.history(catalog)[0]["months"][0]
    assert (month["total_cents"], month["unpriced"]) == (0, 0)


def test_a_bottle_without_bought_on_falls_back_to_the_date_it_was_entered(catalog):
    buy(catalog, "thirst-trap", None, created="2026-08-09T22:30:00Z")
    buy(catalog, "peely-base", "2026-08-01")
    month = bottles.history(catalog)[0]["months"][0]
    assert month["label"] == "August 2026"
    by_title = {r["title"]: r for r in month["rows"]}
    assert by_title["Thirst Trap"]["date"] == "2026-08-09"
    assert by_title["Thirst Trap"]["dated_by_entry"] is True
    assert by_title["Peely Base"]["dated_by_entry"] is False
    assert [r["title"] for r in month["rows"]] == ["Thirst Trap", "Peely Base"]


def test_archived_and_empty_bottles_are_history_too(catalog):
    buy(catalog, "thirst-trap", "2026-10-03", 1550, state="empty")
    buy(catalog, "peely-base", "2026-10-04", 1550, archived=True)
    buy(catalog, "hit-the-lights", "2026-10-05", 1550)
    year = bottles.history(catalog)[0]
    assert year["count"] == 3 and year["total_cents"] == 4650


def test_the_same_day_is_ordered_by_entry_newest_first(catalog):
    first = buy(catalog, "thirst-trap", "2026-10-03")
    second = buy(catalog, "peely-base", "2026-10-03")
    rows = bottles.history(catalog)[0]["months"][0]["rows"]
    assert [r["id"] for r in rows] == [second, first]


def test_group_history_is_pure():
    rows = [
        {
            "id": 1,
            "bought_on": "2026-01-31",
            "created_at": "2026-05-01T00:00:00Z",
            "price_paid_cents": 500,
        },
        {
            "id": 2,
            "bought_on": None,
            "created_at": "2026-02-01T10:00:00Z",
            "price_paid_cents": None,
        },
    ]
    years = bottles.group_history(rows)
    assert [m["label"] for m in years[0]["months"]] == ["February 2026", "January 2026"]


# mark_bought


def test_mark_bought_makes_full_bottles_and_removes_the_items(catalog):
    a = wishlist.add(catalog, shade_id(catalog, "thirst-trap"))
    b = wishlist.add(catalog, shade_id(catalog, "peely-base"))
    keep = wishlist.add(catalog, shade_id(catalog, "hit-the-lights"))
    new_ids = wishlist.mark_bought(catalog, [(a, 1550), (b, None)], "2026-10-25")
    assert len(new_ids) == 2
    rows = [bottles.get(catalog, i) for i in new_ids]
    assert [r["title"] for r in rows] == ["Thirst Trap", "Peely Base"]
    assert [(r["state"], r["bought_on"], r["price_paid_cents"]) for r in rows] == [
        ("full", "2026-10-25", 1550),
        ("full", "2026-10-25", None),
    ]
    assert [i["id"] for i in wishlist.items(catalog)] == [keep]


def test_mark_bought_changes_nothing_for_an_unknown_item(catalog):
    a = wishlist.add(catalog, shade_id(catalog, "thirst-trap"))
    with pytest.raises(LookupError):
        wishlist.mark_bought(catalog, [(a, 1550), (9999, None)], "2026-10-25")
    assert catalog.execute("select count(*) from bottle").fetchone()[0] == 0
    assert wishlist.get(catalog, a) is not None
    assert not catalog.in_transaction


def test_mark_bought_refuses_no_items_a_repeat_and_a_bad_date(catalog):
    a = wishlist.add(catalog, shade_id(catalog, "thirst-trap"))
    for items, day in (
        ([], "2026-10-25"),
        ([(a, None), (a, None)], "2026-10-25"),
        ([(a, None)], "soon"),
    ):
        with pytest.raises(ValueError):
            wishlist.mark_bought(catalog, items, day)
    assert catalog.execute("select count(*) from bottle").fetchone()[0] == 0


def test_mark_bought_rolls_back_when_a_write_fails(catalog, monkeypatch):
    a = wishlist.add(catalog, shade_id(catalog, "thirst-trap"))
    b = wishlist.add(catalog, shade_id(catalog, "peely-base"))
    real_remove = wishlist.remove

    def failing(conn, item_id):
        if item_id == b:
            raise RuntimeError("disk full")
        real_remove(conn, item_id)

    monkeypatch.setattr(wishlist, "remove", failing)
    with pytest.raises(RuntimeError):
        wishlist.mark_bought(catalog, [(a, 100), (b, 100)], "2026-10-25")
    assert catalog.execute("select count(*) from bottle").fetchone()[0] == 0
    assert len(wishlist.items(catalog)) == 2
