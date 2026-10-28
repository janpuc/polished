"""The builder through the test client: every edit is a round trip against a draft (DESIGN 10)."""

import re

import pytest
from shade_data import made_from, seed, shade_id
from test_routes_wheels import make_wheel, swatch

from polished import stacks, wheels

BLACK = made_from("thirst-trap", 1, "One-Coat Black")
FLAKIE = made_from("aurora-unicorn-skin", 3, "Flakie Holo Taco")
SPIRIT = made_from("jam-session", 2, "Spirit Fingers")
PARTIAL = {"HX-Request": "true"}


@pytest.fixture
def catalog(conn):
    seed(conn, [BLACK, SPIRIT, FLAKIE])
    return conn


@pytest.fixture
def wheel(client, catalog):
    return make_wheel(client)


def open_sheet(client, wheel_id, position=12):
    response = client.post(f"/wheels/{wheel_id}/slots/{position}/draft", headers=PARTIAL)
    assert response.status_code == 200
    return int(re.search(r"/stacks/(\d+)/cancel", response.text).group(1)), response


def add(client, stack_id, conn, handle, **data):
    return client.post(
        f"/stacks/{stack_id}/layers",
        data={"shade_id": shade_id(conn, handle), **data},
        headers=PARTIAL,
    )


def titles(conn, stack_id):
    return [(layer["title"], layer["coats"]) for layer in stacks.layers(conn, stack_id)]


def region(text, element_id):
    """The element with this id, up to its closing tag, for asserting what is inside."""
    start = text.index(f'id="{element_id}"')
    return text[start : text.index("</div>\n", start)]


# --- the full flow ---------------------------------------------------------------------


def test_the_builder_flow_from_an_empty_slot_to_a_saved_swatch(client, catalog, wheel):
    stack_id, opened = open_sheet(client, wheel)
    # The sheet: heading, empty state, the shortcut, the search form and a slot tile out of band.
    assert "Slot 12" in opened.text and "Holos" in opened.text
    assert "No layers yet. Search for the base shade, or tap Over black." in opened.text
    assert "Nothing on this nail yet" in opened.text
    assert 'id="picker-form"' in opened.text and 'id="save-form"' in opened.text
    assert (
        'id="save-button"' in opened.text
        and " disabled" in opened.text.split('id="save-button"')[1][:80]
    )
    assert 'id="slot-12"' in opened.text and 'hx-swap-oob="outerHTML"' in opened.text
    assert "Resumed your draft." not in opened.text
    # Three taps on + build x + y + z.
    first = add(client, stack_id, catalog, "spirit-fingers")
    assert first.status_code == 200
    assert first.headers["HX-Trigger"] == "pickerReset"
    assert first.text.lstrip().startswith('<div id="stack-layers"')
    assert "is-new" in first.text and "Spirit Fingers" in first.text
    assert re.search(r'<p id="stack-summary"[^>]*hx-swap-oob="true">Spirit Fingers</p>', first.text)
    assert (
        'id="save-button"' in first.text
        and "disabled" not in first.text.split('id="save-button"')[1][:80]
    )
    assert 'id="picker-results" hx-swap-oob="innerHTML"' in first.text
    add(client, stack_id, catalog, "flakie-holo-taco")
    assert titles(catalog, stack_id) == [("Spirit Fingers", 1), ("Flakie Holo Taco", 1)]
    # Over black puts the black base first, with one coat; a second tap says it is there.
    over = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert over.status_code == 200 and "Already over black." not in over.text
    assert titles(catalog, stack_id)[0] == ("One-Coat Black", 1)
    again = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert "Already over black." in again.text and len(titles(catalog, stack_id)) == 3
    # Move: the second layer goes up; a layer's coats change; a layer goes.
    layers = stacks.layers(catalog, stack_id)
    move = client.post(
        f"/stacks/{stack_id}/layers/{layers[1]['id']}/move", data={"dir": "up"}, headers=PARTIAL
    )
    assert move.status_code == 200 and move.headers.get("HX-Trigger") is None
    assert [t for t, _ in titles(catalog, stack_id)][0] == layers[1]["title"]
    coats = client.post(
        f"/stacks/{stack_id}/layers/{layers[1]['id']}/coats", data={"delta": "1"}, headers=PARTIAL
    )
    assert coats.status_code == 200
    assert dict(titles(catalog, stack_id))[layers[1]["title"]] == 2
    gone = client.post(f"/stacks/{stack_id}/layers/{layers[2]['id']}/delete", headers=PARTIAL)
    assert gone.status_code == 200 and len(titles(catalog, stack_id)) == 2
    # Save: the tile comes back out of band as saved, the sheet closes.
    saved = client.post(
        f"/stacks/{stack_id}/save",
        data={"name": "Night owl", "note": "Two coats", "painted_on": "2026-10-20"},
        headers=PARTIAL,
    )
    assert saved.status_code == 200
    assert saved.headers["HX-Trigger"] == "sheetClose"
    assert 'id="slot-12"' in saved.text and "is-saved" in saved.text and "is-filled" in saved.text
    assert 'id="slot-list"' in saved.text
    assert 'id="hub-name" class="hub-name" hx-swap-oob="outerHTML">1<' in saved.text
    assert 'id="hub-count" class="hub-count" hx-swap-oob="outerHTML">of 20<' in saved.text
    assert re.search(
        r'<span id="ring-label" class="visually-hidden" hx-swap-oob="outerHTML">[^<]*, 1 of 20 swatched<',
        saved.text,
    )
    slot = wheels.slot_grid(catalog, wheels.get(catalog, wheel))[11]
    assert slot["filled"] and " + " in slot["summary"]
    assert slot["summary"] in saved.text
    row = catalog.execute("select note, painted_on from wheel_slot where position = 12").fetchone()
    assert (row["note"], row["painted_on"]) == ("Two coats", "2026-10-20")


def test_a_swatched_on_date_in_the_future_is_refused_and_the_draft_stays(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    refused = client.post(
        f"/stacks/{stack_id}/save", data={"painted_on": "2999-01-01"}, headers=PARTIAL
    )
    assert refused.status_code == 422 and "in the future" in refused.text
    assert refused.headers["HX-Retarget"] == "#save-error"
    assert stacks.layers(catalog, stack_id)  # still a draft with its layer


def test_edits_are_refused_after_the_save_with_409(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    assert client.post(f"/stacks/{stack_id}/save", headers=PARTIAL).status_code == 200
    layer_id = stacks.layers(catalog, stack_id)[0]["id"]
    refused = [
        client.get(f"/stacks/{stack_id}/sheet"),
        add(client, stack_id, catalog, "spirit-fingers"),
        client.post(f"/stacks/{stack_id}/layers/{layer_id}/move", data={"dir": "up"}),
        client.post(f"/stacks/{stack_id}/layers/{layer_id}/coats", data={"delta": "1"}),
        client.post(f"/stacks/{stack_id}/layers/{layer_id}/delete"),
        client.post(f"/stacks/{stack_id}/template/over-black"),
        client.post(f"/stacks/{stack_id}/template/copy", data={"source": "last"}),
        client.get(f"/stacks/{stack_id}/copy-sources"),
        client.post(f"/stacks/{stack_id}/save"),
        client.post(f"/stacks/{stack_id}/cancel"),
    ]
    assert [r.status_code for r in refused] == [409] * len(refused)
    assert titles(catalog, stack_id) == [("Flakie Holo Taco", 1)]


def test_unknown_things_are_404_and_bad_input_is_422(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    layer = add(client, stack_id, catalog, "flakie-holo-taco")
    assert layer.status_code == 200
    layer_id = stacks.layers(catalog, stack_id)[0]["id"]
    assert client.post("/wheels/99/slots/1/draft").status_code == 404
    assert client.post(f"/wheels/{wheel}/slots/21/draft").status_code == 404
    assert client.post(f"/wheels/{wheel}/slots/0/draft").status_code == 404
    assert client.post("/stacks/999/layers", data={"shade_id": 1}).status_code == 409
    assert client.post(f"/stacks/{stack_id}/layers", data={"shade_id": 99999}).status_code == 404
    assert client.post(f"/stacks/{stack_id}/layers/9999/delete").status_code == 404
    assert (
        client.post(f"/stacks/{stack_id}/layers/9999/coats", data={"delta": "1"}).status_code == 404
    )
    assert (
        client.post(f"/stacks/{stack_id}/template/copy", data={"source_stack_id": 9999}).status_code
        == 404
    )
    assert client.post(f"/stacks/{stack_id}/layers", data={"shade_id": "x"}).status_code == 422
    assert client.post(f"/stacks/{stack_id}/layers").status_code == 422
    bad_dir = client.post(f"/stacks/{stack_id}/layers/{layer_id}/move", data={"dir": "left"})
    assert bad_dir.status_code == 422
    bad_delta = client.post(f"/stacks/{stack_id}/layers/{layer_id}/coats", data={"delta": "2"})
    assert bad_delta.status_code == 422
    assert client.post(f"/stacks/{stack_id}/template/copy").status_code == 422
    assert client.post(f"/wheels/{wheel}/slots/1/clear").status_code == 200


def test_the_ninth_layer_is_a_422_with_the_list_and_a_message(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    for _ in range(8):
        add(client, stack_id, catalog, "flakie-holo-taco")
    full = add(client, stack_id, catalog, "spirit-fingers")
    assert full.status_code == 422
    assert full.text.lstrip().startswith('<div id="stack-layers"')
    assert "A swatch holds up to 8 layers." in full.text and "pickerReset" not in str(full.headers)
    assert "disabled" in re.search(r'<button[^>]*template/over-black"[^>]*>', full.text).group(0)
    assert len(stacks.layers(catalog, stack_id)) == 8
    black = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert black.status_code == 422 and "A swatch holds up to 8 layers." in black.text


# --- templates -------------------------------------------------------------------------


def test_over_black_inserts_the_base_and_says_so_when_it_is_there(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    first = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert first.status_code == 200 and "Already over black." not in first.text
    assert titles(catalog, stack_id) == [("One-Coat Black", 1), ("Flakie Holo Taco", 1)]
    assert "Base" in first.text and "Top" in first.text
    assert re.search(r"<button[^>]*disabled[^>]*>.*?Over black", first.text, re.S)
    again = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert "Already over black." in again.text
    assert len(stacks.layers(catalog, stack_id)) == 2


def test_without_a_black_in_the_catalog_the_pill_is_hidden_and_the_route_is_422(client, conn):
    seed(conn, [FLAKIE])
    wheel_id = make_wheel(client)
    stack_id, opened = open_sheet(client, wheel_id)
    assert "Over black" not in opened.text
    assert "No layers yet. Search for the base shade." in opened.text
    refused = client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL)
    assert refused.status_code == 422 and "no black base in the catalog" in refused.text


def test_copy_from_lists_saved_swatches_and_copies_the_rows(client, catalog, wheel):
    swatch(catalog, wheel, 3, "one-coat-black", "flakie-holo-taco")
    swatch(catalog, wheel, 4, "spirit-fingers")
    stack_id, opened = open_sheet(client, wheel, 12)
    assert "Copy from…" in opened.text and "Same as last" in opened.text
    listing = client.get(f"/stacks/{stack_id}/copy-sources", headers=PARTIAL)
    assert listing.status_code == 200
    assert "One-Coat Black + Flakie Holo Taco" in listing.text and "Holos, slot 3" in listing.text
    assert listing.text.index("Spirit Fingers") < listing.text.index("One-Coat Black")
    assert "hx-confirm" not in listing.text
    found = client.get(f"/stacks/{stack_id}/copy-sources?q=flakie")
    assert "Holos, slot 3" in found.text and "Holos, slot 4" not in found.text
    none = client.get(f"/stacks/{stack_id}/copy-sources?q=zzzz")
    assert "No saved swatch uses “zzzz”." in none.text
    source = catalog.execute("select stack_id from wheel_slot where position = 3").fetchone()[0]
    copied = client.post(
        f"/stacks/{stack_id}/template/copy",
        data={"source_stack_id": source, "filter": "all"},
        headers=PARTIAL,
    )
    assert copied.status_code == 200 and copied.headers["HX-Trigger"] == "pickerReset"
    assert titles(catalog, stack_id) == [("One-Coat Black", 1), ("Flakie Holo Taco", 1)]
    assert catalog.execute("select count(*) from stack").fetchone()[0] == 3
    assert "hx-confirm" in client.get(f"/stacks/{stack_id}/copy-sources").text


def test_same_as_last_copies_the_most_recent_save_and_says_when_there_is_none(
    client, catalog, wheel
):
    stack_id, opened = open_sheet(client, wheel)
    assert "Same as last" not in opened.text and "Copy from…" not in opened.text
    nothing = client.post(
        f"/stacks/{stack_id}/template/copy", data={"source": "last"}, headers=PARTIAL
    )
    assert nothing.status_code == 200 and "Nothing is saved yet to copy." in nothing.text
    swatch(catalog, wheel, 3, "one-coat-black")
    swatch(catalog, wheel, 4, "spirit-fingers", "flakie-holo-taco")
    last = client.post(
        f"/stacks/{stack_id}/template/copy", data={"source": "last"}, headers=PARTIAL
    )
    assert last.status_code == 200
    assert titles(catalog, stack_id) == [("Spirit Fingers", 1), ("Flakie Holo Taco", 1)]


# --- the draft lifecycle ---------------------------------------------------------------


def test_cancel_discards_the_draft_and_closes_the_sheet(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    cancelled = client.post(f"/stacks/{stack_id}/cancel", headers=PARTIAL)
    assert cancelled.status_code == 200 and cancelled.headers["HX-Trigger"] == "sheetClose"
    assert 'id="slot-12"' in cancelled.text and "is-saved" not in cancelled.text
    assert "tip-dot" not in cancelled.text
    assert catalog.execute("select count(*) from stack").fetchone()[0] == 0
    assert catalog.execute("select count(*) from wheel_slot").fetchone()[0] == 0


def test_dismissing_keeps_the_draft_and_the_next_tap_resumes_it(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    page = client.get(f"/w/{wheels.get(catalog, wheel)['slug']}").text
    assert "tip-dot" in page and "draft in progress" in page
    again_id, again = open_sheet(client, wheel)
    assert again_id == stack_id
    assert "Resumed your draft." in again.text and "Flakie Holo Taco" in again.text
    assert "tip-dot" in again.text
    reopened = client.get(f"/stacks/{stack_id}/sheet")
    assert reopened.status_code == 200 and "Flakie Holo Taco" in reopened.text
    assert 'id="slot-12"' not in reopened.text


def tip_urls(text):
    return re.findall(r'src="(/tips/stack/\d+\.svg\?v=\w+)"', text)


def test_the_head_shows_the_stacks_composite_tip_and_every_edit_appends_a_new_picture(
    client, catalog, wheel
):
    stack_id, opened = open_sheet(client, wheel)
    head = opened.text.split('class="builder-body')[0]
    assert (
        '<span class="tip tip-xl" aria-hidden="true"><span id="stack-tip" class="tip-face"></span></span>'
        in head
    )
    assert "Slot 12" in head and 'class="builder-caption">Holos<' in head
    first = add(client, stack_id, catalog, "spirit-fingers")
    # Out of band, appended over the old picture (so the page can cross-fade), with a URL that
    # carries the layers' revision: a second layer, then a coat, then a removal are each a new one.
    assert 'hx-swap-oob="beforeend:#stack-tip"' in first.text and 'class="tip-fresh"' in first.text
    seen = tip_urls(first.text)
    assert len(seen) == 1 and seen[0].startswith(f"/tips/stack/{stack_id}.svg?v=")
    second = add(client, stack_id, catalog, "flakie-holo-taco")
    layers = stacks.layers(catalog, stack_id)
    coats = client.post(
        f"/stacks/{stack_id}/layers/{layers[0]['id']}/coats", data={"delta": "1"}, headers=PARTIAL
    )
    gone = client.post(f"/stacks/{stack_id}/layers/{layers[1]['id']}/delete", headers=PARTIAL)
    seen += tip_urls(second.text) + tip_urls(coats.text) + tip_urls(gone.text)
    assert len(seen) == 4 and len(set(seen)) == 4
    assert client.get(seen[-1]).status_code == 200
    # The last layer gone: nothing to draw, a blank nail fades in over the old picture.
    last = client.post(
        f"/stacks/{stack_id}/layers/{stacks.layers(catalog, stack_id)[0]['id']}/delete",
        headers=PARTIAL,
    )
    assert tip_urls(last.text) == [] and 'class="tip-fresh tip-blank"' in last.text
    # A reopened draft draws its tip in the head from the start.
    add(client, stack_id, catalog, "flakie-holo-taco")
    again = client.get(f"/stacks/{stack_id}/sheet").text
    assert re.search(r'<span id="stack-tip" class="tip-face"><img src="/tips/stack/', again)
    assert "tip-fresh" not in again


def test_resumed_note_is_a_footnote_in_the_head_not_a_notice(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    _, again = open_sheet(client, wheel)
    head, body = again.text.split('class="builder-body')
    assert '<p class="footnote muted">Resumed your draft.</p>' in head
    assert "Resumed your draft." not in body and 'class="notice"' not in body


def test_a_saved_slot_opens_with_its_layers_name_and_remove(client, catalog, wheel):
    swatch(catalog, wheel, 12, "one-coat-black", "flakie-holo-taco")
    stack_id, sheet = open_sheet(client, wheel)
    assert "One-Coat Black + Flakie Holo Taco" in sheet.text
    assert "Remove swatch" in sheet.text and "hx-confirm" in sheet.text
    assert "Resumed" not in sheet.text
    fresh_id, fresh = open_sheet(client, make_wheel(client, "Other"), 1)
    assert "Remove swatch" not in fresh.text
    removed = client.post(f"/wheels/{wheel}/slots/12/clear", headers=PARTIAL)
    assert removed.status_code == 200 and removed.headers["HX-Trigger"] == "sheetClose"
    assert 'id="ring-label"' in removed.text and ", 0 of 20 swatched<" in removed.text
    assert client.post(f"/stacks/{stack_id}/layers", data={"shade_id": 1}).status_code == 409
    assert fresh_id != stack_id


def test_layer_responses_leave_the_name_form_alone(client, catalog, wheel):
    stack_id, sheet = open_sheet(client, wheel)
    assert 'id="stack-name"' in sheet.text and 'id="stack-note"' in sheet.text
    responses = [
        add(client, stack_id, catalog, "flakie-holo-taco"),
        client.post(f"/stacks/{stack_id}/template/over-black", headers=PARTIAL),
    ]
    for response in responses:
        for form_part in ('id="save-form"', 'id="stack-name"', 'name="note"', 'id="painted-on"'):
            assert form_part not in response.text
        assert 'id="picker-form"' not in response.text
    # What was typed is what gets saved, after any number of layer edits.
    saved = client.post(
        f"/stacks/{stack_id}/save", data={"name": "  Typed name ", "note": ""}, headers=PARTIAL
    )
    assert saved.status_code == 200
    assert catalog.execute("select name from stack where id = ?", (stack_id,)).fetchone()[0] == (
        "Typed name"
    )


def test_save_errors_are_inline(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    empty = client.post(f"/stacks/{stack_id}/save", headers=PARTIAL)
    assert empty.status_code == 422 and empty.headers["HX-Retarget"] == "#save-error"
    assert "Add at least one layer before saving." in empty.text
    add(client, stack_id, catalog, "flakie-holo-taco")
    bad = client.post(
        f"/stacks/{stack_id}/save", data={"painted_on": "20/10/2026"}, headers=PARTIAL
    )
    assert bad.status_code == 422 and bad.headers["HX-Retarget"] == "#save-error"
    assert "Painted on needs a date like 2026-10-25." in bad.text
    assert stacks.slot_of(catalog, stack_id).position == 12  # still a draft


def test_the_sheet_prefills_name_note_and_date_of_a_saved_slot(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "flakie-holo-taco")
    client.post(
        f"/stacks/{stack_id}/save",
        data={"name": "Frost", "note": "Dries fast", "painted_on": "2026-09-01"},
    )
    _, sheet = open_sheet(client, wheel)
    assert 'value="Frost"' in sheet.text and "Dries fast</textarea>" in sheet.text
    assert 'value="2026-09-01"' in sheet.text and '<details class="more-fields" open>' in sheet.text


# --- the picker ------------------------------------------------------------------------


def test_search_rows_add_a_layer_and_owned_come_first(client, catalog, wheel):
    stack_id, opened = open_sheet(client, wheel)
    flakie = shade_id(catalog, "flakie-holo-taco")
    catalog.execute("insert into bottle (shade_id, state) values (?, 'full')", (flakie,))
    owned = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=owned")
    assert owned.status_code == 200 and "Flakie Holo Taco" in owned.text
    assert "Spirit Fingers" not in owned.text and "Owned ×" not in owned.text  # every row is owned
    everything = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all")
    assert "Owned ×1" in everything.text
    assert (
        f'hx-post="/stacks/{stack_id}/layers"' in owned.text
        and f'{{"shade_id": {flakie}}}' in owned.text
    )
    everything = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all")
    assert everything.text.index("Flakie Holo Taco") < everything.text.index("Spirit Fingers")
    toppers = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=toppers")
    assert "Spirit Fingers" not in toppers.text
    named = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all&q=spirit")
    assert "Spirit Fingers" in named.text and "Flakie" not in named.text
    nothing = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=owned&q=spirit")
    assert "Nothing owned matches “spirit”." in nothing.text and 'for="scope-all"' in nothing.text
    assert client.get("/search?ctx=stack&q=x").status_code == 422
    # With no bottle in the house the sheet opens on All.
    assert 'id="scope-owned" name="filter" value="owned" checked' not in opened.text


def test_a_barcode_the_resolver_knows_comes_first_as_a_suggestion(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    from polished import identifiers

    identifiers.learn(catalog, "gtin", "810170284120", shade_id(catalog, "spirit-fingers"))
    page = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all&q=810170284120").text
    assert "Barcode 0810170284120 is" in page
    assert "Spirit Fingers" in page and "pick-add" in page
    unknown = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all&q=5901234123457").text
    assert "5901234123457 is not on any bottle yet." in unknown


def test_a_short_number_in_the_picker_is_just_a_search(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    page = client.get(f"/search?ctx=stack&stack_id={stack_id}&filter=all&q=259").text
    assert "pick-lead" not in page and "P259" not in page
    assert "Nothing matches “259”." in page


def test_the_sheet_opens_on_owned_once_there_is_a_bottle(client, catalog, wheel):
    catalog.execute(
        "insert into bottle (shade_id, state) values (?, 'full')",
        (shade_id(catalog, "flakie-holo-taco"),),
    )
    _, sheet = open_sheet(client, wheel)
    assert re.search(r'id="scope-owned"[^>]*checked', sheet.text)
    assert "Spirit Fingers" not in sheet.text.split('id="picker-results"')[1].split("</form>")[0]


# --- where a saved stack shows up --------------------------------------------------------


def test_the_shade_page_and_the_highlight_reflect_the_saved_stack(client, catalog, wheel):
    stack_id, _ = open_sheet(client, wheel)
    add(client, stack_id, catalog, "one-coat-black")
    add(client, stack_id, catalog, "flakie-holo-taco")
    client.post(f"/stacks/{stack_id}/save")
    flakie = shade_id(catalog, "flakie-holo-taco")
    slug = wheels.get(catalog, wheel)["slug"]
    shade = client.get(f"/shades/{flakie}").text
    assert "Swatched on" in shade and "Holos, slot 12" in shade
    assert f'href="/w/{slug}?hl={flakie}#slot-12"' in shade
    page = client.get(f"/w/{slug}?hl={flakie}").text
    assert re.search(r'id="slot-12" class="slot [^"]*is-hl', page)
    assert "One-Coat Black + Flakie Holo Taco" in page
    spirit = client.get(f"/shades/{shade_id(catalog, 'spirit-fingers')}").text
    assert "Swatched on" not in spirit
