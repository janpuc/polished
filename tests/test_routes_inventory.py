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
    return re.findall(r'class="row-title">([^<]+)<', html)


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
    assert "+ Add bottle" in response.text and "owned ×1" in response.text
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
    pressed = re.findall(r'class="state-chip state-(\w+)" aria-pressed="true"', response.text)
    assert pressed == ["low"]
    assert conn.execute("select state from bottle").fetchone()[0] == "low"


def test_emptying_the_last_bottle_turns_the_shade_page_action_back_to_i_have_this(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    bottle = make_bottle(client, conn)
    assert "+ Add bottle" in client.get(f"/shades/{shade}").text
    response = client.post(f"/bottles/{bottle}/state", data={"state": "empty", "ctx": "shade"})
    assert 'hx-swap-oob="true"' in response.text and "I have this" in response.text
    assert "owned ×" not in response.text
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
    assert "Archived" in archived.text and "Restore" in archived.text
    assert conn.execute("select archived from bottle").fetchone()[0] == 1
    assert "I have this" in client.get(f"/shades/{shade}").text
    restored = client.post(f"/bottles/{bottle}/archive", data={"archived": "0"})
    assert "Archive" in restored.text and "Restore" not in restored.text
    assert "+ Add bottle" in client.get(f"/shades/{shade}").text


def test_delete_removes_the_card_closes_the_sheet_and_updates_the_action_bar(seeded):
    client, conn = seeded
    bottle = make_bottle(client, conn)
    response = client.post(f"/bottles/{bottle}/delete", data={"ctx": "shade"}, headers=HX)
    assert response.status_code == 200
    assert response.headers["hx-trigger"] == "sheetClose"
    assert f'id="bottle-{bottle}"' not in response.text and "I have this" in response.text
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
    assert "2 bottles in 2 shades" in full.text
    part = client.get("/bottles", params={"state": "half"}, headers=HX)
    assert "<html" not in part.text and titles_in(part.text) == ["Thirst Trap"]
    assert titles_in(client.get("/bottles?archived=1").text) == ["Rest In Peach"]
    assert 'class="bottle ' not in client.get("/bottles?state=empty").text
    assert "No bottles at this level." in client.get("/bottles?state=empty").text


def test_the_shade_page_has_two_primary_actions_and_a_bottle_list(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    page = client.get(f"/shades/{shade}").text
    assert "I have this" in page and "♡ Wishlist" in page
    assert f'hx-get="/shades/{shade}/bottles/new"' in page and 'hx-target="#sheet-body"' in page
    assert 'id="sheet-body"' in page and "/static/js/sheet.js" in page
    assert "owned ×" not in page

    make_bottle(client, conn)
    make_bottle(client, conn, state="low")
    client.post(f"/shades/{shade}/wishlist")
    page = client.get(f"/shades/{shade}").text
    assert "+ Add bottle" in page and "owned ×2" in page and "♥ On wishlist" in page
    assert page.count('class="bottle"') == 2


def test_shade_rows_show_the_owned_badge_and_wishlist_heart(seeded):
    client, conn = seeded
    make_bottle(client, conn, "thirst-trap")
    make_bottle(client, conn, "thirst-trap")
    client.post(f"/shades/{sid(conn, 'thirst-trap')}/wishlist")
    client.post(f"/shades/{sid(conn, 'peely-base')}/wishlist")
    html = client.get("/shades", params={"q": "thirst"}).text
    assert "owned ×2" in html and 'aria-label="On the wishlist"' in html
    peely = client.get("/shades", params={"q": "peely"}).text
    assert "owned ×" not in peely and 'aria-label="On the wishlist"' in peely
    search = client.get("/search", params={"q": "thirst", "ctx": "home"}).text
    assert "owned ×2" in search


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
    assert (
        re.search(r"<strong>0</strong><span>bottles</span>", html) and "Recent bottles" not in html
    )
    make_bottle(client, conn, "thirst-trap", printed_code="259")
    make_bottle(client, conn, "thirst-trap")
    make_bottle(client, conn, "peely-base", state="half")
    client.post(f"/shades/{sid(conn, 'rest-in-peach')}/wishlist")
    html = client.get("/").text
    assert "<strong>3</strong><span>bottles</span>" in html
    assert "<strong>2</strong><span>shades owned</span>" in html
    assert "<strong>1</strong><span>wishlist · $13.50</span>" in html
    assert "Recent bottles" in html
    assert titles_in(html)[:3] == ["Peely Base", "Thirst Trap", "Thirst Trap"]


# Wishlist


def test_adding_to_the_wishlist_returns_the_button_with_the_default_priority(seeded):
    client, conn = seeded
    shade = sid(conn, "thirst-trap")
    response = client.post(f"/shades/{shade}/wishlist", headers=HX)
    assert response.status_code == 200 and "<html" not in response.text
    assert "♥ On wishlist" in response.text and 'id="shade-actions"' in response.text
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
    assert "<strong>3</strong> shades" in page.text and "$44.00" in page.text
    assert "2 buyable now, $29.00" in page.text
    assert "Open in Holo Taco checkout" in page.text and "Copy the list" in page.text
    assert 'target="_blank" rel="noopener"' in page.text
    assert "/static/js/copy.js" in page.text


def test_an_empty_wishlist_says_so(client):
    page = client.get("/wishlist").text
    assert "Nothing on the wishlist yet" in page and "Open in Holo Taco checkout" not in page


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
    assert "Open in Holo Taco checkout" in response.text and "2 not buyable now" in response.text
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
    assert "Would like" not in response.text and 'value="pink!"' in response.text
    assert client.post(f"/wishlist/{item}", data={"priority": "7"}).status_code == 422
    assert client.post("/wishlist/9999", data={"priority": "1"}).status_code == 404
    assert (
        client.post(f"/wishlist/{item}", data={"priority": "1"}, headers=NO_ORIGIN).status_code
        == 403
    )
    assert (
        conn.execute("select priority from wishlist_item where id = ?", (item,)).fetchone()[0] == 3
    )


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
    assert "♡ Wishlist" in from_shade.text and 'id="wishlist"' not in from_shade.text
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
    assert "Gifted Glow" in page and "Added by hand" in page and "I have this" in page
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
