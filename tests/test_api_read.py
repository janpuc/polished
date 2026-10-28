"""The GET endpoints of /api/v1: shapes, a few semantics, ETag and 304 (docs/NATIVE.md 3)."""

import re
from datetime import date

from conftest import make_client, make_settings

from polished import shades, tips

pytest_plugins = ["test_api_support"]

TIP_KEYS = {"id", "hex", "hex2", "finishes", "topper", "clear", "coats", "colours", "revision"}
SHADE_ROW_KEYS = {
    "id", "title", "kind", "source", "is_topper", "price_cents", "compare_at_cents", "status",
    "finishes", "owned_count", "wishlisted", "hero_image_url", "released_on",
    "official_collection", "marks", "tip",
}  # fmt: skip
BOTTLE_KEYS = {
    "id", "shade_id", "state", "bought_on", "price_paid_cents", "opened_on",
    "notes", "archived", "created_at", "updated_at",
}  # fmt: skip
WHEEL_KEYS = {
    "id", "slug", "name", "slot_count", "archived", "filled", "drafts", "tag_url", "created_at",
}  # fmt: skip
TILE_KEYS = {
    "position", "filled", "has_draft", "stack_id", "draft_stack_id", "summary", "layers",
    "painted_on", "note",
}  # fmt: skip
LAYER_KEYS = {"id", "ord", "shade_id", "title", "coats", "label", "tip"}


def shade_id(api, title: str) -> int:
    conn = api.conn()
    try:
        return conn.execute("select id from shade where title = ?", (title,)).fetchone()[0]
    finally:
        conn.close()


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["items"]]


def check_row(row: dict) -> None:
    assert set(row) == SHADE_ROW_KEYS
    assert set(row["tip"]) == TIP_KEYS
    assert re.fullmatch(r"#[0-9a-f]{6}", row["tip"]["hex"])


# --- every GET -----------------------------------------------------------------------------


def get_paths(api) -> list[str]:
    ids = api.ids
    return [
        "/api/v1/me",
        "/api/v1/home",
        "/api/v1/shades",
        "/api/v1/shades?q=taco",
        "/api/v1/shades/facets",
        f"/api/v1/shades/{ids['spirit']}",
        "/api/v1/bottles",
        "/api/v1/bottles/history",
        "/api/v1/wishlist",
        "/api/v1/wheels",
        f"/api/v1/wheels/{ids['holos']}",
        "/api/v1/w/k3m9xq",
        f"/api/v1/stacks/{ids['draft_stack']}",
        "/api/v1/stacks/copy-sources",
        "/api/v1/stacks/pick?q=flak",
        "/api/v1/lookup?q=259",
        "/api/v1/identifiers",
        "/api/v1/sync",
        "/api/v1/auth/devices",
    ]


def test_every_get_has_etag_cache_control_and_the_api_header(api):
    for path in get_paths(api):
        response = api.get(path)
        assert response.status_code == 200, path
        assert re.fullmatch(r'"[0-9a-f]{24}"', response.headers["etag"]), path
        assert response.headers["cache-control"] == "private, no-cache", path
        assert response.headers["x-polished-api"] == "1", path
        assert response.headers["content-type"] == "application/json", path


def test_every_get_answers_304_to_its_etag(api):
    for path in get_paths(api):
        first = api.get(path)
        etag = first.headers["etag"]
        for header in (etag, f"W/{etag}", f'"other", {etag}', "*"):
            again = api.get(path, headers={"If-None-Match": header})
            assert again.status_code == 304, (path, header)
            assert again.content == b""
            assert again.headers["etag"] == etag
            assert again.headers["cache-control"] == "private, no-cache"
            assert again.headers["x-polished-api"] == "1"
        assert api.get(path, headers={"If-None-Match": '"stale"'}).status_code == 200


def test_the_etag_changes_when_the_data_does(api):
    before = api.get("/api/v1/bottles").headers["etag"]
    conn = api.conn()
    conn.execute("update bottle set state = 'low' where id = 1")
    conn.close()
    response = api.get("/api/v1/bottles", headers={"If-None-Match": before})
    assert response.status_code == 200
    assert response.headers["etag"] != before


def test_errors_are_not_given_an_etag(api):
    response = api.get("/api/v1/shades/999999")
    assert response.status_code == 404
    assert "etag" not in response.headers


# --- me, home, sync ------------------------------------------------------------------------


def test_me(api):
    body = api.get("/api/v1/me").json()
    assert body["user"] == {"sub": "dev", "name": "Dev", "first_name": "Dev"}
    assert body["server"] == {
        "version": "dev",
        "public_url": "http://localhost:8080",
        "store_url": "https://holotaco.com",
        "timezone": "Europe/Warsaw",
        "over_black_available": True,
        "shade_count": body["server"]["shade_count"],
    }
    assert body["server"]["shade_count"] > 20


def test_me_says_over_black_is_unavailable_without_the_shade(api):
    conn = api.conn()
    conn.execute("update shade set handle = 'x' where handle = 'one-coat-black'")
    conn.close()
    assert api.get("/api/v1/me").json()["server"]["over_black_available"] is False


def test_home(api):
    body = api.get("/api/v1/home").json()
    assert set(body) == {"greeting_name", "date", "wear", "recent", "wheel", "counts"}
    assert body["greeting_name"] == "Dev"
    date.fromisoformat(body["date"])
    assert set(body["wear"]) == {"shade", "bottle", "worn_today"}
    check_row(body["wear"]["shade"])
    assert body["wear"]["bottle"]["shade_id"] == body["wear"]["shade"]["id"]
    assert body["wear"]["worn_today"] is False
    assert len(body["recent"]) == 5
    assert set(body["recent"][0]) == {"bottle", "shade"}
    assert set(body["recent"][0]["bottle"]) == BOTTLE_KEYS
    check_row(body["recent"][0]["shade"])
    assert [r["bottle"]["id"] for r in body["recent"]] == sorted(
        (r["bottle"]["id"] for r in body["recent"]), reverse=True
    )
    assert body["wheel"]["name"] == "Holos"
    assert set(body["wheel"]) == WHEEL_KEYS | {"tiles"}
    assert len(body["wheel"]["tiles"]) == 20
    assert body["counts"] == {
        "bottles": 5,
        "shades": 4,
        "wished": 3,
        "wished_cents": body["counts"]["wished_cents"],
    }
    assert body["counts"]["wished_cents"] > 0


def test_home_of_an_empty_household(tmp_path):
    client = make_client(make_settings(tmp_path, dev_token="t"))
    body = client.get("/api/v1/home", headers={"Authorization": "Bearer t"}).json()
    assert body["recent"] == [] and body["wheel"] is None and body["wear"] is None
    assert body["counts"] == {"bottles": 0, "shades": 0, "wished": 0, "wished_cents": 0}


def test_home_another_picks_another_owned_shade(api):
    first = api.get("/api/v1/home").json()["wear"]["shade"]["id"]
    for _ in range(10):
        other = api.get("/api/v1/home?another=1").json()["wear"]
        assert other["shade"]["id"] != first
        assert other["shade"]["owned_count"] > 0


def test_sync(api):
    body = api.get("/api/v1/sync").json()
    assert set(body) == {"running", "last", "runs", "cooldown_until"}
    assert body["running"] is False
    assert body["last"] == body["runs"][0]
    assert body["last"]["status"] == "ok"
    assert {"started_at", "finished_at", "trigger", "products_seen", "new_shades"} <= set(
        body["last"]
    )
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", body["last"]["started_at"])


def test_sync_reports_a_running_run_and_the_cooldown(api):
    conn = api.conn()
    conn.execute(
        "insert into sync_run (started_at, trigger, status) values (strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'manual', 'running')"
    )
    conn.close()
    body = api.get("/api/v1/sync").json()
    assert body["running"] is True
    assert body["cooldown_until"] is not None


# --- shades --------------------------------------------------------------------------------


def test_shades_page_shape(api):
    body = api.get("/api/v1/shades").json()
    assert set(body) == {"items", "total", "page", "has_more", "fuzzy"}
    assert (body["page"], body["has_more"], body["fuzzy"]) == (1, False, False)
    assert body["total"] == len(body["items"]) > 20
    for row in body["items"]:
        check_row(row)
        assert row["marks"] == []
    assert titles(api.get("/api/v1/shades")) == sorted(
        (r["title"] for r in body["items"]), key=str.casefold
    )


def test_search_ranks_exact_then_prefix_then_words(api):
    names = titles(api.get("/api/v1/shades?q=magnetic%20taco"))
    assert names[0] == "Magnetic Taco"
    assert "Holo Magnetic Taco" in names[1:]


def test_search_marks_are_unicode_scalar_offsets_and_fuzzy_is_flagged(api):
    typo = api.get("/api/v1/shades?q=magentic%20taco").json()
    assert typo["fuzzy"] is True
    first = typo["items"][0]
    assert first["title"] == "Magnetic Taco"
    assert first["marks"] == [[0, 8], [9, 13]]
    clean = api.get("/api/v1/shades?q=magnetic%20taco").json()
    assert clean["fuzzy"] is False
    assert clean["items"][0]["marks"] == [[0, 8], [9, 13]]


def test_marks_count_scalars_not_utf16_units_or_bytes(api):
    conn = api.conn()
    shades.create_manual(conn, "\U0001f984 Pony Ride", "polish")  # one scalar, two UTF-16 units
    shades.create_manual(conn, "Cre\u0300me Pony", "polish")  # e + combining grave
    conn.close()
    rows = {r["title"]: r for r in api.get("/api/v1/shades?q=pony").json()["items"]}
    assert rows["\U0001f984 Pony Ride"]["marks"] == [[2, 6]]
    assert rows["Cre\u0300me Pony"]["marks"] == [[7, 11]]
    accents = api.get("/api/v1/shades?q=creme%20brulee").json()["items"][0]
    assert accents["title"] == "Crème Brûlée"
    assert accents["marks"] == [[0, 5], [6, 12]]


def test_search_with_no_match_is_empty_and_not_fuzzy(api):
    body = api.get("/api/v1/shades?q=zzzzzzqq").json()
    assert (body["items"], body["total"], body["fuzzy"]) == ([], 0, False)


def test_shades_filters(api):
    holo = api.get("/api/v1/shades?finish=holographic").json()["items"]
    assert holo and all("holographic" in r["finishes"] for r in holo)
    either = api.get("/api/v1/shades?finish=holographic&finish=glitter").json()["items"]
    assert len(either) > len(holo)
    owned = api.get("/api/v1/shades?owned=owned").json()
    assert {r["title"] for r in owned["items"]} == {
        "Spirit Fingers", "One-Coat Black", "Flakie Holo Taco", "Thirst Trap",
    }  # fmt: skip
    assert all(r["owned_count"] > 0 for r in owned["items"])
    wished = api.get("/api/v1/shades?owned=wishlist").json()["items"]
    assert {r["title"] for r in wished} == {"Mermaid Jelly", "Crème Brûlée", "Silver Flake Taco"}
    assert all(r["wishlisted"] for r in wished)
    toppers = api.get("/api/v1/shades?kind=topper").json()["items"]
    assert toppers and all(r["is_topper"] for r in toppers)
    # A stale bookmark still lists.
    assert api.get("/api/v1/shades?kind=nonsense&sort=nonsense").json()["total"] > 20


def test_shades_paging(api):
    second = api.get("/api/v1/shades?page=2").json()
    assert (second["page"], second["items"], second["has_more"]) == (2, [], False)
    assert api.get("/api/v1/shades?page=0").json()["page"] == 1


def test_shade_status_and_prices(api):
    rows = {r["title"]: r for r in api.get("/api/v1/shades").json()["items"]}
    status = rows["Spirit Fingers"]["status"]
    assert set(status) == {"key", "label", "buyable"}
    assert rows["Spirit Fingers"]["price_cents"] == 1550
    assert rows["Gifted Mystery"]["status"] is None
    assert rows["Gifted Mystery"]["source"] == "manual"


def test_tip_matches_the_web_tip_url(api):
    """The API's revision is the one in the web's /tips/shade/<id>.svg?v=… for the same shade."""
    spirit = api.ids["spirit"]
    conn = api.conn()
    row = conn.execute(
        f"select s.id as shade_id, {tips.TIP_FIELDS} from shade s where s.id = ?", (spirit,)
    ).fetchone()
    conn.close()
    drawn = tips.tip_shade(row)
    tip = api.get(f"/api/v1/shades/{spirit}").json()["shade"]["tip"]
    assert tip["revision"] == tips.revision([drawn])
    assert tip["hex"] == drawn.hex and tip["finishes"] == sorted(drawn.finishes)
    assert tip["coats"] == 1 and tip["topper"] is drawn.topper


def test_tip_uses_the_households_override(api):
    spirit = api.ids["spirit"]
    conn = api.conn()
    conn.execute(
        "update shade set swatch_override_hex = '#123456', swatch_hex2 = '#abcdef' where id = ?",
        (spirit,),
    )
    conn.close()
    detail = api.get(f"/api/v1/shades/{spirit}").json()
    assert detail["tip_source"] == "override"
    assert (detail["shade"]["tip"]["hex"], detail["shade"]["tip"]["hex2"]) == ("#123456", None)


def test_facets(api):
    body = api.get("/api/v1/shades/facets").json()
    assert set(body) == {"finish", "color", "collection", "official"}
    assert "holographic" in body["finish"] and "blue" in body["color"]


def test_shade_detail(api):
    body = api.get(f"/api/v1/shades/{api.ids['spirit']}").json()
    assert set(body) == {
        "shade", "images", "tags", "sku", "handle", "store_url", "on_sale", "bottles",
        "wishlist", "swatched_on", "tip_source",
    }  # fmt: skip
    check_row(body["shade"])
    assert body["shade"]["owned_count"] == 2
    assert set(body["tags"]) == {"finish", "color", "collection"}
    assert body["store_url"] == f"https://holotaco.com/products/{body['handle']}"
    assert body["tip_source"] == "sampled"
    assert [b["state"] for b in body["bottles"]] == ["full", "half"]  # newest first
    assert all(set(b) == BOTTLE_KEYS for b in body["bottles"])
    assert body["wishlist"] is None
    swatched = body["swatched_on"]
    assert len(swatched) == 1
    assert (swatched[0]["wheel_id"], swatched[0]["slug"], swatched[0]["name"], swatched[0]["position"]) == (
        api.ids["holos"], "k3m9xq", "Holos", 13,
    )  # fmt: skip
    assert isinstance(swatched[0]["stack_id"], int)


def test_shade_detail_of_a_wishlisted_shade(api):
    body = api.get(f"/api/v1/shades/{shade_id(api, 'Mermaid Jelly')}").json()
    assert body["wishlist"] == {
        "id": body["wishlist"]["id"],
        "priority": 1,
        "note": "For the blue week",
    }
    assert body["shade"]["wishlisted"] is True


def test_shade_detail_of_a_manual_shade(api):
    body = api.get(f"/api/v1/shades/{api.ids['manual']}").json()
    assert body["shade"]["status"] is None
    assert (body["handle"], body["store_url"], body["images"], body["tip_source"]) == (
        None,
        None,
        [],
        "none",
    )
    assert body["shade"]["tip"]["hex"] == tips.NEUTRAL_HEX


def test_shade_404(api):
    response = api.get("/api/v1/shades/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- bottles -------------------------------------------------------------------------------


def test_bottles_group_by_shade(api):
    groups = api.get("/api/v1/bottles").json()["groups"]
    assert [g["shade"]["title"] for g in groups] == [
        "Flakie Holo Taco", "One-Coat Black", "Spirit Fingers", "Thirst Trap",
    ]  # fmt: skip
    spirit = groups[2]
    assert [b["state"] for b in spirit["bottles"]] == ["full", "half"]
    check_row(spirit["shade"])
    assert spirit["shade"]["owned_count"] == 2


def test_bottles_filters(api):
    low = api.get("/api/v1/bottles?state=low").json()["groups"]
    assert [g["shade"]["title"] for g in low] == ["Thirst Trap"]
    archived = api.get("/api/v1/bottles?archived=true").json()["groups"]
    assert [g["shade"]["title"] for g in archived] == ["Magnetic Taco"]
    assert archived[0]["bottles"][0]["archived"] is True
    assert len(api.get("/api/v1/bottles?state=nonsense").json()["groups"]) == 4


def test_bottle_history(api):
    years = api.get("/api/v1/bottles/history").json()["years"]
    assert [y["year"] for y in years] == [2026, 2025]
    first = years[0]
    assert set(first) == {"year", "count", "total_cents", "unpriced", "months"}
    assert [m["month"] for m in first["months"]] == [10, 8, 7, 2]
    october = first["months"][0]
    assert october["label"] == "October 2026"
    assert (october["count"], october["total_cents"], october["unpriced"]) == (2, 1650, 1)
    assert [r["dated_by_entry"] for r in october["rows"]] == [
        True,
        False,
    ]  # the undated gift: 12 Oct
    row = october["rows"][1]
    assert set(row) == {"bottle", "shade", "dated_by_entry"}
    assert row["shade"]["title"] == "Flakie Holo Taco"
    assert first["count"] == 5 and first["total_cents"] == 1550 + 1200 + 1650


# --- wishlist ------------------------------------------------------------------------------


def test_wishlist(api):
    body = api.get("/api/v1/wishlist").json()
    assert set(body) == {"items", "summary", "cart"}
    assert [(i["priority"], i["shade"]["title"]) for i in body["items"]] == [
        (1, "Mermaid Jelly"), (2, "Crème Brûlée"), (3, "Silver Flake Taco"),
    ]  # fmt: skip
    first = body["items"][0]
    assert set(first) == {"id", "shade", "priority", "note", "added_on", "buyable"}
    assert (first["note"], first["added_on"], first["buyable"]) == (
        "For the blue week",
        "2026-10-10",
        True,
    )
    check_row(first["shade"])
    summary = body["summary"]
    assert summary["count"] == 3
    assert summary["buyable_cents"] == sum(
        i["shade"]["price_cents"] for i in body["items"] if i["buyable"]
    )
    cart = body["cart"]
    assert cart["url"].startswith("https://holotaco.com/cart/")
    assert cart["count"] == len(cart["names"]) == summary["buyable_count"]
    assert cart["names"][0] == "Mermaid Jelly"


def test_wishlist_cart_follows_max_priority(api):
    one = api.get("/api/v1/wishlist?max_priority=1").json()["cart"]
    assert one["names"] == ["Mermaid Jelly"] and one["count"] == 1
    assert api.get("/api/v1/wishlist?max_priority=9").status_code == 422


def test_wishlist_cart_skips_what_cannot_be_bought(api):
    conn = api.conn()
    conn.execute("update shade set available = 0 where title = 'Mermaid Jelly'")
    conn.close()
    body = api.get("/api/v1/wishlist").json()
    assert body["items"][0]["buyable"] is False
    assert "Mermaid Jelly" not in body["cart"]["names"]
    assert body["cart"]["skipped"] == 1


# --- wheels and stacks ---------------------------------------------------------------------


def test_wheels_list_has_tiles(api):
    items = api.get("/api/v1/wheels").json()["items"]
    assert [w["name"] for w in items] == ["Holos", "Toppers"]
    holos, toppers = items
    assert set(holos) == WHEEL_KEYS | {"tiles"}
    assert (holos["filled"], holos["drafts"], holos["slot_count"]) == (2, 1, 20)
    assert len(holos["tiles"]) == 20 and len(toppers["tiles"]) == 12
    assert holos["tag_url"] == "http://localhost:8080/w/k3m9xq"
    assert all(set(t) == TILE_KEYS for t in holos["tiles"])
    tile = holos["tiles"][11]
    assert (tile["position"], tile["filled"], tile["painted_on"]) == (12, True, "2026-10-20")
    assert tile["summary"] == "One-Coat Black ×2 + Flakie Holo Taco"
    assert [(layer["label"], layer["coats"]) for layer in tile["layers"]] == [
        ("Base", 2),
        ("Top", 1),
    ]
    assert all(set(layer) == LAYER_KEYS for layer in tile["layers"])
    assert holos["tiles"][13]["has_draft"] is True and holos["tiles"][13]["filled"] is False
    assert holos["tiles"][0] == {
        "position": 1, "filled": False, "has_draft": False, "stack_id": None,
        "draft_stack_id": None, "summary": "", "layers": [], "painted_on": None, "note": None,
    }  # fmt: skip


def test_wheels_archived_flag(api):
    conn = api.conn()
    conn.execute("update wheel set archived = 1 where name = 'Toppers'")
    conn.close()
    assert [w["name"] for w in api.get("/api/v1/wheels").json()["items"]] == ["Holos"]
    archived = api.get("/api/v1/wheels?archived=true").json()["items"]
    assert [(w["name"], w["archived"]) for w in archived] == [("Toppers", True)]


def test_wheel_by_slug_and_by_id_are_the_same_wheel(api):
    by_slug = api.get("/api/v1/w/k3m9xq").json()
    by_id = api.get(f"/api/v1/wheels/{api.ids['holos']}").json()
    assert by_slug == by_id
    assert set(by_slug) == WHEEL_KEYS | {"tiles", "filled_count", "others"}
    assert by_slug["filled_count"] == 2
    assert [o["name"] for o in by_slug["others"]] == ["Toppers"]
    assert set(by_slug["others"][0]) == {"id", "name", "slug"}


def test_wheel_404s_are_json_after_auth(api, bare_client):
    for path in ("/api/v1/w/zzzzzz", "/api/v1/wheels/999999"):
        response = api.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
        assert bare_client.get(path).status_code == 401  # auth comes first


def test_stack_sheet_of_a_draft(api):
    body = api.get(f"/api/v1/stacks/{api.ids['draft_stack']}").json()
    assert set(body) == {
        "stack_id", "wheel", "position", "name", "note", "painted_on", "layers", "summary",
        "full", "tip",
    }  # fmt: skip
    assert body["wheel"] == {"id": api.ids["holos"], "slug": "k3m9xq", "name": "Holos"}
    assert (body["position"], body["full"], body["summary"]) == (
        14,
        False,
        "One-Coat Black ×2 + Flakie Holo Taco",
    )
    assert [layer["title"] for layer in body["layers"]] == ["One-Coat Black", "Flakie Holo Taco"]
    assert body["tip"] == [layer["tip"] for layer in body["layers"]]


def test_stack_sheet_of_a_saved_stack_is_a_409(api):
    response = api.get(f"/api/v1/stacks/{api.ids['saved_stack']}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_a_draft"
    assert api.get("/api/v1/stacks/999999").status_code == 409


def test_stack_copy_sources(api):
    items = api.get("/api/v1/stacks/copy-sources").json()["items"]
    assert [i["position"] for i in items] == [13, 12]  # most recently saved first
    assert set(items[0]) == {
        "stack_id", "wheel_name", "wheel_slug", "position", "name", "painted_on", "summary", "layers",
    }  # fmt: skip
    assert items[1]["summary"] == "One-Coat Black ×2 + Flakie Holo Taco"
    only = api.get("/api/v1/stacks/copy-sources?q=flakie").json()["items"]
    assert [i["position"] for i in only] == [12]
    assert api.get("/api/v1/stacks/copy-sources?q=nothing").json()["items"] == []


def test_stack_pick_scopes_and_barcode(api):
    everything = api.get("/api/v1/stacks/pick?q=flak&scope=all").json()
    assert set(everything) == {"items", "total"}
    assert {r["title"] for r in everything["items"]} >= {"Flakie Holo Taco", "Silver Flake Taco"}
    assert everything["items"][0]["title"] == "Flakie Holo Taco"  # owned first
    owned = api.get("/api/v1/stacks/pick?q=flak&scope=owned").json()
    assert owned["items"][0]["title"] == "Flakie Holo Taco"
    assert all(r["owned_count"] > 0 for r in owned["items"])
    toppers = api.get("/api/v1/stacks/pick?scope=toppers").json()["items"]
    assert toppers and all(r["is_topper"] for r in toppers)
    by_barcode = api.get("/api/v1/stacks/pick?q=810170284120").json()
    assert [r["title"] for r in by_barcode["items"]] == ["Spirit Fingers"]
    assert by_barcode["total"] == 1
    assert api.get("/api/v1/stacks/pick?q=259").json() == {"items": [], "total": 0}  # a search
    assert api.get("/api/v1/stacks/pick?scope=bogus").status_code == 422


# --- lookup and identifiers ----------------------------------------------------------------


def lookup(api, q: str, via: str = "typed") -> dict:
    return api.get("/api/v1/lookup", params={"q": q, "via": via}).json()


def test_lookup_outcomes(api):
    match = lookup(api, "810170284120", "scan")
    assert (match["outcome"], match["kind"], match["code"]) == ("match", "gtin", "0810170284120")
    assert match["shade"]["title"] == "Spirit Fingers"
    check_row({k: v for k, v in match["shade"].items() if k != "images"})
    assert isinstance(match["shade"]["images"], list)
    assert isinstance(match["identifier_id"], int) and match["results"] is None

    short = lookup(api, "259")  # not a barcode: an ordinary name search
    assert (short["outcome"], short["kind"], short["code"], short["shade"]) == (
        "results",
        None,
        None,
        None,
    )
    assert short["results"]["items"] == []

    unknown = lookup(api, "5901234123457", "scan")
    assert (unknown["outcome"], unknown["code"], unknown["shade"]) == (
        "unknown_code",
        "5901234123457",
        None,
    )
    assert lookup(api, "P999")["outcome"] == "results"
    assert lookup(api, "12345678", "scan")["outcome"] == "invalid_code"

    results = lookup(api, "flakie")
    assert results["outcome"] == "results" and results["shade"] is None
    assert results["results"]["total"] == len(results["results"]["items"]) >= 1
    check_row(results["results"]["items"][0])


def test_lookup_by_sku(api):
    conn = api.conn()
    sku = conn.execute("select sku from shade where id = ?", (api.ids["spirit"],)).fetchone()[0]
    conn.close()
    body = lookup(api, sku.lower())
    assert (body["outcome"], body["kind"], body["shade"]["title"]) == (
        "match",
        "sku",
        "Spirit Fingers",
    )


def test_lookup_counts_a_scan_as_a_use(api):
    conn = api.conn()
    before = conn.execute("select use_count from shade_identifier where kind = 'gtin'").fetchone()[
        0
    ]
    lookup(api, "810170284120", "scan")
    assert (
        conn.execute("select use_count from shade_identifier where kind = 'gtin'").fetchone()[0]
        == before + 1
    )
    conn.close()


def test_identifiers(api):
    items = api.get("/api/v1/identifiers").json()["items"]
    assert [(i["kind"], i["value"]) for i in items] == [("gtin", "0810170284120")]
    first = items[0]
    assert set(first) == {"id", "kind", "value", "shade", "use_count", "created_at", "last_used_at"}
    assert (first["use_count"], first["shade"]["title"]) == (2, "Spirit Fingers")
    check_row(first["shade"])


# --- the web is untouched ------------------------------------------------------------------


def test_web_pages_do_not_carry_the_api_header(api):
    response = api.client.get("/shades", headers={"Authorization": ""})
    assert response.status_code == 200
    assert "x-polished-api" not in response.headers
    assert response.headers["content-type"].startswith("text/html")
