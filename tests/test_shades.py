import pytest
from shade_data import made_from, seed, shade_id

from polished import shades
from polished.shades import ShadeQuery, Status, status


def titles(page):
    return [row["title"] for row in page.rows]


def find(conn, **params):
    return shades.list_shades(conn, ShadeQuery.from_params(**params), size=200)


@pytest.fixture
def catalog(conn):
    seed(conn)
    return conn


# Search


def test_tokens_are_folded_and_split_on_punctuation():
    assert shades.tokens("  Crème-Brûlée!  ") == ["creme", "brulee"]
    assert shades.tokens("don't") == ["don", "t"]
    assert shades.tokens("   ") == []


def test_every_token_must_match_in_any_order(catalog):
    assert titles(find(catalog, q="thirst trap")) == ["Thirst Trap"]
    assert titles(find(catalog, q="trap thirst")) == ["Thirst Trap"]
    assert titles(find(catalog, q="thirst zebra")) == []


def test_search_reads_tag_values_and_handle_words(catalog):
    assert "Thirst Trap" in titles(find(catalog, q="flakie red"))
    assert titles(find(catalog, q="peely")) == ["Peely Base"]


def test_search_folds_accents_on_both_sides(conn):
    seed(conn, [made_from("thirst-trap", 1, "Crème Brûlée")])
    assert titles(find(conn, q="creme brulee")) == ["Crème Brûlée"]
    assert "Crème Brûlée" in titles(find(conn, q="CRÈME"))


def test_search_ranks_titles_that_start_with_the_query_first(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Alpha Pink"),
            made_from("thirst-trap", 2, "Pink Zebra"),
            made_from("thirst-trap", 3, "Pinkie Pie"),
            made_from("thirst-trap", 4, "Beta Pink"),
        ],
    )
    # Aurora Unicorn Skin also matches, through its color:pink tag, and sorts among the rest.
    assert titles(find(conn, q="pink")) == [
        "Pink Zebra",
        "Pinkie Pie",
        "Alpha Pink",
        "Aurora Unicorn Skin™",
        "Beta Pink",
    ]


def test_the_home_search_returns_at_most_30_rows_and_the_total(conn):
    seed(conn, [made_from("thirst-trap", n, f"Berry {n:02d}") for n in range(40)])
    result = shades.search(conn, "berry")
    assert len(result.rows) == shades.SEARCH_LIMIT == 30
    assert result.total == 40
    assert titles(result)[0] == "Berry 00"


def test_a_search_treats_percent_and_underscore_as_plain_characters(catalog):
    assert titles(find(catalog, q="100%")) == []
    assert titles(find(catalog, q="_")) == titles(find(catalog))


# Filters


def test_finish_filter_is_any_of(catalog):
    assert titles(find(catalog, finish=["flakie"])) == ["Aurora Unicorn Skin™", "Thirst Trap"]
    assert titles(find(catalog, finish=["flakie", "creme"])) == [
        "Aurora Unicorn Skin™",
        "Rest In Peach",
        "Royal-Tea Blue",
        "Thirst Trap",
    ]


def test_color_filter_is_any_of_and_combines_with_finish_by_and(catalog):
    assert titles(find(catalog, color=["blue"])) == [
        "Aurora Unicorn Skin™",
        "Hit The Lights",
        "Royal-Tea Blue",
    ]
    assert titles(find(catalog, color=["blue", "red"], finish=["flakie"])) == [
        "Aurora Unicorn Skin™",
        "Thirst Trap",
    ]


def test_collection_filter_takes_one_collection(catalog):
    assert titles(find(catalog, collection="soon-retiring")) == ["Jam Session", "Rest In Peach"]
    assert titles(find(catalog, collection="nowhere")) == []


def test_kind_filter_splits_the_catalog_in_three(catalog):
    assert titles(find(catalog, kind="topper")) == ["Aurora Unicorn Skin™", "Sticky Base"]
    assert titles(find(catalog, kind="base")) == ["Peely Base"]
    polish = titles(find(catalog, kind="polish"))
    assert "Thirst Trap" in polish
    assert not {"Aurora Unicorn Skin™", "Sticky Base", "Peely Base"} & set(polish)
    assert len(polish) + 2 + 1 == find(catalog).total == 9


def test_status_filters(catalog):
    assert titles(find(catalog, status="buyable")) == [
        "Aurora Unicorn Skin™",
        "Peely Base",
        "Rest In Peach",
        "Royal-Tea Blue",
        "Sticky Base",
        "Thirst Trap",
    ]
    assert titles(find(catalog, status="retired")) == ["Gold Play Button"]
    assert titles(find(catalog, status="sold_out")) == ["Hit The Lights", "Jam Session"]


def test_unknown_filter_values_mean_no_filter(catalog):
    assert find(catalog, kind="gadget", status="soon", sort="random").total == 9
    assert find(catalog, finish=[""], color=[""]).total == 9


def test_a_filter_and_the_row_status_agree_on_every_shade(catalog):
    catalog.execute("update product set missing_since = '2026-10-01' where handle = 'peely-base'")
    catalog.execute("update shade set available = 1 where handle = 'gold-play-button'")
    everything = find(catalog).rows
    for key in ("buyable", "retired", "sold_out"):
        expected = {
            r["title"]
            for r in everything
            if (r["status"].buyable if key == "buyable" else r["status"].key == key)
        }
        assert set(titles(find(catalog, status=key))) == expected


def test_a_missing_product_is_in_no_status_filter(catalog):
    catalog.execute("update product set missing_since = '2026-10-01' where handle = 'thirst-trap'")
    for key in ("buyable", "retired", "sold_out"):
        assert "Thirst Trap" not in titles(find(catalog, status=key))
    assert "Thirst Trap" in titles(find(catalog))


# Sorting and pages


def test_sort_by_name_newest_and_price(conn):
    seed(
        conn,
        [
            made_from(
                "thirst-trap", 1, "Old One", price="20.00", published="2020-01-01T00:00:00-05:00"
            ),
            made_from(
                "thirst-trap", 2, "New One", price="9.00", published="2026-10-20T00:00:00-04:00"
            ),
        ],
    )
    assert titles(find(conn))[:3] == ["Aurora Unicorn Skin™", "Gold Play Button", "Hit The Lights"]
    newest = titles(find(conn, sort="newest"))
    assert newest[0] == "New One"
    assert newest.index("Old One") > newest.index("New One")
    cheapest = titles(find(conn, sort="price"))
    assert cheapest[0] == "New One"
    assert cheapest[-1] == "Old One"


def test_sort_by_price_puts_manual_shades_without_a_price_last(catalog):
    catalog.execute(
        "insert into shade (source, kind, title, search_text) values ('manual', 'polish', 'Gift', 'gift')"
    )
    assert titles(find(catalog, sort="price"))[-1] == "Gift"


def test_pages_hold_40_rows_and_say_whether_more_follow(conn):
    seed(conn, [made_from("thirst-trap", n, f"Berry {n:02d}") for n in range(45)])
    first = shades.list_shades(conn, ShadeQuery())
    second = shades.list_shades(conn, ShadeQuery(), page=2)
    third = shades.list_shades(conn, ShadeQuery(), page=3)
    assert (len(first.rows), first.total, first.has_more) == (40, 54, True)
    assert (len(second.rows), second.has_more) == (14, False)
    assert third.rows == []
    assert not {r["id"] for r in first.rows} & {r["id"] for r in second.rows}
    assert shades.list_shades(conn, ShadeQuery(), page=0).page == 1


def test_query_params_keep_only_what_differs_from_the_defaults():
    query = ShadeQuery.from_params(
        q=" pink ", finish=["flakie", "flakie"], status="buyable", sort="price"
    )
    assert query.params(page=3) == [
        ("q", "pink"),
        ("finish", "flakie"),
        ("status", "buyable"),
        ("sort", "price"),
        ("page", "3"),
    ]
    assert ShadeQuery().params() == []
    assert query.filter_count() == 2


# Status (DESIGN 5.3): a row per outcome


def state(**values):
    row = {
        "source": "holotaco",
        "missing_since": None,
        "retired": 0,
        "retiring": 0,
        "available": 1,
        "price_cents": 1550,
        "compare_at_cents": None,
    }
    return {**row, **values}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (state(missing_since="2026-10-01", retired=1), Status("missing", "Not listed", False)),
        (state(retired=1, available=1), Status("retired", "Retired, last stock", True)),
        (state(retired=1, available=0), Status("retired", "Retired", False)),
        (state(available=0), Status("sold_out", "Sold out", False)),
        (state(available=0, retiring=1), Status("sold_out", "Sold out, retiring", False)),
        (state(retiring=1), Status("retiring", "Retiring soon", True)),
        (state(), Status("available", "In stock", True)),
        (state(source="manual", available=None), None),
        (state(source="sheet", available=None), Status("sheet_only", "Not in the shop", False)),
        (
            state(source="sheet", available=None, retired=1),
            Status("sheet_only", "Not in the shop", False),
        ),
    ],
)
def test_status_table(row, expected):
    assert status(row) == expected


def test_a_sale_is_a_strictly_lower_price():
    assert shades.on_sale(state(compare_at_cents=1650))
    assert not shades.on_sale(state(compare_at_cents=1550))
    assert not shades.on_sale(state(compare_at_cents=None))


def test_rows_carry_their_status_and_finishes(catalog):
    rows = {r["title"]: r for r in find(catalog).rows}
    assert rows["Thirst Trap"]["status"].key == "available"
    assert rows["Gold Play Button"]["status"].key == "retired"
    assert rows["Jam Session"]["status"].label == "Sold out, retiring"
    assert rows["Rest In Peach"]["status"].key == "retiring"
    assert rows["Jam Session"]["finishes"] == ["holographic", "iridescent", "shimmer"]


# Facets and detail


def test_facets_list_what_the_catalog_has(catalog):
    facets = shades.facets(catalog)
    assert "flakie" in facets["finish"] and "creme" in facets["finish"]
    assert facets["finish"][0] in ("holographic", "creme", "flakie")  # the most common first
    assert "red" in facets["color"]
    assert facets["collection"] == sorted(facets["collection"])


def test_detail_has_images_tags_status_and_sale(catalog):
    shade = shades.get_shade(catalog, shade_id(catalog, "rest-in-peach"))
    assert shade["title"] == "Rest In Peach"
    assert shade["status"].key == "retiring"
    assert shade["on_sale"] is True
    assert len(shade["images"]) == 2 and shade["images"][0] == shade["hero_image_url"]
    assert shade["tags"]["finish"] == ["creme"]
    assert "soon-retiring" in shade["tags"]["collection"]
    assert "raw_json" not in shade


def test_detail_of_a_missing_shade_and_a_manual_one(catalog):
    catalog.execute("update product set missing_since = '2026-10-01' where handle = 'thirst-trap'")
    assert shades.get_shade(catalog, shade_id(catalog, "thirst-trap"))["status"].key == "missing"
    manual = catalog.execute(
        "insert into shade (source, kind, title, search_text) values ('manual', 'polish', 'Gift', 'gift')"
    ).lastrowid
    detail = shades.get_shade(catalog, manual)
    assert detail["status"] is None and detail["images"] == [] and detail["on_sale"] is False
    assert shades.get_shade(catalog, 9999) is None


# The release sheet: sort, collection filter, sheet-only shades


@pytest.fixture
def sheeted(catalog):
    from conftest import FIXTURES

    from polished.catalog import sheet

    text = (FIXTURES / "release_sheet_trimmed.csv").read_text(encoding="utf-8")
    sheet.apply_sheet(catalog, sheet.parse_sheet(text, min_rows=1))
    return catalog


def test_sort_by_release_date_puts_the_newest_first_and_the_undated_last(sheeted):
    order = titles(find(sheeted, sort="released"))
    assert order[:4] == ["Hit The Lights", "Diamond Dasher Taco", "Silent Night", "Thirst Trap"]
    assert (
        order.index("Aurora Unicorn Skin™")
        < order.index("Play Rosé")
        < order.index("Royal-Tea Blue")
    )
    assert set(order[-2:]) == {"Peely Base", "Sticky Base"}  # not on the sheet
    assert order[-2:] == sorted(order[-2:])
    assert ShadeQuery.from_params(sort="released").params() == [("sort", "released")]


def test_the_collection_filter_takes_an_official_name_or_a_shop_tag(sheeted):
    assert titles(find(sheeted, collection="Mini Advent Calendar Collection")) == [
        "Diamond Dasher Taco",
        "Silent Night",
    ]
    assert titles(find(sheeted, collection="soon-retiring")) == ["Jam Session", "Rest In Peach"]
    assert titles(find(sheeted, collection="Holo Taco Unicorn Skin Collection")) == [
        "Aurora Unicorn Skin™"
    ]
    assert find(sheeted, collection="Mini Advent Calendar Collection").total == 2
    assert ShadeQuery.from_params(collection="Holo Taco x Julien Collection").filter_count() == 1


def test_facets_add_the_official_collection_names(sheeted):
    facets = shades.facets(sheeted)
    assert "Mini Advent Calendar Collection" in facets["official"]
    assert facets["official"] == sorted(facets["official"], key=str.casefold)
    assert "soon-retiring" in facets["collection"]  # the shop's tags are still offered


def test_facets_have_no_official_collections_before_the_sheet_is_read(catalog):
    assert shades.facets(catalog)["official"] == []


def test_a_sheet_only_shade_is_listed_and_found_but_is_in_no_status_filter(sheeted):
    assert "Silent Night" in titles(find(sheeted))
    assert titles(find(sheeted, q="advent")) == []  # search reads the name, not the collection
    assert titles(find(sheeted, q="silent")) == ["Silent Night"]
    assert titles(find(sheeted, q="rose")) == ["Play Rosé"]
    for key in ("buyable", "retired", "sold_out"):
        assert not {"Silent Night", "Red Flake Taco"} & set(titles(find(sheeted, status=key)))
    row = next(r for r in find(sheeted).rows if r["title"] == "Silent Night")
    assert row["status"].key == "sheet_only" and row["price_cents"] is None


def test_toppers_and_polishes_filter_over_sheet_only_shades(sheeted):
    assert {"Silver Flake Taco", "Red Flake Taco"} <= set(titles(find(sheeted, kind="topper")))
    assert {"Silent Night", "Play Rosé"} <= set(titles(find(sheeted, kind="polish")))


def test_a_filter_and_the_row_status_agree_with_sheet_only_shades_present(sheeted):
    everything = find(sheeted).rows
    for key in ("buyable", "retired", "sold_out"):
        expected = {
            r["title"]
            for r in everything
            if (r["status"].buyable if key == "buyable" else r["status"].key == key)
        }
        assert set(titles(find(sheeted, status=key))) == expected


def test_detail_of_a_sheet_only_shade_has_no_photos_and_the_sheets_facts(sheeted):
    detail = shades.get_shade(sheeted, shade_id_by_title(sheeted, "Red Flake Taco"))
    assert detail["status"].label == "Not in the shop"
    assert detail["images"] == [] and detail["handle"] is None
    assert (detail["released_on"], detail["retired"]) == ("2022-12-06", 1)


def shade_id_by_title(conn, title):
    return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]
