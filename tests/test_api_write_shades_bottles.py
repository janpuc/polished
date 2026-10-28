"""POST /shades, PUT /shades/{id}/tip-colour and the bottle writes (docs/NATIVE.md 3)."""

import pytest
from test_api_support import TODAY, assert_error

pytest_plugins = ["test_api_support"]

BOTTLE_KEYS = {
    "id", "shade_id", "state", "bought_on", "price_paid_cents", "opened_on",
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
            "bought_on": "2026-10-20",
            "price_paid_cents": 1550,
            "opened_on": TODAY,
            "notes": "  from the pop-up  ",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"bottle"}
    bottle = body["bottle"]
    assert set(bottle) == BOTTLE_KEYS
    assert bottle | {"id": 0, "created_at": "", "updated_at": ""} == {
        "id": 0, "shade_id": shade_id, "state": "half",
        "bought_on": "2026-10-20", "price_paid_cents": 1550, "opened_on": TODAY,
        "notes": "from the pop-up", "archived": False, "created_at": "", "updated_at": "",
    }  # fmt: skip
    assert api.get(f"/api/v1/shades/{shade_id}").json()["bottles"][0] == bottle


def test_add_a_bottle_with_nothing_but_the_defaults(api):
    shade_id = api.shade("Mermaid Jelly")
    response = api.client.post(f"/api/v1/shades/{shade_id}/bottles", json={})
    assert response.status_code == 201
    bottle = response.json()["bottle"]
    assert (bottle["state"], bottle["bought_on"]) == ("full", None)
    assert bottle["price_paid_cents"] is None and bottle["archived"] is False
    owned = api.get(f"/api/v1/shades/{shade_id}").json()["shade"]["owned_count"]
    assert owned == 1


def test_a_stray_printed_code_from_an_older_app_is_accepted_and_ignored(api):
    """App builds from before P codes were retired still send the field: no 422, nothing stored,
    nothing learned, and it is not in the answer."""
    shade_id = api.shade("Thirst Trap")
    identifiers = api.count("shade_identifier")
    for code in ("P259", "259", "batch 7", None, 12):
        response = api.client.post(
            f"/api/v1/shades/{shade_id}/bottles", json={"state": "half", "printed_code": code}
        )
        assert response.status_code == 201, code
        body = response.json()
        assert set(body) == {"bottle"} and set(body["bottle"]) == BOTTLE_KEYS
        assert body["bottle"]["state"] == "half"
    assert api.count("shade_identifier") == identifiers
    assert "printed_code" not in api.rows("select * from bottle limit 1")[0]


def test_add_a_bottle_to_an_unknown_shade_is_a_404(api):
    assert_error(api.client.post("/api/v1/shades/999999/bottles", json={}), 404, "not_found")


# --- editing a bottle ----------------------------------------------------------------------


def spirit_bottle(api) -> dict:
    """The half-full Spirit Fingers bottle of the household (bought 2026-07-21, $15.50)."""
    return api.get(f"/api/v1/shades/{api.shade('Spirit Fingers')}").json()["bottles"][-1]


def test_patch_changes_only_what_is_sent(api):
    before = spirit_bottle(api)
    assert before["state"] == "half"
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
            "price_paid_cents": None,
            "opened_on": None,
            "notes": "dried out",
            "bought_on": "2026-07-22",
        },
    ).json()
    assert changed["price_paid_cents"] is None
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


def test_patch_accepts_and_ignores_a_stray_printed_code(api):
    bottle = spirit_bottle(api)
    url = f"/api/v1/bottles/{bottle['id']}"
    response = api.client.patch(url, json={"printed_code": "777", "state": "low"})
    assert response.status_code == 200
    assert response.json()["state"] == "low" and "printed_code" not in response.json()
    assert api.client.patch(url, json={"printed_code": "777"}).status_code == 200
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
