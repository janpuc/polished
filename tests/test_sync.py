import copy
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import synthetic_products

from polished.catalog.fetch import FeedError
from polished.catalog.hashing import EXCLUDED_FROM_HASH, content_hash
from polished.catalog.sync import SyncRunner, apply_feed, format_time
from polished.cli import main
from polished.db import connect

TZ = ZoneInfo("Europe/Warsaw")
START = datetime(2026, 10, 25, 4, 5, 38, tzinfo=UTC)


class Syncer:
    """Applies feeds the way a run does: a running row, apply_feed, one day later each time."""

    def __init__(self, conn):
        self.conn = conn
        self.now = START

    def apply(self, products):
        run_id = self.conn.execute(
            "insert into sync_run (started_at, trigger, status) values (?, 'cli', 'running')",
            (format_time(self.now),),
        ).lastrowid
        counts = apply_feed(self.conn, run_id, [products], self.now, TZ)
        self.now += timedelta(days=1)
        return counts


@pytest.fixture
def syncer(conn):
    return Syncer(conn)


def product_row(conn, handle):
    return conn.execute("select * from product where handle = ?", (handle,)).fetchone()


def shade_row(conn, handle):
    return conn.execute("select * from shade where handle = ?", (handle,)).fetchone()


def by_handle(feed, handle):
    return next(p for p in feed if p["handle"] == handle)


def table_dump(conn):
    """Every catalog table's rows, minus product.last_seen (the one column a rerun moves)."""
    dump = {}
    for table in ("product", "shade", "shade_alias", "shade_tag"):
        rows = conn.execute(f"select * from {table} order by 1, 2").fetchall()
        dump[table] = [{k: v for k, v in dict(r).items() if k != "last_seen"} for r in rows]
    return dump


def test_the_fixture_lands_in_the_expected_rows(syncer, conn, feed):
    counts = syncer.apply(feed)
    assert (counts.products_seen, counts.new_shades, counts.changed_shades) == (16, 9, 0)
    roles = dict(conn.execute("select role, count(*) from product group by role").fetchall())
    assert roles == {"shade": 9, "bundle": 2, "alias": 4, "skipped": 1}
    kinds = dict(conn.execute("select kind, count(*) from shade group by kind").fetchall())
    assert kinds == {"polish": 7, "topcoat": 1, "basecoat": 1}


def test_shade_fields_are_copied_from_the_product(syncer, conn, feed):
    syncer.apply(feed)
    shade = shade_row(conn, "thirst-trap")
    source = by_handle(feed, "thirst-trap")
    assert shade["title"] == source["title"]
    assert shade["sku"] == source["variants"][0]["sku"]
    assert shade["price_cents"] == 1550
    assert shade["compare_at_cents"] == 1550
    assert shade["available"] == 1
    assert shade["hero_image_url"] == source["images"][0]["src"]
    assert shade["source"] == "holotaco"
    assert "thirst trap" in shade["search_text"]
    tags = conn.execute(
        "select ns, value from shade_tag where shade_id = ? order by ns, value", (shade["id"],)
    ).fetchall()
    assert all(r["ns"] in ("finish", "color", "collection") for r in tags)
    assert len(tags) == sum(
        1 for t in source["tags"] if t.split(":")[0] in ("finish", "color", "collection")
    )


def test_product_row_keeps_the_feed_without_the_description(syncer, conn, feed):
    feed[0]["body_html"] = "<p>long text</p>"
    syncer.apply(feed)
    row = product_row(conn, feed[0]["handle"])
    assert "body_html" not in json.loads(row["raw_json"])
    assert json.loads(row["tags_json"]) == feed[0]["tags"]


def test_is_topper_retired_and_retiring_follow_the_tags(syncer, conn, feed):
    syncer.apply(feed)
    flags = {
        r["handle"]: (r["is_topper"], r["retired"], r["retiring"])
        for r in conn.execute("select * from shade")
    }
    assert flags["aurora-unicorn-skin"] == (1, 0, 0)  # Top Coat
    assert flags["sticky-base"][0] == 1  # polish tagged color:clear
    assert flags["peely-base"][0] == 0  # a Base Coat is not a topper
    assert flags["thirst-trap"] == (0, 0, 0)
    assert flags["gold-play-button"] == (0, 1, 0)
    assert flags["jam-session"] == (0, 0, 1)


def test_the_on_sale_fixture_shade_has_compare_at_above_price(syncer, conn, feed):
    syncer.apply(feed)
    shade = shade_row(conn, "rest-in-peach")
    assert shade["price_cents"] < shade["compare_at_cents"]


def test_aliases_resolve_by_handle_and_by_the_manual_list(syncer, conn, feed):
    counts = syncer.apply(feed)
    links = {
        r["handle"]: (r["target"], r["source"])
        for r in conn.execute(
            "select p.handle, s.handle as target, a.source from shade_alias a"
            " join product p on p.id = a.product_id join shade s on s.id = a.shade_id"
        )
    }
    assert links == {
        "thirst-trap-birthday-gift": ("thirst-trap", "handle"),
        "aurora-unicorn-skin-birthday-gift": ("aurora-unicorn-skin", "handle"),
        "royal-tea-blue-birthday-gift": ("royal-tea-blue-2021", "manual"),
    }
    assert counts.unresolved_aliases == 1  # the Linear Holo Taco gift: no such shade in the fixture


def test_an_unresolved_alias_resolves_on_a_later_run(syncer, conn, feed):
    assert syncer.apply(feed).unresolved_aliases == 1
    linear = copy.deepcopy(by_handle(feed, "thirst-trap"))
    linear.update(id=1, handle="linear-holo-taco", title="Linear Holo Taco")
    linear["variants"][0]["id"] = 2
    counts = syncer.apply([*feed, linear])
    assert counts.unresolved_aliases == 0
    gift = product_row(conn, "linear-holo-taco™-birthday-gift")
    link = conn.execute("select * from shade_alias where product_id = ?", (gift["id"],)).fetchone()
    assert (link["source"], shade_row(conn, "linear-holo-taco")["id"]) == (
        "manual",
        link["shade_id"],
    )


def test_a_second_run_over_the_same_feed_reports_changed_shades_0_and_changes_nothing(
    syncer, conn, feed
):
    syncer.apply(feed)
    before = table_dump(conn)
    counts = syncer.apply(feed)
    assert (counts.new_shades, counts.changed_shades) == (0, 0)
    assert (counts.newly_missing, counts.returned) == (0, 0)
    assert table_dump(conn) == before


def test_a_price_change_propagates_to_the_shade(syncer, conn, feed):
    syncer.apply(feed)
    by_handle(feed, "thirst-trap")["variants"][0]["price"] = "17.25"
    counts = syncer.apply(feed)
    assert counts.changed_shades == 1
    assert shade_row(conn, "thirst-trap")["price_cents"] == 1725
    assert product_row(conn, "thirst-trap")["price_cents"] == 1725


def test_an_availability_change_propagates_to_the_shade(syncer, conn, feed):
    syncer.apply(feed)
    by_handle(feed, "thirst-trap")["variants"][0]["available"] = False
    syncer.apply(feed)
    assert shade_row(conn, "thirst-trap")["available"] == 0


def test_a_retirement_tag_change_propagates_to_the_shade(syncer, conn, feed):
    syncer.apply(feed)
    by_handle(feed, "thirst-trap")["tags"] += ["collection:soon-retiring"]
    syncer.apply(feed)
    shade = shade_row(conn, "thirst-trap")
    assert (shade["retiring"], shade["retired"]) == (1, 0)
    by_handle(feed, "thirst-trap")["tags"] += ["collection:retirement"]
    syncer.apply(feed)
    assert shade_row(conn, "thirst-trap")["retired"] == 1
    tags = {r["value"] for r in conn.execute("select value from shade_tag where ns = 'collection'")}
    assert {"retirement", "soon-retiring"} <= tags


def test_a_dropped_tag_is_dropped_from_shade_tag(syncer, conn, feed):
    syncer.apply(feed)
    shade_id = shade_row(conn, "thirst-trap")["id"]
    feed_shade = by_handle(feed, "thirst-trap")
    feed_shade["tags"] = [t for t in feed_shade["tags"] if not t.startswith("finish:")]
    syncer.apply(feed)
    count = conn.execute(
        "select count(*) from shade_tag where shade_id = ? and ns = 'finish'", (shade_id,)
    ).fetchone()[0]
    assert count == 0


def test_a_product_missing_for_three_runs_gets_missing_since(syncer, conn, feed):
    syncer.apply(feed)
    gone = [p for p in feed if p["handle"] != "hit-the-lights"]
    assert syncer.apply(gone).newly_missing == 0
    assert syncer.apply(gone).newly_missing == 0
    row = product_row(conn, "hit-the-lights")
    assert (row["absent_syncs"], row["missing_since"]) == (2, None)
    assert syncer.apply(gone).newly_missing == 1
    row = product_row(conn, "hit-the-lights")
    assert (row["absent_syncs"], row["missing_since"]) == (3, "2026-10-28")
    assert syncer.apply(gone).newly_missing == 0  # counted once
    assert product_row(conn, "hit-the-lights")["missing_since"] == "2026-10-28"


def test_a_feed_below_70_percent_of_the_last_one_counts_nothing_as_absent(syncer, conn):
    syncer.apply(synthetic_products(100))
    counts = syncer.apply(synthetic_products(69))
    assert counts.newly_missing == 0
    assert conn.execute("select max(absent_syncs) from product").fetchone()[0] == 0
    # The next run is measured against the last successful run, so a shrink that lasts is believed.
    syncer.apply(synthetic_products(69))
    assert conn.execute("select max(absent_syncs) from product").fetchone()[0] == 1


def test_a_feed_at_70_percent_still_counts_absences(syncer, conn):
    syncer.apply(synthetic_products(100))
    syncer.apply(synthetic_products(70))
    assert conn.execute("select max(absent_syncs) from product").fetchone()[0] == 1


def test_a_returning_product_clears_missing_since(syncer, conn, feed):
    syncer.apply(feed)
    gone = [p for p in feed if p["handle"] != "hit-the-lights"]
    for _ in range(3):
        syncer.apply(gone)
    assert product_row(conn, "hit-the-lights")["missing_since"] is not None
    counts = syncer.apply(feed)
    assert counts.returned == 1
    row = product_row(conn, "hit-the-lights")
    assert (row["missing_since"], row["absent_syncs"]) == (None, 0)
    assert counts.changed_shades == 0


def test_no_shade_row_is_ever_deleted(syncer, conn, feed):
    syncer.apply(feed)
    shades = conn.execute("select count(*) from shade").fetchone()[0]
    for _ in range(5):
        syncer.apply([by_handle(feed, "super-magnet")])
    assert conn.execute("select count(*) from shade").fetchone()[0] == shades
    assert conn.execute("select count(*) from product").fetchone()[0] == len(feed)


def test_an_empty_feed_is_refused_and_writes_nothing(syncer, conn):
    with pytest.raises(FeedError, match="no products"):
        syncer.apply([])
    assert conn.execute("select count(*) from product").fetchone()[0] == 0


def test_absence_accounting_uses_the_last_successful_run_only(syncer, conn):
    syncer.apply(synthetic_products(100))
    conn.execute(
        "insert into sync_run (started_at, trigger, status, products_seen)"
        " values ('2026-10-26T00:00:00Z', 'cli', 'error', 5)"
    )
    syncer.apply(synthetic_products(80))
    assert conn.execute("select max(absent_syncs) from product").fetchone()[0] == 1


def test_the_run_row_is_closed_with_the_counts(syncer, conn, feed):
    syncer.apply(feed)
    run = conn.execute("select * from sync_run").fetchone()
    assert (run["status"], run["pages_fetched"], run["products_seen"]) == ("ok", 1, 16)
    assert (run["new_shades"], run["unresolved_aliases"]) == (9, 1)
    assert run["finished_at"] == "2026-10-25T04:05:38Z"


def test_hash_ignores_updated_at_and_body_html(feed):
    product = by_handle(feed, "thirst-trap")
    before = content_hash(product)
    changed = copy.deepcopy(product)
    changed["updated_at"] = "2030-01-01T00:00:00-04:00"
    changed["body_html"] = "<p>new copy</p>"
    changed["variants"][0]["updated_at"] = "2030-01-01"
    assert content_hash(changed) == before
    assert {"updated_at", "body_html"} == EXCLUDED_FROM_HASH


@pytest.mark.parametrize(
    "edit",
    [
        lambda p: p["variants"][0].update(price="99.00"),
        lambda p: p["variants"][0].update(compare_at_price="99.00"),
        lambda p: p["variants"][0].update(available=not p["variants"][0]["available"]),
        lambda p: p["variants"][0].update(sku="HL-99999-NP"),
        lambda p: p["tags"].append("collection:soon-retiring"),
        lambda p: p["images"][0].update(src=p["images"][0]["src"] + "9"),
        lambda p: p.update(title="Another title"),
        lambda p: p.update(handle="another-handle"),
        lambda p: p.update(published_at="2030-01-01T00:00:00-04:00"),
    ],
)
def test_hash_changes_on_price_availability_tags_and_image_src(feed, edit):
    product = by_handle(feed, "thirst-trap")
    before = content_hash(product)
    changed = copy.deepcopy(product)
    edit(changed)
    assert content_hash(changed) != before


def test_hash_does_not_depend_on_tag_order(feed):
    product = by_handle(feed, "thirst-trap")
    shuffled = copy.deepcopy(product)
    shuffled["tags"].reverse()
    assert content_hash(shuffled) == content_hash(product)


async def test_a_run_from_files_applies_the_pages(tmp_path, settings, conn, feed):
    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": feed}), encoding="utf-8")
    runner = SyncRunner(settings)
    outcome = await runner.run("cli", [page])
    assert outcome.status == "ok"
    assert conn.execute("select count(*) from shade").fetchone()[0] == 9
    broken = tmp_path / "broken.json"
    broken.write_text("not json")
    failed = await runner.run("cli", [broken])
    assert failed.status == "error"
    assert "not a products feed" in failed.error


def test_the_sync_command_applies_local_pages_and_a_second_run_changes_nothing(
    tmp_path, monkeypatch, capsys, feed
):
    page = tmp_path / "page.json"
    page.write_text(json.dumps({"products": feed}), encoding="utf-8")
    db = tmp_path / "cli.db"
    monkeypatch.setenv("POLISHED_DB_PATH", str(db))
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    assert main(["migrate"]) == 0
    assert main(["sync", "--from-files", str(page)]) == 0
    assert "9 new shades" in capsys.readouterr().out
    assert main(["sync", "--from-files", str(page)]) == 0
    assert "0 changed" in capsys.readouterr().out
    conn = connect(str(db))
    assert (
        conn.execute("select changed_shades from sync_run order by id desc limit 1").fetchone()[0]
        == 0
    )
    conn.close()


def test_the_sync_command_fails_on_an_unmigrated_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("POLISHED_DB_PATH", str(tmp_path / "none.db"))
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    assert main(["sync", "--from-files", str(tmp_path / "missing.json")]) == 1
    assert "migrate" in capsys.readouterr().err
