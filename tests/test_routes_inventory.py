import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import make_client, make_settings
from shade_data import made_from, seed, shade_id

from polished.db import connect

HX = {"HX-Request": "true"}
NO_ORIGIN = {"Origin": ""}
EXTRA = [made_from("thirst-trap", 1, "Last Stock", tags=["collection:retirement"])]


@pytest.fixture
def seeded(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, EXTRA)
    yield client, conn
    conn.close()


def sid(conn, handle) -> int:
    return shade_id(conn, handle)


def add_bottle(client, shade, **data):
    return client.post(f"/shades/{shade}/bottles", data=data)


def rows(response) -> int:
    return sum('class="shade-row' in line for line in response.text.splitlines())


def titles_in(html: str) -> list[str]:
    return re.findall(r'class="(?:[\w-]+ )*row-title(?: [\w-]+)*"[^>]*>([^<]+)<', html)


# Adding a bottle


def test_add_bottle_stores_the_normalised_p_code_and_returns_the_bottles_partial(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    response = add_bottle(client, shade, state="half", printed_code="259")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "P259" in response.text and 'id="bottles"' in response.text
    assert response.headers["hx-trigger"] == "sheetClose"
    row = conn.execute("select * from bottle").fetchone()
    assert (row["shade_id"], row["state"], row["printed_code"]) == (shade, "half", "P259")


def test_add_bottle_answers_the_same_with_htmx_and_updates_the_action_bar_out_of_band(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    response = client.post(f"/shades/{shade}/bottles", data={"printed_code": "p7"}, headers=HX)
    assert 'hx-swap-oob="true"' in response.text and 'id="shade-actions"' in response.text
    assert "Add bottle" in response.text and "Owned ×1" in response.text
    assert response.headers["hx-trigger"] == "sheetClose"


def test_the_new_bottle_defaults_are_full_and_bought_today(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    sheet = client.get(f"/shades/{shade}/bottles/new", headers=HX)
    today = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    assert "<html" not in sheet.text
    assert re.search(r'value="full" checked', sheet.text)
    assert f'name="bought_on" type="date" value="{today}"' in sheet.text
    assert 'name="printed_code"' in sheet.text and 'inputmode="numeric"' in sheet.text
    assert "Thirst Trap" in sheet.text

    add_bottle(client, shade)  # only the defaults
    row = conn.execute("select * from bottle").fetchone()
    assert (row["state"], row["printed_code"], row["bought_on"]) == ("full", None, None)


def test_a_wrong_field_returns_the_form_for_the_sheet_and_stores_nothing(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    response = add_bottle(client, shade, price_paid="lots", printed_code="259")
    assert response.status_code == 422
    assert response.headers["hx-retarget"] == "#sheet-body"
    assert response.headers["hx-reswap"] == "innerHTML"
    assert "Use an amount like 15.50." in response.text
    assert 'value="259"' in response.text and 'value="lots"' in response.text
    assert "hx-trigger" not in response.headers
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0


def test_a_bottle_for_a_missing_shade_is_404_and_without_origin_403(seeded):
    client, conn = seeded
    assert add_bottle(client, 9999, state="full").status_code == 404
    assert client.get("/shades/9999/bottles/new").status_code == 404
    shade = sid(conn, "thirst-trap")
    refused = client.post(f"/shades/{shade}/bottles", data={"state": "half"}, headers=NO_ORIGIN)
    assert refused.status_code == 403
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0


# Changing and editing a bottle


def make_bottle(client, conn, handle="thirst-trap", **data) -> int:
    add_bottle(client, sid(conn, handle), **data)
    return conn.execute("select max(id) from bottle").fetchone()[0]


def test_a_state_change_is_one_post_and_returns_the_card(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn, printed_code="259")
    response = client.post(f"/bottles/{bottle}/state", data={"state": "low"}, headers=HX)
    assert response.status_code == 200 and "<html" not in response.text
    assert f'id="bottle-{bottle}"' in response.text and "P259" in response.text
    assert re.findall(r'class="bottle-level level-(\w+)"', response.text) == ["low"]
    assert re.search(r"</svg><span>Low</span>", response.text)
    assert f'hx-get="/bottles/{bottle}/edit?ctx=shade"' in response.text
    assert conn.execute("select state from bottle").fetchone()[0] == "low"


def test_emptying_the_last_bottle_keeps_the_shade_page_action_after_the_last_bottle_is_emptied(
    seeded,
):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    bottle = make_bottle(client, conn)
    assert "Add bottle" in client.get(f"/shades/{shade}").text
    response = client.post(f"/bottles/{bottle}/state", data={"state": "empty", "ctx": "shade"})
    assert 'hx-swap-oob="true"' in response.text and "Add bottle" in response.text
    assert "Owned ×" not in response.text
    on_list = client.post(f"/bottles/{bottle}/state", data={"state": "full", "ctx": "list"})
    assert "hx-swap-oob" not in on_list.text


def test_an_unknown_state_is_422_and_an_unknown_bottle_404(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn)
    assert client.post(f"/bottles/{bottle}/state", data={"state": "mostly"}).status_code == 422
    assert client.post(f"/bottles/{bottle}/state", data={}).status_code == 422
    assert client.post("/bottles/9999/state", data={"state": "low"}).status_code == 404
    assert client.get("/bottles/9999/edit").status_code == 404
    assert client.post("/bottles/9999", data={"state": "low"}).status_code == 404
    assert client.post("/bottles/9999/archive").status_code == 404
    assert client.post("/bottles/9999/delete").status_code == 404
    assert conn.execute("select state from bottle").fetchone()[0] == "full"


def test_state_archive_and_delete_without_origin_are_403(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn)
    for path, data in (
        (f"/bottles/{bottle}/state", {"state": "low"}),
        (f"/bottles/{bottle}/archive", {}),
        (f"/bottles/{bottle}/delete", {}),
        (f"/bottles/{bottle}", {"state": "low"}),
    ):
        assert client.post(path, data=data, headers=NO_ORIGIN).status_code == 403
    assert conn.execute("select state, archived from bottle").fetchone()[:] == ("full", 0)


def test_the_edit_sheet_shows_the_bottle_without_the_p_prefix(seeded):
    client, conn = seeded
    bottle = make_bottle(
        client, conn, printed_code="259", price_paid="15.50", notes="gift", state="half"
    )
    sheet = client.get(f"/bottles/{bottle}/edit?ctx=list", headers=HX)
    assert "<html" not in sheet.text
    assert 'name="printed_code" value="259"' in sheet.text
    assert 'value="15.50"' in sheet.text and ">gift</textarea>" in sheet.text
    assert re.search(r'value="half" checked', sheet.text)
    assert 'name="ctx" value="list"' in sheet.text
    assert f"/bottles/{bottle}/delete" in sheet.text and "hx-confirm" in sheet.text


def test_updating_a_bottle_returns_its_card_and_closes_the_sheet(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn, printed_code="259")
    response = client.post(
        f"/bottles/{bottle}",
        data={"state": "low", "printed_code": "p300", "price_paid": "12,5", "ctx": "list"},
    )
    assert response.status_code == 200 and response.headers["hx-trigger"] == "sheetClose"
    assert "P300" in response.text and "$12.50" in response.text
    row = conn.execute("select * from bottle").fetchone()
    assert (row["state"], row["printed_code"], row["price_paid_cents"]) == ("low", "P300", 1250)
    bad = client.post(f"/bottles/{bottle}", data={"bought_on": "soon"})
    assert bad.status_code == 422 and bad.headers["hx-retarget"] == "#sheet-body"
    assert conn.execute("select printed_code from bottle").fetchone()[0] == "P300"


def test_archive_and_restore(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    bottle = make_bottle(client, conn)
    archived = client.post(f"/bottles/{bottle}/archive", data={"archived": "1"})
    assert "is-archived" in archived.text and "Archived" in archived.text
    assert archived.headers["hx-trigger"] == "sheetClose"
    assert conn.execute("select archived from bottle").fetchone()[0] == 1
    assert "Add bottle" in client.get(f"/shades/{shade}").text
    # Archive and Restore live in the edit sheet, one POST each.
    sheet = client.get(f"/bottles/{bottle}/edit?ctx=shade").text
    assert "Restore this bottle" in sheet and "Archive this bottle" not in sheet
    assert f'hx-post="/bottles/{bottle}/archive"' in sheet and '"archived": "0"' in sheet
    restored = client.post(f"/bottles/{bottle}/archive", data={"archived": "0"})
    assert "is-archived" not in restored.text and "Archived" not in restored.text
    sheet = client.get(f"/bottles/{bottle}/edit?ctx=shade").text
    assert "Archive this bottle" in sheet and '"archived": "1"' in sheet
    assert "Add bottle" in client.get(f"/shades/{shade}").text


def test_archiving_from_the_list_swaps_the_row_away_and_closes_the_sheet(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn)
    archived = client.post(f"/bottles/{bottle}/archive", data={"archived": "1", "ctx": "list"})
    assert archived.status_code == 200 and archived.text == ""
    assert archived.headers["hx-trigger"] == "sheetClose"
    assert conn.execute("select archived from bottle").fetchone()[0] == 1
    assert f'id="bottle-{bottle}"' not in client.get("/bottles").text
    restored = client.post(f"/bottles/{bottle}/archive", data={"archived": "0", "ctx": "list"})
    assert restored.text == "" and conn.execute("select archived from bottle").fetchone()[0] == 0
    assert f'id="bottle-{bottle}"' in client.get("/bottles").text


def test_a_bottle_row_shows_its_code_purchase_and_a_level_drawn_in_the_shade_colour(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    conn.execute("update shade set swatch_override_hex = '#c02060' where id = ?", (shade,))
    conn.commit()
    coded = make_bottle(
        client, conn, printed_code="188", bought_on="2026-07-21", price_paid="15.50", state="half"
    )
    plain = make_bottle(client, conn, bought_on="2026-05-18")
    page = client.get("/bottles").text
    assert 'class="bottle-title"><span translate="no">P188</span>' in page
    assert "Bought 21 Jul 2026, $15.50" in page
    assert 'class="bottle-title is-plain">No P code</span>' in page and "Bought 18 May 2026" in page
    assert page.count('fill="#c02060"') == 2  # both bottles: the shade's colour
    assert "Archive</" not in page and " style=" not in page  # Archive is in the edit sheet now
    assert f'hx-get="/bottles/{coded}/edit?ctx=list"' in page
    assert f'hx-get="/bottles/{plain}/edit?ctx=list"' in page
    # Empty has no liquid to draw; the other levels fill to a different height.
    heights = {}
    for state in ("full", "half", "low", "empty"):
        client.post(f"/bottles/{plain}/state", data={"state": state, "ctx": "list"})
        row = re.search(rf'id="bottle-{plain}".*?</article>', client.get("/bottles").text, re.S)
        glyph = re.search(r'<path d="M2 ([\d.]+)H14', row.group(0))
        heights[state] = float(glyph.group(1)) if glyph else None
    assert heights == {"full": 10.0, "half": 18.0, "low": 22.0, "empty": None}


def test_delete_removes_the_card_closes_the_sheet_and_updates_the_action_bar(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn)
    response = client.post(f"/bottles/{bottle}/delete", data={"ctx": "shade"}, headers=HX)
    assert response.status_code == 200
    assert response.headers["hx-trigger"] == "sheetClose"
    assert f'id="bottle-{bottle}"' not in response.text and "Add bottle" in response.text
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0


# Pages


def test_bottles_page_is_a_full_page_or_a_fragment_and_filters(seeded):
    client, conn = seeded
    make_bottle(client, conn, "thirst-trap", state="half", printed_code="1")
    make_bottle(client, conn, "peely-base", state="full")
    gone = make_bottle(client, conn, "rest-in-peach", state="low")
    client.post(f"/bottles/{gone}/archive", data={"archived": "1"})

    full = client.get("/bottles")
    assert "<html" in full.text and 'id="bottle-groups"' in full.text
    assert titles_in(full.text) == ["Peely Base", "Thirst Trap"]
    assert "2 bottles in 2 shades" in full.text and "Show archived" in full.text
    # The level filter is one row of five chips, no horizontal scroller.
    assert full.text.count('<a class="chip') == 5 and "chip-scroll" not in full.text
    part = client.get("/bottles", params={"state": "half"}, headers=HX)
    assert "<html" not in part.text and titles_in(part.text) == ["Thirst Trap"]
    assert titles_in(client.get("/bottles?archived=1").text) == ["Rest In Peach"]
    assert "Hide archived" in client.get("/bottles?archived=1").text
    assert 'class="bottle ' not in client.get("/bottles?state=empty").text
    assert "Nothing at this level" in client.get("/bottles?state=empty").text


def test_the_shade_page_has_two_primary_actions_and_a_bottle_list(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    page = client.get(f"/shades/{shade}").text
    assert "Add bottle" in page and 'aria-pressed="false"' in page
    assert f'hx-get="/shades/{shade}/bottles/new"' in page and 'hx-target="#sheet-body"' in page
    assert 'id="sheet-body"' in page and "/static/js/sheet.js" in page
    assert "Owned ×" not in page

    make_bottle(client, conn)
    make_bottle(client, conn, state="low")
    client.post(f"/shades/{shade}/wishlist")
    page = client.get(f"/shades/{shade}").text
    assert "Add bottle" in page and "Owned ×2" in page and 'aria-pressed="true"' in page
    assert page.count('class="bottle"') == 2


def test_shade_rows_show_the_owned_badge_and_wishlist_heart(seeded):
    client, conn = seeded
    make_bottle(client, conn, "thirst-trap")
    make_bottle(client, conn, "thirst-trap")
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist")
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist")
    html = client.get("/shades", params={"q": "thirst"}).text
    assert "Owned ×2" in html and 'aria-label="On the wishlist"' in html
    peely = client.get("/shades", params={"q": "peely"}).text
    assert "Owned ×" not in peely and 'aria-label="On the wishlist"' in peely
    search = client.get("/search", params={"q": "thirst", "ctx": "home"}).text
    assert "Owned ×2" in search


def test_the_owned_filter_lists_only_owned_shades(seeded):
    client, conn = seeded
    make_bottle(client, conn, "thirst-trap")
    make_bottle(client, conn, "peely-base", state="empty")
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist")
    owned = client.get("/shades?owned=owned")
    assert rows(owned) == 1 and titles_in(owned.text) == ["Thirst Trap"]
    assert titles_in(client.get("/shades?owned=wishlist").text) == ["Peely Base"]
    assert rows(client.get("/shades?owned=not_owned")) == rows(client.get("/shades")) - 1
    assert rows(client.get("/shades?owned=bogus")) == rows(client.get("/shades"))
    assert 'name="owned" value="owned" checked' in owned.text


def test_home_shows_counts_and_recent_bottles(seeded):
    client, conn = seeded
    html = client.get("/").text
    assert "bottles</a>" not in html and "Recent bottles" not in html  # nothing to count yet
    assert "No bottles yet" in html and 'href="/lookup?scan=1"' in html
    make_bottle(client, conn, "thirst-trap", printed_code="259")
    make_bottle(client, conn, "thirst-trap")
    make_bottle(client, conn, "peely-base", state="half")
    client.post(f"/shades/{sid(conn, 'rest-in-peach')}/wishlist")
    html = client.get("/").text
    line = re.search(r'<p class="stats-line">(.*?)</p>', html, re.S).group(1)
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', line) == [
        ("/bottles", "3 bottles"),
        ("/shades?owned=owned", "2 shades"),
        ("/wishlist", "1 wished"),
    ]
    assert "Recent bottles" in html and "No bottles yet" not in html
    assert re.findall(r'class="shelf-title">([^<]+)<', html)[:3] == [
        "Peely Base",
        "Thirst Trap",
        "Thirst Trap",
    ]


def test_home_groups_the_browse_links_and_keeps_the_rest_on_more(seeded):
    client, _ = seeded
    html = client.get("/").text
    for href in ("/shades", "/shades?kind=topper", "/more"):
        assert f'class="group-link" href="{href}"' in html
    for kept_out in ("/shades/new", "/sync", "/identifiers", "Sign out"):
        assert kept_out not in html
    more = client.get("/more")
    assert more.status_code == 200
    for href in ("/shades/new", "/sync", "/identifiers"):
        assert f'class="group-link" href="{href}"' in more.text
    assert "Signed in as Dev" in more.text and "Sign out" in more.text


# Wishlist


def test_adding_to_the_wishlist_returns_the_button_with_the_default_priority(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    response = client.post(f"/shades/{shade}/wishlist", headers=HX)
    assert response.status_code == 200 and "<html" not in response.text
    assert 'aria-pressed="true"' in response.text and 'id="shade-actions"' in response.text
    assert conn.execute("select priority from wishlist_item").fetchone()[0] == 2
    client.post(f"/shades/{shade}/wishlist", data={"priority": "1"})
    assert conn.execute("select count(*), min(priority) from wishlist_item").fetchone()[:] == (1, 2)


def test_wishlist_priority_must_be_1_to_3_and_the_shade_must_exist(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    assert client.post(f"/shades/{shade}/wishlist", data={"priority": "4"}).status_code == 422
    assert client.post(f"/shades/{shade}/wishlist", data={"priority": "0"}).status_code == 422
    assert client.post("/shades/9999/wishlist").status_code == 404
    assert client.post(f"/shades/{shade}/wishlist", headers=NO_ORIGIN).status_code == 403
    assert conn.execute("select count(*) from wishlist_item").fetchone()[0] == 0


def test_the_wishlist_page_shows_groups_a_total_and_the_checkout_button(seeded):
    client, conn = seeded
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist", data={"priority": "2"})
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist", data={"priority": "1"})
    client.post(f"/shades/{sid(conn, 'hit-the-lights')}/wishlist", data={"priority": "1"})
    page = client.get("/wishlist")
    assert "<html" in page.text
    assert page.text.index("Want most") < page.text.index("Would like")
    assert titles_in(page.text) == ["Peely Base", "Hit The Lights", "Thirst Trap"]
    assert "$29.00</strong> for 2 shades in stock" in page.text and "1 not buyable" in page.text
    assert "Open in Holo Taco checkout" in page.text and "Copy list" in page.text
    assert 'target="_blank" rel="noopener"' in page.text
    assert "/static/js/copy.js" in page.text


def test_an_empty_wishlist_says_so(client):
    page = client.get("/wishlist").text
    assert "Nothing on the wishlist" in page and "Open in Holo Taco checkout" not in page


def test_the_cart_route_returns_the_permalink_for_buyable_items_only(seeded):
    client, conn = seeded
    for handle, priority in (
        ("thirst-trap", 2),
        ("peely-base", 1),
        ("hit-the-lights", 1),
        ("gold-play-button", 3),
    ):
        client.post(f"/shades/{sid(conn, handle)}/wishlist", data={"priority": str(priority)})
    response = client.get("/wishlist/cart")
    assert "<html" not in response.text
    links = re.findall(r"holotaco\.com/cart/[0-9:,]*", response.text)
    assert links == ["holotaco.com/cart/30936560795738:1,42093180747866:1"]
    assert "Open in Holo Taco checkout" in response.text and "2 not buyable" in response.text
    only_first = client.get("/wishlist/cart", params={"max_priority": 1}, headers=HX)
    assert re.findall(r"holotaco\.com/cart/[0-9:,]*", only_first.text) == [
        "holotaco.com/cart/30936560795738:1"
    ]


def test_the_cart_box_says_so_when_nothing_is_buyable(seeded):
    client, conn = seeded
    client.post(f"/shades/{sid(conn, 'hit-the-lights')}/wishlist")
    html = client.get("/wishlist/cart").text
    assert "cart/" not in html and "Nothing on this part of the list is in stock" in html


def test_changing_priority_moves_the_item_and_keeps_the_note(seeded):
    client, conn = seeded
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist")
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist", data={"priority": "3"})
    item = conn.execute(
        "select id from wishlist_item where shade_id = ?", (sid(conn, "thirst-trap"),)
    ).fetchone()[0]
    response = client.post(
        f"/wishlist/{item}", data={"priority": "3", "note": " pink! "}, headers=HX
    )
    assert response.status_code == 200 and "<html" not in response.text
    assert 'id="wishlist"' in response.text and "Maybe one day" in response.text
    assert 'section-title">Would like' not in response.text and ">pink!</button>" in response.text
    assert client.post(f"/wishlist/{item}", data={"priority": "7"}).status_code == 422
    assert client.post("/wishlist/9999", data={"priority": "1"}).status_code == 404
    assert (
        client.post(f"/wishlist/{item}", data={"priority": "1"}, headers=NO_ORIGIN).status_code
        == 403
    )
    assert (
        conn.execute("select priority from wishlist_item where id = ?", (item,)).fetchone()[0] == 3
    )


def test_the_priority_menu_posts_the_priority_alone_and_keeps_the_note(seeded):
    client, conn = seeded
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist")
    item = conn.execute("select id from wishlist_item").fetchone()[0]
    client.post(f"/wishlist/{item}", data={"priority": "2", "note": "pair with black"})
    page = client.get("/wishlist").text
    # A select per row, one option per priority, the current one selected; no segmented control.
    assert (
        f'<select name="priority" aria-label="Priority of Thirst Trap"'
        f' hx-post="/wishlist/{item}/priority"' in page
    )
    assert re.findall(r'<option value="(\d)"( selected)?>([^<]+)</option>', page) == [
        ("1", "", "Want most"),
        ("2", " selected", "Would like"),
        ("3", "", "Maybe one day"),
    ]
    assert 'name="priority" value=' not in page
    moved = client.post(f"/wishlist/{item}/priority", data={"priority": "1"}, headers=HX)
    assert moved.status_code == 200 and "pair with black" in moved.text
    assert conn.execute("select priority, note from wishlist_item").fetchone()[:] == (
        1,
        "pair with black",
    )
    assert client.post(f"/wishlist/{item}/priority", data={"priority": "7"}).status_code == 422
    assert client.post("/wishlist/9999/priority", data={"priority": "1"}).status_code == 404
    refused = client.post(f"/wishlist/{item}/priority", data={"priority": "3"}, headers=NO_ORIGIN)
    assert refused.status_code == 403
    cleared = client.post(f"/wishlist/{item}", data={"priority": "1", "note": ""}, headers=HX)
    assert "Add a note" in cleared.text
    assert conn.execute("select note from wishlist_item").fetchone()[0] is None


def test_a_wishlist_row_has_a_note_button_and_a_sheet_with_the_note_and_remove(seeded):
    client, conn = seeded
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist")
    item = conn.execute("select id from wishlist_item").fetchone()[0]
    page = client.get("/wishlist").text
    assert "Add a note</button>" in page and f'hx-get="/wishlist/{item}/edit"' in page
    assert "Remove" not in page and "wish-controls" not in page
    sheet = client.get(f"/wishlist/{item}/edit", headers=HX)
    assert sheet.status_code == 200 and "<html" not in sheet.text
    assert 'name="note"' in sheet.text and 'name="priority" value="2"' in sheet.text
    assert (
        f'hx-post="/wishlist/{item}/delete"' in sheet.text and "Remove from wishlist" in sheet.text
    )
    assert client.get("/wishlist/9999/edit").status_code == 404
    saved = client.post(f"/wishlist/{item}", data={"priority": "2", "note": "autumn"}, headers=HX)
    assert saved.headers["hx-trigger"] == "sheetClose" and ">autumn</button>" in saved.text
    assert 'name="note"' in client.get(f"/wishlist/{item}/edit").text
    assert "autumn" in client.get(f"/wishlist/{item}/edit").text
    removed = client.post(f"/wishlist/{item}/delete", data={"ctx": "list"}, headers=HX)
    assert removed.headers["hx-trigger"] == "sheetClose" and "Thirst Trap" not in removed.text
    assert conn.execute("select count(*) from wishlist_item").fetchone()[0] == 0


def test_removing_from_the_list_or_from_the_shade_page(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    client.post(f"/shades/{shade}/wishlist")
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist")
    first, second = (r[0] for r in conn.execute("select id from wishlist_item order by id"))
    from_list = client.post(f"/wishlist/{first}/delete", data={"ctx": "list"}, headers=HX)
    assert 'id="wishlist"' in from_list.text and "Thirst Trap" not in from_list.text
    client.post(f"/shades/{shade}/wishlist")
    again = conn.execute("select id from wishlist_item where shade_id = ?", (shade,)).fetchone()[0]
    from_shade = client.post(f"/wishlist/{again}/delete", data={"ctx": "shade"})
    assert 'aria-pressed="false"' in from_shade.text and 'id="wishlist"' not in from_shade.text
    assert client.post("/wishlist/9999/delete").status_code == 404
    assert client.post(f"/wishlist/{second}/delete", headers=NO_ORIGIN).status_code == 403
    assert conn.execute("select id from wishlist_item").fetchall()[0][0] == second


# Manual shades


def test_new_shade_form_is_declared_before_the_shade_page(seeded):
    client, _ = seeded
    page = client.get("/shades/new", params={"title": "Gifted Glow"})
    assert page.status_code == 200 and 'value="Gifted Glow"' in page.text
    assert client.get("/shades/new", headers=HX).status_code == 200


def test_creating_a_manual_shade_redirects_to_it(seeded):
    client, conn = seeded
    response = client.post("/shades", data={"title": "Gifted Glow", "kind": "topper"})
    assert response.status_code == 302
    shade = conn.execute("select * from shade where source = 'manual'").fetchone()
    assert response.headers["location"] == f"/shades/{shade['id']}"
    assert (shade["title"], shade["kind"], shade["is_topper"]) == ("Gifted Glow", "topcoat", 1)
    page = client.get(response.headers["location"]).text
    assert "Gifted Glow" in page and "Added by hand" in page and "Add bottle" in page
    assert "View on holotaco.com" not in page


def test_a_manual_shade_needs_a_name(seeded):
    client, conn = seeded
    empty = client.post("/shades", data={"title": "  ", "kind": "polish"})
    assert empty.status_code == 422 and "Give the shade a name." in empty.text
    odd = client.post("/shades", data={"title": "X", "kind": "glitter"})
    assert odd.status_code == 422
    assert client.post("/shades", data={"title": "X"}, headers=NO_ORIGIN).status_code == 403
    assert conn.execute("select count(*) from shade where source = 'manual'").fetchone()[0] == 0


# The shared pieces


def test_sheet_script_and_the_422_swap_setting_are_served(seeded):
    client, _ = seeded
    script = client.get("/static/js/sheet.js")
    assert script.status_code == 200 and "sheetClose" in script.text
    assert client.get("/static/js/copy.js").status_code == 200
    assert '"code": "422", "swap": true' in client.get("/wishlist").text


def test_inventory_pages_need_a_login_when_oidc_is_on(oidc_client):
    for path in ("/bottles", "/wishlist", "/wishlist/cart", "/shades/new"):
        response = oidc_client.get(path)
        assert response.status_code == 302 and response.headers["location"].startswith(
            "/auth/login"
        )
    assert oidc_client.post("/shades/1/bottles", data={"state": "full"}).status_code == 401


# Purchase history and "I bought these"


def seed_history(client, conn):
    for handle, day, price in (
        ("thirst-trap", "2026-10-03", "15.50"),
        ("peely-base", "2026-10-20", ""),
        ("hit-the-lights", "2026-02-14", "12.00"),
    ):
        add_bottle(client, sid(conn, handle), bought_on=day, price_paid=price)


def test_history_is_a_page_with_years_months_totals_and_rows_linking_to_shades(seeded):
    client, conn = seeded
    seed_history(client, conn)
    page = client.get("/bottles/history")
    assert page.status_code == 200 and "<html" in page.text
    assert "2026:</span> 3 bottles, $27.50" in page.text and "1 without a price" in page.text
    assert page.text.index("October 2026") < page.text.index("February 2026")
    assert "2 bottles, $15.50, 1 without a price" in page.text
    assert titles_in(page.text) == ["Peely Base", "Thirst Trap", "Hit The Lights"]
    assert f'href="/shades/{sid(conn, "thirst-trap")}"' in page.text
    assert "Bought 3 Oct 2026" in page.text and "$15.50" in page.text
    assert "·" not in page.text


def test_history_keeps_empty_and_archived_bottles_and_says_when_it_used_the_entry_date(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    add_bottle(client, shade, bought_on="2026-10-03")
    conn.execute("update bottle set state = 'empty'")
    add_bottle(client, shade)
    conn.execute("update bottle set archived = 1 where id = 2")
    page = client.get("/bottles/history").text
    assert page.count('class="row-link history-row') == 2
    assert "empty" in page and "Added " in page and "archived" in page


def test_an_empty_history_says_so_and_both_pages_carry_the_switch(client):
    page = client.get("/bottles/history").text
    assert "No purchases yet" in page
    assert 'href="/bottles/history" aria-current="page"' in page
    collection = client.get("/bottles").text
    assert 'href="/bottles" aria-current="page"' in collection
    assert 'href="/bottles/history"' in collection


def test_a_shade_with_only_past_bottles_lists_them_under_past_bottles(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    add_bottle(client, shade, bought_on="2026-10-03", price_paid="15.50")
    conn.execute("update bottle set state = 'empty'")
    page = client.get(f"/shades/{shade}").text
    assert "Past bottles" in page and "No P code" in page
    assert "Bought 3 Oct 2026, $15.50" in page
    assert '<h2 class="section-title">Bottles</h2>' not in page
    add_bottle(client, shade)
    both = client.get(f"/shades/{shade}").text
    assert both.index(">Bottles</h2>") < both.index("Past bottles")


def wish_items(client, conn, *handles_and_priority):
    for handle, priority in handles_and_priority:
        client.post(f"/shades/{sid(conn, handle)}/wishlist", data={"priority": str(priority)})
    return {r["shade_id"]: r["id"] for r in conn.execute("select id, shade_id from wishlist_item")}


def test_the_wishlist_offers_i_bought_these_next_to_the_checkout_box(seeded):
    client, conn = seeded
    wish_items(client, conn, ("thirst-trap", 1))
    page = client.get("/wishlist").text
    assert "I bought these" in page and 'hx-get="/wishlist/bought"' in page
    assert "/static/js/sheet.js" in page
    assert page.index("cart-box") < page.index("I bought these")


def test_the_sheet_ticks_buyable_items_in_the_checkout_selection_and_prefills_prices(seeded):
    client, conn = seeded
    ids = wish_items(
        client,
        conn,
        ("thirst-trap", 1),
        ("peely-base", 3),
        ("last-stock", 1),
    )
    conn.execute("update shade set available = 0 where handle = 'last-stock'")
    today = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    sheet = client.get("/wishlist/bought?max_priority=1").text
    assert "<html" not in sheet and f'value="{today}"' in sheet
    checked = re.findall(r'name="item" value="(\d+)"( checked)?', sheet)
    assert {i: bool(c) for i, c in checked} == {
        str(ids[sid(conn, "thirst-trap")]): True,
        str(ids[sid(conn, "peely-base")]): False,
        str(ids[sid(conn, "last-stock")]): False,
    }
    assert f'name="price-{ids[sid(conn, "thirst-trap")]}" value="15.50"' in sheet
    everything = client.get("/wishlist/bought").text
    assert everything.count(" checked") == 2


def test_the_sheet_uses_the_household_timezone_for_today(tmp_path):
    settings = make_settings(tmp_path, timezone="Pacific/Kiritimati")
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, EXTRA)
    wish_items(client, conn, ("thirst-trap", 1))
    today = datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()
    assert f'value="{today}"' in client.get("/wishlist/bought").text
    conn.close()


def test_submitting_creates_bottles_removes_the_items_and_confirms(seeded):
    client, conn = seeded
    ids = wish_items(client, conn, ("thirst-trap", 1), ("peely-base", 1), ("hit-the-lights", 2))
    a, b, c = (ids[sid(conn, h)] for h in ("thirst-trap", "peely-base", "hit-the-lights"))
    response = client.post(
        "/wishlist/bought",
        headers=HX,
        data={
            "item": [str(a), str(b)],
            "bought_on": "2026-10-25",
            f"price-{a}": "15.50",
            f"price-{b}": "",
            f"price-{c}": "9",
        },
    )
    assert response.status_code == 200 and response.headers["HX-Trigger"] == "sheetClose"
    assert "<html" not in response.text and 'id="wishlist"' in response.text
    assert (
        "2 bottles added. See them in" in response.text
        and 'href="/bottles/history"' in response.text
    )
    bought = conn.execute(
        "select shade_id, state, bought_on, price_paid_cents from bottle order by id"
    ).fetchall()
    assert [tuple(r) for r in bought] == [
        (sid(conn, "thirst-trap"), "full", "2026-10-25", 1550),
        (sid(conn, "peely-base"), "full", "2026-10-25", None),
    ]
    assert [r[0] for r in conn.execute("select id from wishlist_item")] == [c]
    assert "Hit The Lights" in response.text and "Thirst Trap" not in response.text


def test_buying_the_last_item_leaves_the_empty_wishlist_with_the_confirmation(seeded):
    client, conn = seeded
    ids = wish_items(client, conn, ("thirst-trap", 1))
    (item,) = ids.values()
    text = client.post("/wishlist/bought", data={"item": str(item), "bought_on": "2026-10-25"}).text
    assert "1 bottle added." in text and "Nothing on the wishlist" in text


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"bought_on": "yesterday"}, "Use a date like 2026-10-25."),
        ({"price": "lots"}, "Use an amount like 15.50."),
        ({"item": None}, "Tick the shades you bought."),
    ],
)
def test_a_wrong_field_returns_the_sheet_with_a_message_and_changes_nothing(
    seeded, changes, message
):
    client, conn = seeded
    ids = wish_items(client, conn, ("thirst-trap", 1), ("peely-base", 1))
    a, b = (ids[sid(conn, h)] for h in ("thirst-trap", "peely-base"))
    data = {
        "item": [str(a), str(b)],
        "bought_on": changes.get("bought_on", "2026-10-25"),
        f"price-{a}": changes.get("price", "15.50"),
        f"price-{b}": "7.25",
    }
    if "item" in changes:
        del data["item"]
    response = client.post("/wishlist/bought", headers=HX, data=data)
    assert response.status_code == 422
    assert response.headers["HX-Retarget"] == "#sheet-body" and "HX-Trigger" not in response.headers
    assert message in response.text and "I bought these" in response.text
    assert 'value="7.25"' in response.text
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0
    assert conn.execute("select count(*) from wishlist_item").fetchone()[0] == 2


def test_an_unknown_item_is_404_and_nothing_changes(seeded):
    client, conn = seeded
    ids = wish_items(client, conn, ("thirst-trap", 1))
    (item,) = ids.values()
    response = client.post(
        "/wishlist/bought", data={"item": [str(item), "9999"], "bought_on": "2026-10-25"}
    )
    assert response.status_code == 404
    assert (
        client.post("/wishlist/bought", data={"item": "x", "bought_on": "2026-10-25"}).status_code
        == 422
    )
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0
    assert conn.execute("select count(*) from wishlist_item").fetchone()[0] == 1


def test_marking_bought_needs_the_origin_header(seeded):
    client, conn = seeded
    ids = wish_items(client, conn, ("thirst-trap", 1))
    (item,) = ids.values()
    response = client.post(
        "/wishlist/bought",
        headers=NO_ORIGIN,
        data={"item": str(item), "bought_on": "2026-10-25"},
    )
    assert response.status_code == 403
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 0
    assert conn.execute("select count(*) from wishlist_item").fetchone()[0] == 1


def test_history_and_bought_routes_need_a_login_when_oidc_is_on(oidc_client):
    for path in ("/bottles/history", "/wishlist/bought"):
        assert oidc_client.get(path).status_code in (302, 303, 401, 403)
    assert oidc_client.post("/wishlist/bought").status_code in (302, 303, 401, 403)


# Tips replace bottle photos in every list; the bottle photo stays on the shade page and the lookup result


def test_lists_of_shades_show_the_painted_tip_never_a_bottle_photo(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    add_bottle(client, shade, state="half", printed_code="259", bought_on="2026-08-02")
    client.post(f"/shades/{sid(conn, 'last-stock')}/wishlist")
    for url in ("/", "/bottles", "/bottles/history", "/wishlist"):
        html = client.get(url).text
        assert re.search(
            r'<span class="tip-(?:m|l)" aria-hidden="true"><img src="/tips/shade/\d+\.svg\?v=\w+"',
            html,
        ), url
        assert 'class="thumb' not in html and "cdn.shopify.com" not in html, url
    sheet = client.get("/wishlist/bought", headers=HX).text
    assert 'class="tip-s"' in sheet and 'class="thumb' not in sheet
    assert 'class="tip-m"' in client.get("/search", params={"q": "thirst", "ctx": "home"}).text
