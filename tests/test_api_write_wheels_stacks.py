"""The wheel writes (create, rename, archive, delete, the tag, the slots) and the builder's."""

import re

import pytest
from starlette.testclient import TestClient
from test_api_support import DEV_TOKEN, LOOPBACK, TODAY, assert_error

pytest_plugins = ["test_api_support"]

WHEEL_KEYS = {
    "id",
    "slug",
    "name",
    "slot_count",
    "archived",
    "filled",
    "drafts",
    "tag_url",
    "created_at",
}
SLUG = re.compile(r"[0-9a-hjkmnp-tv-z]{6}")


def holos(api) -> dict:
    return api.get(f"/api/v1/wheels/{api.ids['holos']}").json()


def sheet(api, stack_id: int) -> dict:
    return api.get(f"/api/v1/stacks/{stack_id}").json()


def titles(sheet_body: dict) -> list[str]:
    return [layer["title"] for layer in sheet_body["layers"]]


# --- create, rename, archive ---------------------------------------------------------------


def test_create_a_wheel(api):
    response = api.client.post("/api/v1/wheels", json={"name": "  Jellies ", "slot_count": 12})
    assert response.status_code == 201
    wheel = response.json()
    assert set(wheel) == WHEEL_KEYS
    assert (wheel["name"], wheel["slot_count"], wheel["archived"]) == ("Jellies", 12, False)
    assert (wheel["filled"], wheel["drafts"]) == (0, 0)
    assert SLUG.fullmatch(wheel["slug"])
    assert wheel["tag_url"] == f"http://localhost:8080/w/{wheel['slug']}"
    assert api.get(f"/api/v1/w/{wheel['slug']}").json()["id"] == wheel["id"]
    assert "Jellies" in [w["name"] for w in api.get("/api/v1/wheels").json()["items"]]


def test_create_defaults_to_20_slots_and_cuts_the_name_to_60(api):
    wheel = api.client.post("/api/v1/wheels", json={"name": "n" * 90}).json()
    assert (wheel["slot_count"], wheel["name"]) == (20, "n" * 60)


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({"name": "  "}, "name", "A wheel needs a name."),
        ({"name": "A", "slot_count": 0}, "slot_count", "A wheel has 1 to 40 slots."),
        ({"name": "A", "slot_count": 41}, "slot_count", "A wheel has 1 to 40 slots."),
    ],
)
def test_create_refuses_a_bad_name_or_size(api, body, field, message):
    wheels = api.count("wheel")
    error = assert_error(api.client.post("/api/v1/wheels", json=body), 422, "validation", field)
    assert error["message"] == message
    assert api.count("wheel") == wheels


def test_rename_keeps_the_slug_and_archive_hides_the_wheel(api):
    wheel = holos(api)
    url = f"/api/v1/wheels/{wheel['id']}"
    renamed = api.client.patch(url, json={"name": "  Holo wheel "}).json()
    assert set(renamed) == WHEEL_KEYS
    assert (renamed["name"], renamed["slug"]) == ("Holo wheel", wheel["slug"])
    assert (renamed["filled"], renamed["drafts"]) == (2, 1)
    archived = api.client.patch(url, json={"archived": True}).json()
    assert archived["archived"] is True
    assert "Holo wheel" not in [w["name"] for w in api.get("/api/v1/wheels").json()["items"]]
    assert "Holo wheel" in [
        w["name"] for w in api.get("/api/v1/wheels?archived=true").json()["items"]
    ]
    assert api.get(f"/api/v1/w/{wheel['slug']}").status_code == 200  # the tag still works
    assert api.client.patch(url, json={"archived": False}).json()["archived"] is False
    both = api.client.patch(url, json={"name": "Again", "archived": True}).json()
    assert (both["name"], both["archived"]) == ("Again", True)


@pytest.mark.parametrize("body", [{}, {"name": None}, {"archived": None}])
def test_patch_needs_a_name_or_archived(api, body):
    assert_error(
        api.client.patch(f"/api/v1/wheels/{api.ids['holos']}", json=body), 422, "validation"
    )


def test_patch_with_an_empty_name_changes_nothing(api):
    error = assert_error(
        api.client.patch(
            f"/api/v1/wheels/{api.ids['holos']}", json={"name": " ", "archived": True}
        ),
        422,
        "validation",
        "name",
    )
    assert error["message"] == "A wheel needs a name."
    assert holos(api)["archived"] is False


def test_patch_and_delete_of_an_unknown_wheel_are_404s(api):
    assert_error(api.client.patch("/api/v1/wheels/999", json={"name": "x"}), 404, "not_found")
    assert_error(api.client.delete("/api/v1/wheels/999"), 404, "not_found")


# --- delete --------------------------------------------------------------------------------


def test_delete_a_wheel_counts_the_swatches_that_went(api):
    wheel = holos(api)
    stacks, layers = api.count("stack"), api.count("stack_layer")
    bottles, shades = api.count("bottle"), api.count("shade")
    response = api.client.delete(f"/api/v1/wheels/{wheel['id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted_swatches": 2}
    assert api.get(f"/api/v1/w/{wheel['slug']}").status_code == 404
    assert api.get(f"/api/v1/wheels/{wheel['id']}").status_code == 404
    assert api.count("stack") == stacks - 3  # two saved swatches and the draft
    assert api.count("stack_layer") == layers - 5
    assert (api.count("bottle"), api.count("shade")) == (bottles, shades)
    assert [w["name"] for w in api.get("/api/v1/wheels").json()["items"]] == ["Toppers"]
    assert_error(api.client.delete(f"/api/v1/wheels/{wheel['id']}"), 404, "not_found")


def test_delete_a_wheel_without_swatches(api):
    assert api.client.delete(f"/api/v1/wheels/{api.ids['holos'] + 1}").json() == {
        "deleted_swatches": 0
    }


# --- the tag -------------------------------------------------------------------------------


def test_regenerate_gives_a_new_address_and_the_old_one_404s(api):
    wheel = holos(api)
    response = api.client.post(f"/api/v1/wheels/{wheel['id']}/slug/regenerate")
    assert response.status_code == 200
    new = response.json()
    assert set(new) == WHEEL_KEYS and SLUG.fullmatch(new["slug"]) and new["slug"] != wheel["slug"]
    assert new["tag_url"].endswith(new["slug"])
    assert api.get(f"/api/v1/w/{wheel['slug']}").status_code == 404
    assert api.get(f"/api/v1/w/{new['slug']}").json()["id"] == wheel["id"]
    assert_error(api.client.post("/api/v1/wheels/999/slug/regenerate"), 404, "not_found")


def test_take_swaps_the_two_tags(api):
    first = holos(api)
    second = api.get(f"/api/v1/wheels/{first['id'] + 1}").json()
    response = api.client.post(
        f"/api/v1/wheels/{first['id']}/slug/take", json={"from_wheel_id": second["id"]}
    )
    assert response.status_code == 200
    assert response.json()["slug"] == second["slug"]
    assert api.get(f"/api/v1/wheels/{second['id']}").json()["slug"] == first["slug"]
    assert api.get(f"/api/v1/w/{first['slug']}").json()["id"] == second["id"]


def test_take_its_own_tag_is_same_wheel(api):
    wheel = holos(api)
    error = assert_error(
        api.client.post(
            f"/api/v1/wheels/{wheel['id']}/slug/take", json={"from_wheel_id": wheel["id"]}
        ),
        422,
        "same_wheel",
    )
    assert error["message"] == "A wheel cannot take its own tag."
    assert holos(api)["slug"] == wheel["slug"]


def test_take_from_or_for_an_unknown_wheel_is_a_404(api):
    wheel = holos(api)
    assert_error(
        api.client.post(f"/api/v1/wheels/{wheel['id']}/slug/take", json={"from_wheel_id": 999}),
        404,
        "not_found",
    )
    assert_error(
        api.client.post("/api/v1/wheels/999/slug/take", json={"from_wheel_id": wheel["id"]}),
        404,
        "not_found",
    )
    assert holos(api)["slug"] == wheel["slug"]


# --- slots ---------------------------------------------------------------------------------


def draft_url(api, position: int, wheel_id: int | None = None) -> str:
    return f"/api/v1/wheels/{wheel_id or api.ids['holos']}/slots/{position}/draft"


def test_open_a_draft_on_an_empty_slot_then_resume_it(api):
    first = api.client.post(draft_url(api, 3))
    assert first.status_code == 200
    body = first.json()
    assert body["resumed"] is False and body["layers"] == [] and body["full"] is False
    assert (body["position"], body["wheel"]["id"], body["wheel"]["name"]) == (
        3,
        api.ids["holos"],
        "Holos",
    )
    assert {k: v for k, v in body.items() if k != "resumed"} == sheet(api, body["stack_id"])
    again = api.client.post(draft_url(api, 3)).json()
    assert again["resumed"] is True and again["stack_id"] == body["stack_id"]
    tile = holos(api)["tiles"][2]
    assert (tile["has_draft"], tile["draft_stack_id"], tile["filled"]) == (
        True,
        body["stack_id"],
        False,
    )


def test_a_draft_of_a_saved_slot_starts_from_its_layers(api):
    body = api.client.post(draft_url(api, 12)).json()
    assert body["resumed"] is False
    assert titles(body) == ["One-Coat Black", "Flakie Holo Taco"]
    assert body["stack_id"] != holos(api)["tiles"][11]["stack_id"]
    assert holos(api)["tiles"][11]["filled"] is True  # the saved swatch stays until Save


def test_the_existing_draft_is_resumed_with_its_layers(api):
    body = api.client.post(draft_url(api, 14)).json()
    assert body["resumed"] is True and body["stack_id"] == api.ids["draft_stack"]
    assert titles(body) == ["One-Coat Black", "Flakie Holo Taco"]


@pytest.mark.parametrize("position", [0, 21, -1])
def test_a_draft_outside_the_wheel_is_a_404(api, position):
    assert_error(api.client.post(draft_url(api, position)), 404, "not_found")


def test_a_draft_on_an_unknown_wheel_is_a_404(api):
    assert_error(api.client.post(draft_url(api, 1, 999)), 404, "not_found")


def test_clear_a_slot_takes_the_swatch_and_the_draft(api):
    wheel_id = api.ids["holos"]
    stacks = api.count("stack")
    for position in (12, 14):
        response = api.client.delete(f"/api/v1/wheels/{wheel_id}/slots/{position}")
        assert response.status_code == 204 and response.content == b""
    tiles = holos(api)["tiles"]
    assert tiles[11]["filled"] is False and tiles[13]["has_draft"] is False
    assert api.count("stack") == stacks - 2  # the saved swatch of 12 and the draft of 14
    assert sheet_gone(api, api.ids["draft_stack"])
    assert api.client.delete(f"/api/v1/wheels/{wheel_id}/slots/12").status_code == 204  # empty now
    assert api.client.delete(f"/api/v1/wheels/{wheel_id}/slots/5").status_code == 204  # never used


def sheet_gone(api, stack_id: int) -> bool:
    return api.get(f"/api/v1/stacks/{stack_id}").status_code == 409


@pytest.mark.parametrize(("wheel", "position"), [(1, 0), (1, 21), (999, 1)])
def test_clear_outside_the_wheel_is_a_404(api, wheel, position):
    assert_error(api.client.delete(f"/api/v1/wheels/{wheel}/slots/{position}"), 404, "not_found")


# --- layers --------------------------------------------------------------------------------


def new_draft(api, position: int = 5) -> int:
    return api.client.post(draft_url(api, position)).json()["stack_id"]


def add_layer(api, stack_id: int, title: str):
    return api.client.post(f"/api/v1/stacks/{stack_id}/layers", json={"shade_id": api.shade(title)})


def test_add_layers_with_the_default_coats(api):
    stack_id = new_draft(api)
    response = add_layer(api, stack_id, "One-Coat Black")
    assert response.status_code == 200
    first = response.json()
    assert set(first) == set(sheet(api, stack_id))
    assert [(layer["title"], layer["coats"], layer["label"]) for layer in first["layers"]] == [
        ("One-Coat Black", 1, "")
    ]
    body = add_layer(api, stack_id, "Flakie Holo Taco").json()  # every shade starts at one coat
    assert [(layer["coats"], layer["label"]) for layer in body["layers"]] == [
        (1, "Base"),
        (1, "Top"),
    ]
    assert body["summary"] == "One-Coat Black + Flakie Holo Taco"
    assert [t["id"] for t in body["tip"]] == [layer["shade_id"] for layer in body["layers"]]
    assert body == sheet(api, stack_id)


def test_the_same_shade_can_be_added_twice(api):
    stack_id = new_draft(api)
    add_layer(api, stack_id, "One-Coat Black")
    assert len(add_layer(api, stack_id, "One-Coat Black").json()["layers"]) == 2


def test_a_stack_holds_eight_layers(api):
    stack_id = new_draft(api)
    for _ in range(8):
        body = add_layer(api, stack_id, "Flakie Holo Taco").json()
    assert body["full"] is True and len(body["layers"]) == 8
    error = assert_error(add_layer(api, stack_id, "Flakie Holo Taco"), 422, "stack_full")
    assert error["message"] == "A swatch holds up to 8 layers."
    assert len(sheet(api, stack_id)["layers"]) == 8


def test_add_a_layer_with_an_unknown_shade_is_a_404(api):
    stack_id = new_draft(api)
    assert_error(
        api.client.post(f"/api/v1/stacks/{stack_id}/layers", json={"shade_id": 999999}),
        404,
        "not_found",
    )


def layer_ids(api, stack_id: int) -> list[int]:
    return [layer["id"] for layer in sheet(api, stack_id)["layers"]]


def test_coats_go_up_and_down_between_1_and_5(api):
    stack_id = api.ids["draft_stack"]
    black = layer_ids(api, stack_id)[0]  # two coats
    url = f"/api/v1/stacks/{stack_id}/layers/{black}"
    coats = lambda: api.client.get(f"/api/v1/stacks/{stack_id}").json()["layers"][0]["coats"]  # noqa: E731
    assert api.client.patch(url, json={"coats_delta": 1}).json()["layers"][0]["coats"] == 3
    for _ in range(4):
        api.client.patch(url, json={"coats_delta": 1})
    assert coats() == 5
    for _ in range(6):
        api.client.patch(url, json={"coats_delta": -1})
    assert coats() == 1


def test_move_swaps_neighbours_and_stops_at_the_ends(api):
    stack_id = api.ids["draft_stack"]
    base, top = layer_ids(api, stack_id)
    url = lambda layer: f"/api/v1/stacks/{stack_id}/layers/{layer}"  # noqa: E731
    assert titles(api.client.patch(url(base), json={"move": "up"}).json()) == [
        "One-Coat Black",
        "Flakie Holo Taco",
    ]
    moved = api.client.patch(url(base), json={"move": "down"}).json()
    assert titles(moved) == ["Flakie Holo Taco", "One-Coat Black"]
    assert [layer["ord"] for layer in moved["layers"]] == [1, 2]
    assert [layer["label"] for layer in moved["layers"]] == ["Base", "Top"]
    assert titles(api.client.patch(url(base), json={"move": "down"}).json())[1] == "One-Coat Black"
    assert titles(api.client.patch(url(top), json={"move": "up"}).json())[0] == "Flakie Holo Taco"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"coats_delta": 1, "move": "up"},
        {"coats_delta": 2},
        {"coats_delta": 0},
        {"move": "left"},
    ],
)
def test_patch_a_layer_needs_exactly_one_valid_change(api, body):
    stack_id = api.ids["draft_stack"]
    before = sheet(api, stack_id)
    assert_error(
        api.client.patch(
            f"/api/v1/stacks/{stack_id}/layers/{before['layers'][0]['id']}", json=body
        ),
        422,
        "validation",
    )
    assert sheet(api, stack_id) == before


def test_remove_a_layer_renumbers_the_rest(api):
    stack_id = api.ids["draft_stack"]
    base, top = layer_ids(api, stack_id)
    body = api.client.delete(f"/api/v1/stacks/{stack_id}/layers/{base}").json()
    assert titles(body) == ["Flakie Holo Taco"]
    assert (body["layers"][0]["ord"], body["layers"][0]["label"]) == (1, "")
    assert body["layers"][0]["id"] == top


def test_a_layer_of_another_stack_is_a_404(api):
    stack_id = api.ids["draft_stack"]
    other = new_draft(api)
    add_layer(api, other, "Thirst Trap")
    foreign = layer_ids(api, other)[0]
    base = layer_ids(api, stack_id)[0]
    for call in (
        lambda: api.client.patch(
            f"/api/v1/stacks/{stack_id}/layers/{foreign}", json={"coats_delta": 1}
        ),
        lambda: api.client.delete(f"/api/v1/stacks/{stack_id}/layers/{foreign}"),
        lambda: api.client.delete(f"/api/v1/stacks/{stack_id}/layers/999999"),
    ):
        assert_error(call(), 404, "not_found")
    assert layer_ids(api, stack_id)[0] == base


def test_every_edit_of_a_stack_that_is_not_a_draft_is_a_409(api):
    saved = api.ids["saved_stack"]
    layer = api.get(f"/api/v1/wheels/{api.ids['holos']}").json()["tiles"][11]["layers"][0]["id"]
    attempts = [
        api.client.post(
            f"/api/v1/stacks/{saved}/layers", json={"shade_id": api.shade("Thirst Trap")}
        ),
        api.client.patch(f"/api/v1/stacks/{saved}/layers/{layer}", json={"coats_delta": 1}),
        api.client.delete(f"/api/v1/stacks/{saved}/layers/{layer}"),
        api.client.post(f"/api/v1/stacks/{saved}/template", json={"kind": "over_black"}),
        api.client.post(f"/api/v1/stacks/{saved}/template", json={"kind": "last"}),
        api.client.post(f"/api/v1/stacks/{saved}/save", json={}),
        api.client.post(f"/api/v1/stacks/{saved}/cancel"),
        api.client.post("/api/v1/stacks/999999/cancel"),
    ]
    for response in attempts:
        assert_error(response, 409, "not_a_draft")
    tile = api.get(f"/api/v1/wheels/{api.ids['holos']}").json()["tiles"][11]
    assert [layer["title"] for layer in tile["layers"]] == ["One-Coat Black", "Flakie Holo Taco"]


# --- templates -----------------------------------------------------------------------------


def template(api, stack_id: int, **body):
    return api.client.post(f"/api/v1/stacks/{stack_id}/template", json=body)


def test_over_black_puts_the_black_base_first_with_one_coat(api):
    stack_id = new_draft(api)
    add_layer(api, stack_id, "Flakie Holo Taco")
    body = template(api, stack_id, kind="over_black").json()
    assert body["result"] == "added"
    assert [(layer["title"], layer["coats"]) for layer in body["layers"]] == [
        ("One-Coat Black", 1),
        ("Flakie Holo Taco", 1),
    ]
    again = template(api, stack_id, kind="over_black")
    assert again.status_code == 200
    assert again.json()["result"] == "already"
    assert titles(again.json()) == ["One-Coat Black", "Flakie Holo Taco"]
    assert {k: v for k, v in again.json().items() if k != "result"} == sheet(api, stack_id)


def test_over_black_is_unavailable_without_the_catalog_shade(api):
    conn = api.conn()
    conn.execute("update shade set handle = 'x' where handle = 'one-coat-black'")
    conn.close()
    stack_id = new_draft(api)
    body = template(api, stack_id, kind="over_black").json()
    assert body["result"] == "unavailable" and body["layers"] == []


def test_over_black_on_a_full_stack_is_stack_full(api):
    stack_id = new_draft(api)
    for _ in range(8):
        add_layer(api, stack_id, "Flakie Holo Taco")
    assert_error(template(api, stack_id, kind="over_black"), 422, "stack_full")
    assert len(sheet(api, stack_id)["layers"]) == 8


def test_copy_replaces_the_layers_with_a_saved_stacks(api):
    stack_id = new_draft(api)
    add_layer(api, stack_id, "Thirst Trap")
    body = template(api, stack_id, kind="copy", source_stack_id=api.ids["saved_stack"]).json()
    assert body["result"] == "copied"
    assert titles(body) == ["One-Coat Black", "Flakie Holo Taco"]
    assert body["stack_id"] == stack_id
    saved_layers = api.get("/api/v1/stacks/copy-sources").json()["items"]
    assert body["layers"][0]["id"] not in [
        layer["id"] for s in saved_layers for layer in s["layers"]
    ]


def test_copy_needs_a_saved_stack(api):
    stack_id = new_draft(api)
    assert_error(template(api, stack_id, kind="copy"), 422, "validation", "source_stack_id")
    assert_error(template(api, stack_id, kind="copy", source_stack_id=999999), 404, "not_found")
    assert_error(
        template(api, stack_id, kind="copy", source_stack_id=api.ids["draft_stack"]),
        404,
        "not_found",
    )


def test_last_copies_the_stack_saved_most_recently(api):
    stack_id = new_draft(api)
    body = template(api, stack_id, kind="last").json()
    assert body["result"] == "copied"
    assert titles(body) == ["Spirit Fingers"]  # slot 13 was saved after slot 12


def test_last_with_nothing_saved_leaves_the_draft_alone(api):
    for position in (12, 13):
        api.client.delete(f"/api/v1/wheels/{api.ids['holos']}/slots/{position}")
    stack_id = api.ids["draft_stack"]
    before = sheet(api, stack_id)
    body = template(api, stack_id, kind="last").json()
    assert body["result"] == "nothing_saved"
    assert {k: v for k, v in body.items() if k != "result"} == before


def test_an_unknown_template_is_a_422(api):
    assert_error(template(api, api.ids["draft_stack"], kind="shuffle"), 422, "validation", "kind")


# --- save and cancel -----------------------------------------------------------------------


def save(api, stack_id: int, **body):
    return api.client.post(f"/api/v1/stacks/{stack_id}/save", json=body)


def test_save_fills_the_slot_and_answers_its_tile(api):
    stack_id = new_draft(api, 5)
    add_layer(api, stack_id, "One-Coat Black")
    add_layer(api, stack_id, "Flakie Holo Taco")
    response = save(api, stack_id, name="  Night  ", note="two coats", painted_on="2026-10-25")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"wheel_id", "position", "tile"}
    assert (body["wheel_id"], body["position"]) == (api.ids["holos"], 5)
    tile = body["tile"]
    assert (tile["filled"], tile["has_draft"], tile["stack_id"], tile["draft_stack_id"]) == (
        True,
        False,
        stack_id,
        None,
    )
    assert (tile["painted_on"], tile["note"]) == ("2026-10-25", "two coats")
    assert tile["summary"] == "One-Coat Black + Flakie Holo Taco"
    assert holos(api)["tiles"][4] == tile
    assert holos(api)["filled"] == 3
    assert api.rows("select name, status from stack where id = ?", stack_id) == [
        {"name": "Night", "status": "saved"}
    ]
    assert sheet_gone(api, stack_id)  # no longer a draft


def test_save_defaults_to_today_and_replaces_the_earlier_swatch(api):
    old = holos(api)["tiles"][11]["stack_id"]
    draft = api.client.post(draft_url(api, 12)).json()["stack_id"]
    layer = layer_ids(api, draft)[0]
    api.client.delete(f"/api/v1/stacks/{draft}/layers/{layer}")
    tile = save(api, draft).json()["tile"]
    assert tile["painted_on"] == TODAY
    assert tile["stack_id"] == draft
    assert [layer["title"] for layer in tile["layers"]] == ["Flakie Holo Taco"]
    assert api.count("stack", "id = ?", old) == 0
    assert holos(api)["filled"] == 2


@pytest.mark.parametrize(
    ("painted_on", "message"),
    [
        ("2026-10-27", "Swatched on can't be in the future. Pick today or an earlier day."),
        ("yesterday", "Painted on needs a date like 2026-10-25."),
    ],
)
def test_save_refuses_a_bad_date_and_keeps_the_draft(api, painted_on, message):
    stack_id = api.ids["draft_stack"]
    error = assert_error(
        save(api, stack_id, painted_on=painted_on), 422, "validation", "painted_on"
    )
    assert error["message"] == message
    assert sheet(api, stack_id)["stack_id"] == stack_id  # still a draft


def test_save_an_empty_stack_is_empty_stack(api):
    stack_id = new_draft(api)
    error = assert_error(save(api, stack_id), 422, "empty_stack")
    assert error["message"] == "Add at least one layer before saving."
    assert sheet(api, stack_id)["layers"] == []


def test_save_is_all_or_nothing(api, monkeypatch):
    """The slot is written, then the stack row fails: the slot goes back too, the old swatch stays."""
    wheel_id = api.ids["holos"]
    draft = api.client.post(draft_url(api, 12)).json()["stack_id"]
    before = api.rows("select * from wheel_slot where wheel_id = ? order by position", wheel_id)
    stacks_before = api.rows("select id, status, name from stack order by id")
    monkeypatch.setattr("polished.stacks._NOW_MS", "no_such_function()")
    client = TestClient(
        api.client.app,
        base_url=api.settings.public_url,
        headers={"Authorization": f"Bearer {DEV_TOKEN}"},
        client=LOOPBACK,
        raise_server_exceptions=False,
    )
    response = client.post(f"/api/v1/stacks/{draft}/save", json={"name": "x"})
    assert_error(response, 500, "server_error")
    assert (
        api.rows("select * from wheel_slot where wheel_id = ? order by position", wheel_id)
        == before
    )
    assert api.rows("select id, status, name from stack order by id") == stacks_before


def test_cancel_throws_the_draft_away_and_keeps_the_saved_swatch(api):
    draft = api.client.post(draft_url(api, 12)).json()["stack_id"]
    add_layer(api, draft, "Thirst Trap")
    response = api.client.post(f"/api/v1/stacks/{draft}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert (body["wheel_id"], body["position"]) == (api.ids["holos"], 12)
    tile = body["tile"]
    assert (tile["filled"], tile["has_draft"], tile["draft_stack_id"]) == (True, False, None)
    assert [layer["title"] for layer in tile["layers"]] == ["One-Coat Black", "Flakie Holo Taco"]
    assert api.count("stack", "id = ?", draft) == 0
    assert_error(api.client.post(f"/api/v1/stacks/{draft}/cancel"), 409, "not_a_draft")


def test_cancel_on_an_empty_slot_leaves_an_empty_tile(api):
    draft = new_draft(api, 7)
    tile = api.client.post(f"/api/v1/stacks/{draft}/cancel").json()["tile"]
    assert (tile["filled"], tile["has_draft"], tile["layers"]) == (False, False, [])
    assert api.count("wheel_slot", "wheel_id = ? and position = 7", api.ids["holos"]) == 0


def test_a_builder_session_end_to_end(api):
    """A wheel, a draft, three layers, over black, save, then the shade says where it is used."""
    wheel = api.client.post("/api/v1/wheels", json={"name": "Session", "slot_count": 4}).json()
    stack_id = api.client.post(f"/api/v1/wheels/{wheel['id']}/slots/2/draft").json()["stack_id"]
    for title in ("Thirst Trap", "Flakie Holo Taco"):
        add_layer(api, stack_id, title)
    assert template(api, stack_id, kind="over_black").json()["result"] == "added"
    body = save(api, stack_id, name="Session swatch").json()
    assert titles(body["tile"]) == ["One-Coat Black", "Thirst Trap", "Flakie Holo Taco"]
    detail = api.get(f"/api/v1/shades/{api.shade('Thirst Trap')}").json()
    assert (detail["swatched_on"][0]["wheel_id"], detail["swatched_on"][0]["position"]) == (
        wheel["id"],
        2,
    )
    assert api.client.delete(f"/api/v1/wheels/{wheel['id']}").json() == {"deleted_swatches": 1}
