"""catalog/overrides.py: the curated finish and kind of Matte Taco (DESIGN 14, item 90)."""

import pytest
from shade_data import apply, made_from, seed, shade_id

from polished import shades, stacks, tips, wheels
from polished.api import rows

BLACK = made_from("thirst-trap", 1, "One-Coat Black")
# The shop lists Matte Taco as a "Nail Polish" tagged color:clear only, and Glossy Taco as a top coat.
MATTE = made_from("thirst-trap", 2, "Matte Taco", tags=["collection:essentials", "color:clear"])
GLOSSY = made_from("thirst-trap", 3, "Glossy Taco", tags=["collection:essentials", "color:clear"])
GLOSSY["product_type"] = "Top Coat"


@pytest.fixture
def catalog(conn):
    seed(conn, [BLACK, MATTE, GLOSSY])
    return conn


def finishes(conn, handle):
    return {
        r[0]
        for r in conn.execute(
            "select value from shade_tag where ns = 'finish' and shade_id = ?",
            (shade_id(conn, handle),),
        )
    }


def stored(conn, handle):
    return conn.execute(
        "select kind, is_topper, search_text from shade where handle = ?", (handle,)
    ).fetchone()


def test_a_sync_gives_matte_taco_the_matte_finish_and_the_top_coat_kind(catalog):
    assert finishes(catalog, "matte-taco") == {"matte"}
    row = stored(catalog, "matte-taco")
    assert (row["kind"], row["is_topper"]) == ("topcoat", 1)
    assert "matte" in row["search_text"].split()


def test_glossy_taco_needs_nothing(catalog):
    assert finishes(catalog, "glossy-taco") == set()
    assert stored(catalog, "glossy-taco")["kind"] == "topcoat"


def test_an_unchanged_product_gets_its_override_back_on_the_next_sync(catalog):
    matte = shade_id(catalog, "matte-taco")
    catalog.execute("delete from shade_tag where shade_id = ? and ns = 'finish'", (matte,))
    catalog.execute("update shade set kind = 'polish' where id = ?", (matte,))
    counts = apply(catalog, [BLACK, MATTE, GLOSSY])
    assert counts.changed_shades == 0 and counts.new_shades == 0  # nothing in the feed changed
    assert finishes(catalog, "matte-taco") == {"matte"}
    assert stored(catalog, "matte-taco")["kind"] == "topcoat"


def test_a_stack_ending_in_matte_taco_has_no_gloss(catalog):
    wheel = wheels.create(catalog, "Holos")
    draft = stacks.open_draft(catalog, wheel, 1).stack_id
    for handle in ("one-coat-black", "matte-taco"):
        stacks.append(catalog, draft, shade_id(catalog, handle))
    layers = [tips.tip_shade(layer) for layer in stacks.layers(catalog, draft)]
    matte_ops = tips.ops(layers)
    gloss_ops = tips.ops(layers[:1])  # the black alone keeps its gloss
    assert not any(op["op"] == "path" for op in matte_ops)
    assert any(op["op"] == "path" for op in gloss_ops)
    assert tips.render(layers).count("<path") < tips.render(layers[:1]).count("<path")


def test_the_api_tip_of_matte_taco_lists_matte(catalog):
    shade = shades.get_shade(catalog, shade_id(catalog, "matte-taco"))
    assert "matte" in rows.shade_row(catalog, shade).tip.finishes
    assert (
        "matte"
        not in rows.shade_row(
            catalog, shades.get_shade(catalog, shade_id(catalog, "glossy-taco"))
        ).tip.finishes
    )
