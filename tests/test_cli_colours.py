"""python -m polished colours --recompute (cli.py): a mocked CDN, the manual override untouched."""

import httpx
from conftest import load_feed
from shade_data import apply, shade_id
from test_colour import bottle, near

from polished.catalog.colour import fill_colours
from polished.cli import _colours, main


def transport(seen, glass):
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=bottle(glass))

    return httpx.MockTransport(handle)


def test_recompute_reads_shades_again_but_never_the_override(settings, conn):
    apply(conn, load_feed())
    fill_colours(conn, transport=transport([], (200, 40, 90)))
    target = shade_id(conn, "thirst-trap")
    conn.execute("update shade set swatch_override_hex = '#123456' where id = ?", (target,))

    seen = []
    assert (
        _colours(settings, recompute=True, only=None, transport=transport(seen, (20, 160, 60))) == 0
    )
    assert seen and {r.url.host for r in seen} == {"cdn.shopify.com"}
    row = conn.execute("select * from shade where id = ?", (target,)).fetchone()
    assert near(row["swatch_hex"], (20, 160, 60))
    assert row["swatch_override_hex"] == "#123456"


def test_without_recompute_only_the_pending_shades_are_read(settings, conn):
    apply(conn, load_feed())
    fill_colours(conn, transport=transport([], (200, 40, 90)))
    seen = []
    assert (
        _colours(settings, recompute=False, only=None, transport=transport(seen, (0, 0, 255))) == 0
    )
    assert seen == []


def test_only_limits_the_recompute_to_the_named_titles(settings, conn):
    apply(conn, load_feed())
    fill_colours(conn, transport=transport([], (200, 40, 90)))
    target = shade_id(conn, "thirst-trap")
    title = conn.execute("select title from shade where id = ?", (target,)).fetchone()[0]
    seen = []
    _colours(
        settings, recompute=True, only=[title.upper()], transport=transport(seen, (20, 160, 60))
    )
    assert seen
    changed = conn.execute(
        "select id from shade where swatch_hex like '#1_a%' or swatch_hex like '#14%'"
    ).fetchall()
    assert [r[0] for r in changed] == [target]


def test_the_command_exists(settings, conn, monkeypatch):
    monkeypatch.setenv("POLISHED_DB_PATH", settings.db_path)
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    assert main(["colours", "--recompute", "--only", "Nothing Called This"]) == 0
