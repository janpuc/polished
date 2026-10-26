"""The release sheet applied to the catalog (DESIGN 5.6): enrichment, sheet-only shades, merging,
and a sync that survives a sheet that fails."""

import logging

import httpx
import pytest
from conftest import FIXTURES, load_feed
from shade_data import apply, made_from, seed

from polished.catalog import sheet as sheet_module
from polished.catalog.sheet import (
    SheetError,
    SheetRow,
    apply_sheet,
    fetch_sheet,
    merge_sheet_shade,
    parse_sheet,
)
from polished.catalog.sync import SyncRunner
from polished.cli import main
from polished.db import connect

SHEET_URL = "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=1"
SHEET_TEXT = (FIXTURES / "release_sheet_trimmed.csv").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def small_sheet(monkeypatch):
    """The fixture sheet has 13 rows, not 300+; tests of the minimum itself raise it again."""
    monkeypatch.setattr(sheet_module, "MIN_ROWS", 1)


def rows(text: str = SHEET_TEXT) -> list[SheetRow]:
    return parse_sheet(text)


def shade(conn, title):
    return conn.execute("select * from shade where title = ?", (title,)).fetchone()


@pytest.fixture
def seeded(conn):
    seed(conn)
    return conn


def sheet_row(name, released_on="2026-01-02", collection="A Collection", retired=False):
    return SheetRow(sheet_module.normalise_name(name), name, released_on, collection, retired)


# Shop shades get the sheet's facts


def test_matched_shades_get_date_collection_and_retired(seeded):
    counts = apply_sheet(seeded, rows())
    assert (counts.rows, counts.matched, counts.created, counts.merged) == (13, 7, 6, 0)
    royal = shade(seeded, "Royal-Tea Blue")
    assert (royal["released_on"], royal["official_collection"]) == (
        "2019-07-06",
        "Holo Taco Launch Collection",
    )
    assert royal["sheet_key"] == "royal tea blue"
    aurora = shade(seeded, "Aurora Unicorn Skin™")  # the shop's title has a ™, the sheet's not
    assert aurora["official_collection"] == "Holo Taco Unicorn Skin Collection"
    assert aurora["source"] == "holotaco"
    assert shade(seeded, "Sticky Base")["released_on"] is None  # not on the sheet
    assert counts.unlisted == ["Sticky Base"]


def test_a_shade_is_retired_when_either_the_shop_or_the_sheet_says_so(seeded):
    assert shade(seeded, "Hit The Lights")["retired"] == 0  # sold out, no retirement tag
    assert shade(seeded, "Gold Play Button")["retired"] == 1  # tagged
    apply_sheet(seeded, rows())
    hit = shade(seeded, "Hit The Lights")
    assert (hit["retired"], hit["sheet_retired"]) == (1, 1)  # the sheet only
    gold = shade(seeded, "Gold Play Button")
    assert (gold["retired"], gold["sheet_retired"]) == (1, 1)  # both
    assert shade(seeded, "Jam Session")["retired"] == 0  # soon-retiring is not retired
    assert shade(seeded, "Thirst Trap")["retired"] == 0


def test_the_sheet_unretires_only_what_the_shop_does_not_tag(seeded):
    apply_sheet(seeded, rows())
    changed = [
        sheet_row("Hit The Lights", "2026-07-11", "7th Anniversary Jackpot Collection", False),
        sheet_row("Gold Play Button", "2021-11-13", "Holo Taco Cristmas Collection", False),
    ]
    apply_sheet(seeded, changed)
    assert shade(seeded, "Hit The Lights")["retired"] == 0
    assert shade(seeded, "Gold Play Button")["retired"] == 1  # the shop's tag still says so


def test_a_product_change_in_the_feed_keeps_the_sheets_retirement(seeded):
    apply_sheet(seeded, rows())
    products = load_feed()
    next(p for p in products if p["handle"] == "hit-the-lights")["variants"][0]["price"] = "9.99"
    apply(seeded, products)
    hit = shade(seeded, "Hit The Lights")
    assert hit["price_cents"] == 999
    assert hit["retired"] == 1
    assert hit["released_on"] == "2026-07-11"


def test_the_shop_sync_alone_leaves_the_sheets_facts_in_place(seeded):
    apply_sheet(seeded, rows())
    before = seeded.execute("select id, released_on, official_collection from shade").fetchall()
    apply(seeded, load_feed())
    assert (
        seeded.execute("select id, released_on, official_collection from shade").fetchall()
        == before
    )


# Sheet-only shades


def test_a_row_the_shop_does_not_list_becomes_a_sheet_only_shade(seeded):
    apply_sheet(seeded, rows())
    silver = shade(seeded, "Silver Flake Taco")
    assert silver["source"] == "sheet"
    assert (silver["product_id"], silver["handle"], silver["sku"]) == (None, None, None)
    assert (silver["price_cents"], silver["available"], silver["hero_image_url"]) == (None,) * 3
    assert (silver["kind"], silver["released_on"]) == ("polish", "2022-12-06")
    assert silver["official_collection"] == "12 Days of Cristmas Release"
    assert silver["search_text"] == "silver flake taco"
    assert silver["swatch_hex"] is None and silver["swatch_override_hex"] is None


def test_sheet_only_toppers_are_found_by_name_and_retired_by_the_sheet(seeded):
    apply_sheet(seeded, rows())
    toppers = {
        r["title"]: r["is_topper"]
        for r in seeded.execute("select title, is_topper from shade where source = 'sheet'")
    }
    assert toppers == {
        "Silver Flake Taco": 1,
        "Red Flake Taco": 1,
        "Diamond Dasher Taco": 1,
        "Glow In The Dark Taco": 1,
        "Silent Night": 0,
        "Play Rosé": 0,
    }
    assert shade(seeded, "Red Flake Taco")["retired"] == 1
    assert shade(seeded, "Glow In The Dark Taco")["retired"] == 0  # "Seasonal"
    assert shade(seeded, "Play Rosé")["search_text"] == "play rose"


def test_a_second_run_changes_nothing_and_creates_no_second_shade(seeded):
    apply_sheet(seeded, rows())
    dump = seeded.execute("select * from shade order by id").fetchall()
    counts = apply_sheet(seeded, rows())
    assert (counts.created, counts.merged, counts.matched) == (0, 0, 7)
    assert seeded.execute("select * from shade order by id").fetchall() == dump
    assert seeded.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6


def test_shades_that_leave_the_sheet_are_not_deleted(seeded):
    apply_sheet(seeded, rows())
    total = seeded.execute("select count(*) from shade").fetchone()[0]
    apply_sheet(seeded, [sheet_row("Royal-Tea Blue", "2019-07-06", "Holo Taco Launch Collection")])
    assert seeded.execute("select count(*) from shade").fetchone()[0] == total
    assert shade(seeded, "Silver Flake Taco")["released_on"] == "2022-12-06"


def test_a_sheet_only_shade_follows_its_row(seeded):
    apply_sheet(
        seeded, [sheet_row("Silent Night", "2025-11-15", "Mini Advent Calendar Collection")]
    )
    apply_sheet(seeded, [sheet_row("Silent Night", "2025-11-16", "Advent", True)])
    night = shade(seeded, "Silent Night")
    assert (night["released_on"], night["official_collection"], night["retired"]) == (
        "2025-11-16",
        "Advent",
        1,
    )
    assert (
        seeded.execute("select count(*) from shade where title = 'Silent Night'").fetchone()[0] == 1
    )


def test_an_alias_points_a_sheet_name_at_a_differently_named_shop_shade(seeded, monkeypatch):
    monkeypatch.setattr(sheet_module, "ALIASES", {"thirsty trap": "thirst trap"})
    counts = apply_sheet(seeded, [sheet_row("Thirsty Trap", "2025-10-04", "Holoween Collection")])
    assert (counts.matched, counts.created) == (1, 0)
    assert shade(seeded, "Thirst Trap")["official_collection"] == "Holoween Collection"
    assert seeded.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 0


def test_a_polish_beats_a_top_coat_of_the_same_name(conn):
    top = made_from("aurora-unicorn-skin", 1, "Twin Shade")
    polish = made_from("thirst-trap", 2, "Twin Shade")
    polish["handle"] = "twin-shade-polish"
    seed(conn, [top, polish])
    apply_sheet(conn, [sheet_row("Twin Shade", "2024-01-01", "Twins")])
    kinds = dict(
        conn.execute("select kind, official_collection from shade where title = 'Twin Shade'")
    )
    assert kinds == {"topcoat": None, "polish": "Twins"}


def test_too_many_unmatched_rows_mean_the_names_changed_and_nothing_is_written(seeded):
    many = [sheet_row(f"Shade Number {n}") for n in range(sheet_module.MAX_NEW_SHEET_SHADES + 1)]
    before = seeded.execute("select * from shade order by id").fetchall()
    with pytest.raises(SheetError, match="names probably changed"):
        apply_sheet(seeded, [sheet_row("Royal-Tea Blue"), *many])
    assert seeded.execute("select * from shade order by id").fetchall() == before
    assert not seeded.in_transaction


# Merging


def own_a_sheet_only_shade(conn):
    """A sheet-only Silver Flake Taco with a bottle, a stack layer, a learned code, a wish, an
    alias and a tip colour of the household's own."""
    apply_sheet(conn, rows())
    sheet_id = shade(conn, "Silver Flake Taco")["id"]
    conn.execute("insert into bottle (shade_id, printed_code) values (?, 'P99')", (sheet_id,))
    stack = conn.execute("insert into stack default values").lastrowid
    conn.execute(
        "insert into stack_layer (stack_id, ord, shade_id) values (?, 1, ?)", (stack, sheet_id)
    )
    conn.execute(
        "insert into shade_identifier (kind, value, shade_id) values ('printed', 'P99', ?)",
        (sheet_id,),
    )
    conn.execute(
        "insert into wishlist_item (shade_id, priority, note) values (?, 3, 'for winter')",
        (sheet_id,),
    )
    conn.execute("update shade set swatch_override_hex = '#c0c0c0' where id = ?", (sheet_id,))
    return sheet_id, stack


def appears_in_the_shop(conn, title="Silver Flake Taco™"):
    apply(conn, [*load_feed(), made_from("thirst-trap", 50, title)])
    return shade(conn, title)


def test_a_sheet_only_shade_is_merged_onto_the_shop_shade_that_appears(seeded):
    sheet_id, stack = own_a_sheet_only_shade(seeded)
    shop = appears_in_the_shop(seeded)
    assert shop["source"] == "holotaco" and shop["id"] != sheet_id
    counts = apply_sheet(seeded, rows())
    assert (counts.merged, counts.created) == (1, 0)

    assert seeded.execute("select count(*) from shade where id = ?", (sheet_id,)).fetchone()[0] == 0
    assert (
        seeded.execute("select count(*) from shade where title like 'Silver Flake%'").fetchone()[0]
        == 1
    )
    merged = shade(seeded, "Silver Flake Taco™")
    assert merged["id"] == shop["id"]
    assert (merged["released_on"], merged["official_collection"]) == (
        "2022-12-06",
        "12 Days of Cristmas Release",
    )
    assert merged["swatch_override_hex"] == "#c0c0c0"
    assert seeded.execute("select shade_id from bottle").fetchall()[0][0] == shop["id"]
    assert (
        seeded.execute("select shade_id from stack_layer where stack_id = ?", (stack,)).fetchone()[
            0
        ]
        == shop["id"]
    )
    assert seeded.execute("select shade_id from shade_identifier").fetchone()[0] == shop["id"]
    wish = seeded.execute("select shade_id, priority, note from wishlist_item").fetchall()
    assert [tuple(r) for r in wish] == [(shop["id"], 3, "for winter")]
    assert seeded.execute("pragma foreign_key_check").fetchall() == []
    status = seeded.execute(
        "select * from shade_status where shade_id = ?", (shop["id"],)
    ).fetchone()
    assert (status["bottle_count"], status["wishlisted"]) == (1, 1)


def test_merging_keeps_the_better_priority_and_the_notes_of_a_shade_wished_twice(seeded):
    sheet_id, _ = own_a_sheet_only_shade(seeded)
    shop = appears_in_the_shop(seeded)
    seeded.execute(
        "insert into wishlist_item (shade_id, priority, note) values (?, 1, null)", (shop["id"],)
    )
    merge_sheet_shade(seeded, sheet_id, shop["id"])
    (item,) = seeded.execute("select shade_id, priority, note from wishlist_item").fetchall()
    assert tuple(item) == (shop["id"], 1, "for winter")


def test_merging_does_not_overwrite_a_tip_colour_the_shop_shade_already_has(seeded):
    sheet_id, _ = own_a_sheet_only_shade(seeded)
    shop = appears_in_the_shop(seeded)
    seeded.execute("update shade set swatch_override_hex = '#111111' where id = ?", (shop["id"],))
    merge_sheet_shade(seeded, sheet_id, shop["id"])
    assert shade(seeded, "Silver Flake Taco™")["swatch_override_hex"] == "#111111"


def test_the_merge_handles_every_table_that_points_at_a_shade(conn):
    handled = {"bottle", "stack_layer", "shade_identifier", "shade_alias", "wishlist_item"}
    deleted_with_the_row = {"shade_tag"}  # a sheet-only shade has none
    pointing = {
        row["name"]
        for row in conn.execute("select name from sqlite_master where type = 'table'")
        if any(
            fk["table"] == "shade" for fk in conn.execute(f"pragma foreign_key_list({row['name']})")
        )
    }
    assert pointing == handled | deleted_with_the_row


# The runner: fetch, order, tolerance


def store_transport(calls):
    def handler(request):
        calls.append(("shop", str(request.url)))
        return httpx.Response(200, json={"products": load_feed()})

    return httpx.MockTransport(handler)


def sheet_transport(calls, respond):
    def handler(request):
        calls.append(("sheet", str(request.url)))
        return respond(request)

    return httpx.MockTransport(handler)


def colour_refused():
    return httpx.MockTransport(lambda request: httpx.Response(404))


def runner_for(tmp_path, calls, respond, url=SHEET_URL, **overrides):
    from conftest import make_settings

    settings = make_settings(tmp_path, release_sheet_url=url, **overrides)
    return SyncRunner(
        settings,
        transport=store_transport(calls),
        sheet_transport=sheet_transport(calls, respond),
        colour_transport=colour_refused(),
    )


@pytest.fixture
def sheet_ok():
    return lambda request: httpx.Response(
        200, text=SHEET_TEXT, headers={"content-type": "text/csv"}
    )


async def test_a_run_fetches_the_sheet_once_after_the_shop_pages(
    conn, settings, tmp_path, sheet_ok
):
    calls = []
    runner = runner_for(tmp_path, calls, sheet_ok)
    outcome = await runner.run("schedule")
    assert outcome.status == "ok"
    assert [kind for kind, _ in calls] == ["shop", "sheet"]
    assert calls[1][1] == SHEET_URL
    check = connect(settings.db_path)
    assert shade(check, "Thirst Trap")["official_collection"] == "Holoween Collection"
    assert check.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6
    check.close()


async def test_the_sheet_request_says_who_is_asking(tmp_path):
    seen = []

    def respond(request):
        seen.append(request.headers)
        return httpx.Response(200, text=SHEET_TEXT)

    text = await fetch_sheet(SHEET_URL, version="1.2.3", transport=sheet_transport([], respond))
    assert text.startswith(",,,")
    assert seen[0]["user-agent"] == "polished/1.2.3 (+https://github.com/janpuc/polished)"


async def test_google_redirect_to_googleusercontent_is_followed(tmp_path):
    hops = []

    def respond(request):
        hops.append(request.url.host)
        if request.url.host == "docs.google.com":
            return httpx.Response(
                307, headers={"location": "https://doc-0k-sheets.googleusercontent.com/export/x"}
            )
        return httpx.Response(200, content="\ufeff".encode() + SHEET_TEXT.encode())

    text = await fetch_sheet(SHEET_URL, version="x", transport=sheet_transport([], respond))
    assert hops == ["docs.google.com", "doc-0k-sheets.googleusercontent.com"]
    assert text.startswith(",,,")  # the byte order mark is gone


@pytest.mark.parametrize(
    "respond",
    [
        lambda r: httpx.Response(307, headers={"location": "https://evil.example.test/x"}),
        lambda r: httpx.Response(
            307, headers={"location": "http://doc-0k.googleusercontent.com/x"}
        ),
        lambda r: httpx.Response(302, headers={"location": SHEET_URL}),  # a loop
        lambda r: httpx.Response(429),
        lambda r: httpx.Response(503),
        lambda r: httpx.Response(200, content=b"x" * (sheet_module.MAX_BYTES + 1)),
        lambda r: httpx.Response(200, content=b"\xff\xfe\x00bad"),
    ],
)
async def test_a_sheet_that_cannot_be_fetched_is_a_sheet_error(respond):
    with pytest.raises(SheetError):
        await fetch_sheet(SHEET_URL, version="x", transport=sheet_transport([], respond))


async def test_a_transport_error_is_a_sheet_error():
    def refuse(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(SheetError, match="request failed"):
        await fetch_sheet(SHEET_URL, version="x", transport=sheet_transport([], refuse))


def failing_sheets():
    def broken_transport(request):
        raise httpx.ReadTimeout("slow")

    return {
        "403": lambda r: httpx.Response(403),
        "429": lambda r: httpx.Response(429),
        "503": lambda r: httpx.Response(503),
        "timeout": broken_transport,
        "login page": lambda r: httpx.Response(200, text="<html><body>Sign in</body></html>"),
        "no header": lambda r: httpx.Response(200, text="a,b\n1,2\n"),
        "no collection column": lambda r: httpx.Response(
            200, text='Release date,Shade name,Retired?\n"Jul 6, 2019",Royal-Tea Blue,\n'
        ),
    }


@pytest.mark.parametrize("name", list(failing_sheets()))
async def test_a_sheet_that_fails_changes_nothing_and_the_sync_is_still_ok(
    name, conn, settings, tmp_path, caplog
):
    calls = []
    runner = runner_for(tmp_path, calls, failing_sheets()[name])
    with caplog.at_level(logging.WARNING, logger="polished.sync"):
        outcome = await runner.run("schedule")
    assert outcome.status == "ok"
    assert "release sheet skipped" in caplog.text
    check = connect(settings.db_path)
    assert check.execute("select count(*) from shade").fetchone()[0] == 9
    assert (
        check.execute(
            "select count(*) from shade where released_on is not null or source = 'sheet'"
        ).fetchone()[0]
        == 0
    )
    assert check.execute("select status from sync_run").fetchone()[0] == "ok"
    check.close()


async def test_a_sheet_with_too_few_rows_is_not_applied(
    conn, settings, tmp_path, sheet_ok, monkeypatch
):
    monkeypatch.setattr(sheet_module, "MIN_ROWS", 300)
    runner = runner_for(tmp_path, [], sheet_ok)
    assert (await runner.run("schedule")).status == "ok"
    check = connect(settings.db_path)
    assert (
        check.execute("select count(*) from shade where released_on is not null").fetchone()[0] == 0
    )
    check.close()


async def test_a_failing_sheet_leaves_what_an_earlier_run_stored(
    conn, settings, tmp_path, sheet_ok
):
    good = runner_for(tmp_path, [], sheet_ok)
    assert (await good.run("schedule")).status == "ok"
    bad = runner_for(tmp_path, [], lambda r: httpx.Response(503))
    assert (await bad.run("schedule")).status == "ok"
    check = connect(settings.db_path)
    assert shade(check, "Hit The Lights")["retired"] == 1
    assert check.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6
    check.close()


async def test_a_bug_in_the_sheet_step_cannot_fail_the_sync(
    conn, tmp_path, sheet_ok, monkeypatch, caplog
):
    def boom(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr("polished.catalog.sync.apply_sheet", boom)
    runner = runner_for(tmp_path, [], sheet_ok)
    with caplog.at_level(logging.WARNING, logger="polished.sync"):
        assert (await runner.run("schedule")).status == "ok"
    assert "release sheet step failed" in caplog.text


async def test_an_empty_url_turns_the_sheet_off(conn, tmp_path, sheet_ok):
    calls = []
    runner = runner_for(tmp_path, calls, sheet_ok, url="")
    assert (await runner.run("schedule")).status == "ok"
    assert [kind for kind, _ in calls] == ["shop"]


async def test_a_run_from_files_stays_offline_unless_given_a_sheet_file(
    conn, settings, tmp_path, feed, sheet_ok
):
    import json

    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": feed}), encoding="utf-8")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text(SHEET_TEXT, encoding="utf-8")
    calls = []
    runner = runner_for(tmp_path, calls, sheet_ok)

    assert (await runner.run("cli", [page])).status == "ok"
    assert calls == []
    assert (
        conn.execute("select count(*) from shade where released_on is not null").fetchone()[0] == 0
    )

    assert (await runner.run("cli", [page], sheet)).status == "ok"
    assert calls == []
    assert (
        conn.execute("select count(*) from shade where released_on is not null").fetchone()[0] == 13
    )
    assert conn.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6


async def test_a_missing_sheet_file_is_a_warning_not_a_failure(conn, tmp_path, feed, caplog):
    import json

    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": feed}), encoding="utf-8")
    runner = runner_for(tmp_path, [], lambda r: httpx.Response(500))
    with caplog.at_level(logging.WARNING, logger="polished.sync"):
        outcome = await runner.run("cli", [page], tmp_path / "nowhere.csv")
    assert outcome.status == "ok"
    assert "release sheet skipped" in caplog.text


def test_the_sync_command_reads_the_sheet_file(tmp_path, monkeypatch, capsys, feed):
    import json

    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": feed}), encoding="utf-8")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text(SHEET_TEXT, encoding="utf-8")
    monkeypatch.setenv("POLISHED_DB_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    assert main(["migrate"]) == 0
    assert main(["sync", "--from-files", str(page), "--sheet", str(sheet)]) == 0
    conn = connect(str(tmp_path / "cli.db"))
    assert (
        shade(conn, "Hit The Lights")["official_collection"] == "7th Anniversary Jackpot Collection"
    )
    assert conn.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6
    assert main(["sync", "--from-files", str(page), "--sheet", str(sheet)]) == 0
    assert conn.execute("select count(*) from shade where source = 'sheet'").fetchone()[0] == 6
    conn.close()


def test_the_default_url_and_an_empty_one(tmp_path):
    from conftest import make_settings

    from polished.config import RELEASE_SHEET_URL, Settings

    assert (
        Settings(
            _env_file=None, public_url="http://localhost:8080", auth_mode="none"
        ).release_sheet_url
        == RELEASE_SHEET_URL
    )
    assert make_settings(tmp_path, release_sheet_url="").release_sheet_url == ""
    with pytest.raises(ValueError, match="http"):
        make_settings(tmp_path, release_sheet_url="ftp://example.test/x.csv")
