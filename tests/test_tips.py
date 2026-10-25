"""Generated nail tips: the SVG drawing (tips.py), its routes and the colour override."""

import re
import xml.etree.ElementTree as ET

import pytest
from shade_data import made_from, seed, shade_id
from test_routes_wheels import make_wheel, swatch

from polished import tips
from polished.tips import TipShade, render

BLACK = made_from("thirst-trap", 1, "One-Coat Black")
FLAKIE = made_from("aurora-unicorn-skin", 3, "Flakie Holo Taco")


def shade(id, hex, *finishes, topper=False, hex2=None, clear=False, coats=1):
    return TipShade(id, hex, hex2, frozenset(finishes), topper, clear, coats)


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def tags(root: ET.Element) -> list[str]:
    return [element.tag.removeprefix("{http://www.w3.org/2000/svg}") for element in root.iter()]


@pytest.fixture
def catalog(conn):
    seed(conn, [BLACK, FLAKIE])
    conn.execute("update shade set swatch_hex = '#101010' where handle = 'one-coat-black'")
    conn.execute(
        "update shade set is_topper = 1, swatch_hex = '#ff66cc' where handle = 'flakie-holo-taco'"
    )
    conn.execute(
        "delete from shade_tag where shade_id in (select id from shade where handle in ('one-coat-black', 'flakie-holo-taco')) and ns = 'finish'"
    )
    for handle, finish in (
        ("one-coat-black", "creme"),
        ("flakie-holo-taco", "flakie"),
        ("flakie-holo-taco", "holographic"),
    ):
        conn.execute(
            "insert into shade_tag (shade_id, ns, value) values (?, 'finish', ?)",
            (shade_id(conn, handle), finish),
        )
    return conn


# --- the drawing ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "layers",
    [
        [shade(1, "#c72bb9", "creme")],
        [shade(2, "#3b343c", "jelly", "glitter", "holographic", "shimmer")],
        [
            shade(3, "#ceaf43", "chrome", "metallic"),
            shade(4, "#71ad44", "flakie", "holographic", topper=True),
        ],
        [shade(5, "#f43b7a", "magnetic"), shade(6, "#55472d", "thermal", hex2="#123456")],
        [shade(7, "#a59cbb", "iridescent", "reflective", "matte", hex2="#462221")],
        [shade(8, "#ffffff", clear=True)],
        [],
    ],
)
def test_every_finish_draws_a_well_formed_svg_without_script_or_style(layers):
    svg = render(layers)
    root = parse(svg)
    assert root.tag.endswith("svg") and root.get("viewBox") == "0 0 102 168"
    assert not {"script", "style", "foreignObject", "image", "a"} & set(tags(root))
    for element in root.iter():
        assert "style" not in element.attrib
        assert not any(name.lower().startswith("on") for name in element.attrib)
        assert "href" not in " ".join(element.attrib)


def test_a_shade_is_drawn_the_same_every_time_and_differs_by_id():
    glitter = [shade(40, "#336699", "glitter")]
    assert render(glitter) == render(glitter)
    assert render(glitter) != render([shade(41, "#336699", "glitter")])


def test_finishes_leave_their_marks():
    assert "polygon" in tags(parse(render([shade(1, "#336699", "flakie", topper=True)])))
    glitter = tags(parse(render([shade(2, "#336699", "glitter")])))
    assert "circle" in glitter and glitter.count("path") >= 5  # stars (and the gloss)
    assert "filter" in tags(parse(render([shade(3, "#336699", "magnetic")])))
    assert "polygon" not in tags(parse(render([shade(4, "#336699", "creme")])))
    assert "circle" in tags(parse(render([shade(5, "#336699", "shimmer")])))


def test_matte_has_no_gloss_and_everything_else_has_one():
    matte, creme = (render([shade(1, "#336699", f)]) for f in ("matte", "creme"))
    assert creme.count("<path") > matte.count("<path")


def test_a_flakie_topper_over_black_shows_flakes_on_black():
    svg = render([shade(1, "#101010", "creme"), shade(2, "#ff66cc", "flakie", topper=True)])
    assert 'fill="#101010"' in svg and "<polygon" in svg
    assert tips.lighten(tips.NUDE_HEX, 0.25) not in svg  # black is the base, not the nude


def test_a_lone_topper_or_jelly_goes_on_a_sheer_nude_so_it_is_visible():
    assert tips.lighten(tips.NUDE_HEX, 0.25) in render(
        [shade(1, "#ff66cc", "glitter", topper=True)]
    )
    assert tips.lighten(tips.NUDE_HEX, 0.25) in render([shade(2, "#336699", "jelly")])


def test_an_opaque_polish_covers_the_layers_below_and_a_jelly_tints_them():
    covered = render([shade(1, "#aa0000", "creme"), shade(2, "#0000bb", "creme")])
    assert "#aa0000" not in covered and "#0000bb" in covered
    tinted = render([shade(1, "#aa0000", "creme"), shade(2, "#0000bb", "jelly")])
    assert "#aa0000" in tinted and 'fill="#0000bb" fill-opacity="0.78"' in tinted


def test_a_clear_base_coat_draws_nothing_of_its_own():
    assert render([shade(1, "#aa0000", "creme"), shade(2, "#ffffff", clear=True)]) == render(
        [shade(1, "#aa0000", "creme")]
    ).replace("", "")  # same drawing as the colour alone


def test_the_override_replaces_the_colour_and_the_second_colour():
    row = {
        "shade_id": 9, "kind": "polish", "is_topper": 0, "swatch_hex": "#112233",
        "swatch_hex2": "#445566", "swatch_override_hex": "#abcdef", "finishes": "creme",
    }  # fmt: skip
    drawn = tips.tip_shade(row)
    assert (drawn.hex, drawn.hex2) == ("#abcdef", None)
    row["swatch_override_hex"] = None
    assert (tips.tip_shade(row).hex, tips.tip_shade(row).hex2) == ("#112233", "#445566")
    row["swatch_hex"] = None
    assert tips.tip_shade(row).hex == tips.NEUTRAL_HEX


# --- the routes -----------------------------------------------------------------------------


def test_the_shade_route_serves_a_cacheable_svg_under_the_csp(client, catalog):
    response = client.get(f"/tips/shade/{shade_id(catalog, 'one-coat-black')}.svg?v=x")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert (
        "private" in response.headers["cache-control"]
        and "max-age=31536000" in response.headers["cache-control"]
    )
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "<script" not in response.text
    again = client.get(
        f"/tips/shade/{shade_id(catalog, 'one-coat-black')}.svg",
        headers={"If-None-Match": response.headers["etag"]},
    )
    assert again.status_code == 304


def test_unknown_shades_and_stacks_are_404(client, catalog):
    assert client.get("/tips/shade/99999.svg").status_code == 404
    assert client.get("/tips/stack/99999.svg").status_code == 404
    assert client.get("/tips/shade/abc.svg").status_code == 404


def test_the_stack_route_draws_the_layers_in_order(client, catalog):
    wheel_id = make_wheel(client)
    swatch(catalog, wheel_id, 1, "one-coat-black", "flakie-holo-taco")
    stack_id = catalog.execute(
        "select stack_id from wheel_slot where wheel_id = ?", (wheel_id,)
    ).fetchone()[0]
    svg = client.get(f"/tips/stack/{stack_id}.svg").text
    assert 'fill="#101010"' in svg and "<polygon" in svg


def test_the_url_changes_when_the_colour_does(client, catalog):
    wheel_id = make_wheel(client)
    swatch(catalog, wheel_id, 1, "one-coat-black")
    slug = catalog.execute("select slug from wheel").fetchone()[0]
    before = re.search(r"/tips/stack/\d+\.svg\?v=\w+", client.get(f"/w/{slug}").text).group(0)
    client.post(
        f"/shades/{shade_id(catalog, 'one-coat-black')}/tip-colour", data={"hex": "#336699"}
    )
    after = re.search(r"/tips/stack/\d+\.svg\?v=\w+", client.get(f"/w/{slug}").text).group(0)
    assert before != after


# --- the override ---------------------------------------------------------------------------


def test_the_shade_page_shows_the_tip_and_a_colour_input(client, catalog):
    page = client.get(f"/shades/{shade_id(catalog, 'one-coat-black')}").text
    assert "Tip colour" in page and 'type="color"' in page and 'value="#101010"' in page
    assert f"/tips/shade/{shade_id(catalog, 'one-coat-black')}.svg" in page
    assert "Reset" not in page


def test_saving_a_colour_overrides_and_reset_goes_back(client, catalog):
    target = shade_id(catalog, "one-coat-black")
    saved = client.post(f"/shades/{target}/tip-colour", data={"hex": "#336699"})
    assert saved.status_code == 303 and saved.headers["location"] == f"/shades/{target}"
    assert (
        catalog.execute("select swatch_override_hex from shade where id = ?", (target,)).fetchone()[
            0
        ]
        == "#336699"
    )
    page = client.get(f"/shades/{target}").text
    assert 'value="#336699"' in page and "Reset" in page and "Your colour" in page
    assert 'fill="#336699"' in client.get(f"/tips/shade/{target}.svg").text
    client.post(f"/shades/{target}/tip-colour", data={"reset": "1"})
    assert (
        catalog.execute("select swatch_override_hex from shade where id = ?", (target,)).fetchone()[
            0
        ]
        is None
    )


@pytest.mark.parametrize("value", ["", "red", "#12345", "#gg0000", "336699", "#3366999"])
def test_a_bad_colour_is_422_and_nothing_is_saved(client, catalog, value):
    target = shade_id(catalog, "one-coat-black")
    response = client.post(f"/shades/{target}/tip-colour", data={"hex": value})
    assert response.status_code == 422 and "Pick a colour." in response.text
    assert (
        catalog.execute("select swatch_override_hex from shade where id = ?", (target,)).fetchone()[
            0
        ]
        is None
    )


def test_an_unknown_shade_is_404(client, catalog):
    assert client.post("/shades/99999/tip-colour", data={"hex": "#336699"}).status_code == 404
