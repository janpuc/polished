import sqlite3

import pytest
from shade_data import seed, shade_id

from polished import wheels


def put_stack(conn, wheel_id, position, shade_ids, status="saved") -> int:
    """A stack row with layers, hand-inserted and held by a slot, bypassing stacks.py."""
    stack = conn.execute("insert into stack (status) values (?)", (status,)).lastrowid
    for ord_, shade in enumerate(shade_ids, start=1):
        conn.execute(
            "insert into stack_layer (stack_id, ord, shade_id, coats) values (?, ?, ?, 2)",
            (stack, ord_, shade),
        )
    column = "stack_id" if status == "saved" else "draft_stack_id"
    conn.execute(
        f"insert into wheel_slot (wheel_id, position, {column}) values (?, ?, ?)"
        f" on conflict (wheel_id, position) do update set {column} = excluded.{column}",
        (wheel_id, position, stack),
    )
    return stack


@pytest.fixture
def catalog(conn):
    seed(conn)
    return conn


def test_a_slug_is_six_characters_of_the_crockford_alphabet():
    assert set(wheels.SLUG_ALPHABET) == set("0123456789abcdefghjkmnpqrstvwxyz")
    assert len(wheels.SLUG_ALPHABET) == 32
    for letter in "ilou":
        assert letter not in wheels.SLUG_ALPHABET
    for _ in range(200):
        slug = wheels.new_slug()
        assert len(slug) == 6
        assert set(slug) <= set(wheels.SLUG_ALPHABET)


def test_create_stores_the_slug_and_defaults_to_twenty_slots(conn):
    wheel_id = wheels.create(conn, "  Holos ")
    wheel = wheels.get(conn, wheel_id)
    assert wheel["name"] == "Holos"
    assert wheel["slot_count"] == 20
    assert wheel["archived"] == 0
    assert len(wheel["slug"]) == 6
    assert wheels.get_by_slug(conn, wheel["slug"])["id"] == wheel_id
    assert wheels.get_by_slug(conn, "zzzzzz") is None
    assert wheels.get(conn, 999) is None


def test_create_refuses_an_empty_name_and_a_slot_count_outside_1_to_40(conn):
    with pytest.raises(ValueError):
        wheels.create(conn, "   ")
    for count in (0, 41):
        with pytest.raises(ValueError):
            wheels.create(conn, "Holos", count)
    assert wheels.create(conn, "Small", 1) and wheels.create(conn, "Large", 40)


def test_a_taken_slug_is_retried_with_a_new_one(conn, monkeypatch):
    first = wheels.create(conn, "One")
    taken = wheels.get(conn, first)["slug"]
    drawn = iter([taken, taken, "abc234"])
    monkeypatch.setattr(wheels, "new_slug", lambda: next(drawn))
    second = wheels.create(conn, "Two")
    assert wheels.get(conn, second)["slug"] == "abc234"


def test_running_out_of_free_slugs_raises(conn, monkeypatch):
    taken = wheels.get(conn, wheels.create(conn, "One"))["slug"]
    monkeypatch.setattr(wheels, "new_slug", lambda: taken)
    with pytest.raises(RuntimeError):
        wheels.create(conn, "Two")


def test_other_integrity_errors_are_not_retried(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into wheel (slug, name, slot_count) values ('abc234', 'x', 99)")


def test_regenerate_changes_the_slug_and_frees_the_old_one(conn):
    wheel_id = wheels.create(conn, "Holos")
    old = wheels.get(conn, wheel_id)["slug"]
    new = wheels.regenerate_slug(conn, wheel_id)
    assert new != old
    assert wheels.get(conn, wheel_id)["slug"] == new
    assert wheels.get_by_slug(conn, old) is None
    assert wheels.get_by_slug(conn, new)["id"] == wheel_id


def test_regenerate_retries_a_collision_and_rejects_an_unknown_wheel(conn, monkeypatch):
    first = wheels.get(conn, wheels.create(conn, "One"))["slug"]
    second = wheels.create(conn, "Two")
    drawn = iter([first, "k3m9xq"])
    monkeypatch.setattr(wheels, "new_slug", lambda: next(drawn))
    assert wheels.regenerate_slug(conn, second) == "k3m9xq"
    monkeypatch.setattr(wheels, "new_slug", lambda: "abc234")
    with pytest.raises(wheels.WheelNotFound):
        wheels.regenerate_slug(conn, 999)


def test_take_tag_swaps_the_two_slugs(conn):
    a, b = wheels.create(conn, "Old"), wheels.create(conn, "New")
    slug_a, slug_b = (wheels.get(conn, i)["slug"] for i in (a, b))
    wheels.take_tag(conn, b, from_wheel_id=a)
    assert wheels.get(conn, b)["slug"] == slug_a
    assert wheels.get(conn, a)["slug"] == slug_b


def test_take_tag_refuses_itself_and_unknown_wheels_and_changes_nothing(conn):
    a = wheels.create(conn, "Old")
    slug = wheels.get(conn, a)["slug"]
    with pytest.raises(ValueError):
        wheels.take_tag(conn, a, from_wheel_id=a)
    with pytest.raises(wheels.WheelNotFound):
        wheels.take_tag(conn, a, from_wheel_id=999)
    assert wheels.get(conn, a)["slug"] == slug


def test_rename_and_archive_keep_the_slug(conn):
    wheel_id = wheels.create(conn, "Holos")
    slug = wheels.get(conn, wheel_id)["slug"]
    wheels.rename(conn, wheel_id, " Shimmers ")
    wheels.set_archived(conn, wheel_id, True)
    wheel = wheels.get(conn, wheel_id)
    assert (wheel["name"], wheel["archived"], wheel["slug"]) == ("Shimmers", 1, slug)
    assert wheels.get_by_slug(conn, slug)["id"] == wheel_id
    wheels.set_archived(conn, wheel_id, False)
    assert wheels.get(conn, wheel_id)["archived"] == 0
    with pytest.raises(ValueError):
        wheels.rename(conn, wheel_id, "")


def test_list_hides_archived_wheels_and_counts_filled_slots_and_drafts(catalog):
    shade = shade_id(catalog, "thirst-trap")
    keep, old = wheels.create(catalog, "Zeta"), wheels.create(catalog, "alpha")
    gone = wheels.create(catalog, "Gone")
    wheels.set_archived(catalog, gone, True)
    put_stack(catalog, keep, 1, [shade])
    put_stack(catalog, keep, 2, [shade])
    put_stack(catalog, keep, 3, [shade], status="draft")
    listed = wheels.list_wheels(catalog)
    assert [(w["name"], w["filled"], w["drafts"]) for w in listed] == [
        ("alpha", 0, 0),
        ("Zeta", 2, 1),
    ]
    assert [w["name"] for w in wheels.list_wheels(catalog, archived=True)] == ["Gone"]
    assert old and keep


def test_the_grid_has_a_tile_for_every_position_1_to_20(catalog):
    wheel = wheels.get(catalog, wheels.create(catalog, "Holos"))
    grid = wheels.slot_grid(catalog, wheel)
    assert [t["position"] for t in grid] == list(range(1, 21))
    assert not any(t["filled"] or t["has_draft"] for t in grid)
    assert all(t["layers"] == [] and t["summary"] == "" for t in grid)


def test_the_grid_follows_slot_count(conn):
    wheel = wheels.get(conn, wheels.create(conn, "Small", slot_count=6))
    assert [t["position"] for t in wheels.slot_grid(conn, wheel)] == [1, 2, 3, 4, 5, 6]


def test_the_grid_shows_summary_layers_and_the_draft_flag(catalog):
    black, trap, topper = (
        shade_id(catalog, h) for h in ("jam-session", "thirst-trap", "aurora-unicorn-skin")
    )
    wheel_id = wheels.create(catalog, "Holos")
    put_stack(catalog, wheel_id, 12, [black, trap, topper])
    put_stack(catalog, wheel_id, 12, [trap], status="draft")
    put_stack(catalog, wheel_id, 5, [trap], status="draft")
    grid = {t["position"]: t for t in wheels.slot_grid(catalog, wheels.get(catalog, wheel_id))}
    filled = grid[12]
    assert filled["filled"] and filled["has_draft"]
    assert [layer["label"] for layer in filled["layers"]] == ["Base", "2nd", "Top"]
    assert filled["summary"].count(" + ") == 2 and "×2" in filled["summary"]
    assert [layer["hero_image_url"] for layer in filled["layers"]]
    assert not grid[5]["filled"] and grid[5]["has_draft"] and grid[5]["summary"] == ""
    assert not grid[6]["filled"] and not grid[6]["has_draft"]


def test_slot_tile_is_the_same_tile_as_the_grid(catalog):
    wheel_id = wheels.create(catalog, "Holos")
    put_stack(catalog, wheel_id, 3, [shade_id(catalog, "thirst-trap")])
    wheel = wheels.get(catalog, wheel_id)
    assert wheels.slot_tile(catalog, wheel, 3) == wheels.slot_grid(catalog, wheel)[2]
    assert wheels.slot_tile(catalog, wheel, 4)["filled"] is False


def test_tag_url_is_public_url_plus_slug():
    assert wheels.tag_url("https://polished.janpuc.com", "k3m9xq") == (
        "https://polished.janpuc.com/w/k3m9xq"
    )
    assert wheels.tag_url("http://localhost:8080/", "abc234") == "http://localhost:8080/w/abc234"


def swatched(catalog):
    black, trap, topper = (
        shade_id(catalog, h) for h in ("jam-session", "thirst-trap", "aurora-unicorn-skin")
    )
    return black, trap, topper


def test_swatched_on_lists_wheel_slug_and_position_by_name_then_position(catalog):
    black, trap, topper = swatched(catalog)
    holos, glitter = wheels.create(catalog, "Holos"), wheels.create(catalog, "Glitter")
    put_stack(catalog, holos, 12, [black, topper])
    put_stack(catalog, holos, 3, [topper, topper])  # twice in one stack: one row
    put_stack(catalog, glitter, 7, [topper, trap])
    put_stack(catalog, holos, 4, [trap])
    found = wheels.swatched_on(catalog, topper)
    assert [(w["name"], w["position"]) for w in found] == [
        ("Glitter", 7),
        ("Holos", 3),
        ("Holos", 12),
    ]
    assert found[0]["slug"] == wheels.get(catalog, glitter)["slug"]
    assert wheels.swatched_on(catalog, shade_id(catalog, "rest-in-peach")) == []


def test_swatched_on_ignores_drafts_and_archived_wheels(catalog):
    _, trap, topper = swatched(catalog)
    holos, old = wheels.create(catalog, "Holos"), wheels.create(catalog, "Old")
    put_stack(catalog, holos, 1, [trap])
    put_stack(catalog, holos, 1, [topper], status="draft")
    put_stack(catalog, old, 2, [topper])
    wheels.set_archived(catalog, old, True)
    assert wheels.swatched_on(catalog, topper) == []
    assert [w["position"] for w in wheels.swatched_on(catalog, trap)] == [1]


def test_highlight_positions_are_the_slots_of_one_wheel_holding_the_shade(catalog):
    black, trap, topper = swatched(catalog)
    holos, other = wheels.create(catalog, "Holos"), wheels.create(catalog, "Other")
    put_stack(catalog, holos, 12, [black, topper])
    put_stack(catalog, holos, 3, [topper])
    put_stack(catalog, holos, 8, [trap])
    put_stack(catalog, holos, 9, [topper], status="draft")
    put_stack(catalog, other, 1, [topper])
    assert wheels.highlight_positions(catalog, holos, topper) == [3, 12]
    assert wheels.highlight_positions(catalog, other, topper) == [1]
    assert wheels.highlight_positions(catalog, holos, shade_id(catalog, "rest-in-peach")) == []


def test_highlight_works_on_an_archived_wheel(catalog):
    _, _, topper = swatched(catalog)
    old = wheels.create(catalog, "Old")
    put_stack(catalog, old, 2, [topper])
    wheels.set_archived(catalog, old, True)
    assert wheels.highlight_positions(catalog, old, topper) == [2]


def test_deleting_a_wheel_row_cascades_to_its_slots(catalog):
    wheel_id = wheels.create(catalog, "Holos")
    put_stack(catalog, wheel_id, 1, [shade_id(catalog, "thirst-trap")])
    catalog.execute("delete from wheel where id = ?", (wheel_id,))
    assert catalog.execute("select count(*) from wheel_slot").fetchone()[0] == 0
