"""Ranked, typo-tolerant name search (DESIGN 6): the tiers, the typo rules, the highlight marks and
the places that search (home, /shades, the builder and learn pickers)."""

import itertools
import re
import statistics
import time

import pytest
from markupsafe import Markup
from shade_data import made_from, seed, shade_id

from polished import bottles, search, shades, stacks, wheels
from polished.bottles import BottleInput
from polished.db import connect
from polished.migrate import migrate
from polished.shades import ShadeQuery
from polished.web import marked

# The Holo Taco pair Jan mixes up, and the other names the fuzzy cases are about.
EXTRA = [
    made_from("thirst-trap", 1, "Magnetic Taco", tags=["finish:magnetic", "color:blue"]),
    made_from("thirst-trap", 2, "Holo Magnetic Taco", tags=["finish:magnetic", "color:purple"]),
    made_from("thirst-trap", 3, "Magnetic Attraction Duo", tags=["finish:magnetic"]),
    made_from("thirst-trap", 4, "One-Coat Black", tags=["color:black"]),
    made_from("thirst-trap", 5, "Black Holo Wish", tags=["color:black", "finish:holographic"]),
    made_from("thirst-trap", 6, "Spirit Fingers", tags=["finish:glitter"]),
    made_from("thirst-trap", 7, "Crème Brûlée", tags=["finish:creme"]),
    made_from("thirst-trap", 8, "Taco Tuesday", tags=["collection:magnetic"]),
]


@pytest.fixture
def catalog(conn):
    seed(conn, EXTRA)
    return conn


def titles(page):
    return [row["title"] for row in page.rows]


def find(conn, text, **params):
    return shades.list_shades(conn, ShadeQuery.from_params(q=text, **params), size=200)


def row_titles(html: str) -> list[str]:
    """The titles of the result rows, without the <mark> tags."""
    return [
        re.sub(r"<[^>]+>", "", t) for t in re.findall(r'<span class="row-title">(.*?)</span>', html)
    ]


# query -> the titles that must come first, in this order
RANKING = [
    # Jan's pair: the exact title beats the one that only contains the words.
    ("magnetic taco", ["Magnetic Taco", "Holo Magnetic Taco"]),
    ("Magnetic Taco", ["Magnetic Taco", "Holo Magnetic Taco"]),
    ("holo magnetic taco", ["Holo Magnetic Taco"]),
    ("taco magnetic", ["Magnetic Taco", "Holo Magnetic Taco"]),  # whole words, shorter first
    # Starts with, shorter first, before a title that only contains the word.
    ("magnetic", ["Magnetic Taco", "Magnetic Attraction Duo", "Holo Magnetic Taco"]),
    # Word starts, as you type.
    ("holo magn", ["Holo Magnetic Taco"]),
    ("magnetic ta", ["Magnetic Taco", "Holo Magnetic Taco"]),
    # Typos.
    ("magentic taco", ["Magnetic Taco", "Holo Magnetic Taco"]),
    ("holo magnetc", ["Holo Magnetic Taco"]),
    ("holo magnetik taco", ["Holo Magnetic Taco"]),
    ("spirit fingrs", ["Spirit Fingers"]),
    ("sprit fingers", ["Spirit Fingers"]),
    # A missing space, a space in the wrong place, a hyphen.
    ("spiritfingers", ["Spirit Fingers"]),
    ("one coat black", ["One-Coat Black"]),
    ("one-coat black", ["One-Coat Black"]),
    ("onecoat", ["One-Coat Black"]),
    ("onecoat black", ["One-Coat Black"]),
    ("magnetictaco", ["Magnetic Taco", "Holo Magnetic Taco"]),
    # Accents, case and the trademark sign are ignored on both sides.
    ("creme brulee", ["Crème Brûlée"]),
    ("CRÈME BRÛLÉE", ["Crème Brûlée"]),
    ("creme brule", ["Crème Brûlée"]),
    ("aurora unicorn skin", ["Aurora Unicorn Skin™"]),
    ("aurora unicorn skin™", ["Aurora Unicorn Skin™"]),
    ("auroar unicorn", ["Aurora Unicorn Skin™"]),
    # The shades of the trimmed fixture.
    ("thirst trap", ["Thirst Trap"]),
    ("thrist trap", ["Thirst Trap"]),
    ("royal tea blue", ["Royal-Tea Blue"]),
    ("royal-tea", ["Royal-Tea Blue"]),
    ("rest in peach", ["Rest In Peach"]),
    ("hit the lighst", ["Hit The Lights"]),
    # A title that starts with the word, then one that has it as a word.
    ("black", ["Black Holo Wish", "One-Coat Black"]),
]


@pytest.mark.parametrize(("text", "expected"), RANKING, ids=[r[0] for r in RANKING])
def test_a_query_finds_its_shades_first_in_this_order(catalog, text, expected):
    found = titles(find(catalog, text))
    assert found[: len(expected)] == expected, found


def test_the_tiers_run_from_exact_to_fuzzy(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Sea Glass Bloom", tags=["color:blue"]),
            made_from("thirst-trap", 2, "Glass", tags=["color:blue"]),
            made_from("thirst-trap", 3, "Glassy Night", tags=["color:blue"]),
            made_from("thirst-trap", 4, "Bloom Glassware", tags=["color:blue"]),
            made_from("thirst-trap", 5, "Quiet Night", tags=["color:glass"]),
            made_from("thirst-trap", 6, "Glaas Rain", tags=["color:blue"]),
        ],
    )
    assert titles(find(conn, "glass")) == [
        "Glass",  # the title is the query
        "Glassy Night",  # the title starts with it
        "Sea Glass Bloom",  # a whole word of the title
        "Bloom Glassware",  # a word of the title starts with it
        "Quiet Night",  # only a tag has it
        "Glaas Rain",  # one edit away
    ]


def test_a_shorter_title_wins_inside_a_tier_then_the_title(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Moon Dust Deluxe Edition"),
            made_from("thirst-trap", 2, "Moon Dust Deluxe"),
            made_from("thirst-trap", 3, "Moon Dust B"),
            made_from("thirst-trap", 4, "Moon Dust A"),
        ],
    )
    assert titles(find(conn, "moon dust")) == [
        "Moon Dust A",
        "Moon Dust B",
        "Moon Dust Deluxe",
        "Moon Dust Deluxe Edition",
    ]


def test_fewer_edits_come_first_in_the_fuzzy_tier_whatever_the_length(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Sparkle Mist"),
            made_from("thirst-trap", 2, "Sparkel Mist Duo"),
            made_from("thirst-trap", 3, "Sparkel Mizt"),
        ],
    )
    # One edit (a swap) in a longer title beats two edits in a shorter one.
    assert titles(find(conn, "sparkle mist")) == [
        "Sparkle Mist",
        "Sparkel Mist Duo",
        "Sparkel Mizt",
    ]


def test_typo_budget_is_none_under_4_letters_one_to_7_and_two_from_8(conn):
    assert [search.allowed_edits(n) for n in (1, 3, 4, 7, 8, 12)] == [0, 0, 1, 1, 2, 2]
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Zebra Glow"),
            made_from("thirst-trap", 2, "Moonlighting"),
        ],
    )
    assert titles(find(conn, "zebrq glow")) == ["Zebra Glow"]  # 5 letters: one edit
    assert titles(find(conn, "zebqq glow")) == []
    assert titles(find(conn, "moonlihtng")) == ["Moonlighting"]  # 10 letters: two edits
    assert titles(find(conn, "moonlxxxting")) == []  # three
    assert titles(find(conn, "glw")) == []  # 3 letters: none


@pytest.mark.parametrize(
    ("a", "b", "limit", "expected"),
    [
        ("magnetic", "magnetic", 2, 0),
        ("magentic", "magnetic", 2, 1),  # a swap of neighbours is one edit
        ("magnetc", "magnetic", 1, 1),
        ("fingrs", "fingers", 1, 1),
        ("abcd", "wxyz", 1, 2),  # more than the limit comes back as limit + 1
        ("abcdefgh", "ab", 2, 3),  # ... without comparing, when the lengths differ too much
    ],
)
def test_distance(a, b, limit, expected):
    assert search.distance(a, b, limit) == expected


def test_nothing_matching_gives_an_empty_page(catalog):
    for text in ("zzzzzzzz", "qqqq xxxx", "xylophone", "thirst zebra"):
        page = find(catalog, text)
        assert page.rows == [] and page.total == 0, text


def test_a_query_without_words_ranks_nothing(conn):
    seed(conn)
    assert search.rank(conn, "   ") == []
    assert search.rank(conn, "!!!") == []
    assert search.rank(conn, "™") == []


def test_the_order_does_not_depend_on_the_order_shades_were_added(tmp_path):
    results = []
    for number, order in enumerate((EXTRA, EXTRA[::-1])):
        path = str(tmp_path / f"order{number}.db")
        migrate(path)
        conn = connect(path)
        seed(conn, order)
        queries = ("magnetic", "taco", "holo", "magentic taco", "black", "o")
        results.append({q: titles(find(conn, q)) for q in queries})
        assert results[-1] == {q: titles(find(conn, q)) for q in queries}  # and again
        conn.close()
    assert results[0] == results[1]


def test_ties_fall_back_to_the_title_so_the_order_is_total(conn):
    seed(conn, [made_from("thirst-trap", n, f"Plum {c}") for n, c in enumerate("DBCA", 1)])
    assert titles(find(conn, "plum")) == ["Plum A", "Plum B", "Plum C", "Plum D"]


@pytest.mark.parametrize(
    "text",
    [
        "'; drop table shade; --",
        "' or 1=1 --",
        '" or ""="',
        "%",
        "_",
        "\\",
        "100%",
        "a%' escape '\\",
        "\x00",
        "magnetic\x00taco",
        "🌈🌈",
        "💅 taco",
        "<script>alert(1)</script>",
        "x" * 100,
        "(((",
        "[a-z]+",
        "{{7*7}}",
    ],
)
def test_odd_input_is_just_text(catalog, text):
    total = catalog.execute("select count(*) from shade").fetchone()[0]
    page = find(catalog, text)
    assert page.total == len(page.rows)
    # Without a word in it the text is no search at all and the list is whole; otherwise a
    # subset (usually empty).
    assert page.total == total if not search.tokens(text) else page.total <= total
    assert catalog.execute("select count(*) from shade").fetchone()[0] == total
    assert shades.search(catalog, text).total == page.total


def test_percent_and_underscore_are_plain_characters(catalog):
    assert find(catalog, "100%").rows == []
    assert find(catalog, "magnetic%").rows == find(catalog, "magnetic").rows
    assert find(catalog, "magnetic_taco").rows[0]["title"] == "Magnetic Taco"


# Filters and sorts keep working with a ranked query


def test_filters_narrow_a_ranked_query(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Magnetic Taco", tags=["finish:magnetic"]),
            made_from("aurora-unicorn-skin", 2, "Holo Magnetic Taco", tags=["finish:magnetic"]),
        ],
    )
    assert titles(find(conn, "magnetic taco")) == ["Magnetic Taco", "Holo Magnetic Taco"]
    assert titles(find(conn, "magnetic taco", kind="topper")) == ["Holo Magnetic Taco"]
    assert titles(find(conn, "magentic taco", kind="polish")) == ["Magnetic Taco"]


def test_other_sorts_keep_their_order_but_only_for_matches(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Magnetic Taco", price="20.00"),
            made_from("thirst-trap", 2, "Holo Magnetic Taco", price="10.00"),
            made_from("thirst-trap", 3, "Plain Taco", price="5.00"),
        ],
    )
    assert titles(find(conn, "magentic", sort="price")) == ["Holo Magnetic Taco", "Magnetic Taco"]


def test_pages_continue_the_ranking(conn):
    seed(conn, [made_from("thirst-trap", n, f"Berry {n:02d}") for n in range(12)])
    query = ShadeQuery.from_params(q="berry")
    first = shades.list_shades(conn, query, page=1, size=5)
    second = shades.list_shades(conn, query, page=2, size=5)
    third = shades.list_shades(conn, query, page=3, size=5)
    assert first.total == 12 and first.has_more and second.has_more and not third.has_more
    assert titles(first) + titles(second) + titles(third) == [f"Berry {n:02d}" for n in range(12)]


def test_owned_and_wishlisted_shades_win_ties_in_the_home_search_only(conn):
    seed(
        conn,
        [
            made_from("thirst-trap", 1, "Moss Alpha"),
            made_from("thirst-trap", 2, "Moss Delta"),
            made_from("thirst-trap", 3, "Moss Gamma"),
            made_from("thirst-trap", 4, "Moss"),
        ],
    )
    bottles.add(conn, shade_id(conn, "moss-gamma"), BottleInput())
    conn.execute("insert into wishlist_item (shade_id) values (?)", (shade_id(conn, "moss-delta"),))
    # Ownership breaks ties of tier and length only: the exact title is still first.
    assert titles(shades.search(conn, "moss")) == ["Moss", "Moss Gamma", "Moss Delta", "Moss Alpha"]
    assert titles(find(conn, "moss")) == ["Moss", "Moss Alpha", "Moss Delta", "Moss Gamma"]


def test_the_pickers_use_the_same_ranking(conn):
    seed(conn, EXTRA)
    bottles.add(conn, shade_id(conn, "magnetic-taco"), BottleInput())
    bottles.add(conn, shade_id(conn, "holo-magnetic-taco"), BottleInput())
    assert titles(shades.pick(conn, "magentic taco", "owned")) == [
        "Magnetic Taco",
        "Holo Magnetic Taco",
    ]
    assert titles(shades.pick(conn, "magnetic taco", "all"))[:2] == [
        "Magnetic Taco",
        "Holo Magnetic Taco",
    ]


# Marks


def test_marks_cover_the_matched_words_only():
    assert search.marks("Holo Magnetic Taco", "magnetic taco") == [(5, 13), (14, 18)]
    assert search.marks("Holo Magnetic Taco", "holo magn") == [(0, 4), (5, 9)]
    assert search.marks("Magnetic Taco", "magentic taco") == [(0, 8), (9, 13)]
    assert search.marks("Holo Magnetic Taco", "taco") == [(14, 18)]
    assert search.marks("Holo Magnetic Taco", "xylophone") == []


def test_marks_follow_accents_hyphens_and_the_trademark_sign():
    title = "Crème Brûlée"
    assert search.marks(title, "creme") == [(0, 5)]
    assert search.marks(title, "brulee") == [(6, 12)]
    assert search.marks("One-Coat Black", "coat") == [(4, 8)]
    assert search.marks("Aurora Unicorn Skin™", "skin") == [(15, 19)]


def test_marks_leave_a_tag_match_and_a_missing_space_unmarked():
    assert search.marks("Thirst Trap", "flakie") == []
    assert search.marks("One-Coat Black", "onecoat") == []


def test_marked_escapes_the_title_and_wraps_only_the_marks():
    html = marked("<b>Taco</b> & Co", [(3, 7)])
    assert html == Markup("&lt;b&gt;<mark>Taco</mark>&lt;/b&gt; &amp; Co")
    assert marked("A <i>", None) == "A <i>"
    assert marked("A <i>", []) == "A <i>"


def test_list_rows_carry_marks_only_for_a_query(catalog):
    assert find(catalog, "magnetic").rows[0]["marks"] == [(0, 8)]
    assert "marks" not in shades.list_shades(catalog, ShadeQuery()).rows[0]


# Routes


def test_home_search_shows_the_difference_between_near_duplicates(client, conn):
    seed(conn, EXTRA)
    html = client.get("/search", params={"q": "magnetic taco", "ctx": "home"}).text
    assert row_titles(html)[:2] == ["Magnetic Taco", "Holo Magnetic Taco"]
    assert '<span class="row-title"><mark>Magnetic</mark> <mark>Taco</mark>' in html
    # The longer title keeps its unmarked "Holo " in front.
    assert '<span class="row-title">Holo <mark>Magnetic</mark> <mark>Taco</mark>' in html


def test_the_shades_page_ranks_a_typo_and_escapes_a_hostile_title(client, conn):
    seed(conn, [*EXTRA, made_from("thirst-trap", 20, "<img src=x onerror=alert(1)> Taco")])
    html = client.get("/shades", params={"q": "magentic taco"}).text
    assert row_titles(html)[:2] == ["Magnetic Taco", "Holo Magnetic Taco"]
    hostile = client.get("/shades", params={"q": "taco"}).text
    assert "<img src=x" not in hostile
    assert "&lt;img src=x onerror=alert(1)&gt; <mark>Taco</mark>" in hostile


def test_the_learn_picker_finds_a_typo(client, conn):
    seed(conn, EXTRA)
    params = {"q": "spirit fingrs", "ctx": "learn", "kind": "gtin", "value": "0810170284120"}
    html = client.get("/search", params=params).text
    assert "<mark>Spirit</mark> <mark>Fingers</mark>" in html


def test_the_builder_picker_finds_a_missing_space(client, conn):
    seed(conn, EXTRA)
    opened = stacks.open_draft(conn, wheels.create(conn, "Holos"), 3)
    params = {"q": "onecoat", "ctx": "stack", "stack_id": opened.stack_id, "filter": "all"}
    html = client.get("/search", params=params).text
    assert row_titles(html) == ["One-Coat Black"]
    assert 'aria-label="Add One-Coat Black"' in html


# Speed


def test_a_query_over_400_shades_takes_well_under_20_ms(conn):
    words = [
        "Sunset",
        "Glitter",
        "Holo",
        "Magnetic",
        "Taco",
        "Black",
        "Pink",
        "Moon",
        "Flake",
        "Aqua",
        "Dust",
        "Jelly",
    ]
    names = sorted({" ".join(c) for c in itertools.islice(itertools.permutations(words, 3), 400)})
    seed(conn, [made_from("thirst-trap", n, name) for n, name in enumerate(names)])
    medians = []
    for text in ("magnetic taco", "magentic taco", "holo magnetc", "xylophone", "a"):
        shades.search(conn, text)
        samples = []
        for _ in range(10):
            started = time.perf_counter()
            shades.search(conn, text)
            samples.append((time.perf_counter() - started) * 1000)
        medians.append(statistics.median(samples))
    assert max(medians) < 20, medians
