import sqlite3

import pytest
from shade_data import made_from, seed, shade_id

from polished import bottles, shades
from polished.bottles import BottleInput


@pytest.fixture
def catalog(conn):
    seed(conn)
    return conn


def owned_count(conn, shade) -> int:
    return conn.execute(
        "select owned_count from shade_status where shade_id = ?", (shade,)
    ).fetchone()[0]


def add(conn, handle, **values) -> int:
    return bottles.add(conn, shade_id(conn, handle), BottleInput(**values))


def test_a_shade_can_have_several_bottles(catalog):
    first = add(catalog, "thirst-trap", printed_code="P259")
    second = add(catalog, "thirst-trap", printed_code="P260", state="half")
    shade = shade_id(catalog, "thirst-trap")
    assert first != second
    assert owned_count(catalog, shade) == 2
    assert [b["printed_code"] for b in bottles.for_shade(catalog, shade)] == ["P260", "P259"]
    assert shades.get_shade(catalog, shade)["owned_count"] == 2


def test_empty_and_archived_bottles_do_not_make_a_shade_owned(catalog):
    shade = shade_id(catalog, "thirst-trap")
    empty = add(catalog, "thirst-trap", state="empty")
    archived = add(catalog, "thirst-trap")
    bottles.set_archived(catalog, archived, True)
    row = catalog.execute("select * from shade_status where shade_id = ?", (shade,)).fetchone()
    assert (row["owned_count"], row["bottle_count"]) == (0, 2)

    keeper = add(catalog, "thirst-trap", state="low")
    assert owned_count(catalog, shade) == 1
    bottles.set_state(catalog, keeper, "empty")
    assert owned_count(catalog, shade) == 0
    bottles.set_state(catalog, empty, "half")
    bottles.set_archived(catalog, archived, False)
    assert owned_count(catalog, shade) == 2


def test_state_changes_and_rejects_an_unknown_state(catalog):
    bottle = add(catalog, "thirst-trap")
    for state in ("half", "low", "empty", "full"):
        bottles.set_state(catalog, bottle, state)
        assert bottles.get(catalog, bottle)["state"] == state
    with pytest.raises(ValueError):
        bottles.set_state(catalog, bottle, "mostly")
    with pytest.raises(sqlite3.IntegrityError):
        catalog.execute("update bottle set state = 'mostly' where id = ?", (bottle,))


def test_a_new_bottle_is_full_by_default(catalog):
    bottle = add(catalog, "thirst-trap")
    assert bottles.get(catalog, bottle)["state"] == "full"
    values, errors = bottles.parse_input()
    assert values.state == "full" and not errors


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("259", "P259"), ("p259", "P259"), (" p 259 ", "P259"), ("pp12", "PP12"), ("", None)],
)
def test_the_p_code_is_stored_uppercase_and_normalised(typed, stored):
    assert bottles.clean_printed_code(typed) == stored


def test_a_code_that_is_not_a_p_number_is_kept_uppercase_not_refused():
    values, errors = bottles.parse_input(printed_code="ab-12 x")
    assert values.printed_code == "AB-12X" and not errors


@pytest.mark.parametrize(
    ("typed", "cents"),
    [("15.50", 1550), ("15,5", 1550), ("$12", 1200), ("0.99", 99), (" 7.05 ", 705), ("", None)],
)
def test_parse_price(typed, cents):
    assert bottles.parse_price(typed) == cents


@pytest.mark.parametrize("typed", ["abc", "1.234", "-3", "12.5.0", "1e3"])
def test_parse_price_rejects_what_is_not_an_amount(typed):
    with pytest.raises(ValueError):
        bottles.parse_price(typed)


def test_parse_input_reports_each_wrong_field():
    values, errors = bottles.parse_input(
        state="mostly", bought_on="yesterday", opened_on="2026-02-30", price_paid="lots"
    )
    assert set(errors) == {"state", "bought_on", "opened_on", "price_paid"}
    assert values.state == "full"
    values, errors = bottles.parse_input(
        state="low",
        printed_code="259",
        bought_on="2026-10-25",
        price_paid="15.50",
        opened_on="2026-10-26",
        notes="  a gift  ",
    )
    assert not errors
    assert values == BottleInput("low", "P259", "2026-10-25", 1550, "2026-10-26", "a gift")


def test_update_changes_every_field(catalog):
    bottle = add(catalog, "thirst-trap", printed_code="P1")
    values, _ = bottles.parse_input("half", "300", "2026-01-02", "10", "2026-01-03", "note")
    bottles.update(catalog, bottle, values)
    row = bottles.get(catalog, bottle)
    assert (row["state"], row["printed_code"], row["bought_on"], row["price_paid_cents"]) == (
        "half",
        "P300",
        "2026-01-02",
        1000,
    )
    assert (row["opened_on"], row["notes"], row["title"]) == (
        "2026-01-03",
        "note",
        "Thirst Trap",
    )


def test_delete_removes_the_bottle(catalog):
    bottle = add(catalog, "thirst-trap")
    bottles.delete(catalog, bottle)
    assert bottles.get(catalog, bottle) is None


def test_groups_are_by_shade_and_filter_by_state_and_archive(catalog):
    a = add(catalog, "thirst-trap", state="half")
    add(catalog, "thirst-trap", state="full")
    add(catalog, "peely-base", state="empty")
    gone = add(catalog, "rest-in-peach")
    bottles.set_archived(catalog, gone, True)

    groups = bottles.list_groups(catalog)
    assert [g["title"] for g in groups] == ["Peely Base", "Thirst Trap"]
    assert [b["id"] for b in groups[1]["bottles"]] == [a + 1, a]
    assert [g["title"] for g in bottles.list_groups(catalog, "empty")] == ["Peely Base"]
    assert [g["title"] for g in bottles.list_groups(catalog, archived=True)] == ["Rest In Peach"]
    assert len(bottles.list_groups(catalog, "no-such-state")) == 2


def test_counts_and_recent(catalog):
    assert bottles.counts(catalog) == {"bottles": 0, "shades": 0}
    first = add(catalog, "thirst-trap")
    add(catalog, "thirst-trap")
    add(catalog, "peely-base", state="empty")
    archived = add(catalog, "rest-in-peach")
    bottles.set_archived(catalog, archived, True)
    assert bottles.counts(catalog) == {"bottles": 2, "shades": 1}
    recent = bottles.recent(catalog, 2)
    assert [b["id"] for b in recent] == [first + 2, first + 1]
    assert all(not b["archived"] for b in bottles.recent(catalog))


# Browse: badges, the owned filter and the ranking that follow from bottles and the wishlist


def titles(page):
    return [row["title"] for row in page.rows]


def test_list_rows_carry_owned_count_and_wishlist_flag(catalog):
    add(catalog, "thirst-trap")
    add(catalog, "thirst-trap")
    catalog.execute(
        "insert into wishlist_item (shade_id) values (?)", (shade_id(catalog, "peely-base"),)
    )
    rows = {r["title"]: r for r in shades.list_shades(catalog, shades.ShadeQuery(), size=100).rows}
    assert (rows["Thirst Trap"]["owned_count"], rows["Thirst Trap"]["wishlisted"]) == (2, 0)
    assert (rows["Peely Base"]["owned_count"], rows["Peely Base"]["wishlisted"]) == (0, 1)


def test_the_owned_filter(catalog):
    add(catalog, "thirst-trap")
    add(catalog, "peely-base", state="empty")
    catalog.execute(
        "insert into wishlist_item (shade_id) values (?)", (shade_id(catalog, "peely-base"),)
    )

    def find(owned):
        query = shades.ShadeQuery.from_params(owned=owned)
        return titles(shades.list_shades(catalog, query, size=100))

    assert find("owned") == ["Thirst Trap"]
    assert find("wishlist") == ["Peely Base"]
    not_owned = find("not_owned")
    assert "Thirst Trap" not in not_owned and "Peely Base" in not_owned
    everything = find("any")
    assert find("nonsense") == everything and len(everything) == 9
    assert shades.ShadeQuery.from_params(owned="owned").filter_count() == 1
    assert ("owned", "owned") in shades.ShadeQuery.from_params(owned="owned").params()


def test_the_home_search_ranks_owned_then_wishlisted_then_the_rest(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Pink Alpha"),
            made_from("thirst-trap", 2, "Pink Beta"),
            made_from("thirst-trap", 3, "Pink Gamma"),
        ],
    )
    gamma = shade_id(conn, "pink-gamma")
    conn.execute("insert into wishlist_item (shade_id) values (?)", (shade_id(conn, "pink-beta"),))
    bottles.add(conn, gamma, BottleInput())
    assert titles(shades.search(conn, "pink"))[:3] == ["Pink Gamma", "Pink Beta", "Pink Alpha"]
    # The browse list keeps its plain order.
    query = shades.ShadeQuery.from_params(q="pink")
    assert titles(shades.list_shades(conn, query))[:3] == ["Pink Alpha", "Pink Beta", "Pink Gamma"]


# Manual shades


def test_a_manual_shade_is_searchable_and_has_no_status(conn):
    seed(conn)
    new = shades.create_manual(conn, "  Crème   de la Gift ", "topper")
    shade = shades.get_shade(conn, new)
    assert (shade["source"], shade["title"], shade["kind"], shade["is_topper"]) == (
        "manual",
        "Crème de la Gift",
        "topcoat",
        1,
    )
    assert shade["status"] is None and shade["price_cents"] is None and shade["product_id"] is None
    found = shades.list_shades(conn, shades.ShadeQuery.from_params(q="creme gift"))
    assert titles(found) == ["Crème de la Gift"]
    toppers = titles(shades.list_shades(conn, shades.ShadeQuery.from_params(kind="topper")))
    assert "Crème de la Gift" in toppers


def test_a_manual_shade_needs_a_title_and_a_known_kind(conn):
    seed(conn)
    with pytest.raises(ValueError):
        shades.create_manual(conn, "   ", "polish")
    with pytest.raises(KeyError):
        shades.create_manual(conn, "Gift", "glitter")
    assert shades.get_shade(conn, shades.create_manual(conn, "Plain", "polish"))["kind"] == "polish"
    assert shades.get_shade(conn, shades.create_manual(conn, "Base", "base"))["kind"] == "basecoat"
