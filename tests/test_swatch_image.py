"""The swatch photo: the filename heuristic, what sync writes and the backfill (DESIGN 5.2)."""

import copy

import pytest
from test_sync import Syncer, by_handle, shade_row

from polished import stacks, wheels
from polished.catalog.parse import swatch_image_url

CDN = "https://cdn.shopify.com/s/files/1/0050/3001/9162/files/"


@pytest.fixture
def syncer(conn):
    return Syncer(conn)


def images(*names):
    return [{"position": i, "src": f"{CDN}{name}?v=1"} for i, name in enumerate(names, 1)]


def test_a_macro_beats_a_hand_which_beats_a_swatch_shot_whatever_the_position():
    shots = images("HT-Bottle-X-Black.jpg", "swatch-x.jpg", "x_hand2_sq.jpg", "DSC_1_macro1.jpg")
    assert swatch_image_url(shots).endswith("DSC_1_macro1.jpg?v=1")
    assert swatch_image_url(shots[:3]).endswith("x_hand2_sq.jpg?v=1")
    assert swatch_image_url(shots[:2]).endswith("swatch-x.jpg?v=1")


def test_the_earliest_position_wins_inside_a_rank():
    shots = images("bottle.jpg", "b_macro2.jpg", "a_macro1.jpg")
    assert swatch_image_url(shots).endswith("b_macro2.jpg?v=1")


def test_bottle_brush_swipe_corner_side_collage_spill_and_gif_shots_are_skipped():
    shots = images(
        "HT-Brainrot-BottleHeroes-X.jpg",
        "HT-Brainrot-CornerMacro-X.jpg",
        "HT-Brainrot-SideMacro-X.jpg",
        "HT-Brush_macro.jpg",
        "x-swipe-macro.jpg",
        "x_collage_macro.jpg",
        "x_spill_macro.jpg",
        "x_macro1.gif",
        "hand-w-bottle.jpg",
    )
    assert swatch_image_url(shots) is None


def test_words_are_whole_words_and_the_shades_own_title_is_not_a_bottle_shot():
    assert swatch_image_url(images("InsideJob-hand2.jpg")) is not None  # "inside" is not "side"
    shots = images("hand2_BottleService.jpg")
    assert swatch_image_url(shots, "Bottle Service") is not None
    assert swatch_image_url(shots) is None


def test_older_products_fall_back_to_a_page_shot_after_the_bottle():
    assert swatch_image_url(images("HT-Bottle-PDP-1.jpg", "HT-Cristmas-PDP-x-2.jpg")).endswith(
        "PDP-x-2.jpg?v=1"
    )
    assert swatch_image_url(images("HT-Cristmas-PDP-x-1.jpg")) is None  # position 1 is the bottle
    assert swatch_image_url(images("only-a-bottle.jpg", "random-2.jpg")) is None
    assert swatch_image_url([]) is None


def with_images(product, *names):
    product["images"] = images(*names)
    return product


def test_sync_writes_the_swatch_for_new_and_changed_shades(syncer, conn, feed):
    syncer.apply(feed)
    feed = copy.deepcopy(feed)
    product = with_images(by_handle(feed, "thirst-trap"), "b-Bottle.jpg", "t_macro1.jpg")
    syncer.apply(feed)
    assert shade_row(conn, "thirst-trap")["swatch_image_url"] == f"{CDN}t_macro1.jpg?v=1"
    with_images(product, "b-Bottle.jpg", "t_hand1.jpg")
    syncer.apply(feed)
    assert shade_row(conn, "thirst-trap")["swatch_image_url"] == f"{CDN}t_hand1.jpg?v=1"


def test_an_unchanged_shade_without_a_swatch_is_filled_by_the_next_sync(syncer, conn, feed):
    feed = copy.deepcopy(feed)
    with_images(by_handle(feed, "thirst-trap"), "b-Bottle.jpg", "t_macro1.jpg")
    syncer.apply(feed)
    conn.execute("update shade set swatch_image_url = null")  # a database from before 005
    hashes = conn.execute("select content_hash from product order by id").fetchall()
    counts = syncer.apply(feed)
    assert counts.changed_shades == 0
    assert shade_row(conn, "thirst-trap")["swatch_image_url"] == f"{CDN}t_macro1.jpg?v=1"
    assert conn.execute("select content_hash from product order by id").fetchall() == hashes


def test_layers_carry_the_swatch_image(syncer, conn, feed):
    feed = copy.deepcopy(feed)
    with_images(by_handle(feed, "thirst-trap"), "b-Bottle.jpg", "t_macro1.jpg")
    syncer.apply(feed)
    shade = shade_row(conn, "thirst-trap")["id"]
    wheel_id = wheels.create(conn, "Holos")
    stack_id = stacks.open_draft(conn, wheel_id, 1).stack_id
    stacks.append(conn, stack_id, shade)
    [layer] = stacks.layers(conn, stack_id)
    assert layer["swatch_image_url"] == f"{CDN}t_macro1.jpg?v=1"
    assert layer["hero_image_url"]
