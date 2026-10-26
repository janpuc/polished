"""The release sheet in the pages: facts on the shade page, the sort and filter on the list,
and the shade page of a shade only the sheet knows."""

import re

import pytest
from conftest import FIXTURES, make_client, make_settings
from shade_data import seed

from polished.catalog import sheet
from polished.db import connect

HX = {"HX-Request": "true"}


@pytest.fixture
def world(tmp_path):
    """The fixture catalog and the fixture sheet applied, behind an AUTH_MODE=none app."""
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn)
    text = (FIXTURES / "release_sheet_trimmed.csv").read_text(encoding="utf-8")
    sheet.apply_sheet(conn, sheet.parse_sheet(text, min_rows=1))
    yield client, conn
    conn.close()


def sid(conn, title):
    return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]


def detail(world, title):
    client, conn = world
    return client.get(f"/shades/{sid(conn, title)}")


def row_lines(response) -> list[str]:
    return [line for line in response.text.splitlines() if 'class="shade-row' in line]


# The shade page of a shop shade


def test_detail_says_when_it_was_released_and_links_the_official_collection(world):
    html = detail(world, "Royal-Tea Blue").text
    assert "Released 6 Jul 2019</p>" in html
    link = re.search(r'<a class="chip chip-long" href="([^"]+)">([^<]+)</a>', html)
    assert link.group(1) == "/shades?collection=Holo%20Taco%20Launch%20Collection"
    assert link.group(2) == "Holo Taco Launch Collection"
    assert "View on holotaco.com" in html


def test_a_collection_name_with_an_ampersand_and_an_apostrophe_is_escaped_and_linked(world):
    html = detail(world, "Rest In Peach").text
    assert "Pastel &amp; Don&#39;t Tell Bundle" in html
    assert 'href="/shades?collection=Pastel%20%26%20Don%27t%20Tell%20Bundle"' in html


def test_the_collection_link_leads_to_the_filtered_list(world):
    client, _ = world
    page = client.get("/shades", params={"collection": "Holo Taco Unicorn Skin Collection"})
    assert len(row_lines(page)) == 1 and "Aurora Unicorn Skin" in page.text
    assert '<option value="Holo Taco Unicorn Skin Collection" selected>' in page.text


def test_a_shade_the_sheet_calls_retired_says_so_even_when_the_shop_does_not(world):
    html = detail(world, "Hit The Lights").text
    assert 'class="status status-retired">Retired</span>' in html
    assert "Released 11 Jul 2026" in html
    assert "Sold out" not in html


def test_a_shade_not_on_the_sheet_has_no_release_line(world):
    html = detail(world, "Sticky Base").text
    assert "Released" not in html and "chip-long" not in html


# The shade page of a sheet-only shade


def test_a_sheet_only_shade_page_has_the_tip_and_no_photos_price_or_shop_link(world):
    html = detail(world, "Silent Night").text
    assert "<h1" in html and "Silent Night" in html
    assert 'class="gallery"' not in html and "cdn.shopify.com" not in html
    assert "View on holotaco.com" not in html and "SKU" not in html
    assert "No longer listed" not in html
    assert 'class="price"' not in html
    assert 'class="status status-sheet_only">Not in the shop</span>' in html
    assert "Released 15 Nov 2025, retired</p>" in html
    assert 'class="tip-l"' in html
    assert "Mini Advent Calendar Collection" in html
    assert "Add bottle" in html and 'aria-label="Add to the wishlist"' in html
    assert "Not read yet" in html  # the tip colour waits for the household


def test_a_sheet_only_shade_that_is_not_retired_says_only_its_date(world):
    html = detail(world, "Silver Flake Taco").text
    assert "Released 6 Dec 2022</p>" in html and ", retired" not in html
    assert "Topper" in html


def test_the_household_can_colour_own_and_wish_for_a_sheet_only_shade(world):
    client, conn = world
    shade = sid(conn, "Silent Night")
    assert client.post(f"/shades/{shade}/tip-colour", data={"hex": "#aa3366"}).status_code == 303
    html = client.get(f"/shades/{shade}").text
    assert "Your colour" in html and "#aa3366" in html
    client.post(f"/shades/{shade}/wishlist", headers=HX)
    client.post(f"/shades/{shade}/bottles", data={"state": "half"}, headers=HX)
    html = client.get(f"/shades/{shade}").text
    assert "Owned ×1" in html and 'aria-label="On the wishlist, tap to remove"' in html
    wishes = client.get("/wishlist").text
    assert "Silent Night" in wishes and "Not in the shop" in wishes
    assert "/cart/" not in wishes  # never in a checkout link


# The list


def test_the_list_sorts_by_release_date_newest_first(world):
    client, _ = world
    page = client.get("/shades", params={"sort": "released"})
    titles = re.findall(r'<span class="row-title">([^<]+?)(?:<span|</span>)', page.text)
    assert titles[:3] == ["Hit The Lights", "Diamond Dasher Taco", "Silent Night"]
    assert '<option value="released" selected>Release date, newest first</option>' in page.text
    assert 'value="newest">Recently listed' in page.text
    assert "<html" not in client.get("/shades", params={"sort": "released"}, headers=HX).text


def test_a_sheet_only_row_says_not_in_the_shop_instead_of_a_price(world):
    client, _ = world
    page = client.get("/shades", params={"q": "silent night"})
    (block,) = re.findall(r'<li class="shade-row">.*?</li>', page.text, re.S)
    assert "Not in the shop" in block and "status-sheet_only" in block
    assert '<span class="row-end price"></span>' in block
    assert "$" not in block


def test_the_search_finds_a_sheet_only_shade_like_any_other(world):
    client, _ = world
    assert "Silent Night" in client.get("/search", params={"q": "silent"}, headers=HX).text
    assert "Play Rosé" in client.get("/shades", params={"q": "rose"}).text


def test_the_collection_filter_offers_official_names_and_keeps_the_shop_tags(world):
    client, _ = world
    html = client.get("/shades").text
    assert '<optgroup label="Official collections">' in html
    assert '<optgroup label="Shop tags">' in html
    assert (
        '<option value="Mini Advent Calendar Collection">Mini Advent Calendar Collection</option>'
        in html
    )
    assert '<option value="soon-retiring">Soon retiring</option>' in html
    both = client.get("/shades", params={"collection": "Mini Advent Calendar Collection"})
    assert len(row_lines(both)) == 2
    tag = client.get("/shades", params={"collection": "soon-retiring"})
    assert len(row_lines(tag)) == 2


def test_the_collection_filter_is_as_before_until_the_sheet_has_been_read(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn)
    conn.close()
    html = client.get("/shades").text
    assert "<optgroup" not in html
    assert '<option value="soon-retiring">Soon retiring</option>' in html
    assert '<option value="released">Release date, newest first</option>' in html


def test_a_sheet_only_shade_is_not_in_the_status_filters(world):
    client, _ = world
    for status in ("buyable", "retired", "sold_out"):
        page = client.get("/shades", params={"status": status})
        assert "Silent Night" not in page.text and "Red Flake Taco" not in page.text
