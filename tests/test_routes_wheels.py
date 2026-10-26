import re

import pytest
from shade_data import made_from, seed, shade_id
from test_auth import signed_in

from polished import stacks, wheels

BLACK = made_from("thirst-trap", 1, "One-Coat Black")
FLAKIE = made_from("aurora-unicorn-skin", 3, "Flakie Holo Taco")


@pytest.fixture
def catalog(conn):
    seed(conn, [BLACK, FLAKIE])
    return conn


def swatch(conn, wheel_id, position, *handles):
    """A saved slot holding these shades, base first."""
    draft = stacks.open_draft(conn, wheel_id, position).stack_id
    for handle in handles:
        stacks.append(conn, draft, shade_id(conn, handle))
    stacks.save(conn, draft)


def make_wheel(client, name="Holos"):
    response = client.post("/wheels", data={"name": name})
    assert response.status_code == 302
    return int(re.fullmatch(r"/wheels/(\d+)/tag", response.headers["location"]).group(1))


# --- the list and create ---------------------------------------------------------------


def test_empty_list_invites_the_first_wheel(client):
    page = client.get("/wheels").text
    assert "No wheels yet" in page and 'action="/wheels"' in page


def test_create_redirects_to_the_tag_page(client, conn):
    wheel_id = make_wheel(client)
    assert wheels.get(conn, wheel_id)["slot_count"] == 20


def test_create_with_a_bad_name_or_count_is_422_and_keeps_the_input(client):
    page = client.post("/wheels", data={"name": "  ", "slot_count": "20"})
    assert page.status_code == 422 and "A wheel needs a name." in page.text
    page = client.post("/wheels", data={"name": "Holos", "slot_count": "41"})
    assert page.status_code == 422 and 'value="Holos"' in page.text
    assert client.post("/wheels", data={"name": "Holos", "slot_count": "x"}).status_code == 422


def test_list_shows_the_count_and_hides_archived_wheels(client, conn):
    first = make_wheel(client, "Holos")
    make_wheel(client, "Glitters")
    client.post(f"/wheels/{first}/archive", data={"archived": "1"})
    page = client.get("/wheels").text
    assert "Glitters" in page and "0 of 20<" in page
    assert "Holos" not in page.split('class="group wheel-list"')[1].split("</ul>")[0]
    assert "Archived wheels" in page
    archived = client.get("/wheels?archived=1").text
    assert "Holos" in archived and "Glitters" not in archived


def test_the_empty_list_shows_the_unpainted_ring_and_the_form_open(client):
    page = client.get("/wheels").text
    assert page.count('class="slot slot-pos-') == 12 and "is-filled" not in page
    assert "new-wheel-box" not in page and 'action="/wheels"' in page


def test_each_wheel_row_is_a_ring_of_its_own_tips_with_its_count(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 3, "one-coat-black", "flakie-holo-taco")
    stacks.open_draft(catalog, wheel_id, 5)
    stack_id = wheels.slot_tile(catalog, wheels.get(catalog, wheel_id), 3)["stack_id"]
    page = client.get("/wheels").text
    row = re.search(r'<a class="wheel-row".*?</a>', page, re.S).group(0)
    assert row.count('class="slot slot-pos-') == 20 and row.count("is-filled") == 1
    assert f'src="/tips/stack/{stack_id}.svg?v=' in row and 'class="ring ring-mini"' in row
    assert "1 of 20, 1 draft<" in row and "mini-dot" not in page
    assert 'aria-label="New wheel"' in page  # the + in the title row opens the form


def test_a_failed_create_keeps_the_form_open_on_the_list(catalog, client):
    wheels.create(catalog, "Holos")
    page = client.post("/wheels", data={"name": " ", "slot_count": "20"}).text
    assert (
        re.search(r'<details class="new-wheel-box" open>', page) and "A wheel needs a name." in page
    )


# --- the tag page and the QR code ------------------------------------------------------


def test_tag_page_shows_the_full_url_and_the_qr(client, conn, settings):
    wheel_id = make_wheel(client)
    slug = wheels.get(conn, wheel_id)["slug"]
    page = client.get(f"/wheels/{wheel_id}/tag").text
    assert re.search(re.escape(settings.public_url) + r"/w/[0-9a-z]{6}\b", page)
    assert f"{settings.public_url}/w/{slug}" in page
    assert f"/wheels/{wheel_id}/qr.svg" in page and "data-copy" in page
    assert "NFC Tools" in page


def test_tag_page_copy_address_is_the_filled_action_and_the_lede_changes_by_width(client):
    wheel_id = make_wheel(client)
    page = client.get(f"/wheels/{wheel_id}/tag").text
    copy = re.search(r'<button type="button" class="([^"]*)" data-copy="#tag-url">', page)
    assert copy and "btn-secondary" not in copy.group(1) and "btn-block" in copy.group(1)
    assert 'class="btn btn-secondary btn-block tag-open"' in page  # Open the wheel is quiet
    # one page, two renderings picked by CSS width: no user-agent branching
    assert 'class="lede tag-lede-narrow"' in page and 'class="lede tag-lede-wide"' in page
    assert "Scan this with the iPhone camera, then write the sticker from NFC Tools there." in page
    assert "Or write it from the Polished app on iPhone." in page
    assert '<details class="tag-steps-wide">' in page  # collapsed: no `open`
    assert 'class="tag-steps-narrow"' in page
    assert page.count("Open NFC Tools on your iPhone and tap Write.") == 2
    assert client.get(f"/wheels/{wheel_id}/tag", headers={"User-Agent": "iPad"}).text == page


def test_tag_page_of_an_unknown_wheel_is_404(client):
    assert client.get("/wheels/99/tag").status_code == 404


def test_qr_is_an_svg_that_differs_per_wheel(client):
    one, two = make_wheel(client, "One"), make_wheel(client, "Two")
    first = client.get(f"/wheels/{one}/qr.svg")
    assert first.headers["content-type"].startswith("image/svg+xml")
    assert first.text.startswith("<svg")
    assert first.headers["cache-control"] == "private, max-age=86400"
    assert client.get(f"/wheels/{two}/qr.svg").text != first.text
    assert client.head(f"/wheels/{one}/qr.svg").status_code == 200
    assert client.get("/wheels/99/qr.svg").status_code == 404


# --- the wheel page --------------------------------------------------------------------


def test_wheel_page_has_a_tile_per_slot(client, conn):
    wheel_id = make_wheel(client)
    page = client.get(f"/w/{wheels.get(conn, wheel_id)['slug']}").text
    ids = re.findall(r'id="slot-(\d+)"', page)
    assert ids == [str(n) for n in range(1, 21)]
    assert "0 of 20 swatched" in page
    assert 'aria-labelledby="ring-label"' in page and 'id="ring-label"' in page
    assert 'hx-post="/wheels/1/slots/7/draft"' in page and 'hx-target="#sheet-body"' in page


def test_a_wheel_with_another_slot_count_has_that_many_tiles(client, conn):
    wheel_id = wheels.create(conn, "Small", 12)
    page = client.get(f"/w/{wheels.get(conn, wheel_id)['slug']}").text
    assert len(re.findall(r'id="slot-\d+"', page)) == 12
    assert "ring-n-12" in page and "ring-n-20" not in page


def test_filled_slots_show_the_stack_drawing_and_the_list(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 3, "one-coat-black", "flakie-holo-taco")
    stacks.open_draft(catalog, wheel_id, 5)
    page = client.get(f"/w/{wheels.get(catalog, wheel_id)['slug']}").text
    assert "1 of 20 swatched" in page
    assert 'class="slot slot-pos-3 ring-n-20 is-filled"' in page
    assert "/tips/stack/" in page and "tip-bands" not in page
    assert "tip-dot" in page and "draft in progress" in page
    summary = wheels.slot_grid(catalog, wheels.get(catalog, wheel_id))[2]["summary"]
    assert "Flakie Holo Taco" in summary and summary in page


def test_unknown_slug_is_404_when_signed_in(client):
    response = client.get("/w/zzzzzz")
    assert response.status_code == 404 and "no wheel with that address" in response.text


def test_signed_out_slug_redirects_to_login_whether_or_not_it_exists(
    oidc_client, oidc_app_settings
):
    unknown = oidc_client.get("/w/abc123")
    assert unknown.status_code == 302
    assert unknown.headers["location"] == "/auth/login?next=%2Fw%2Fabc123"
    from polished.db import connect

    conn = connect(oidc_app_settings.db_path)
    wheels.create(conn, "Holos")
    slug = conn.execute("select slug from wheel").fetchone()["slug"]
    known = oidc_client.get(f"/w/{slug}")
    assert known.headers["location"] == f"/auth/login?next=%2Fw%2F{slug}"
    signed_in(oidc_app_settings, oidc_client)
    assert oidc_client.get(f"/w/{slug}").status_code == 200
    conn.close()


def test_highlight_marks_matching_tiles_and_dims_the_rest(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 2, "one-coat-black", "flakie-holo-taco")
    swatch(catalog, wheel_id, 9, "flakie-holo-taco")
    swatch(catalog, wheel_id, 11, "one-coat-black")
    slug = wheels.get(catalog, wheel_id)["slug"]
    page = client.get(f"/w/{slug}?hl={shade_id(catalog, 'flakie-holo-taco')}").text
    assert len(re.findall(r'class="slot [^"]*\bis-hl\b', page)) == 2
    assert "slot-pos-2 ring-n-20 is-filled is-hl" in page
    assert "slot-pos-9 ring-n-20 is-filled is-hl" in page
    assert "slot-pos-11 ring-n-20 is-filled is-dim" in page
    assert "slot-pos-1 ring-n-20 is-dim" in page
    assert "Flakie Holo Taco</strong> is on slots 2, 9" in page


def test_highlight_of_a_shade_that_is_not_there_says_so(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 2, "one-coat-black")
    slug = wheels.get(catalog, wheel_id)["slug"]
    page = client.get(f"/w/{slug}?hl={shade_id(catalog, 'flakie-holo-taco')}").text
    assert "is not on this wheel" in page and "is-hl" not in page
    plain = client.get(f"/w/{slug}?hl=abc").text
    assert "hl-note" not in plain and "is-dim" not in plain


# --- rename, archive, move the tag -----------------------------------------------------


def test_rename_keeps_the_slug_and_answers_htmx_with_out_of_band_names(client, conn):
    wheel_id = make_wheel(client)
    slug = wheels.get(conn, wheel_id)["slug"]
    plain = client.post(f"/wheels/{wheel_id}", data={"name": "Rainbows"})
    assert plain.status_code == 302 and plain.headers["location"] == f"/w/{slug}"
    fragment = client.post(
        f"/wheels/{wheel_id}", data={"name": "Foils"}, headers={"HX-Request": "true"}
    )
    assert 'id="wheel-name"' in fragment.text and "Foils" in fragment.text
    assert 'id="ring-label"' in fragment.text and ">Foils, 0 of 20 swatched<" in fragment.text
    assert wheels.get(conn, wheel_id)["slug"] == slug
    bad = client.post(f"/wheels/{wheel_id}", data={"name": " "}, headers={"HX-Request": "true"})
    assert bad.status_code == 422 and bad.headers["HX-Retarget"] == "#rename-status"
    assert client.post("/wheels/99", data={"name": "x"}).status_code == 404


def test_the_rename_sheet_has_the_name_and_a_saved_rename_closes_it(client, conn):
    wheel_id = make_wheel(client)
    sheet = client.get(f"/wheels/{wheel_id}/rename")
    assert sheet.status_code == 200 and "<html" not in sheet.text
    assert 'value="Holos"' in sheet.text and f'hx-post="/wheels/{wheel_id}"' in sheet.text
    assert client.get("/wheels/99/rename").status_code == 404
    saved = client.post(
        f"/wheels/{wheel_id}", data={"name": "Foils"}, headers={"HX-Request": "true"}
    )
    assert saved.headers["HX-Trigger"] == "sheetClose"
    assert wheels.get(conn, wheel_id)["name"] == "Foils"


def test_the_wheel_page_ends_in_a_quiet_row_of_actions(client, conn):
    wheel_id = make_wheel(client)
    slug = wheels.get(conn, wheel_id)["slug"]
    page = client.get(f"/w/{slug}").text
    foot = re.search(r'<nav class="wheel-foot".*?</nav>', page, re.S).group(0)
    assert f'href="/wheels/{wheel_id}/tag"' in foot
    assert f'hx-get="/wheels/{wheel_id}/rename"' in foot
    assert f'hx-get="/wheels/{wheel_id}/delete"' in foot and ">Delete</button>" in foot
    assert "btn-danger" in foot and "/archive" not in foot  # Archive lives in the Rename sheet
    assert "This wheel</h2>" not in page and 'id="rename"' not in page


def test_the_rename_sheet_holds_archive_as_a_quiet_action(client, conn):
    wheel_id = make_wheel(client)
    sheet = client.get(f"/wheels/{wheel_id}/rename").text
    quiet = re.search(r'<div class="sheet-quiet">.*?</div>', sheet, re.S).group(0)
    assert f'hx-post="/wheels/{wheel_id}/archive"' in quiet and "hx-confirm" in quiet
    client.post(f"/wheels/{wheel_id}/archive", data={"archived": "1"})
    assert "sheet-quiet" not in client.get(f"/wheels/{wheel_id}/rename").text


def test_archive_keeps_the_slug_and_the_page_shows_the_banner(client, conn):
    one, two = make_wheel(client, "One"), make_wheel(client, "Two")
    slug = wheels.get(conn, one)["slug"]
    response = client.post(f"/wheels/{one}/archive", data={"archived": "1"})
    assert response.headers["location"] == "/wheels"
    assert wheels.get(conn, one)["slug"] == slug
    page = client.get(f"/w/{slug}").text
    assert "This wheel is archived" in page and ">Restore<" in page
    assert "Take the tag of" in page and f'value="{two}"' in page
    assert "Archive wheel" not in page
    restored = client.post(f"/wheels/{one}/archive", data={"archived": "0"})
    assert restored.headers["location"] == f"/w/{slug}"
    assert "This wheel is archived" not in client.get(f"/w/{slug}").text


def test_htmx_buttons_get_hx_redirect_instead_of_a_302(client, conn):
    wheel_id = make_wheel(client)
    response = client.post(f"/wheels/{wheel_id}/archive", headers={"HX-Request": "true"})
    assert response.status_code == 200 and response.headers["HX-Redirect"] == "/wheels"


def test_regenerate_changes_the_slug_and_the_old_one_404s(client, conn):
    wheel_id = make_wheel(client)
    old = wheels.get(conn, wheel_id)["slug"]
    response = client.post(f"/wheels/{wheel_id}/slug/regenerate")
    assert response.headers["location"] == f"/wheels/{wheel_id}/tag"
    assert wheels.get(conn, wheel_id)["slug"] != old
    assert client.get(f"/w/{old}").status_code == 404
    assert client.post("/wheels/99/slug/regenerate").status_code == 404


def test_take_swaps_the_two_slugs(client, conn):
    one, two = make_wheel(client, "One"), make_wheel(client, "Two")
    slug_one, slug_two = (wheels.get(conn, w)["slug"] for w in (one, two))
    page = client.get(f"/wheels/{two}/tag").text
    assert f'value="{one}"' in page
    response = client.post(f"/wheels/{two}/slug/take", data={"from_wheel_id": one})
    assert response.headers["location"] == f"/wheels/{two}/tag"
    assert wheels.get(conn, two)["slug"] == slug_one
    assert wheels.get(conn, one)["slug"] == slug_two
    assert client.post(f"/wheels/{two}/slug/take", data={"from_wheel_id": two}).status_code == 422
    assert client.post(f"/wheels/{two}/slug/take", data={"from_wheel_id": 99}).status_code == 404


# --- swatched on -----------------------------------------------------------------------


def test_shade_page_lists_where_the_shade_is_swatched(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 12, "one-coat-black")
    slug = wheels.get(catalog, wheel_id)["slug"]
    black = shade_id(catalog, "one-coat-black")
    page = client.get(f"/shades/{black}").text
    assert "Swatched on" in page and "Holos, slot 12" in page
    assert f'href="/w/{slug}?hl={black}#slot-12"' in page
    assert "Swatched on" not in client.get(f"/shades/{shade_id(catalog, 'flakie-holo-taco')}").text


def test_a_filled_tip_is_the_stack_drawing_and_never_a_photo(client, catalog):
    wheel_id = make_wheel(client)
    swatch(catalog, wheel_id, 1, "one-coat-black", "flakie-holo-taco")
    stack_id = wheels.slot_tile(catalog, wheels.get(catalog, wheel_id), 1)["stack_id"]
    slug = wheels.get(catalog, wheel_id)["slug"]
    page = client.get(f"/w/{slug}").text
    tile = re.search(r'id="slot-1".*?</div>', page, re.S).group(0)
    assert f'src="/tips/stack/{stack_id}.svg?v=' in tile
    assert "cdn.shopify.com" not in tile and "is-bottle" not in page and "tip-bands" not in page
    slot_list = re.search(r'id="slot-list".*', page, re.S).group(0)
    assert f'src="/tips/stack/{stack_id}.svg?v=' in slot_list  # the composite tip, one per row
    assert '<span class="tip tip-m"' in slot_list and "cdn.shopify.com" not in slot_list
    assert ">1<" in page and "of 20 swatched" in page  # the hub shows the count, not the name twice


# --- home and the shade page ----------------------------------------------------------


def test_home_opens_on_the_ring_of_the_wheel_touched_last(catalog, client):
    page = client.get("/").text
    assert "No wheels yet" in page and 'href="/wheels"' in page
    assert page.count('class="slot slot-pos-') == 12 and "is-filled" not in page
    quiet = wheels.create(catalog, "Winter")
    busy = wheels.create(catalog, "Holos")
    swatch(catalog, busy, 3, "one-coat-black")
    page = client.get("/").text
    slug = wheels.get(catalog, busy)["slug"]
    assert f'<a class="home-wheel" href="/w/{slug}">' in page
    assert "<strong>Holos</strong>, 1 of 20" in page and "Winter" not in page
    assert page.count('class="slot slot-pos-') == 20 and 'class="ring ring-home"' in page
    swatch(catalog, quiet, 1, "flakie-holo-taco")
    catalog.execute(
        "update stack set updated_at = '2030-01-01T00:00:00.000Z' where id = ?",
        (wheels.slot_tile(catalog, wheels.get(catalog, quiet), 1)["stack_id"],),
    )
    assert "<strong>Winter</strong>, 1 of 20" in client.get("/").text


def test_swatched_on_rows_lead_with_the_stack_tip(catalog, client):
    wheel_id = wheels.create(catalog, "Holos")
    swatch(catalog, wheel_id, 12, "one-coat-black", "flakie-holo-taco")
    stack_id = wheels.slot_tile(catalog, wheels.get(catalog, wheel_id), 12)["stack_id"]
    black = shade_id(catalog, "one-coat-black")
    page = client.get(f"/shades/{black}").text
    row = re.search(
        r'<a class="group-link group-link-tip" href="/w/[^"]+">.*?</a>', page, re.S
    ).group(0)
    assert (
        f'<span class="tip tip-s" aria-hidden="true"><span class="tip-face"><img src="/tips/stack/{stack_id}.svg'
        in row
    )
    assert row.index("tip-s") < row.index("Holos, slot 12")


# --- delete -------------------------------------------------------------------------------


def test_delete_sheet_names_the_wheel_and_counts_its_swatches(client, catalog):
    wheel_id = make_wheel(client, "Test")
    empty = client.get(f"/wheels/{wheel_id}/delete", headers={"HX-Request": "true"})
    assert empty.status_code == 200 and "<html" not in empty.text
    assert "Delete Test?" in empty.text
    assert "This removes the wheel and its tag address." in empty.text
    assert "its 0 swatches" not in empty.text
    swatch(catalog, wheel_id, 1, "one-coat-black")
    swatch(catalog, wheel_id, 2, "one-coat-black", "flakie-holo-taco")
    sheet = client.get(f"/wheels/{wheel_id}/delete").text
    assert "Delete Test?" in sheet
    assert "This removes the wheel, its 2 swatches and its tag address." in sheet
    assert "The sticker will stop opening anything." in sheet
    assert 'name="confirm" value="yes"' in sheet and ">Delete wheel<" in sheet
    assert "btn-danger" in sheet and "hx-confirm" not in sheet  # the sheet is the confirmation
    assert "Test, 2 of 20" in re.sub(r"<[^>]+>", "", sheet)  # the mini ring and its count
    assert f'hx-post="/wheels/{wheel_id}/delete"' in sheet and "data-sheet-close" in sheet


def test_delete_sheet_says_one_swatch_goes(client, catalog):
    wheel_id = make_wheel(client, "Test")
    swatch(catalog, wheel_id, 1, "one-coat-black")
    assert "its 1 swatch and its tag address" in client.get(f"/wheels/{wheel_id}/delete").text


def test_the_archived_banner_offers_delete_as_well(client, conn):
    wheel_id = make_wheel(client)
    client.post(f"/wheels/{wheel_id}/archive", data={"archived": "1"})
    page = client.get(f"/w/{wheels.get(conn, wheel_id)['slug']}").text
    banner = re.search(r'<section class="notice banner".*?</section>', page, re.S).group(0)
    assert f'hx-get="/wheels/{wheel_id}/delete"' in banner


def test_delete_removes_the_wheel_and_leaves_the_others(client, catalog):
    gone = make_wheel(client, "Test")
    kept = make_wheel(client, "Holos")
    swatch(catalog, gone, 1, "one-coat-black", "flakie-holo-taco")
    stacks.open_draft(catalog, gone, 4)
    swatch(catalog, kept, 1, "one-coat-black")
    slug = wheels.get(catalog, gone)["slug"]
    shades_before = catalog.execute("select count(*) from shade").fetchone()[0]

    response = client.post(f"/wheels/{gone}/delete", data={"confirm": "yes"})
    assert response.status_code == 302 and response.headers["location"] == "/wheels"

    assert wheels.get(catalog, gone) is None
    assert client.get(f"/w/{slug}").status_code == 404
    assert client.get(f"/wheels/{gone}/tag").status_code == 404
    assert [w["name"] for w in wheels.list_wheels(catalog)] == ["Holos"]
    assert catalog.execute("select count(*) from stack").fetchone()[0] == 1
    assert catalog.execute("select count(*) from shade").fetchone()[0] == shades_before
    listing = client.get("/wheels").text
    assert 'role="status">Deleted Test</p>' in listing and 'wheel-name">Test<' not in listing
    assert "Deleted" not in client.get("/wheels").text  # shown once


def test_delete_from_the_sheet_answers_an_htmx_redirect(client):
    wheel_id = make_wheel(client)
    response = client.post(
        f"/wheels/{wheel_id}/delete", data={"confirm": "yes"}, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200 and response.headers["HX-Redirect"] == "/wheels"


@pytest.mark.parametrize("data", [{}, {"confirm": ""}, {"confirm": "no"}, {"confirm": "YES"}])
def test_delete_without_the_confirmation_does_nothing(client, conn, data):
    wheel_id = make_wheel(client)
    response = client.post(f"/wheels/{wheel_id}/delete", data=data)
    assert response.status_code == 400
    assert wheels.get(conn, wheel_id) is not None


def test_delete_checks_the_origin(client, conn):
    wheel_id = make_wheel(client)
    for origin in ("", "https://evil.example"):
        response = client.post(
            f"/wheels/{wheel_id}/delete", data={"confirm": "yes"}, headers={"Origin": origin}
        )
        assert response.status_code == 403
    assert wheels.get(conn, wheel_id) is not None


def test_delete_is_post_only_and_an_unknown_wheel_is_404(client):
    wheel_id = make_wheel(client)
    assert client.delete(f"/wheels/{wheel_id}/delete").status_code == 405
    assert client.post("/wheels/999/delete", data={"confirm": "yes"}).status_code == 404
    assert client.post("/wheels/999/delete").status_code == 404
    assert client.get("/wheels/999/delete").status_code == 404


def test_delete_needs_a_signed_in_user_when_auth_is_on(oidc_client):
    response = oidc_client.post("/wheels/1/delete", data={"confirm": "yes"})
    assert response.status_code == 401
