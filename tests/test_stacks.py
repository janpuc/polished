import sqlite3

import pytest
from shade_data import made_from, seed, shade_id

from polished import stacks, wheels

BLACK = made_from("thirst-trap", 1, "One-Coat Black")
FINGERS = made_from("thirst-trap", 2, "Spirit Fingers")
FLAKIE = made_from("aurora-unicorn-skin", 3, "Flakie Holo Taco")


@pytest.fixture
def catalog(conn):
    seed(conn, [BLACK, FINGERS, FLAKIE])
    return conn


@pytest.fixture
def black(catalog):
    return shade_id(catalog, "one-coat-black")


@pytest.fixture
def fingers(catalog):
    return shade_id(catalog, "spirit-fingers")


@pytest.fixture
def flakie(catalog):
    return shade_id(catalog, "flakie-holo-taco")


@pytest.fixture
def wheel(catalog):
    return wheels.create(catalog, "Holos")


@pytest.fixture
def draft(catalog, wheel):
    return stacks.open_draft(catalog, wheel, 12).stack_id


def titles(conn, stack_id) -> list[str]:
    return [layer["title"] for layer in stacks.layers(conn, stack_id)]


def coats(conn, stack_id) -> list[int]:
    return [layer["coats"] for layer in stacks.layers(conn, stack_id)]


def ords(conn, stack_id) -> list[int]:
    return [layer["ord"] for layer in stacks.layers(conn, stack_id)]


def save_slot(conn, wheel_id, position, shade_ids, **kwargs) -> int:
    """Builds and saves a stack through the public functions; returns the saved stack id."""
    stack = stacks.open_draft(conn, wheel_id, position).stack_id
    for shade in shade_ids:
        stacks.append(conn, stack, shade)
    stacks.save(conn, stack, **kwargs)
    return stack


def slot_row(conn, wheel_id, position):
    return conn.execute(
        "select * from wheel_slot where wheel_id = ? and position = ?", (wheel_id, position)
    ).fetchone()


def count(conn, table) -> int:
    return conn.execute(f"select count(*) from {table}").fetchone()[0]


# default coats and labels


def test_default_coats_is_1_for_top_coats_base_coats_and_toppers_and_2_for_polish():
    assert stacks.default_coats({"kind": "topcoat", "is_topper": 1}) == 1
    assert stacks.default_coats({"kind": "basecoat", "is_topper": 0}) == 1
    assert stacks.default_coats({"kind": "polish", "is_topper": 1}) == 1
    assert stacks.default_coats({"kind": "polish", "is_topper": 0}) == 2


def test_labels_are_base_2nd_3rd_top_and_none_for_one_layer():
    assert stacks.layer_labels(0) == []
    assert stacks.layer_labels(1) == [""]
    assert stacks.layer_labels(2) == ["Base", "Top"]
    assert stacks.layer_labels(3) == ["Base", "2nd", "Top"]
    assert stacks.layer_labels(5) == ["Base", "2nd", "3rd", "4th", "Top"]
    assert stacks.layer_labels(8)[-2:] == ["7th", "Top"]


def test_summary_names_the_layers_in_painting_order_and_multiplies_above_one():
    layers = [
        {"title": "One-Coat Black", "coats": 1},
        {"title": "Spirit Fingers", "coats": 2},
        {"title": "Flakie Holo Taco", "coats": 1},
    ]
    assert stacks.summary(layers) == "One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco"
    assert stacks.summary(layers[:1]) == "One-Coat Black"
    assert stacks.summary([]) == ""


# draft lifecycle


def test_opening_a_draft_creates_the_slot_row_and_an_empty_draft(catalog, wheel):
    opened = stacks.open_draft(catalog, wheel, 12)
    assert opened.resumed is False
    row = slot_row(catalog, wheel, 12)
    assert row["draft_stack_id"] == opened.stack_id and row["stack_id"] is None
    status = catalog.execute("select status from stack").fetchone()[0]
    assert status == "draft"
    assert stacks.layers(catalog, opened.stack_id) == []


def test_opening_again_resumes_the_same_draft(catalog, wheel, draft, fingers):
    stacks.append(catalog, draft, fingers)
    again = stacks.open_draft(catalog, wheel, 12)
    assert (again.stack_id, again.resumed) == (draft, True)
    assert titles(catalog, draft) == ["Spirit Fingers"]
    assert count(catalog, "stack") == 1


def test_opening_a_saved_slot_copies_its_layers_and_name_into_the_draft(
    catalog, wheel, black, fingers
):
    saved = save_slot(catalog, wheel, 4, [black, fingers], name="Night sky")
    opened = stacks.open_draft(catalog, wheel, 4)
    assert opened.stack_id != saved and opened.resumed is False
    assert titles(catalog, opened.stack_id) == ["One-Coat Black", "Spirit Fingers"]
    assert stacks.sheet(catalog, opened.stack_id)["name"] == "Night sky"
    row = slot_row(catalog, wheel, 4)
    assert (row["stack_id"], row["draft_stack_id"]) == (saved, opened.stack_id)
    # Editing the draft leaves the saved stack alone.
    first = stacks.layers(catalog, opened.stack_id)[0]["id"]
    stacks.change_coats(catalog, opened.stack_id, first, 1)
    assert coats(catalog, opened.stack_id) == [3, 2]
    assert coats(catalog, saved) == [2, 2]


def test_open_refuses_an_unknown_wheel_and_a_position_outside_the_wheel(catalog, wheel):
    for args in ((999, 1), (wheel, 0), (wheel, 21)):
        with pytest.raises(stacks.SlotNotFound):
            stacks.open_draft(catalog, *args)
    assert count(catalog, "wheel_slot") == 0
    stacks.open_draft(catalog, wheel, 20)


def test_sheet_describes_the_draft(catalog, wheel, draft, black, fingers):
    stacks.append(catalog, draft, black)
    stacks.append(catalog, draft, fingers)
    sheet = stacks.sheet(catalog, draft)
    assert (sheet["wheel_id"], sheet["position"], sheet["wheel_name"]) == (wheel, 12, "Holos")
    assert sheet["wheel_slug"] == wheels.get(catalog, wheel)["slug"]
    assert sheet["summary"] == "One-Coat Black ×2 + Spirit Fingers ×2"
    assert [layer["label"] for layer in sheet["layers"]] == ["Base", "Top"]
    assert sheet["full"] is False


# layers


def test_append_adds_on_top_with_default_coats(catalog, draft, black, fingers, flakie):
    stacks.append(catalog, draft, fingers)
    stacks.append(catalog, draft, flakie)
    stacks.append(catalog, draft, black)
    assert titles(catalog, draft) == ["Spirit Fingers", "Flakie Holo Taco", "One-Coat Black"]
    assert coats(catalog, draft) == [2, 1, 2]  # polish 2, topper 1, polish 2
    assert ords(catalog, draft) == [1, 2, 3]


def test_a_base_coat_and_a_top_coat_get_one_coat(catalog, draft):
    stacks.append(catalog, draft, shade_id(catalog, "peely-base"))
    stacks.append(catalog, draft, shade_id(catalog, "aurora-unicorn-skin"))
    assert coats(catalog, draft) == [1, 1]


def test_the_same_shade_may_appear_twice(catalog, draft, fingers):
    stacks.append(catalog, draft, fingers)
    stacks.append(catalog, draft, fingers)
    assert titles(catalog, draft) == ["Spirit Fingers", "Spirit Fingers"]


def test_append_refuses_an_unknown_shade(catalog, draft):
    with pytest.raises(stacks.ShadeNotFound):
        stacks.append(catalog, draft, 999_999)


def test_a_stack_holds_at_most_eight_layers(catalog, draft, fingers):
    for _ in range(8):
        stacks.append(catalog, draft, fingers)
    assert stacks.sheet(catalog, draft)["full"] is True
    with pytest.raises(stacks.StackFull):
        stacks.append(catalog, draft, fingers)
    assert len(stacks.layers(catalog, draft)) == 8


def three_layers(catalog, draft, black, fingers, flakie):
    for shade in (black, fingers, flakie):
        stacks.append(catalog, draft, shade)
    return [layer["id"] for layer in stacks.layers(catalog, draft)]


def test_move_up_and_down_swap_neighbours_through_a_temporary_ord(
    catalog, draft, black, fingers, flakie
):
    a, b, c = three_layers(catalog, draft, black, fingers, flakie)
    assert stacks.move(catalog, draft, c, "up") is True
    assert titles(catalog, draft) == ["One-Coat Black", "Flakie Holo Taco", "Spirit Fingers"]
    assert stacks.move(catalog, draft, a, "down") is True
    assert titles(catalog, draft) == ["Flakie Holo Taco", "One-Coat Black", "Spirit Fingers"]
    assert ords(catalog, draft) == [1, 2, 3]
    assert coats(catalog, draft) == [1, 2, 2]  # coats travel with their layer
    assert b and stacks.layers(catalog, draft)[2]["id"] == b


def test_moving_past_either_end_changes_nothing(catalog, draft, black, fingers, flakie):
    a, _, c = three_layers(catalog, draft, black, fingers, flakie)
    assert stacks.move(catalog, draft, a, "up") is False
    assert stacks.move(catalog, draft, c, "down") is False
    assert titles(catalog, draft) == ["One-Coat Black", "Spirit Fingers", "Flakie Holo Taco"]


def test_move_rejects_an_unknown_direction(catalog, draft, black):
    layer = stacks.append(catalog, draft, black)
    with pytest.raises(ValueError):
        stacks.move(catalog, draft, layer, "sideways")


def test_coats_change_by_one_and_clamp_to_1_through_5(catalog, draft, fingers):
    layer = stacks.append(catalog, draft, fingers)  # 2 coats
    assert stacks.change_coats(catalog, draft, layer, -1) == 1
    assert stacks.change_coats(catalog, draft, layer, -1) == 1
    for expected in (2, 3, 4, 5, 5, 5):
        assert stacks.change_coats(catalog, draft, layer, 1) == expected
    assert coats(catalog, draft) == [5]
    with pytest.raises(ValueError):
        stacks.change_coats(catalog, draft, layer, 2)


def test_remove_deletes_the_layer_and_renumbers(catalog, draft, black, fingers, flakie):
    a, b, c = three_layers(catalog, draft, black, fingers, flakie)
    stacks.remove(catalog, draft, b)
    assert titles(catalog, draft) == ["One-Coat Black", "Flakie Holo Taco"]
    assert ords(catalog, draft) == [1, 2]
    stacks.remove(catalog, draft, a)
    assert ords(catalog, draft) == [1]
    stacks.remove(catalog, draft, c)
    assert stacks.layers(catalog, draft) == []


def test_a_layer_of_another_stack_is_not_found(catalog, wheel, draft, black):
    other = stacks.open_draft(catalog, wheel, 3).stack_id
    layer = stacks.append(catalog, other, black)
    for call in (
        lambda: stacks.move(catalog, draft, layer, "up"),
        lambda: stacks.change_coats(catalog, draft, layer, 1),
        lambda: stacks.remove(catalog, draft, layer),
    ):
        with pytest.raises(stacks.LayerNotFound):
            call()
    assert titles(catalog, other) == ["One-Coat Black"]


# templates


def test_over_black_inserts_the_base_with_one_coat_and_shifts_the_rest(
    catalog, draft, fingers, flakie
):
    stacks.append(catalog, draft, fingers)
    stacks.append(catalog, draft, flakie)
    assert stacks.over_black(catalog, draft, "one-coat-black") == "added"
    assert titles(catalog, draft) == ["One-Coat Black", "Spirit Fingers", "Flakie Holo Taco"]
    assert coats(catalog, draft) == [1, 2, 1]
    assert ords(catalog, draft) == [1, 2, 3]


def test_over_black_on_an_empty_draft_adds_just_the_black(catalog, draft):
    assert stacks.over_black(catalog, draft, "one-coat-black") == "added"
    assert titles(catalog, draft) == ["One-Coat Black"]


def test_over_black_is_a_no_op_when_the_black_is_already_first(catalog, draft, black, fingers):
    stacks.append(catalog, draft, black)
    stacks.append(catalog, draft, fingers)
    before = stacks.layers(catalog, draft)
    assert stacks.over_black(catalog, draft, "one-coat-black") == "already"
    assert stacks.layers(catalog, draft) == before


def test_over_black_adds_when_the_black_is_only_further_up(catalog, draft, black, fingers):
    stacks.append(catalog, draft, fingers)
    stacks.append(catalog, draft, black)
    assert stacks.over_black(catalog, draft, "one-coat-black") == "added"
    assert titles(catalog, draft) == ["One-Coat Black", "Spirit Fingers", "One-Coat Black"]


def test_over_black_reports_a_handle_missing_from_the_catalog(catalog, draft, fingers):
    stacks.append(catalog, draft, fingers)
    assert stacks.over_black_shade(catalog, "no-such-handle") is None
    assert stacks.over_black_shade(catalog, "one-coat-black")["title"] == "One-Coat Black"
    assert stacks.over_black(catalog, draft, "no-such-handle") == "unavailable"
    assert titles(catalog, draft) == ["Spirit Fingers"]


def test_over_black_uses_the_handle_it_is_given(catalog, draft):
    assert stacks.over_black(catalog, draft, "spirit-fingers") == "added"
    assert titles(catalog, draft) == ["Spirit Fingers"]


def test_over_black_on_a_full_stack_is_refused(catalog, draft, fingers):
    for _ in range(8):
        stacks.append(catalog, draft, fingers)
    with pytest.raises(stacks.StackFull):
        stacks.over_black(catalog, draft, "one-coat-black")
    assert ords(catalog, draft) == list(range(1, 9))


def test_copy_duplicates_the_rows_and_never_shares_the_stack(
    catalog, wheel, black, fingers, flakie
):
    source = save_slot(catalog, wheel, 1, [black, fingers])
    draft = stacks.open_draft(catalog, wheel, 2).stack_id
    stacks.append(catalog, draft, flakie)
    assert stacks.copy_from(catalog, draft, source) == 2
    assert titles(catalog, draft) == ["One-Coat Black", "Spirit Fingers"]
    assert coats(catalog, draft) == coats(catalog, source)
    source_ids = {layer["id"] for layer in stacks.layers(catalog, source)}
    assert not source_ids & {layer["id"] for layer in stacks.layers(catalog, draft)}
    stacks.remove(catalog, draft, stacks.layers(catalog, draft)[0]["id"])
    assert titles(catalog, source) == ["One-Coat Black", "Spirit Fingers"]
    stacks.save(catalog, draft)
    assert slot_row(catalog, wheel, 1)["stack_id"] == source
    assert slot_row(catalog, wheel, 2)["stack_id"] == draft


def test_copy_only_takes_a_saved_stack_held_by_a_slot(catalog, wheel, draft, fingers):
    other = stacks.open_draft(catalog, wheel, 3).stack_id
    stacks.append(catalog, other, fingers)
    for source in (other, 999_999):
        with pytest.raises(stacks.SourceNotFound):
            stacks.copy_from(catalog, draft, source)


def test_same_as_last_copies_the_most_recently_saved_stack(catalog, wheel, black, fingers, flakie):
    save_slot(catalog, wheel, 1, [black, fingers])
    save_slot(catalog, wheel, 2, [flakie])
    draft = stacks.open_draft(catalog, wheel, 3).stack_id
    assert stacks.same_as_last(catalog, draft) == 1
    assert titles(catalog, draft) == ["Flakie Holo Taco"]
    # Saving slot 1 again makes it the latest, even though slot 2 has the newer stack id.
    again = stacks.open_draft(catalog, wheel, 1).stack_id
    stacks.save(catalog, again)
    other = stacks.open_draft(catalog, wheel, 4).stack_id
    assert stacks.same_as_last(catalog, other) == 2
    assert titles(catalog, other) == ["One-Coat Black", "Spirit Fingers"]


def test_same_as_last_with_nothing_saved_leaves_the_draft_alone(catalog, draft, fingers):
    stacks.append(catalog, draft, fingers)
    assert stacks.same_as_last(catalog, draft) is None
    assert titles(catalog, draft) == ["Spirit Fingers"]


def test_copy_sources_lists_saved_stacks_newest_first_and_filters_by_shade_name(
    catalog, wheel, black, fingers, flakie
):
    other = wheels.create(catalog, "Glitter")
    first = save_slot(catalog, wheel, 1, [black, fingers])
    second = save_slot(catalog, other, 5, [flakie], name="Top only")
    stacks.open_draft(catalog, wheel, 9)  # a draft is never a source
    found = stacks.copy_sources(catalog)
    assert [s["stack_id"] for s in found] == [second, first]
    assert (found[0]["wheel_name"], found[0]["position"], found[0]["name"]) == (
        "Glitter",
        5,
        "Top only",
    )
    assert found[1]["summary"] == "One-Coat Black ×2 + Spirit Fingers ×2"
    assert [s["stack_id"] for s in stacks.copy_sources(catalog, "SPIRIT")] == [first]
    assert [s["stack_id"] for s in stacks.copy_sources(catalog, "flakie holo")] == [second]
    assert stacks.copy_sources(catalog, "nothing like it") == []
    assert len(stacks.copy_sources(catalog, limit=1)) == 1


def test_copy_sources_treats_like_wildcards_literally(catalog, wheel, fingers):
    save_slot(catalog, wheel, 1, [fingers])
    assert stacks.copy_sources(catalog, "%") == []
    assert stacks.copy_sources(catalog, "_pirit") == []


# save, cancel, clear


def test_save_stores_name_note_and_date_and_clears_the_draft(catalog, wheel, draft, black, fingers):
    stacks.append(catalog, draft, black)
    stacks.append(catalog, draft, fingers)
    ref = stacks.save(
        catalog, draft, name=" Night sky ", note="Dries slow", painted_on="2026-10-20"
    )
    assert (ref.wheel_id, ref.position) == (wheel, 12)
    row = slot_row(catalog, wheel, 12)
    assert (row["stack_id"], row["draft_stack_id"]) == (draft, None)
    assert (row["note"], row["painted_on"]) == ("Dries slow", "2026-10-20")
    stack = catalog.execute("select status, name from stack where id = ?", (draft,)).fetchone()
    assert tuple(stack) == ("saved", "Night sky")


def test_save_defaults_the_date_to_today_and_blank_text_to_null(catalog, draft, black):
    from datetime import date

    stacks.append(catalog, draft, black)
    ref = stacks.save(catalog, draft, name="  ", note="", today=date(2026, 10, 25))
    row = slot_row(catalog, ref.wheel_id, ref.position)
    assert (row["painted_on"], row["note"]) == ("2026-10-25", None)
    assert catalog.execute("select name from stack").fetchone()[0] is None


def test_save_rejects_a_bad_date_and_an_empty_stack(catalog, draft, black):
    with pytest.raises(stacks.EmptyStack):
        stacks.save(catalog, draft)
    stacks.append(catalog, draft, black)
    with pytest.raises(ValueError):
        stacks.save(catalog, draft, painted_on="yesterday")
    assert slot_row(catalog, 1, 12)["draft_stack_id"] == draft


def test_save_replaces_the_slots_previous_stack(catalog, wheel, black, fingers, flakie):
    old = save_slot(catalog, wheel, 12, [black, fingers])
    draft = stacks.open_draft(catalog, wheel, 12).stack_id
    stacks.remove(catalog, draft, stacks.layers(catalog, draft)[0]["id"])
    stacks.append(catalog, draft, flakie)
    stacks.save(catalog, draft)
    assert slot_row(catalog, wheel, 12)["stack_id"] == draft
    assert catalog.execute("select count(*) from stack where id = ?", (old,)).fetchone()[0] == 0
    assert stacks.layers(catalog, old) == []
    assert count(catalog, "stack") == 1
    assert count(catalog, "stack_layer") == 2


def test_a_failed_save_changes_nothing(catalog, wheel, black, draft, monkeypatch):
    old = save_slot(catalog, wheel, 3, [black])
    again = stacks.open_draft(catalog, wheel, 3).stack_id
    original = catalog.execute

    class Failing:
        """Fails the update of the stack row, the last write of save()."""

        def __getattr__(self, name):
            return getattr(catalog, name)

        def execute(self, sql, *args):
            if sql.startswith("update stack set status"):
                raise sqlite3.OperationalError("boom")
            return original(sql, *args)

    with pytest.raises(sqlite3.OperationalError):
        stacks.save(Failing(), again)
    row = slot_row(catalog, wheel, 3)
    assert (row["stack_id"], row["draft_stack_id"]) == (old, again)
    assert titles(catalog, old) == ["One-Coat Black"]


def test_cancel_deletes_the_draft_and_the_otherwise_empty_slot_row(catalog, wheel, draft, fingers):
    stacks.append(catalog, draft, fingers)
    ref = stacks.cancel(catalog, draft)
    assert (ref.wheel_id, ref.position) == (wheel, 12)
    assert slot_row(catalog, wheel, 12) is None
    assert (count(catalog, "stack"), count(catalog, "stack_layer")) == (0, 0)


def test_cancel_keeps_a_slot_that_holds_a_saved_stack(catalog, wheel, black, fingers):
    saved = save_slot(catalog, wheel, 12, [black])
    draft = stacks.open_draft(catalog, wheel, 12).stack_id
    stacks.append(catalog, draft, fingers)
    stacks.cancel(catalog, draft)
    row = slot_row(catalog, wheel, 12)
    assert (row["stack_id"], row["draft_stack_id"]) == (saved, None)
    assert titles(catalog, saved) == ["One-Coat Black"]
    assert count(catalog, "stack") == 1


def test_cancel_keeps_a_slot_row_that_holds_a_note(catalog, wheel, draft):
    catalog.execute("update wheel_slot set note = 'for later' where wheel_id = ?", (wheel,))
    stacks.cancel(catalog, draft)
    row = slot_row(catalog, wheel, 12)
    assert (row["note"], row["draft_stack_id"]) == ("for later", None)


def test_clear_removes_the_stack_the_draft_and_the_row(catalog, wheel, black, fingers):
    save_slot(catalog, wheel, 12, [black])
    draft = stacks.open_draft(catalog, wheel, 12).stack_id
    stacks.append(catalog, draft, fingers)
    save_slot(catalog, wheel, 13, [black])
    stacks.clear_slot(catalog, wheel, 12)
    assert slot_row(catalog, wheel, 12) is None
    assert count(catalog, "stack") == 1  # slot 13's
    assert count(catalog, "stack_layer") == 1
    stacks.clear_slot(catalog, wheel, 12)  # nothing there any more: no error
    stacks.clear_slot(catalog, wheel, 7)


# the 409 guard


def test_a_saved_stack_is_not_a_draft(catalog, wheel, black, fingers):
    saved = save_slot(catalog, wheel, 1, [black])
    layer = stacks.layers(catalog, saved)[0]["id"]
    calls = [
        lambda: stacks.sheet(catalog, saved),
        lambda: stacks.slot_of(catalog, saved),
        lambda: stacks.append(catalog, saved, fingers),
        lambda: stacks.move(catalog, saved, layer, "down"),
        lambda: stacks.change_coats(catalog, saved, layer, 1),
        lambda: stacks.remove(catalog, saved, layer),
        lambda: stacks.over_black(catalog, saved, "one-coat-black"),
        lambda: stacks.copy_from(catalog, saved, saved),
        lambda: stacks.same_as_last(catalog, saved),
        lambda: stacks.save(catalog, saved),
        lambda: stacks.cancel(catalog, saved),
    ]
    for call in calls:
        with pytest.raises(stacks.NotADraft):
            call()
    assert titles(catalog, saved) == ["One-Coat Black"]
    assert coats(catalog, saved) == [2]


def test_an_unknown_or_unattached_stack_is_not_a_draft(catalog, black):
    orphan = catalog.execute("insert into stack default values").lastrowid
    for stack in (orphan, 999_999):
        with pytest.raises(stacks.NotADraft):
            stacks.append(catalog, stack, black)


def test_a_draft_stops_being_one_once_it_is_cancelled_or_saved(catalog, draft, black):
    stacks.append(catalog, draft, black)
    stacks.save(catalog, draft)
    with pytest.raises(stacks.NotADraft):
        stacks.append(catalog, draft, black)
    again = stacks.open_draft(catalog, 1, 5).stack_id
    stacks.cancel(catalog, again)
    with pytest.raises(stacks.NotADraft):
        stacks.cancel(catalog, again)


def test_a_slot_has_one_saved_stack_and_one_draft_at_most(catalog, wheel, draft):
    with pytest.raises(sqlite3.IntegrityError):
        catalog.execute(
            "insert into wheel_slot (wheel_id, position, draft_stack_id) values (?, 13, ?)",
            (wheel, draft),
        )


def test_operations_join_a_transaction_the_caller_holds(catalog, wheel, black):
    from polished.db import transaction

    with pytest.raises(RuntimeError), transaction(catalog):
        stack = stacks.open_draft(catalog, wheel, 1).stack_id
        stacks.append(catalog, stack, black)
        raise RuntimeError
    assert count(catalog, "wheel_slot") == 0
    assert count(catalog, "stack") == 0
