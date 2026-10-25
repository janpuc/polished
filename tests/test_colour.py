"""Reading the polish colour from photos (catalog/colour.py): synthetic images, a mocked CDN."""

import io
import json

import httpx
import pytest
from conftest import load_feed
from PIL import Image, ImageDraw
from shade_data import apply, shade_id

from polished.catalog import colour
from polished.catalog.colour import extract_colours, fill_colours, shade_colours

CDN = "https://cdn.shopify.com/s/files/1/x/files/"


def jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", quality=95)
    return out.getvalue()


def bottle(glass=(200, 40, 90), backdrop=(255, 255, 255)) -> bytes:
    """White backdrop, black cap on top, a coloured glass body in the lower part."""
    image = Image.new("RGB", (240, 240), backdrop)
    draw = ImageDraw.Draw(image)
    draw.rectangle([96, 10, 144, 100], fill=(8, 8, 8))
    draw.rectangle([70, 105, 170, 225], fill=glass)
    return jpeg(image)


def near(hex_colour: str, rgb: tuple[int, int, int], tolerance=14) -> bool:
    got = tuple(int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return all(abs(a - b) <= tolerance for a, b in zip(got, rgb, strict=True))


def test_a_bottle_shot_gives_the_glass_colour_not_the_cap_or_the_backdrop():
    result = extract_colours(bottle(), from_bottle=True)
    assert near(result.hex, (200, 40, 90))
    assert result.hex2 is None


def test_a_dark_backdrop_does_not_become_the_colour():
    result = extract_colours(bottle((30, 110, 190), backdrop=(0, 0, 0)), from_bottle=True)
    assert near(result.hex, (30, 110, 190))


def test_a_swatch_photo_gives_the_nail_not_the_skin_or_a_highlight():
    image = Image.new("RGB", (240, 240), (233, 178, 150))  # skin all around
    draw = ImageDraw.Draw(image)
    draw.rectangle([60, 40, 180, 220], fill=(70, 20, 120))  # the nail
    draw.rectangle([100, 100, 112, 130], fill=(255, 255, 255))  # a highlight
    result = extract_colours(jpeg(image), from_bottle=False)
    assert near(result.hex, (70, 20, 120))


def test_a_second_colour_is_kept_only_when_clearly_different_and_big_enough():
    image = Image.new("RGB", (240, 240), (233, 178, 150))
    draw = ImageDraw.Draw(image)
    draw.rectangle([60, 40, 180, 220], fill=(30, 90, 200))
    draw.rectangle([120, 40, 180, 220], fill=(200, 60, 160))  # half of the nail
    result = extract_colours(jpeg(image), from_bottle=False)
    assert {near(result.hex, (30, 90, 200)), near(result.hex2 or "#000000", (200, 60, 160))} == {
        True
    }
    flat = Image.new("RGB", (240, 240), (120, 130, 140))
    assert extract_colours(jpeg(flat), from_bottle=False).hex2 is None


def test_a_white_or_nude_polish_still_gets_a_colour():
    white = extract_colours(jpeg(Image.new("RGB", (240, 240), (250, 250, 250))), from_bottle=False)
    assert near(white.hex, (250, 250, 250), 8)
    nude = extract_colours(jpeg(Image.new("RGB", (240, 240), (233, 178, 150))), from_bottle=False)
    assert near(nude.hex, (233, 178, 150), 8)


def test_a_topper_takes_the_livelier_colour_not_the_base_it_was_shown_over():
    image = Image.new("RGB", (240, 240), (40, 90, 160))
    draw = ImageDraw.Draw(image)
    for x in range(60, 180, 12):
        for y in range(60, 180, 12):
            draw.rectangle([x, y, x + 5, y + 5], fill=(240, 30, 200))
    assert near(
        extract_colours(jpeg(image), from_bottle=False, accent=True).hex, (240, 30, 200), 45
    )
    assert near(extract_colours(jpeg(image), from_bottle=False).hex, (40, 90, 160), 30)


def test_bytes_that_are_not_an_image_raise_value_error():
    with pytest.raises(ValueError):
        extract_colours(b"<html>", from_bottle=True)


# --- the sync step ----------------------------------------------------------------------------


@pytest.fixture
def seeded(conn):
    apply(conn, load_feed())
    return conn


def cdn_transport(seen, *, body=None, status=200):
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=body if body is not None else bottle())

    return httpx.MockTransport(handle)


def test_fill_colours_reads_each_shade_once_from_the_cdn_only(seeded):
    seen = []
    stored = fill_colours(seeded, transport=cdn_transport(seen))
    assert stored >= len(seen) > 0  # base coats and clear top coats are stored without a download
    assert {r.url.host for r in seen} == {"cdn.shopify.com"}
    assert all(r.url.params["width"] == "240" for r in seen)
    row = seeded.execute("select * from shade where swatch_hex is not null limit 1").fetchone()
    assert near(row["swatch_hex"], (200, 40, 90)) and row["swatch_hex_src"]
    again = []
    assert fill_colours(seeded, transport=cdn_transport(again)) == 0
    assert again == []


def test_a_new_photo_is_read_again_and_an_override_is_left_alone(seeded):
    fill_colours(seeded, transport=cdn_transport([]))
    target = shade_id(seeded, "thirst-trap")
    seeded.execute("update shade set swatch_override_hex = '#123456' where id = ?", (target,))
    seeded.execute(
        "update shade set swatch_image_url = ? where id = ?", (f"{CDN}new_macro1.jpg?v=2", target)
    )
    seen = []
    assert fill_colours(seeded, transport=cdn_transport(seen, body=bottle((20, 160, 60)))) == 1
    assert [r.url.path for r in seen] == ["/s/files/1/x/files/new_macro1.jpg"]
    row = seeded.execute("select * from shade where id = ?", (target,)).fetchone()
    assert row["swatch_override_hex"] == "#123456"
    assert row["swatch_hex_src"] == f"{CDN}new_macro1.jpg?v=2"


@pytest.mark.parametrize("status,body", [(500, b"oops"), (200, b"<html>not an image</html>")])
def test_colour_errors_leave_the_colour_empty_and_stop_after_a_run_of_them(seeded, status, body):
    seen = []
    assert fill_colours(seeded, transport=cdn_transport(seen, body=body, status=status)) == 0
    assert len(seen) == colour.GIVE_UP_AFTER
    assert (
        seeded.execute("select count(*) from shade where swatch_hex is not null").fetchone()[0] == 0
    )


def test_a_network_error_never_escapes(seeded):
    def refuse(request):
        raise httpx.ConnectError("down")

    assert fill_colours(seeded, transport=httpx.MockTransport(refuse)) == 0


def test_the_pauses_between_downloads_are_the_rate_limit(seeded):
    pauses = []
    fill_colours(seeded, transport=cdn_transport([]), sleep=pauses.append)
    assert pauses and set(pauses) == {colour.CDN_INTERVAL_S}


async def test_a_sync_run_reads_colours_and_a_colour_error_does_not_fail_it(
    tmp_path, settings, conn
):
    from polished.catalog.sync import SyncRunner

    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": load_feed()}), encoding="utf-8")
    seen = []
    runner = SyncRunner(settings, colour_transport=cdn_transport(seen))
    assert (await runner.run("cli", [page])).status == "ok"
    assert conn.execute("select count(*) from shade where swatch_hex is not null").fetchone()[0] > 0
    broken = SyncRunner(settings, colour_transport=cdn_transport([], status=500))
    conn.execute("update shade set swatch_hex = null, swatch_hex_src = null")
    assert (await broken.run("cli", [page])).status == "ok"
    assert (
        conn.execute("select count(*) from shade where swatch_hex is not null").fetchone()[0] == 0
    )


def test_the_feed_sync_never_writes_the_override_or_the_colour(seeded):
    target = shade_id(seeded, "thirst-trap")
    seeded.execute(
        "update shade set swatch_override_hex = '#abcdef', swatch_hex = '#010203' where id = ?",
        (target,),
    )
    changed = load_feed()
    next(p for p in changed if p["handle"] == "thirst-trap")["title"] = "Thirst Trap Two"
    apply(seeded, changed)
    row = seeded.execute("select * from shade where id = ?", (target,)).fetchone()
    assert row["title"] == "Thirst Trap Two"
    assert (row["swatch_override_hex"], row["swatch_hex"]) == ("#abcdef", "#010203")


# --- two sources, dark backdrops, sheer coats ---------------------------------------------------

DARK_SKIN = (93, 44, 15)


def nail_photo(background, nail, box=(90, 80, 150, 160)) -> bytes:
    image = Image.new("RGB", (240, 240), background)
    ImageDraw.Draw(image).rectangle(list(box), fill=nail)
    return jpeg(image)


def test_a_white_nail_on_a_dark_skinned_hand_is_white_not_the_skin():
    photo = nail_photo(DARK_SKIN, (238, 236, 232))
    assert near(extract_colours(photo, from_bottle=False).hex, (238, 236, 232), 20)


def test_a_yellow_nail_on_a_black_backdrop_is_yellow_not_the_skin_at_its_edge():
    photo = nail_photo((6, 6, 6), (240, 215, 40), box=(85, 80, 155, 160))
    assert near(extract_colours(photo, from_bottle=False).hex, (240, 215, 40), 30)


def test_a_black_polish_stays_black():
    photo = nail_photo((11, 10, 9), (11, 10, 9))
    assert near(extract_colours(photo, from_bottle=False).hex, (11, 10, 9), 6)


def test_a_skin_dominated_swatch_gives_way_to_a_chrome_bottle():
    swatch = nail_photo(DARK_SKIN, DARK_SKIN)
    chrome = (190, 192, 196)
    assert near(shade_colours(swatch, lambda: bottle(chrome)).hex, chrome)


def test_a_nude_that_both_photos_show_stays_nude():
    nude = (196, 140, 120)
    swatch = nail_photo((233, 178, 150), nude)
    result = shade_colours(swatch, lambda: bottle(nude))
    assert near(result.hex, nude, 20)


def test_a_swatch_that_is_not_skin_is_kept_and_the_bottle_is_not_fetched():
    def no_bottle():
        raise AssertionError("the bottle photo is not needed")

    assert near(
        shade_colours(nail_photo((233, 178, 150), (70, 20, 120)), no_bottle).hex, (70, 20, 120)
    )


def test_only_the_bottle_when_there_is_no_swatch_photo():
    assert near(shade_colours(None, lambda: bottle()).hex, (200, 40, 90))
    with pytest.raises(ValueError):
        shade_colours(None, lambda: None)


@pytest.mark.parametrize(
    "kind,colours,finishes,sheer",
    [
        ("basecoat", set(), set(), True),
        ("topcoat", {"clear"}, set(), True),
        ("topcoat", {"clear"}, {"glitter"}, False),
        ("topcoat", {"clear"}, {"flakie"}, False),
        ("topcoat", {"clear"}, {"holographic"}, False),
        ("topcoat", {"pink"}, set(), False),
        ("polish", {"red"}, {"creme"}, False),
    ],
)
def test_which_shades_are_sheer(kind, colours, finishes, sheer):
    assert colour.is_sheer(kind, colours, finishes) is sheer


def test_a_base_coat_gets_the_fixed_neutral_without_a_download(seeded):
    target = shade_id(seeded, "thirst-trap")
    seeded.execute("update shade set kind = 'basecoat' where id = ?", (target,))
    seen = []
    fill_colours(seeded, transport=cdn_transport(seen), only=["Thirst Trap"], recompute=True)
    row = seeded.execute("select * from shade where id = ?", (target,)).fetchone()
    assert (row["swatch_hex"], row["swatch_hex2"]) == (colour.SHEER_HEX, None)
    assert seen == []


def test_a_known_shade_takes_its_checked_colour_without_a_download(seeded, monkeypatch):
    target = shade_id(seeded, "thirst-trap")
    monkeypatch.setitem(colour.KNOWN_COLOURS, "thirst-trap", ("#d4a84f", "#6b4a1e"))
    seeded.execute("update shade set swatch_override_hex = '#123456' where id = ?", (target,))
    seen = []
    fill_colours(seeded, transport=cdn_transport(seen), only=["Thirst Trap"], recompute=True)
    row = seeded.execute("select * from shade where id = ?", (target,)).fetchone()
    assert (row["swatch_hex"], row["swatch_hex2"]) == ("#d4a84f", "#6b4a1e")
    assert row["swatch_override_hex"] == "#123456"
    assert seen == []
