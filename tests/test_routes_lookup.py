import re

import pytest
from conftest import make_client, make_settings
from shade_data import made_from, seed, shade_id

from polished.db import connect

HX = {"HX-Request": "true"}
NO_ORIGIN = {"Origin": ""}
UPC = "810170284120"
GTIN = "0810170284120"
EXTRA = [made_from("thirst-trap", 1, "Spirit Fingers"), made_from("thirst-trap", 2, "Other Shade")]


@pytest.fixture
def seeded(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, EXTRA)
    yield client, conn
    conn.close()


def sid(conn, title) -> int:
    return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]


def learn(client, shade, value=UPC, kind="gtin", **headers):
    return client.post(
        "/identifiers", data={"kind": kind, "value": value, "shade_id": shade}, headers=headers
    )


def stored(conn):
    return [tuple(r) for r in conn.execute("select kind, value, shade_id from shade_identifier")]


# The page


def test_the_lookup_page_has_the_scanner_the_photo_fallback_and_the_field(seeded):
    client, _ = seeded
    page = client.get("/lookup")
    assert page.status_code == 200
    html = page.text
    assert "data-scan-open" in html and 'id="scanner"' in html and "<video" in html
    assert 'type="file" accept="image/*" capture="environment"' in html
    assert '/static/js/scanner.js?v=dev"' in html and "/static/js/sheet.js" in html
    assert 'hx-get="/lookup/resolve"' in html and 'name="q"' in html
    assert 'data-autoscan="0"' in html
    assert 'data-autoscan="1"' in client.get("/lookup?scan=1").text


def test_the_viewfinder_comes_first_then_one_field_and_the_photo_fallback(seeded):
    client, _ = seeded
    html = client.get("/lookup?scan=1").text
    order = [
        html.index(marker)
        for marker in (
            'class="viewfinder"',
            "Point at the barcode under the bottle",
            'placeholder="Type the digits, a P code, or a name"',
            "Take a photo instead",
            'id="lookup-result"',
            "Learned codes",
        )
    ]
    assert order == sorted(order)
    assert html.count('name="q"') == 1 and html.count("<button") == 2  # open and close the camera
    assert '<dialog id="scanner"' in html and 'id="scanner-status"' in html
    assert 'class="scanner-bar"' not in html


def test_the_result_card_pairs_the_bottle_photo_with_the_shades_own_tip(seeded):
    client, conn = seeded
    shade = sid(conn, "Thirst Trap")
    learn(client, shade)
    card = client.get("/lookup/resolve", params={"q": UPC, "via": "scan"}).text
    card = re.search(r'<a class="result-card".*?</a>', card, re.S).group(0)
    assert f'href="/shades/{shade}"' in card
    assert re.search(r'<img class="thumb" src="https://cdn\.shopify\.com/[^"]+"', card)
    assert re.search(
        rf'<span class="tip tip-l" aria-hidden="true"><span class="tip-face"><img src="/tips/shade/{shade}\.svg',
        card,
    )
    assert card.index('class="thumb"') < card.index('class="tip tip-l"')


def test_a_code_in_the_query_resolves_without_javascript(seeded):
    client, _ = seeded
    html = client.get(f"/lookup?q={UPC}").text
    assert f"New barcode {GTIN}. Which shade is it?" in html
    assert f'value="{UPC}"' in html


def test_the_home_page_and_the_bottles_page_offer_scanning(seeded):
    client, _ = seeded
    assert 'href="/lookup?scan=1"' in client.get("/").text
    assert 'href="/lookup?scan=1"' in client.get("/bottles").text


def test_a_number_typed_in_the_home_search_offers_the_lookup(seeded):
    client, _ = seeded
    for q in ("259", "p259", UPC):
        assert f'href="/lookup?q={q}"' in client.get("/search", params={"q": q}).text
    assert "Look up" not in client.get("/search", params={"q": "spirit"}).text


# Resolving


def test_an_unknown_barcode_asks_which_shade_with_the_typeahead(seeded):
    client, _ = seeded
    response = client.get("/lookup/resolve", params={"q": GTIN, "via": "scan"})
    assert response.status_code == 200 and "<html" not in response.text
    assert f"New barcode {GTIN}. Which shade is it?" in response.text
    assert 'hx-get="/search"' in response.text
    assert (
        """hx-vals='{"ctx": "learn", "kind": "gtin", "value": "0810170284120"}'""" in response.text
    )


def test_the_learn_typeahead_rows_save_the_barcode_in_one_tap(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    rows = client.get(
        "/search", params={"q": "spirit", "ctx": "learn", "kind": "gtin", "value": UPC}
    )
    assert rows.status_code == 200 and "<html" not in rows.text
    assert 'hx-post="/identifiers"' in rows.text and 'hx-target="#lookup-result"' in rows.text
    assert f'"shade_id": {shade}' in rows.text.replace("&#34;", '"')
    assert GTIN in rows.text  # the value was normalised to 13 digits
    assert (
        "Add it by hand"
        not in client.get(
            "/search", params={"q": "nothing", "ctx": "learn", "kind": "gtin", "value": UPC}
        ).text
    )
    assert 'href="/shades/' not in rows.text


def test_the_learn_typeahead_for_a_p_code_opens_the_add_bottle_sheet(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    rows = client.get(
        "/search", params={"q": "spirit", "ctx": "learn", "kind": "printed", "value": "259"}
    )
    assert f'hx-get="/shades/{shade}/bottles/new?ctx=lookup&amp;printed_code=P259"' in rows.text


def test_the_learn_typeahead_needs_a_valid_code_and_stack_is_not_built_yet(seeded):
    client, _ = seeded
    bad = {"q": "spirit", "ctx": "learn"}
    assert client.get("/search", params=bad).status_code == 422
    assert (
        client.get("/search", params={**bad, "kind": "gtin", "value": "795203598"}).status_code
        == 422
    )
    assert client.get("/search", params={"q": "spirit", "ctx": "stack"}).status_code == 422


def test_posting_the_code_saves_it_normalised_and_shows_the_match_with_add_bottle(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    saved = learn(client, shade, UPC)
    assert saved.status_code == 200 and "<html" not in saved.text
    assert stored(conn) == [("gtin", GTIN, shade)]
    assert "Saved. " in saved.text and "Spirit Fingers" in saved.text
    assert "Add bottle" in saved.text
    assert f'hx-get="/shades/{shade}/bottles/new?ctx=lookup"' in saved.text

    match = client.get("/lookup/resolve", params={"q": UPC, "via": "scan"})
    assert "Spirit Fingers" in match.text and "Add bottle" in match.text
    assert "New barcode" not in match.text and "This isn’t it" in match.text
    assert conn.execute("select use_count from shade_identifier").fetchone()[0] == 1


def test_a_known_barcode_keeps_its_shade_and_says_so(seeded):
    client, conn = seeded
    first, second = sid(conn, "Spirit Fingers"), sid(conn, "Other Shade")
    learn(client, first)
    again = learn(client, second)
    assert again.status_code == 200
    assert "already points at Spirit Fingers" in again.text and "Saved. " not in again.text
    assert stored(conn) == [("gtin", GTIN, first)]


def test_a_bad_post_is_refused_and_stores_nothing(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    assert learn(client, shade, "795203598").status_code == 422
    assert learn(client, shade, UPC, kind="sku").status_code == 422
    assert learn(client, 9999).status_code == 404
    assert learn(client, shade, **NO_ORIGIN).status_code == 403
    assert client.post("/identifiers", data={"kind": "gtin"}).status_code == 422
    assert stored(conn) == []


def test_this_isnt_it_forgets_the_barcode_and_asks_again(seeded):
    client, conn = seeded
    learn(client, sid(conn, "Spirit Fingers"))
    identifier = conn.execute("select id from shade_identifier").fetchone()[0]
    response = client.post(f"/identifiers/{identifier}/delete", data={"ctx": "lookup"})
    assert f"New barcode {GTIN}. Which shade is it?" in response.text
    assert stored(conn) == []
    assert client.post(f"/identifiers/{identifier}/delete").status_code == 404


def test_an_invalid_number_is_invalid_code_and_a_bad_scan_says_try_again(seeded):
    client, _ = seeded
    typed = client.get("/lookup/resolve", params={"q": "12345678901"})
    assert "isn’t a valid barcode number" in typed.text and "New barcode" not in typed.text
    scanned = client.get("/lookup/resolve", params={"q": "12345678901", "via": "scan"})
    assert "Couldn’t read that reliably" in scanned.text


def test_a_p_code_is_a_suggestion_never_a_match(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    unknown = client.get("/lookup/resolve", params={"q": "259"})
    assert "P259 isn’t on any bottle yet" in unknown.text
    client.post(f"/shades/{shade}/bottles", data={"printed_code": "259"})
    suggestion = client.get("/lookup/resolve", params={"q": "259"})
    assert "P259 was Spirit Fingers on a bottle you added before" in suggestion.text
    assert "Yes, add a bottle" in suggestion.text and "Not that one?" in suggestion.text
    assert "This isn’t it" not in suggestion.text
    assert (
        f'hx-get="/shades/{shade}/bottles/new?ctx=lookup&amp;printed_code=P259"' in suggestion.text
    )


def test_a_sku_is_a_match_without_a_forget_button(seeded):
    client, conn = seeded
    sku = conn.execute("select sku from shade where title = 'Spirit Fingers'").fetchone()[0]
    response = client.get("/lookup/resolve", params={"q": sku.lower()})
    assert "Spirit Fingers" in response.text and f"SKU {sku}" in response.text
    assert "Add bottle" in response.text and "This isn’t it" not in response.text


def test_a_name_gives_ordinary_rows_and_nothing_gives_nothing(seeded):
    client, _ = seeded
    rows = client.get("/lookup/resolve", params={"q": "spirit"})
    assert rows.text.count('class="shade-row') == 1 and 'href="/shades/' in rows.text
    assert client.get("/lookup/resolve", params={"q": ""}).text.strip() == ""


# Adding a bottle after a lookup, and learning the P code


def test_the_sheet_after_a_lookup_prefills_the_p_code_and_targets_the_result(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    sheet = client.get(
        f"/shades/{shade}/bottles/new", params={"ctx": "lookup", "printed_code": "p259"}
    )
    assert 'name="ctx" value="lookup"' in sheet.text
    assert 'value="259"' in sheet.text and 'hx-target="#lookup-result"' in sheet.text
    plain = client.get(f"/shades/{shade}/bottles/new")
    assert 'hx-target="#bottles"' in plain.text and 'name="ctx" value="shade"' in plain.text
    odd = client.get(f"/shades/{shade}/bottles/new", params={"ctx": "elsewhere"})
    assert 'name="ctx" value="shade"' in odd.text


def test_saving_a_bottle_from_the_lookup_learns_the_code_and_shows_what_was_added(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    response = client.post(
        f"/shades/{shade}/bottles", data={"printed_code": "259", "ctx": "lookup"}
    )
    assert response.status_code == 200 and response.headers["hx-trigger"] == "sheetClose"
    assert "Added Spirit Fingers with P259." in response.text and "data-scan-open" in response.text
    assert stored(conn) == [("printed", "P259", shade)]
    assert conn.execute("select count(*) from bottle").fetchone()[0] == 1


def test_a_conflicting_p_code_saves_the_bottle_and_keeps_the_old_mapping(seeded):
    client, conn = seeded
    first, second = sid(conn, "Spirit Fingers"), sid(conn, "Other Shade")
    client.post(f"/shades/{first}/bottles", data={"printed_code": "259"})
    on_shade_page = client.post(f"/shades/{second}/bottles", data={"printed_code": "p259"})
    assert "P259 was Spirit Fingers before" in on_shade_page.text
    from_lookup = client.post(
        f"/shades/{second}/bottles", data={"printed_code": "259", "ctx": "lookup"}
    )
    assert "P259 was Spirit Fingers before" in from_lookup.text
    assert stored(conn) == [("printed", "P259", first)]
    codes = [
        r[0] for r in conn.execute("select printed_code from bottle where shade_id = ?", (second,))
    ]
    assert codes == ["P259", "P259"]


def test_a_bottle_without_a_p_code_or_with_an_odd_one_learns_nothing(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    client.post(f"/shades/{shade}/bottles", data={})
    client.post(f"/shades/{shade}/bottles", data={"printed_code": "no-code"})
    assert stored(conn) == []
    refused = client.post(
        f"/shades/{shade}/bottles", data={"printed_code": "259", "price_paid": "x"}
    )
    assert refused.status_code == 422 and stored(conn) == []


# The learned codes page


def test_the_identifiers_page_lists_and_removes_learned_codes(seeded):
    client, conn = seeded
    shade = sid(conn, "Spirit Fingers")
    assert "Nothing learned yet" in client.get("/identifiers").text
    learn(client, shade)
    client.post(f"/shades/{shade}/bottles", data={"printed_code": "259"})
    page = client.get("/identifiers").text
    assert GTIN in page and "P259" in page and "Spirit Fingers" in page
    identifier = conn.execute("select id from shade_identifier where kind = 'printed'").fetchone()[
        0
    ]
    removed = client.post(f"/identifiers/{identifier}/delete")
    assert removed.status_code == 200 and removed.text == ""
    assert stored(conn) == [("gtin", GTIN, shade)]


# Static files and the gate


def test_the_wasm_is_served_from_this_site_as_application_wasm_under_a_csp_that_allows_it(seeded):
    client, _ = seeded
    wasm = client.get("/static/vendor/zxing-wasm/zxing_reader.wasm")
    assert wasm.status_code == 200
    assert wasm.headers["content-type"] == "application/wasm"
    assert wasm.content[:4] == b"\x00asm"
    assert "'wasm-unsafe-eval'" in wasm.headers["content-security-policy"]
    for path in ("reader/index.js", "share.js"):
        assert client.get(f"/static/vendor/zxing-wasm/{path}").status_code == 200
    script = client.get("/static/js/scanner.js").text
    assert "/static/vendor/zxing-wasm/zxing_reader.wasm" in script
    assert "cdn" not in script.lower() and "jsdelivr" not in script.lower()


def test_the_vendored_versions_are_recorded():
    from polished.web import STATIC_DIR

    versions = (STATIC_DIR / "vendor" / "VERSIONS.txt").read_text()
    assert "zxing-wasm" in versions and "3.1.6" in versions
    assert "5003fb4b88c4fbd1fd518a2fd8c8ad365c519e183a08c03a322dddfea3cea84e" in versions


def test_the_lookup_routes_need_a_sign_in(oidc_client):
    assert oidc_client.get("/lookup").status_code == 302
    assert oidc_client.get("/lookup/resolve", params={"q": GTIN}).status_code == 302
    assert oidc_client.get("/identifiers").status_code == 302
    assert learn(oidc_client, 1).status_code == 401


def test_the_wasm_content_type_survives_a_head_request(seeded):
    client, _ = seeded
    head = client.head("/static/vendor/zxing-wasm/zxing_reader.wasm")
    assert head.status_code == 200 and head.headers["content-type"] == "application/wasm"


def test_learn_rows_show_one_shade_per_line(seeded):
    client, conn = seeded
    html = client.get(
        "/search", params={"q": "s", "ctx": "learn", "kind": "gtin", "value": UPC}
    ).text
    titles = re.findall(r'class="row-title">', html)
    assert html.count('class="shade-row') == len(titles) >= 2
    assert shade_id(conn, "spirit-fingers")
