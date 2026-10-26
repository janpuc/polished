import re

import pytest
from conftest import make_client, make_settings
from shade_data import made_from, seed, shade_id

from polished.db import connect

HX = {"HX-Request": "true"}
RESTORE = {"HX-Request": "true", "HX-History-Restore-Request": "true"}

# In-stock holographic shades the fixture feed lacks (its two holographic ones are retired or
# sold out), so the finish + status filter has something to count.
HOLO_TAGS = ["finish:holographic", "color:purple", "collection:holographic"]
EXTRA = [
    made_from("thirst-trap", 1, "Holo One", tags=HOLO_TAGS),
    made_from("thirst-trap", 2, "Holo Two", tags=HOLO_TAGS),
    made_from("thirst-trap", 3, "Holo Gone", tags=HOLO_TAGS, available=False),
]


def rows(response) -> int:
    """What `grep -c 'class="shade-row'` counts: lines, and each shade is one line."""
    return sum('class="shade-row' in line for line in response.text.splitlines())


@pytest.fixture
def seeded(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, EXTRA)
    yield client, conn
    conn.close()


def test_shades_is_a_full_page_for_a_normal_request_and_a_fragment_for_htmx(seeded):
    client, _ = seeded
    full = client.get("/shades", params={"q": "spirit"})
    assert "<html" in full.text and 'id="shade-filters"' in full.text
    part = client.get("/shades", params={"q": "thirst"}, headers=HX)
    assert "<html" not in part.text
    assert "<mark>Thirst</mark> Trap" in part.text and 'id="shade-filters"' not in part.text


def test_a_history_restore_gets_the_full_page(seeded):
    client, _ = seeded
    response = client.get("/shades", params={"kind": "topper"}, headers=RESTORE)
    assert "<html" in response.text
    assert "Aurora Unicorn Skin" in response.text


def test_pages_are_private_and_vary_on_the_htmx_headers(seeded):
    client, _ = seeded
    for headers in ({}, HX, RESTORE):
        response = client.get("/shades", headers=headers)
        assert response.headers["cache-control"] == "private, no-cache"
        vary = response.headers["vary"].lower()
        assert "hx-request" in vary and "hx-history-restore-request" in vary


def test_a_fragment_updates_the_counts_out_of_band_and_a_page_does_not(seeded):
    client, _ = seeded
    part = client.get("/shades", params={"kind": "topper"}, headers=HX).text
    assert '<span id="result-count" hx-swap-oob="true">2 shades</span>' in part
    assert '<span id="filter-count" hx-swap-oob="true">1</span>' in part
    full = client.get("/shades", params={"kind": "topper"}).text
    assert "hx-swap-oob" not in full
    assert '<p id="result-count"' in full and "2 shades" in full


def test_finish_and_status_filters_count_the_rows(seeded):
    client, _ = seeded
    response = client.get("/shades", params={"finish": "holographic", "status": "buyable"})
    assert rows(response) == 2
    assert "Holo One" in response.text and "Holo Gone" not in response.text
    assert rows(client.get("/shades", params={"finish": "holographic"})) == 5
    assert rows(client.get("/shades?finish=holographic&status=buyable", headers=HX)) == 2


def test_filter_form_keeps_the_current_choices(seeded):
    client, _ = seeded
    html = client.get(
        "/shades?finish=creme&finish=flakie&color=red&collection=metallic&kind=polish&status=sold_out&sort=price&q=trap"
    ).text
    for fragment in (
        'name="finish" value="creme" checked',
        'name="finish" value="flakie" checked',
        'name="color" value="red" checked',
        'name="kind" value="polish" checked',
        'name="status" value="sold_out" checked',
        '<option value="metallic" selected>',
        '<option value="price" selected>',
        'value="trap"',
    ):
        assert fragment in html
    # The panel stays shut over the results; the badge on its button counts the active filters.
    assert '<details class="filter-toggle">' in html
    assert re.search(r'<span id="filter-count" class="badge">\d+</span>', html)
    assert re.search(r'<span id="filter-count" class="badge"></span>', client.get("/shades").text)


def test_load_more_continues_the_same_search_on_the_next_page(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, [made_from("thirst-trap", n, f"Berry {n:02d}") for n in range(45)])
    conn.close()
    first = client.get("/shades", params={"q": "berry", "sort": "price"})
    assert rows(first) == 40
    more = re.search(r'hx-get="([^"]+)"', first.text.split('id="shade-list"')[1]).group(1)
    assert more.replace("&amp;", "&") == "/shades?q=berry&sort=price&page=2"
    second = client.get(more.replace("&amp;", "&"), headers=HX)
    assert rows(second) == 5 and "<html" not in second.text and "Load more" not in second.text


def test_no_matches_says_so(seeded):
    client, _ = seeded
    html = client.get("/shades", params={"q": "zzzz"}).text
    assert "No shades match" in html and "0 shades" in html


def test_detail_shows_price_status_images_and_the_shop_link(seeded):
    client, conn = seeded
    response = client.get(f"/shades/{shade_id(conn, 'rest-in-peach')}")
    html = response.text
    assert response.status_code == 200
    assert "Rest In Peach" in html and "Retiring soon" in html
    assert "$13.50" in html and "$16.50" in html and "Sale" in html
    assert html.count("<img") == 4  # two photos, the tip beside the title, the tip in Tip colour
    assert 'href="https://holotaco.com/products/rest-in-peach"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "/shades?finish=creme" in html


def test_detail_status_labels(seeded):
    client, conn = seeded
    assert "Retired" in client.get(f"/shades/{shade_id(conn, 'gold-play-button')}").text
    assert "Sold out, retiring" in client.get(f"/shades/{shade_id(conn, 'jam-session')}").text
    conn.execute("update product set missing_since = '2026-10-01' where handle = 'thirst-trap'")
    html = client.get(f"/shades/{shade_id(conn, 'thirst-trap')}").text
    assert "Not listed" in html and "No longer listed on holotaco.com" in html
    assert "View on holotaco.com" not in html


def test_detail_of_a_manual_shade_has_no_status_price_or_link(seeded):
    client, conn = seeded
    manual = conn.execute(
        "insert into shade (source, kind, title, search_text) values ('manual', 'polish', 'Gift', 'gift')"
    ).lastrowid
    html = client.get(f"/shades/{manual}").text
    assert "Gift" in html and "Added by hand" in html
    assert "holotaco.com/products" not in html and "cdn.shopify.com" not in html


def test_an_unknown_shade_is_a_404_page(seeded):
    client, _ = seeded
    response = client.get("/shades/9999")
    assert response.status_code == 404 and "<html" in response.text


def test_search_returns_rows_without_the_page_around_them(seeded):
    client, _ = seeded
    response = client.get("/search", params={"q": "thirst", "ctx": "home"})
    assert response.status_code == 200 and "<html" not in response.text
    assert rows(response) == 1 and 'href="/shades/' in response.text
    assert (
        client.get("/search", params={"q": "thirst", "ctx": "home"}, headers=HX).text
        == response.text
    )


def test_search_with_nothing_typed_returns_nothing_and_no_match_says_so(seeded):
    client, _ = seeded
    assert client.get("/search", params={"q": "  ", "ctx": "home"}).text.strip() == ""
    assert "Nothing matches" in client.get("/search", params={"q": "zzzz", "ctx": "home"}).text


def test_search_offers_the_whole_list_when_there_are_more_than_30_matches(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, [made_from("thirst-trap", n, f"Berry {n:02d}") for n in range(35)])
    conn.close()
    response = client.get("/search", params={"q": "berry"})
    assert rows(response) == 30
    assert '<a href="/shades?q=berry">All 35 matches</a>' in response.text


def test_search_rejects_a_context_this_stage_does_not_have(seeded):
    client, _ = seeded
    assert client.get("/search", params={"q": "x", "ctx": "stack"}).status_code == 422


def test_rows_show_tip_title_finish_chips_and_status(seeded):
    client, _ = seeded
    html = client.get("/shades", params={"q": "jam session"}).text
    row = re.search(r'<li class="shade-row">.*?</li>', html, re.S).group(0)
    assert re.search(
        r'<span class="tip-m" aria-hidden="true"><img src="/tips/shade/\d+\.svg\?v=\w+"', row
    )
    assert 'width="40" height="66"' in row and 'loading="lazy"' in row
    assert (
        "cdn.shopify.com" not in row
    )  # a bottle photo is for the shade page and the lookup result
    assert "<mark>Jam</mark> <mark>Session</mark>" in html and ">Holographic<" in html
    assert 'class="status status-sold_out">Sold out, retiring<' in html
    assert "$15.50" in html


def test_a_row_puts_the_heart_after_the_name_and_the_owned_count_under_the_price(seeded):
    client, conn = seeded
    shade = shade_id(conn, "jam-session")
    client.post(f"/shades/{shade}/wishlist")
    client.post(f"/shades/{shade}/bottles", data={"state": "full"})
    client.post(f"/shades/{shade}/bottles", data={"state": "half"})
    html = client.get("/shades", params={"q": "jam session"}).text
    row = re.search(r'<li class="shade-row">.*?</li>', html, re.S).group(0)
    title = re.search(r'<span class="row-title">(.*?)</span></span>', row, re.S).group(1)
    assert (
        title.startswith("<mark>Jam</mark> <mark>Session</mark>")
        and 'aria-label="On the wishlist"' in title
    )
    assert row.index('class="row-end price"') < row.index('class="row-sub"')
    assert re.search(
        r'class="row-end footnote"><span aria-label="Owned ×2" role="img">×2</span>', row
    )
    assert 'class="pill"' not in row and "row-flags" not in row
    sub = re.search(
        r'<span class="row-sub">(.*?)</span></span>\s*<span class="row-end footnote"', row, re.S
    )
    assert sub.group(1).startswith('<span class="status status-sold_out">Sold out, retiring</span>')


def test_the_shades_page_filter_panel_ends_in_one_filled_button_that_counts(seeded):
    client, _ = seeded
    html = client.get("/shades").text
    panel = html[html.index('class="filter-panel"') :]
    assert re.search(
        r'<button type="button" id="filter-show" class="btn" data-close-details>Show 12 shades</button>',
        panel,
    )
    assert panel.count('class="btn"') == 1 and "Clear all" in panel  # the other buttons are text
    narrowed = client.get("/shades", params={"kind": "topper"}, headers=HX).text
    assert re.search(
        r'<button type="button" id="filter-show"[^>]*hx-swap-oob="true">Show \d+ shades?</button>',
        narrowed,
    )


def test_the_detail_head_pairs_the_tip_with_the_title_and_the_facets_are_a_quiet_list(seeded):
    client, conn = seeded
    shade = shade_id(conn, "jam-session")
    client.post(f"/shades/{shade}/bottles", data={"state": "full"})
    html = client.get(f"/shades/{shade}").text
    head = re.search(r'<div class="detail-head">.*?</div>\s*</div>', html, re.S).group(0)
    assert head.index(f"/tips/shade/{shade}.svg") < head.index("<h1")
    assert "$15.50" in head and "Owned ×1" in head and "Sold out, retiring" in head
    facets = re.search(r'<dl class="facets">.*?</dl>', html, re.S).group(0)
    assert re.findall(r"<dt>(\w+)</dt>", facets) == ["Finish", "Colour", "Collections"]
    assert 'class="section-title">Finish' not in html
    assert '<details class="tip-colour-box">' in html and html.index("tip-colour-box") > html.index(
        "facets"
    )


def test_the_tip_colour_form_opens_by_itself_on_an_error(seeded):
    client, conn = seeded
    shade = shade_id(conn, "jam-session")
    bad = client.post(f"/shades/{shade}/tip-colour", data={"hex": "nope"})
    assert bad.status_code == 422 and '<details class="tip-colour-box" open>' in bad.text


def test_home_has_a_sticky_search_that_waits_200ms(seeded):
    client, _ = seeded
    html = client.get("/").text
    assert 'hx-trigger="input changed delay:200ms, search"' in html
    assert 'hx-get="/search"' in html and 'hx-target="#search-results"' in html
    assert "Search 12 shades" in html  # 9 fixture shades + 3 extra
    assert 'class="search-bar"' in html
