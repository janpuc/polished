"""Home as the shelf: the wear hero and its two requests, the rack, the wheel card, the collection
numbers, the empty states and the motion rules that live in CSS and JS (docs/VISUAL.md section 6)."""

import re
from datetime import date

import pytest
from conftest import make_client, make_settings
from shade_data import made_from, seed, shade_id

from polished import stacks, wear, wheels
from polished.db import connect
from polished.routes.wear import facts_line
from polished.web import STATIC_DIR

HX = {"HX-Request": "true"}
NO_ORIGIN = {"Origin": ""}
EXTRA = [
    made_from("thirst-trap", 1, "Last Stock", tags=["collection:retirement", "finish:glitter"]),
    made_from("jam-session", 2, "Jam Jar", tags=["finish:jelly", "finish:shimmer"]),
]
ARRIVED = "polished_arrived"


@pytest.fixture
def seeded(tmp_path):
    settings = make_settings(tmp_path)
    client = make_client(settings)
    conn = connect(settings.db_path)
    seed(conn, EXTRA)
    yield client, conn, settings
    conn.close()


def own(client, conn, handle, **data) -> int:
    response = client.post(f"/shades/{shade_id(conn, handle)}/bottles", data=data)
    assert response.status_code == 200
    return conn.execute("select max(id) from bottle").fetchone()[0]


def today(settings) -> date:
    return wear.local_today(settings.timezone)


def hero(html: str) -> str:
    return re.search(r'<div id="wear-slot".*?(?=</section>)', html, re.S).group(0)


def shown_shade(html: str) -> int:
    return int(re.search(r'class="wear-name"><a href="/shades/(\d+)"', html).group(1))


# --- "I wore this" -----------------------------------------------------------------------


def test_i_wore_this_logs_the_day_and_returns_the_hero_saying_worn_today(seeded):
    client, conn, settings = seeded
    own(client, conn, "thirst-trap", printed_code="259", state="half")
    shade = shade_id(conn, "thirst-trap")
    response = client.post(f"/wear/{shade}", headers=HX)
    assert response.status_code == 200 and "<html" not in response.text
    assert "Worn today" in response.text and "I wore this" not in response.text
    assert 'id="wear-primary"' in response.text and 'id="wear-another"' in response.text
    assert [tuple(r) for r in conn.execute("select shade_id, worn_on from wear")] == [
        (shade, today(settings).isoformat())
    ]


def test_wearing_the_same_shade_twice_in_a_day_is_one_wearing(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    shade = shade_id(conn, "thirst-trap")
    for _ in range(2):
        assert client.post(f"/wear/{shade}", headers=HX).status_code == 200
    assert conn.execute("select count(*) from wear").fetchone()[0] == 1


def test_wearing_without_htmx_goes_back_to_home(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    response = client.post(f"/wear/{shade_id(conn, 'thirst-trap')}")
    assert response.status_code == 303 and response.headers["location"] == "/"
    assert conn.execute("select count(*) from wear").fetchone()[0] == 1


def test_wearing_an_unknown_shade_is_a_404_and_logs_nothing(seeded):
    client, conn, _ = seeded
    assert client.post("/wear/99999", headers=HX).status_code == 404
    assert conn.execute("select count(*) from wear").fetchone()[0] == 0


def test_wearing_is_checked_for_its_origin_like_every_post(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    shade = shade_id(conn, "thirst-trap")
    assert client.post(f"/wear/{shade}", headers=NO_ORIGIN | HX).status_code == 403
    foreign = {"Origin": "https://elsewhere.example"} | HX
    assert client.post(f"/wear/{shade}", headers=foreign).status_code == 403
    assert conn.execute("select count(*) from wear").fetchone()[0] == 0


def test_home_flips_the_hero_after_wearing_and_keeps_another(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    page = client.get("/").text
    assert "I wore this" in hero(page) and "Worn today" not in hero(page)
    assert f'hx-post="/wear/{shown_shade(page)}"' in page
    client.post(f"/wear/{shown_shade(page)}", headers=HX)
    page = client.get("/").text
    assert "Worn today" in hero(page) and "I wore this" not in hero(page)
    assert 'id="wear-another"' in hero(page)


def test_the_hero_names_the_shade_its_finishes_and_the_bottle(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap", printed_code="259", state="half")
    page = hero(client.get("/").text)
    assert 'class="wear-name"><a href="/shades/' in page and "Thirst Trap" in page
    assert re.search(r'class="wear-facts">[^<]*P259, half left<', page)
    assert 'class="tip tip-xl"' in page  # the shade's own tip, never a photo
    assert "cdn.shopify.com" not in page and "style=" not in page  # the CSP allows no style


def test_facts_line_reads_finishes_then_the_bottle():
    bottle = {"printed_code": "P12", "state": "half"}
    assert (
        facts_line(["holographic", "metallic"], bottle) == "Holographic, metallic. P12, half left"
    )
    assert facts_line([], {"printed_code": None, "state": "full"}) == "Full"
    assert facts_line(["rose-gold"], {"printed_code": "P7", "state": "low"}) == (
        "Rose gold. P7, running low"
    )
    assert facts_line(["jelly"], None) == "Jelly"
    assert facts_line([], None) == ""


# --- "Another" ---------------------------------------------------------------------------


def test_another_is_a_different_owned_shade_than_the_one_shown_with_the_sweep(seeded):
    client, conn, _ = seeded
    for handle in ("thirst-trap", "peely-base", "jam-session"):
        own(client, conn, handle)
    shown = shown_shade(client.get("/").text)
    seen = set()
    for _ in range(12):
        response = client.get(f"/wear/another?shown={shown}", headers=HX)
        assert response.status_code == 200 and "<html" not in response.text
        assert "is-arriving" in response.text  # the one sweep across the new tip
        assert f'hx-get="/wear/another?shown={shown_shade(response.text)}"' in response.text
        seen.add(shown_shade(response.text))
    assert shown not in seen and len(seen) == 2


def test_another_with_one_shade_owned_comes_back_to_it(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    shade = shade_id(conn, "thirst-trap")
    assert shown_shade(client.get(f"/wear/another?shown={shade}", headers=HX).text) == shade


def test_another_never_offers_a_shade_without_a_bottle_left(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    empty = own(client, conn, "peely-base")
    client.post(f"/bottles/{empty}/state", data={"state": "empty"})
    for _ in range(8):
        page = client.get("/wear/another", headers=HX).text
        assert shown_shade(page) == shade_id(conn, "thirst-trap")


def test_another_asked_for_as_a_page_is_homes_own(seeded):
    client, conn, _ = seeded
    for handle in ("thirst-trap", "peely-base"):
        own(client, conn, handle)
    shown = shade_id(conn, "thirst-trap")
    redirect = client.get(f"/wear/another?shown={shown}")
    assert redirect.status_code == 303 and redirect.headers["location"] == (
        f"/?another=1&shown={shown}"
    )
    page = client.get(redirect.headers["location"]).text
    assert shown_shade(page) == shade_id(conn, "peely-base") and "is-arriving" in hero(page)


def test_without_bottles_there_is_nothing_to_wear_and_one_button_says_where_to_start(seeded):
    client, conn, _ = seeded
    page = client.get("/").text
    assert "Nothing to wear yet" in hero(page) and "Scan a bottle" in hero(page)
    assert "I wore this" not in page and "wear-another" not in page
    fragment = client.get("/wear/another", headers=HX).text
    assert "Nothing to wear yet" in fragment and "<html" not in fragment


# --- the rack ----------------------------------------------------------------------------


def test_the_rack_is_the_six_newest_bottles_each_a_tip_with_its_name(seeded):
    client, conn, _ = seeded
    for handle in ("thirst-trap", "peely-base", "jam-session", "rest-in-peach"):
        own(client, conn, handle)
    for _ in range(4):
        own(client, conn, "last-stock")
    page = client.get("/").text
    rack = re.search(r'<ul class="rack-list">(.*?)</ul>', page, re.S).group(1)
    assert rack.count('class="rack-item') == 6 and rack.count('class="tip tip-l"') == 6
    assert re.findall(r'class="rack-name">([^<]+)<', rack)[:4] == ["Last Stock"] * 4
    assert 'class="rack">' in page and ">All 8 bottles</a>" in page


def test_a_single_bottle_says_so_instead_of_all_one_bottles(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    page = client.get("/").text
    assert ">1 bottle</a>" in page and "All 1 bottles" not in page


def test_an_empty_rack_is_unpainted_tips_on_the_ledge_and_one_line(seeded):
    client, _, _ = seeded
    page = client.get("/").text
    rack = re.search(r'<div class="rack">(.*?)</div>\s*<p class="rack-empty"', page, re.S).group(1)
    assert "rack-list is-empty" in rack and rack.count('class="tip tip-l"') == 3
    assert "cdn.shopify.com" not in rack and "<img" not in rack  # nothing painted yet
    assert "Bottles you add stand here, newest first." in page
    assert page.count('class="btn"') == 1  # the hero's Scan a bottle is the one filled action


def test_a_new_bottle_arrives_on_the_rack_once(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    client.cookies.clear()
    created = client.post(
        f"/shades/{shade_id(conn, 'peely-base')}/bottles", data={"printed_code": "5"}, headers=HX
    )
    bottle = conn.execute("select max(id) from bottle").fetchone()[0]
    assert f"{ARRIVED}={bottle};" in created.headers["set-cookie"]
    page = client.get("/")
    assert re.findall(r'<a class="rack-item( is-arriving)?" href="/shades/(\d+)"', page.text)[
        0
    ] == (" is-arriving", str(shade_id(conn, "peely-base")))
    assert page.text.count("is-arriving") == 1
    assert f"{ARRIVED}=" in page.headers["set-cookie"] and "Max-Age=0" in page.headers["set-cookie"]
    client.cookies.clear()  # the browser dropped it, as told
    assert "rack-item is-arriving" not in client.get("/").text


def test_a_bottle_from_the_lookup_arrives_in_place_and_leaves_no_cookie(seeded):
    client, conn, _ = seeded
    response = client.post(
        f"/shades/{shade_id(conn, 'thirst-trap')}/bottles", data={"ctx": "lookup"}, headers=HX
    )
    assert (
        'class="added-head is-arriving"' in response.text and 'class="tip tip-l"' in response.text
    )
    assert ARRIVED not in response.headers.get("set-cookie", "")


def test_an_arrival_that_is_not_the_newest_bottle_is_ignored(seeded):
    client, conn, _ = seeded
    own(client, conn, "thirst-trap")
    own(client, conn, "peely-base")
    client.cookies.set(ARRIVED, "1")  # the first bottle: no longer the newest
    assert "is-arriving" not in client.get("/").text
    client.cookies.set(ARRIVED, "garbage")
    assert client.get("/").status_code == 200


# --- the wheel card and the collection ------------------------------------------------------


def test_the_wheel_card_has_the_ring_the_name_and_the_count_with_drafts(seeded):
    client, conn, _ = seeded
    wheel = wheels.create(conn, "Holos")
    stack = stacks.open_draft(conn, wheel, 1).stack_id
    stacks.append(conn, stack, shade_id(conn, "thirst-trap"))
    stacks.save(conn, stack)
    stacks.append(conn, stacks.open_draft(conn, wheel, 2).stack_id, shade_id(conn, "peely-base"))
    page = client.get("/").text
    card = re.search(r'<a class="home-wheel".*?</a>', page, re.S).group(0)
    assert 'class="ring ring-card"' in card and card.count('class="slot slot-pos-') == 20
    assert 'class="home-wheel-name">Holos<' in card and "1 of 20, 1 draft<" in card
    assert "All " not in re.search(r'id="wheels-title".*?</div>', page, re.S).group(0)
    wheels.create(conn, "Winter")
    assert ">All 2</a>" in client.get("/").text


def test_with_no_wheel_the_card_is_the_unpainted_ring_and_an_invitation(seeded):
    client, _, _ = seeded
    card = re.search(r'<a class="home-wheel is-empty".*?</a>', client.get("/").text, re.S).group(0)
    assert 'href="/wheels"' in card and "No wheels yet" in card and "Make one" in card
    assert card.count('class="slot slot-pos-') == 12 and "is-filled" not in card


def test_the_collection_is_three_numbers_each_a_link_and_only_when_there_is_something(seeded):
    client, conn, _ = seeded
    assert "Collection" not in client.get("/").text
    client.post(f"/shades/{shade_id(conn, 'rest-in-peach')}/wishlist")
    page = client.get("/").text
    assert "Collection" in page and page.count('class="count-n"') == 3  # a wish alone counts
    own(client, conn, "thirst-trap")
    assert re.findall(r'class="count-n">(\d+)<', client.get("/").text) == ["1", "1", "1"]


def test_the_empty_wishlist_draws_the_unpainted_tip(seeded):
    client, _, _ = seeded
    page = client.get("/wishlist").text
    assert "Nothing on the wishlist" in page
    assert 'class="tip tip-l"' in page and "nail-glyph" not in page


# --- motion and the rest of the CSS and JS contract ------------------------------------------


def css() -> str:
    return re.sub(r"/\*.*?\*/", "", (STATIC_DIR / "css" / "app.css").read_text(), flags=re.S)


def block(text: str, opener: str) -> str:
    """The body of the first at-rule that starts with `opener`, braces matched."""
    start = text.index(opener)
    depth, i = 0, text.index("{", start)
    begin = i
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
        if depth == 0:
            return text[begin + 1 : i - 1]


def test_the_arrival_is_600ms_on_the_spring_curve_and_the_sweep_700ms():
    sheet = css()
    motion = block(sheet, "@media (prefers-reduced-motion: no-preference)")
    assert (
        "animation: tip-arrive 600ms linear(0, 0.4 7%, 0.8 15%, 1.04 30%, 0.98 45%, 1) both"
        in motion
    )
    assert "animation: tip-sweep 700ms" in motion
    assert re.search(r"@keyframes tip-sweep \{\s*from \{[^}]*100% 0[^}]*\}\s*to \{[^}]*0 0", sheet)
    assert "@view-transition" in motion and "navigation: auto" in motion
    assert not re.search(r"transition:\s*all|transition-property:\s*all", sheet)


def test_under_reduced_motion_the_arrival_is_a_fade_with_no_scale_or_sweep_or_view_transition():
    sheet = css()
    reduced = block(sheet, "@media (prefers-reduced-motion: reduce) {\n  .rack-item.is-arriving")
    assert "tip-fade 150ms linear both" in reduced
    assert "scale" not in reduced and "tip-sweep" not in reduced
    assert "@view-transition" not in reduced
    fade = re.search(r"@keyframes tip-fade \{(.*?)\}\s*\}", sheet, re.S).group(1)
    assert "opacity: 0" in fade and "scale" not in fade


def test_the_hidden_state_of_an_arrival_lives_in_its_keyframe_not_the_base_rule():
    sheet = css()
    base = re.search(r"\.tip-face::before \{([^}]*)\}", sheet).group(1)
    assert (
        "opacity: 0" in base and "animation" not in base
    )  # the sweep is only ever visible in motion
    assert "opacity: 0" not in re.search(r"\.rack-item \{([^}]*)\}", sheet).group(1)


def test_the_rack_stands_on_a_full_width_ledge_with_the_pitch_of_each_shell():
    sheet = css()
    assert re.search(r"\.rack::before \{[^}]*height: 1\.5px[^}]*var\(--line\)", sheet)
    assert re.search(r"\.rack \.tip::before \{\s*bottom: -7px;\s*height: 10px;", sheet)
    assert re.search(r"\.rack-list \{[^}]*scroll-snap-type: x mandatory", sheet)
    assert re.search(r"\.rack-list > li[^{]*\{[^}]*scroll-snap-align: start", sheet)
    pitches = re.findall(r"--rack-pitch: (\d+)px", sheet)
    assert pitches == ["88", "104", "120"]


def test_chrome_js_switches_transitions_off_for_a_theme_change():
    script = (STATIC_DIR / "js" / "chrome.js").read_text()
    assert 'matchMedia("(prefers-color-scheme: dark)")' in script and "theme-switching" in script
    assert "requestAnimationFrame" in script
    assert re.search(r"\.theme-switching \*[^{]*\{\s*transition: none !important", css())


def test_the_tip_trip_is_named_by_a_blocking_classic_script_without_inline_style(client):
    html = client.get("/").text
    tag = '<script src="/static/js/transitions.js?v=dev"></script>'
    assert tag in html and html.index(tag) < html.index("htmx.min.js")  # before the first paint
    script = (STATIC_DIR / "js" / "transitions.js").read_text()
    for needle in ("pageswap", "pagereveal", "view-transition-name", "tip-", ".detail-head .tip"):
        assert needle in script
    assert "export " not in script and "setAttribute" not in script  # classic; the CSP has no style
