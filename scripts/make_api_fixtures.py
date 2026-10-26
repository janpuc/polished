"""Records spec/api/fixtures/*.json: real /api/v1 responses from the seeded e2e database plus a
small invented household (bottles, a wishlist, two wheels, a draft, learned codes).

    uv run python scripts/make_api_fixtures.py

The app's tests decode these files, and tests/test_api_fixtures.py checks each against
spec/api/openapi.yaml. Output is deterministic (fixed clock, fixed slug and timestamps); the only
invented value is the example token. Catalog fields and made-up bottles only: nothing here comes
from the live database.
"""

import json
import random
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec" / "api" / "fixtures"
EXAMPLE_TOKEN = "example-token-0123456789abcdefghijklmnopqrstuvwxyz"
EXAMPLE_CODE = "example-code-0123456789abcdefghijklmnopqrstuvwxyz"
NOW = datetime(2026, 10, 26, 16, 30, tzinfo=UTC)
SLUG = "k3m9xq"
USER = ("u-nikola", "Nikola Example")
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
# The slugs the wheels made by the write fixtures get, in order (the real ones are random).
SLUGS = ["j7g2hm", "t4n8qb", "w9d3fj"]


def pinned(node):
    """A write response with the database's own clock readings (created_at, updated_at, added_on,
    set by SQLite's `now`) replaced by the fixtures' fixed day."""
    if isinstance(node, dict):
        return {key: _pin(key, value) for key, value in node.items()}
    if isinstance(node, list):
        return [pinned(item) for item in node]
    return node


def _pin(key, value):
    if key in ("created_at", "updated_at") and isinstance(value, str) and STAMP.fullmatch(value):
        return NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    if key == "added_on" and isinstance(value, str):
        return NOW.date().isoformat()
    return pinned(value)


def add_household(conn) -> dict[str, int]:
    """Bottles, wishlist, wheels, a draft and learned codes on top of a seeded catalog, with every
    timestamp pinned. Returns the ids the fixtures ask about."""
    from polished import bottles, identifiers, shades, stacks, wheels, wishlist
    from polished.bottles import BottleInput

    def shade(title: str) -> int:
        return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]

    def pin(table: str, row_id: int, **columns) -> None:
        sets = ", ".join(f"{name} = ?" for name in columns)
        conn.execute(f"update {table} set {sets} where id = ?", [*columns.values(), row_id])

    spirit, black, flakie = (
        shade("Spirit Fingers"),
        shade("One-Coat Black"),
        shade("Flakie Holo Taco"),
    )
    values = [
        (
            spirit,
            BottleInput("half", "P259", "2026-07-21", 1550, "2026-10-05"),
            "2026-07-21T10:02:11Z",
        ),
        (black, BottleInput("full", None, "2026-08-02", 1200), "2026-08-02T18:40:00Z"),
        (flakie, BottleInput("full", None, "2026-10-01", 1650), "2026-10-01T08:15:30Z"),
        (
            shade("Thirst Trap"),
            BottleInput("low", None, None, None, None, "A gift"),
            "2026-10-12T20:00:00Z",
        ),
        (spirit, BottleInput("full", None, "2025-12-24", None), "2025-12-24T09:00:00Z"),
    ]
    bottle_ids = []
    for shade_id, bottle, stamp in values:
        bottle_id = bottles.add(conn, shade_id, bottle)
        pin("bottle", bottle_id, created_at=stamp, updated_at=stamp)
        bottle_ids.append(bottle_id)
    old = bottles.add(conn, shade("Magnetic Taco"), BottleInput("empty", bought_on="2026-02-14"))
    bottles.set_archived(conn, old, True)
    pin("bottle", old, created_at="2026-02-14T12:00:00Z", updated_at="2026-09-01T12:00:00Z")

    for title, priority, note in (
        ("Mermaid Jelly", 1, "For the blue week"),
        ("Crème Brûlée", 2, None),
        ("Silver Flake Taco", 3, None),
    ):
        item = wishlist.add(conn, shade(title), priority)
        wishlist.update(conn, item, priority, note)
        pin("wishlist_item", item, added_on="2026-10-10")

    printed = identifiers.learn_printed(conn, spirit, "P259")
    pin("shade_identifier", printed.id, created_at="2026-07-21T10:02:30Z")
    learned = identifiers.learn(conn, "gtin", "810170284120", spirit)
    pin("shade_identifier", learned.id, created_at="2026-07-21T10:05:00Z")
    conn.execute(
        "update shade_identifier set use_count = 2, last_used_at = '2026-10-05T09:00:00Z'"
        " where id = ?",
        (learned.id,),
    )

    holos = wheels.create(conn, "Holos", 20)
    toppers = wheels.create(conn, "Toppers", 12)
    pin("wheel", holos, slug=SLUG, created_at="2026-10-01T09:00:00Z")
    pin("wheel", toppers, slug="7b2vdc", created_at="2026-10-02T09:00:00Z")

    def swatch(position: int, layers: list[int], painted_on: str, note: str | None = None) -> int:
        stack_id = stacks.open_draft(conn, holos, position).stack_id
        for shade_id in layers:
            stacks.append(conn, stack_id, shade_id)
        stacks.save(conn, stack_id, note=note or "", painted_on=painted_on)
        conn.execute(
            "update stack set updated_at = ?, created_at = ? where id = ?",
            (f"{painted_on}T18:00:00.000Z",) * 2 + (stack_id,),
        )
        return stack_id

    saved = swatch(12, [black, flakie], "2026-10-20")
    swatch(13, [spirit], "2026-10-22", "Two coats, dried fast")
    draft = stacks.open_draft(conn, holos, 14).stack_id
    stacks.append(conn, draft, black)
    stacks.append(conn, draft, flakie)

    manual = shades.create_manual(conn, "Gifted Mystery", "polish")
    conn.execute(
        "update sync_run set started_at = '2026-10-26T04:00:12Z', finished_at = '2026-10-26T04:01:20Z'"
    )
    return {
        "spirit": spirit,
        "manual": manual,
        "holos": holos,
        "saved_stack": saved,
        "draft_stack": draft,
        "learned_gtin": learned.id,
    }


def record_writes(app, client, db, token, ids, record) -> None:
    """Every write endpoint once, in an order where each step has what it needs. The household
    changes as it goes (the reads were recorded before), so this runs last."""
    import httpx

    from polished import wheels
    from polished.catalog.sync import SyncRunner
    from polished.db import connect

    slugs = iter(SLUGS)
    wheels.new_slug = lambda: next(slugs)

    def query(sql: str, *args):
        conn = connect(db)
        try:
            return conn.execute(sql, args).fetchone()[0]
        finally:
            conn.close()

    def shade(title: str) -> int:
        return query("select id from shade where title = ?", title)

    def write(name: str, method: str, path: str, **kwargs) -> dict | None:
        return record(name, method, path, token, **kwargs)

    # shades
    write(
        "shade_create",
        "POST",
        "/api/v1/shades",
        json={"title": "Birthday Glitter", "kind": "topper"},
    )
    write(
        "shade_tip_colour",
        "PUT",
        f"/api/v1/shades/{ids['spirit']}/tip-colour",
        json={"hex": "#7a3fd1"},
    )
    write(
        "shade_tip_colour_reset",
        "PUT",
        f"/api/v1/shades/{ids['spirit']}/tip-colour",
        json={"hex": None},
    )

    # bottles
    thirst = shade("Thirst Trap")
    created = write(
        "bottle_create",
        "POST",
        f"/api/v1/shades/{thirst}/bottles",
        json={
            "state": "half",
            "printed_code": "321",
            "bought_on": "2026-10-20",
            "price_paid_cents": 1550,
            "opened_on": "2026-10-24",
            "notes": "From the pop-up",
        },
    )
    write(
        "bottle_create_known_code",
        "POST",
        f"/api/v1/shades/{thirst}/bottles",
        json={"state": "full", "printed_code": "P259"},
    )
    write(
        "bottle_update",
        "PATCH",
        f"/api/v1/bottles/{created['bottle']['id']}",
        json={"state": "low", "notes": None, "archived": False},
    )
    write("bottle_delete", "DELETE", f"/api/v1/bottles/{created['bottle']['id']}")
    write(
        "error_validation_bottle",
        "POST",
        f"/api/v1/shades/{thirst}/bottles",
        json={"state": "nearly", "bought_on": "2099-01-01", "price_paid_cents": -5},
    )

    # wishlist
    write("wishlist_add", "PUT", f"/api/v1/shades/{thirst}/wishlist", json={"priority": 2})
    item = query("select id from wishlist_item where shade_id = ?", thirst)
    write(
        "wishlist_update",
        "PATCH",
        f"/api/v1/wishlist/{item}",
        json={"priority": 1, "note": "Birthday"},
    )
    write("wishlist_remove", "DELETE", f"/api/v1/wishlist/{item}")
    first, second = (
        query("select id from wishlist_item where shade_id = ?", shade(t))
        for t in ("Mermaid Jelly", "Crème Brûlée")
    )
    write(
        "wishlist_bought",
        "POST",
        "/api/v1/wishlist/bought",
        json={
            "items": [{"id": first, "price_cents": 1550}, {"id": second, "price_cents": None}],
            "bought_on": "2026-10-25",
        },
    )

    # learned codes
    learned = write(
        "identifier_learn",
        "POST",
        "/api/v1/identifiers",
        json={"kind": "gtin", "value": "5901234123457", "shade_id": thirst},
    )
    write("identifier_forget", "DELETE", f"/api/v1/identifiers/{learned['identifier']['id']}")

    # wheels
    wheel = write(
        "wheel_create", "POST", "/api/v1/wheels", json={"name": "Jellies", "slot_count": 12}
    )
    wid = wheel["id"]
    write("wheel_update", "PATCH", f"/api/v1/wheels/{wid}", json={"name": "Jelly wheel"})
    write("wheel_slug_regenerate", "POST", f"/api/v1/wheels/{wid}/slug/regenerate")
    toppers = query("select id from wheel where name = 'Toppers'")
    write(
        "wheel_slug_take",
        "POST",
        f"/api/v1/wheels/{wid}/slug/take",
        json={"from_wheel_id": toppers},
    )
    write(
        "error_same_wheel", "POST", f"/api/v1/wheels/{wid}/slug/take", json={"from_wheel_id": wid}
    )

    # the builder: a draft on an empty slot, layers, templates, save; a resumed draft, cancel
    opened = write("slot_draft", "POST", f"/api/v1/wheels/{wid}/slots/3/draft")
    stack = opened["stack_id"]
    write("slot_draft_resumed", "POST", f"/api/v1/wheels/{wid}/slots/3/draft")
    write("layer_add", "POST", f"/api/v1/stacks/{stack}/layers", json={"shade_id": thirst})
    flakie = shade("Flakie Holo Taco")
    sheet = write(
        "layer_add_second", "POST", f"/api/v1/stacks/{stack}/layers", json={"shade_id": flakie}
    )
    layer = sheet["layers"][0]["id"]
    write("layer_coats", "PATCH", f"/api/v1/stacks/{stack}/layers/{layer}", json={"coats_delta": 1})
    write("layer_move", "PATCH", f"/api/v1/stacks/{stack}/layers/{layer}", json={"move": "down"})
    write(
        "stack_template_over_black",
        "POST",
        f"/api/v1/stacks/{stack}/template",
        json={"kind": "over_black"},
    )
    last = write(
        "stack_template_last", "POST", f"/api/v1/stacks/{stack}/template", json={"kind": "last"}
    )
    write(
        "stack_template_copy",
        "POST",
        f"/api/v1/stacks/{stack}/template",
        json={"kind": "copy", "source_stack_id": ids["saved_stack"]},
    )
    write("layer_delete", "DELETE", f"/api/v1/stacks/{stack}/layers/{last['layers'][0]['id']}")
    write(
        "stack_save",
        "POST",
        f"/api/v1/stacks/{stack}/save",
        json={"name": "Black and flakes", "note": "Dried fast", "painted_on": "2026-10-25"},
    )
    other = write("slot_draft_new", "POST", f"/api/v1/wheels/{wid}/slots/4/draft")["stack_id"]
    write("error_empty_stack", "POST", f"/api/v1/stacks/{other}/save", json={})
    for _ in range(8):
        record("tmp", "POST", f"/api/v1/stacks/{other}/layers", token, json={"shade_id": flakie})
    write("error_stack_full", "POST", f"/api/v1/stacks/{other}/layers", json={"shade_id": flakie})
    write("stack_cancel", "POST", f"/api/v1/stacks/{other}/cancel")
    (FIXTURES / "tmp.json").unlink()
    write("slot_clear", "DELETE", f"/api/v1/wheels/{wid}/slots/3")
    write("wheel_delete", "DELETE", f"/api/v1/wheels/{wid}")

    # wear
    write("wear_record", "POST", f"/api/v1/wear/{ids['spirit']}")

    # sync: a mock shop (nothing leaves this machine), then the cooldown
    def shop(request):
        from conftest import load_feed

        return httpx.Response(200, json={"products": load_feed()})

    runner = SyncRunner(app.state.settings, transport=httpx.MockTransport(shop), now=lambda: NOW)
    app.state.sync_runner = runner
    write("sync_run", "POST", "/api/v1/sync/run")
    write("error_cooldown", "POST", "/api/v1/sync/run")


def main() -> None:
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
    from e2e.flows.seed import build
    from starlette.testclient import TestClient

    from polished import wear
    from polished.api import auth as tokens
    from polished.config import Settings
    from polished.db import connect
    from polished.server import create_app

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW

    tokens.now = lambda: NOW
    wear.datetime = FixedDatetime
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for old in FIXTURES.glob("*.json"):
        old.unlink()

    with tempfile.TemporaryDirectory() as scratch:
        db = str(Path(scratch) / "polished.db")
        build(db)
        conn = connect(db)
        ids = add_household(conn)
        challenge = tokens.challenge_for("v" * 43)
        code = tokens.mint_login_code(conn, *USER, challenge, "Nikola's iPhone")
        conn.close()

        settings = Settings(
            _env_file=None,
            db_path=db,
            public_url="http://localhost:8080",
            auth_mode="none",
            session_secret="fixtures-fixtures-fixtures-fixtures-0",
            sync_enabled=False,
            release_sheet_url="",
            apple_team_id="ABCDE12345",
        )
        app = create_app(settings)
        app.state.sync_runner.now = lambda: NOW
        client = TestClient(app, base_url=settings.public_url, follow_redirects=False)

        def record(name: str, method: str, path: str, token: str | None = None, **kwargs) -> dict:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = client.request(method, path, headers=headers, **kwargs)
            body = response.json() if response.content else None
            if method != "GET":
                body = pinned(body)
            request = {"method": method, "path": path}
            if "json" in kwargs:
                request["body"] = kwargs["json"]
            (FIXTURES / f"{name}.json").write_text(
                json.dumps(
                    {
                        "request": request,
                        "status": response.status_code,
                        "body": body,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n"
            )
            return body

        exchange = record(
            "auth_exchange",
            "POST",
            "/api/v1/auth/exchange",
            json={
                "code": code,
                "verifier": "v" * 43,
                "device_name": "Nikola's iPhone",
                "platform": "ios",
                "app_version": "1.0.0",
            },
        )
        token = exchange["token"]
        fixture = FIXTURES / "auth_exchange.json"
        fixture.write_text(
            fixture.read_text().replace(token, EXAMPLE_TOKEN).replace(code, EXAMPLE_CODE)
        )
        # Later requests use the real token; the file shows the example.
        get = lambda name, path: record(name, "GET", path, token)  # noqa: E731

        get("me", "/api/v1/me")
        get("home", "/api/v1/home")
        get("shades_page", "/api/v1/shades")
        get("shades_search", "/api/v1/shades?q=magentic%20taco")
        get("shades_filtered", "/api/v1/shades?finish=holographic&owned=owned&sort=newest")
        get("shades_facets", "/api/v1/shades/facets")
        get("shade_detail", f"/api/v1/shades/{ids['spirit']}")
        get("shade_detail_manual", f"/api/v1/shades/{ids['manual']}")
        get("bottles", "/api/v1/bottles")
        get("bottles_archived", "/api/v1/bottles?archived=true")
        get("bottles_history", "/api/v1/bottles/history")
        get("wishlist", "/api/v1/wishlist")
        get("wheels", "/api/v1/wheels")
        get("wheel", f"/api/v1/w/{SLUG}")
        get("wheel_by_id", f"/api/v1/wheels/{ids['holos']}")
        get("stack_sheet", f"/api/v1/stacks/{ids['draft_stack']}")
        get("stack_copy_sources", "/api/v1/stacks/copy-sources")
        get("stack_pick", "/api/v1/stacks/pick?q=flak&scope=all")
        get("stack_pick_suggestion", "/api/v1/stacks/pick?q=P259")
        get("lookup_match", "/api/v1/lookup?q=810170284120&via=scan")
        get("lookup_suggestion", "/api/v1/lookup?q=259")
        get("lookup_unknown_code", "/api/v1/lookup?q=5901234123457&via=scan")
        get("lookup_unknown_printed", "/api/v1/lookup?q=P999")
        get("lookup_invalid_code", "/api/v1/lookup?q=12345678&via=scan")
        get("lookup_results", "/api/v1/lookup?q=flakie")
        # Resolving a barcode counts as a use, with the real clock; put the numbers back.
        conn = connect(db)
        conn.execute(
            "update shade_identifier set use_count = 2, last_used_at = '2026-10-05T09:00:00Z'"
            " where id = ?",
            (ids["learned_gtin"],),
        )
        conn.close()
        get("identifiers", "/api/v1/identifiers")
        get("sync", "/api/v1/sync")
        get("auth_devices", "/api/v1/auth/devices")
        record("error_unauthorized", "GET", "/api/v1/home")
        get("error_not_found", "/api/v1/shades/999999")
        get("error_not_a_draft", f"/api/v1/stacks/{ids['saved_stack']}")
        get("error_validation", "/api/v1/shades?page=x")
        random.seed(0)
        get("home_another", "/api/v1/home?another=1")
        record_writes(app, client, db, token, ids, record)
    print(f"wrote {len(list(FIXTURES.glob('*.json')))} fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
