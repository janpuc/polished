"""Records spec/api/fixtures/*.json: real /api/v1 responses from the seeded e2e database plus a
small invented household (bottles, a wishlist, two wheels, a draft, learned codes).

    uv run python scripts/make_api_fixtures.py

The app's tests decode these files, and tests/test_api_fixtures.py checks each against
spec/api/openapi.yaml. Output is deterministic (fixed clock, fixed hash seed, fixed slug and
timestamps); the only invented value is the example token. Catalog fields and made-up bottles
only: nothing here comes from the live database.
"""

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec" / "api" / "fixtures"
EXAMPLE_TOKEN = "example-token-0123456789abcdefghijklmnopqrstuvwxyz"
NOW = datetime(2026, 10, 26, 16, 30, tzinfo=UTC)
SLUG = "k3m9xq"
USER = ("u-nikola", "Nikola Example")
# The first nail-tip recipe of a shade hashes a frozenset's repr, which varies with the hash seed.
HASH_SEED = "0"


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


def main() -> None:
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
    from e2e.flows.seed import build
    from starlette.testclient import TestClient

    from polished.api import auth as tokens
    from polished.api import home as api_home
    from polished.config import Settings
    from polished.db import connect
    from polished.server import create_app

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW

    tokens.now = lambda: NOW
    api_home.datetime = FixedDatetime
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
            body = response.json()
            (FIXTURES / f"{name}.json").write_text(
                json.dumps(
                    {
                        "request": {"method": method, "path": path},
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
        fixture.write_text(fixture.read_text().replace(token, EXAMPLE_TOKEN))
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
    print(f"wrote {len(list(FIXTURES.glob('*.json')))} fixtures to {FIXTURES}")


if __name__ == "__main__":
    if os.environ.get("PYTHONHASHSEED") != HASH_SEED:
        os.execve(
            sys.executable, [sys.executable, *sys.argv], {**os.environ, "PYTHONHASHSEED": HASH_SEED}
        )
    main()
