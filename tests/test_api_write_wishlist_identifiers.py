"""The wishlist writes (add, change, remove, bought) and the learned-code writes."""

import pytest
from starlette.testclient import TestClient
from test_api_support import DEV_TOKEN, LOOPBACK, TODAY, assert_error

pytest_plugins = ["test_api_support"]

PRIORITY_MESSAGE = "Priority must be 1, 2 or 3."
PRICE_MESSAGE = "Use an amount like 15.50."
EAN = "5901234123457"  # a valid EAN-13 nobody has taught the app


def wish(api):
    return api.get("/api/v1/wishlist").json()


def item_of(api, title: str) -> dict:
    return next(i for i in wish(api)["items"] if i["shade"]["title"] == title)


# --- add -----------------------------------------------------------------------------------


def test_put_adds_a_shade_to_the_wishlist(api):
    shade_id = api.shade("Thirst Trap")
    response = api.client.put(f"/api/v1/shades/{shade_id}/wishlist", json={"priority": 1})
    assert response.status_code == 200
    item = response.json()
    assert set(item) == {"id", "shade", "priority", "note", "added_on", "buyable"}
    assert (item["priority"], item["note"]) == (1, None)
    assert item["shade"]["id"] == shade_id and item["shade"]["wishlisted"] is True
    assert item_of(api, "Thirst Trap") == item
    assert api.get(f"/api/v1/shades/{shade_id}").json()["wishlist"] == {
        "id": item["id"], "priority": 1, "note": None,
    }  # fmt: skip


def test_put_without_a_priority_is_the_middle_one(api):
    shade_id = api.shade("Thirst Trap")
    assert api.client.put(f"/api/v1/shades/{shade_id}/wishlist", json={}).json()["priority"] == 2


def test_put_on_a_wished_shade_keeps_the_existing_item(api):
    before = item_of(api, "Mermaid Jelly")
    assert (before["priority"], before["note"]) == (1, "For the blue week")
    response = api.client.put(
        f"/api/v1/shades/{before['shade']['id']}/wishlist", json={"priority": 3}
    )
    assert response.status_code == 200
    assert response.json() == before
    assert len(wish(api)["items"]) == 3


@pytest.mark.parametrize("priority", [0, 4, -1, "high", None])
def test_put_refuses_a_priority_outside_1_to_3(api, priority):
    shade_id = api.shade("Thirst Trap")
    error = assert_error(
        api.client.put(f"/api/v1/shades/{shade_id}/wishlist", json={"priority": priority}),
        422,
        "validation",
        "priority",
    )
    assert error["message"] == PRIORITY_MESSAGE
    assert len(wish(api)["items"]) == 3


def test_put_for_an_unknown_shade_is_a_404(api):
    assert_error(
        api.client.put("/api/v1/shades/999999/wishlist", json={"priority": 1}), 404, "not_found"
    )


# --- change and remove ---------------------------------------------------------------------


def test_patch_priority_keeps_the_note_and_answers_the_whole_wishlist(api):
    item = item_of(api, "Mermaid Jelly")
    response = api.client.patch(f"/api/v1/wishlist/{item['id']}", json={"priority": 3})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "summary", "cart"}
    assert body == wish(api)
    moved = next(i for i in body["items"] if i["id"] == item["id"])
    assert (moved["priority"], moved["note"]) == (3, "For the blue week")
    assert [i["priority"] for i in body["items"]] == [2, 3, 3]  # priority 1 first


def test_patch_note_keeps_the_priority_and_an_empty_note_clears_it(api):
    item = item_of(api, "Mermaid Jelly")
    url = f"/api/v1/wishlist/{item['id']}"
    body = api.client.patch(url, json={"note": "  for Nikola  "}).json()
    changed = next(i for i in body["items"] if i["id"] == item["id"])
    assert (changed["priority"], changed["note"]) == (1, "for Nikola")
    for cleared in ("", None):
        api.client.patch(url, json={"note": "again"})
        body = api.client.patch(url, json={"note": cleared}).json()
        assert next(i for i in body["items"] if i["id"] == item["id"])["note"] is None


def test_patch_cuts_a_long_note_to_200_characters(api):
    item = item_of(api, "Mermaid Jelly")
    body = api.client.patch(f"/api/v1/wishlist/{item['id']}", json={"note": "n" * 400}).json()
    assert next(i for i in body["items"] if i["id"] == item["id"])["note"] == "n" * 200


def test_patch_both_together_and_nothing(api):
    item = item_of(api, "Crème Brûlée")
    url = f"/api/v1/wishlist/{item['id']}"
    body = api.client.patch(url, json={"priority": 1, "note": "now"}).json()
    both = next(i for i in body["items"] if i["id"] == item["id"])
    assert (both["priority"], both["note"]) == (1, "now")
    assert api.client.patch(url, json={}).json() == body


@pytest.mark.parametrize("priority", [0, 4, "x"])
def test_patch_refuses_a_bad_priority(api, priority):
    item = item_of(api, "Mermaid Jelly")
    error = assert_error(
        api.client.patch(f"/api/v1/wishlist/{item['id']}", json={"priority": priority}),
        422,
        "validation",
        "priority",
    )
    assert error["message"] == PRIORITY_MESSAGE
    assert item_of(api, "Mermaid Jelly") == item


def test_patch_and_delete_of_an_unknown_item_are_404s(api):
    assert_error(api.client.patch("/api/v1/wishlist/999", json={"priority": 1}), 404, "not_found")
    assert_error(api.client.delete("/api/v1/wishlist/999"), 404, "not_found")


def test_delete_takes_the_item_off(api):
    item = item_of(api, "Mermaid Jelly")
    response = api.client.delete(f"/api/v1/wishlist/{item['id']}")
    assert response.status_code == 204 and response.content == b""
    assert [i["id"] for i in wish(api)["items"]] == [2, 3]
    assert api.get(f"/api/v1/shades/{item['shade']['id']}").json()["wishlist"] is None
    assert_error(api.client.delete(f"/api/v1/wishlist/{item['id']}"), 404, "not_found")


# --- I bought these ------------------------------------------------------------------------


def test_bought_makes_bottles_and_empties_the_items_in_one_go(api):
    mermaid, creme = item_of(api, "Mermaid Jelly"), item_of(api, "Crème Brûlée")
    bottles_before = api.count("bottle")
    response = api.client.post(
        "/api/v1/wishlist/bought",
        json={
            "items": [
                {"id": creme["id"], "price_cents": 1450},
                {"id": mermaid["id"], "price_cents": None},
            ],
            "bought_on": "2026-10-24",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"bottles", "wishlist"}
    assert [b["shade_id"] for b in body["bottles"]] == [
        creme["shade"]["id"],
        mermaid["shade"]["id"],
    ]
    for bottle, price in zip(body["bottles"], (1450, None), strict=True):
        assert (bottle["state"], bottle["bought_on"], bottle["archived"]) == (
            "full",
            "2026-10-24",
            False,
        )
        assert bottle["price_paid_cents"] == price
    assert [i["shade"]["title"] for i in body["wishlist"]["items"]] == ["Silver Flake Taco"]
    assert body["wishlist"] == wish(api)
    assert api.count("bottle") == bottles_before + 2
    history = api.get("/api/v1/bottles/history").json()
    assert history["years"][0]["months"][0]["rows"][0]["bottle"]["bought_on"] == "2026-10-24"


def test_bought_defaults_to_today_in_the_household_timezone(api):
    item = item_of(api, "Mermaid Jelly")
    body = api.client.post("/api/v1/wishlist/bought", json={"items": [{"id": item["id"]}]}).json()
    assert body["bottles"][0]["bought_on"] == TODAY
    assert body["bottles"][0]["price_paid_cents"] is None


def state(api):
    return (
        api.count("bottle"),
        api.count("wishlist_item"),
        api.rows("select id, shade_id, priority, note from wishlist_item order by id"),
    )


@pytest.mark.parametrize(
    ("body", "status", "code", "field"),
    [
        ({"items": []}, 422, "validation", "items"),
        ({"items": [{"id": 1}, {"id": 1}]}, 422, "validation", "items"),
        (
            {"items": [{"id": 1}, {"id": 2, "price_cents": -3}]},
            422,
            "validation",
            "items.1.price_cents",
        ),
        (
            {"items": [{"id": 1, "price_cents": 1_000_000}]},
            422,
            "validation",
            "items.0.price_cents",
        ),
        ({"items": [{"id": 1, "price_cents": "15.50"}]}, 422, "validation", "items.0.price_cents"),
        ({"items": [{"id": 1}], "bought_on": "2026-10-27"}, 422, "validation", "bought_on"),
        ({"items": [{"id": 1}], "bought_on": "soon"}, 422, "validation", "bought_on"),
        ({"items": [{"id": 1}, {"id": 999}]}, 404, "not_found", None),
        ({"items": [{"id": 999}]}, 404, "not_found", None),
    ],
)
def test_bought_changes_nothing_when_anything_is_wrong(api, body, status, code, field):
    before = state(api)
    assert_error(api.client.post("/api/v1/wishlist/bought", json=body), status, code, field)
    assert state(api) == before


def test_bought_messages_are_the_forms(api):
    error = assert_error(
        api.client.post("/api/v1/wishlist/bought", json={"items": [{"id": 1, "price_cents": -1}]}),
        422,
        "validation",
    )
    assert error["message"] == PRICE_MESSAGE
    assert (
        api.client.post("/api/v1/wishlist/bought", json={"items": []}).json()["error"]["message"]
        == "Tick the shades you bought."
    )
    future = api.client.post(
        "/api/v1/wishlist/bought", json={"items": [{"id": 1}], "bought_on": "2026-12-01"}
    )
    assert (
        future.json()["error"]["message"]
        == "That date is in the future. Pick today or an earlier day."
    )


def test_bought_is_all_or_nothing_when_a_write_fails_halfway(api, monkeypatch):
    """The second bottle cannot be written: the first bottle and both removals roll back."""
    from polished import bottles

    real_add = bottles.add
    calls = []

    def failing_add(conn, shade_id, values):
        calls.append(shade_id)
        if len(calls) == 2:
            raise RuntimeError("disk full")
        return real_add(conn, shade_id, values)

    monkeypatch.setattr(bottles, "add", failing_add)
    before = state(api)
    client = TestClient(
        api.client.app,
        base_url=api.settings.public_url,
        headers={"Authorization": f"Bearer {DEV_TOKEN}"},
        client=LOOPBACK,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/api/v1/wishlist/bought", json={"items": [{"id": 1}, {"id": 2}], "bought_on": TODAY}
    )
    assert_error(response, 500, "server_error")
    assert len(calls) == 2
    assert state(api) == before


def test_bought_twice_is_a_404_the_second_time(api):
    body = {"items": [{"id": 1}], "bought_on": TODAY}
    assert api.client.post("/api/v1/wishlist/bought", json=body).status_code == 200
    assert_error(api.client.post("/api/v1/wishlist/bought", json=body), 404, "not_found")
    assert api.count("bottle", "shade_id = ?", api.shade("Mermaid Jelly")) == 1


# --- learned codes -------------------------------------------------------------------------


def test_learn_a_barcode(api):
    shade_id = api.shade("Thirst Trap")
    response = api.client.post(
        "/api/v1/identifiers", json={"kind": "gtin", "value": f" {EAN} ", "shade_id": shade_id}
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"identifier", "created", "shade"}
    assert body["created"] is True
    assert body["identifier"] == {
        "id": body["identifier"]["id"], "kind": "gtin", "value": EAN, "shade_id": shade_id,
    }  # fmt: skip
    assert body["shade"]["id"] == shade_id
    found = api.get(f"/api/v1/lookup?q={EAN}&via=scan").json()
    assert (found["outcome"], found["shade"]["id"]) == ("match", shade_id)
    assert body["identifier"]["id"] in [
        i["id"] for i in api.get("/api/v1/identifiers").json()["items"]
    ]


def test_learn_a_printed_code_in_any_spelling(api):
    shade_id = api.shade("Thirst Trap")
    response = api.client.post(
        "/api/v1/identifiers", json={"kind": "printed", "value": "p 321", "shade_id": shade_id}
    )
    assert response.status_code == 201
    assert response.json()["identifier"]["value"] == "P321"


def test_learning_a_known_code_again_changes_nothing(api):
    spirit = api.shade("Spirit Fingers")
    request = {"kind": "gtin", "value": "810170284120", "shade_id": spirit}
    known = api.rows("select id from shade_identifier where kind = 'gtin'")
    response = api.client.post("/api/v1/identifiers", json=request)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is False and body["identifier"]["id"] == known[0]["id"]
    assert api.count("shade_identifier") == 2


def test_a_known_code_keeps_its_shade_when_another_is_asked_for(api):
    other = api.shade("Thirst Trap")
    response = api.client.post(
        "/api/v1/identifiers", json={"kind": "gtin", "value": "810170284120", "shade_id": other}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is False
    assert body["identifier"]["shade_id"] == api.shade("Spirit Fingers")
    assert body["shade"]["title"] == "Spirit Fingers"


@pytest.mark.parametrize(
    ("kind", "value", "field", "fragment"),
    [
        ("gtin", "12345678", "value", "isn\u2019t a valid barcode number"),
        ("gtin", "hello", "value", "isn\u2019t a valid barcode number"),
        ("printed", "hello", "value", "isn\u2019t a P code"),
        ("sku", "HL-1", "kind", "gtin or printed"),
    ],
)
def test_learn_refuses_what_is_not_a_code(api, kind, value, field, fragment):
    before = api.count("shade_identifier")
    shade_id = api.shade("Thirst Trap")
    error = assert_error(
        api.client.post(
            "/api/v1/identifiers", json={"kind": kind, "value": value, "shade_id": shade_id}
        ),
        422,
        "validation",
        field,
    )
    assert fragment in error["message"]
    assert api.count("shade_identifier") == before


def test_learn_for_an_unknown_shade_is_a_404(api):
    request = {"kind": "gtin", "value": EAN, "shade_id": 999999}
    assert_error(api.client.post("/api/v1/identifiers", json=request), 404, "not_found")
    assert api.count("shade_identifier", "value = ?", EAN) == 0


def test_forget_a_code(api):
    learned = api.get("/api/v1/identifiers").json()["items"][0]
    response = api.client.delete(f"/api/v1/identifiers/{learned['id']}")
    assert response.status_code == 204 and response.content == b""
    assert learned["id"] not in [i["id"] for i in api.get("/api/v1/identifiers").json()["items"]]
    outcome = api.get(f"/api/v1/lookup?q={learned['value']}&via=scan").json()["outcome"]
    assert outcome in ("unknown_code", "unknown_printed")
    assert_error(api.client.delete(f"/api/v1/identifiers/{learned['id']}"), 404, "not_found")
