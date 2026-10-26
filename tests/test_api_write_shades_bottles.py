"""POST /shades, PUT /shades/{id}/tip-colour and the bottle writes (docs/NATIVE.md 3)."""

import pytest
from test_api_support import TODAY, assert_error

pytest_plugins = ["test_api_support"]

BOTTLE_KEYS = {
    "id", "shade_id", "state", "printed_code", "bought_on", "price_paid_cents", "opened_on",
    "notes", "archived", "created_at", "updated_at",
}  # fmt: skip


# --- manual shades -------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["polish", "topper", "base"])
def test_a_manual_shade_comes_back_as_the_detail(api, kind):
    response = api.client.post(
        "/api/v1/shades", json={"title": "  Gifted   Mystery ", "kind": kind}
    )
    assert response.status_code == 201
    body = response.json()
    shade = body["shade"]
    assert shade["title"] == "Gifted Mystery"
    assert shade["source"] == "manual"
    assert shade["status"] is None
    assert shade["price_cents"] is None
    assert (shade["kind"], shade["is_topper"]) == {
        "polish": ("polish", False),
        "topper": ("topcoat", True),
        "base": ("basecoat", False),
    }[kind]
    assert body["bottles"] == [] and body["wishlist"] is None
    assert api.get(f"/api/v1/shades/{shade['id']}").json() == body


def test_a_manual_shade_title_is_cut_to_100_characters(api):
    response = api.client.post("/api/v1/shades", json={"title": "x" * 300, "kind": "polish"})
    assert response.status_code == 201
    assert response.json()["shade"]["title"] == "x" * 100


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({"title": "  ", "kind": "polish"}, "title", "Give the shade a name."),
        ({"title": "A", "kind": "gel"}, "kind", "Pick polish, topper or base coat."),
    ],
)
def test_a_manual_shade_needs_a_name_and_a_kind(api, body, field, message):
    before = api.count("shade")
    error = assert_error(api.client.post("/api/v1/shades", json=body), 422, "validation", field)
    assert error["message"] == message
    assert api.count("shade") == before


def test_a_manual_shade_with_both_wrong_names_both(api):
    error = assert_error(
        api.client.post("/api/v1/shades", json={"title": "", "kind": "x"}),
        422,
        "validation",
        "title",
    )
    assert set(error["fields"]) == {"title", "kind"}


def test_a_missing_field_is_a_validation_error_naming_it(api):
    assert_error(
        api.client.post("/api/v1/shades", json={"kind": "polish"}), 422, "validation", "title"
    )
    assert_error(api.client.post("/api/v1/shades", content=b"not json"), 422, "validation")


# --- tip colour ----------------------------------------------------------------------------


def test_tip_colour_sets_and_resets_the_override(api):
    shade_id = api.shade("Spirit Fingers")
    url = f"/api/v1/shades/{shade_id}/tip-colour"
    response = api.client.put(url, json={"hex": "#AA00CC"})
    assert response.status_code == 200
    body = response.json()
    assert body["tip_source"] == "override"
    assert body["shade"]["tip"]["hex"] == "#aa00cc"
    assert body["shade"]["tip"]["hex2"] is None  # an override replaces the second colour too
    again = api.client.put(url, json={"hex": "#aa00cc"})
    assert again.json() == body  # idempotent
    reset = api.client.put(url, json={"hex": None})
    assert reset.status_code == 200
    assert reset.json()["tip_source"] in ("sampled", "none")
    assert reset.json()["shade"]["tip"]["hex"] != "#aa00cc"
    assert api.rows("select swatch_override_hex as h from shade where id = ?", shade_id) == [
        {"h": None}
    ]


@pytest.mark.parametrize("hex_value", ["red", "#abc", "#12345g", "123456", "", 5])
def test_tip_colour_refuses_what_is_not_a_hex_colour(api, hex_value):
    shade_id = api.shade("Spirit Fingers")
    error = assert_error(
        api.client.put(f"/api/v1/shades/{shade_id}/tip-colour", json={"hex": hex_value}),
        422,
        "validation",
        "hex",
    )
    assert error["message"] == "Pick a colour."


def test_tip_colour_of_an_unknown_shade_is_a_404(api):
    assert_error(
        api.client.put("/api/v1/shades/999999/tip-colour", json={"hex": "#aa00cc"}),
        404,
        "not_found",
    )
    assert_error(
        api.client.put("/api/v1/shades/999999/tip-colour", json={"hex": None}), 404, "not_found"
    )


# --- adding a bottle -----------------------------------------------------------------------


def test_add_a_bottle_with_everything(api):
    shade_id = api.shade("Thirst Trap")
    response = api.client.post(
        f"/api/v1/shades/{shade_id}/bottles",
        json={
            "state": "half",
            "printed_code": "p 321",
            "bought_on": "2026-10-20",
            "price_paid_cents": 1550,
            "opened_on": TODAY,
            "notes": "  from the pop-up  ",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"bottle", "learned"}
    bottle = body["bottle"]
    assert set(bottle) == BOTTLE_KEYS
    assert bottle | {"id": 0, "created_at": "", "updated_at": ""} == {
        "id": 0, "shade_id": shade_id, "state": "half", "printed_code": "P321",
        "bought_on": "2026-10-20", "price_paid_cents": 1550, "opened_on": TODAY,
        "notes": "from the pop-up", "archived": False, "created_at": "", "updated_at": "",
    }  # fmt: skip
    assert body["learned"] == {"code": "P321", "previous_shade": None}
    assert api.get(f"/api/v1/shades/{shade_id}").json()["bottles"][0] == bottle


def test_add_a_bottle_with_nothing_but_the_defaults(api):
    shade_id = api.shade("Mermaid Jelly")
    response = api.client.post(f"/api/v1/shades/{shade_id}/bottles", json={})
    assert response.status_code == 201
    bottle = response.json()["bottle"]
    assert (bottle["state"], bottle["printed_code"], bottle["bought_on"]) == ("full", None, None)
    assert bottle["price_paid_cents"] is None and bottle["archived"] is False
    assert response.json()["learned"] is None
    owned = api.get(f"/api/v1/shades/{shade_id}").json()["shade"]["owned_count"]
    assert owned == 1


def test_a_known_p_code_for_the_same_shade_learns_nothing_new(api):
    spirit = api.shade("Spirit Fingers")  # the household already taught P259 = Spirit Fingers
    body = api.client.post(f"/api/v1/shades/{spirit}/bottles", json={"printed_code": "259"}).json()
    assert body["bottle"]["printed_code"] == "P259"
    assert body["learned"] is None


def test_a_p_code_that_meant_another_shade_keeps_its_old_match(api):
    thirst = api.shade("Thirst Trap")
    body = api.client.post(f"/api/v1/shades/{thirst}/bottles", json={"printed_code": "P259"}).json()
    assert body["bottle"]["printed_code"] == "P259"  # the bottle is saved with its code
    assert body["learned"]["code"] == "P259"
    assert body["learned"]["previous_shade"]["title"] == "Spirit Fingers"
    mapping = api.rows("select shade_id from shade_identifier where value = 'P259'")
    assert mapping == [{"shade_id": api.shade("Spirit Fingers")}]


def test_a_code_that_is_not_a_p_number_is_kept_on_the_bottle_and_not_learned(api):
    shade_id = api.shade("Thirst Trap")
    ids = api.count("shade_identifier")
    body = api.client.post(
        f"/api/v1/shades/{shade_id}/bottles", json={"printed_code": "batch 7"}
    ).json()
    assert body["bottle"]["printed_code"] == "BATCH7"
    assert body["learned"] is None
    assert api.count("shade_identifier") == ids


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state", "nearly", "Pick full, half, low or empty."),
        ("bought_on", "last tuesday", "Use a date like 2026-10-25."),
        ("opened_on", "2026-13-40", "Use a date like 2026-10-25."),
        ("bought_on", "2026-10-27", "That date is in the future. Pick today or an earlier day."),
        ("opened_on", "2099-01-01", "That date is in the future. Pick today or an earlier day."),
        ("price_paid_cents", -5, "Use an amount like 15.50."),
        ("price_paid_cents", 1_000_000, "Use an amount like 15.50."),
        ("price_paid_cents", "15.50", "Use an amount like 15.50."),
        ("bought_on", 20261020, "Use a date like 2026-10-25."),
    ],
)
def test_add_a_bottle_validates_in_the_forms_words(api, field, value, message):
    shade_id = api.shade("Thirst Trap")
    before = api.count("bottle")
    error = assert_error(
        api.client.post(f"/api/v1/shades/{shade_id}/bottles", json={field: value}),
        422,
        "validation",
        field,
    )
    assert error["message"] == message
    assert api.count("bottle") == before


def test_today_in_the_household_timezone_is_not_the_future(api):
    # 16:30 UTC on the 26th: it is the 26th in Warsaw, and tomorrow is still the future.
    shade_id = api.shade("Thirst Trap")
    ok = api.client.post(f"/api/v1/shades/{shade_id}/bottles", json={"bought_on": TODAY})
    assert ok.status_code == 201
    late = api.client.post(f"/api/v1/shades/{shade_id}/bottles", json={"bought_on": "2026-10-27"})
    assert late.status_code == 422


def test_every_wrong_field_is_reported(api):
    shade_id = api.shade("Thirst Trap")
    error = assert_error(
        api.client.post(
            f"/api/v1/shades/{shade_id}/bottles",
            json={"state": "x", "bought_on": "nope", "price_paid_cents": -1},
        ),
        422,
        "validation",
    )
    assert set(error["fields"]) == {"state", "bought_on", "price_paid_cents"}


def test_add_a_bottle_to_an_unknown_shade_is_a_404(api):
    assert_error(api.client.post("/api/v1/shades/999999/bottles", json={}), 404, "not_found")


# --- editing a bottle ----------------------------------------------------------------------


def spirit_bottle(api) -> dict:
    """The half-full Spirit Fingers bottle of the household (P259, bought 2026-07-21, $15.50)."""
    return api.get(f"/api/v1/shades/{api.shade('Spirit Fingers')}").json()["bottles"][-1]


def test_patch_changes_only_what_is_sent(api):
    before = spirit_bottle(api)
    assert before["printed_code"] == "P259" and before["state"] == "half"
    response = api.client.patch(f"/api/v1/bottles/{before['id']}", json={"state": "low"})
    assert response.status_code == 200
    after = response.json()
    assert after["state"] == "low"
    assert {k: v for k, v in after.items() if k not in ("state", "updated_at")} == {
        k: v for k, v in before.items() if k not in ("state", "updated_at")
    }
    assert after["updated_at"] >= before["updated_at"]
    assert spirit_bottle(api) == after


def test_patch_any_subset_including_clearing_with_null(api):
    bottle = spirit_bottle(api)
    url = f"/api/v1/bottles/{bottle['id']}"
    changed = api.client.patch(
        url,
        json={
            "printed_code": None,
            "price_paid_cents": None,
            "opened_on": None,
            "notes": "dried out",
            "bought_on": "2026-07-22",
        },
    ).json()
    assert changed["printed_code"] is None and changed["price_paid_cents"] is None
    assert changed["opened_on"] is None and changed["notes"] == "dried out"
    assert changed["bought_on"] == "2026-07-22" and changed["state"] == "half"
    assert api.client.patch(url, json={"price_paid_cents": 0}).json()["price_paid_cents"] == 0


def test_patch_with_an_empty_body_changes_nothing(api):
    bottle = spirit_bottle(api)
    again = api.client.patch(f"/api/v1/bottles/{bottle['id']}", json={}).json()
    assert {k: v for k, v in again.items() if k != "updated_at"} == {
        k: v for k, v in bottle.items() if k != "updated_at"
    }


def test_patch_archives_and_restores(api):
    bottle = spirit_bottle(api)
    url = f"/api/v1/bottles/{bottle['id']}"
    owned = lambda: api.get(f"/api/v1/shades/{bottle['shade_id']}").json()["shade"]["owned_count"]  # noqa: E731
    assert owned() == 2
    assert api.client.patch(url, json={"archived": True}).json()["archived"] is True
    assert owned() == 1
    assert api.client.patch(url, json={"archived": True}).json()["archived"] is True  # idempotent
    assert api.client.patch(url, json={"archived": False}).json()["archived"] is False
    assert owned() == 2
    both = api.client.patch(url, json={"archived": True, "state": "empty"}).json()
    assert (both["archived"], both["state"]) == (True, "empty")


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({"state": "nearly"}, "state", "Pick full, half, low or empty."),
        ({"state": None}, "state", "Pick full, half, low or empty."),
        ({"bought_on": "yesterday"}, "bought_on", "Use a date like 2026-10-25."),
        (
            {"opened_on": "2026-10-27"},
            "opened_on",
            "That date is in the future. Pick today or an earlier day.",
        ),
        ({"price_paid_cents": -1}, "price_paid_cents", "Use an amount like 15.50."),
        ({"price_paid_cents": "1.5"}, "price_paid_cents", "Use an amount like 15.50."),
    ],
)
def test_patch_validates_and_changes_nothing(api, body, field, message):
    bottle = spirit_bottle(api)
    error = assert_error(
        api.client.patch(f"/api/v1/bottles/{bottle['id']}", json=body), 422, "validation", field
    )
    assert error["message"] == message
    assert spirit_bottle(api) == bottle


def test_patch_with_a_wrong_field_does_not_apply_the_right_one(api):
    bottle = spirit_bottle(api)
    response = api.client.patch(
        f"/api/v1/bottles/{bottle['id']}",
        json={"state": "empty", "bought_on": "nope", "archived": True},
    )
    assert response.status_code == 422
    assert spirit_bottle(api) == bottle


def test_an_old_future_date_does_not_block_an_unrelated_edit(api):
    bottle = spirit_bottle(api)
    conn = api.conn()
    conn.execute("update bottle set bought_on = '2027-01-01' where id = ?", (bottle["id"],))
    conn.close()
    response = api.client.patch(f"/api/v1/bottles/{bottle['id']}", json={"state": "low"})
    assert response.status_code == 200
    assert response.json()["bought_on"] == "2027-01-01"  # stored as it was
    assert response.json()["state"] == "low"


def test_patch_does_not_learn_a_p_code(api):
    thirst = api.shade("Thirst Trap")
    bottle = api.get(f"/api/v1/shades/{thirst}").json()["bottles"][0]
    api.client.patch(f"/api/v1/bottles/{bottle['id']}", json={"printed_code": "777"})
    assert api.count("shade_identifier", "value = 'P777'") == 0


def test_patch_an_unknown_bottle_is_a_404(api):
    assert_error(
        api.client.patch("/api/v1/bottles/999999", json={"state": "low"}), 404, "not_found"
    )


# --- deleting ------------------------------------------------------------------------------


def test_delete_removes_the_bottle(api):
    bottle = spirit_bottle(api)
    response = api.client.delete(f"/api/v1/bottles/{bottle['id']}")
    assert response.status_code == 204 and response.content == b""
    assert api.count("bottle", "id = ?", bottle["id"]) == 0
    assert_error(api.client.delete(f"/api/v1/bottles/{bottle['id']}"), 404, "not_found")
    assert api.get(f"/api/v1/shades/{bottle['shade_id']}").json()["shade"]["owned_count"] == 1
