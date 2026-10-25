"""Catalog rows for the browse tests: the 16-product fixture feed plus products made from it."""

import copy
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from conftest import load_feed

from polished.catalog.sync import apply_feed, format_time

NOW = datetime(2026, 10, 25, 4, 5, 38, tzinfo=UTC)


def apply(conn, products, now=NOW):
    run_id = conn.execute(
        "insert into sync_run (started_at, trigger, status) values (?, 'cli', 'running')",
        (format_time(now),),
    ).lastrowid
    return apply_feed(conn, run_id, [products], now, ZoneInfo("Europe/Warsaw"))


def made_from(handle, number, title, tags=None, available=True, price="15.50", published=None):
    """A shade-like product copied from a fixture product, with its own ids, title and handle."""
    product = copy.deepcopy(next(p for p in load_feed() if p["handle"] == handle))
    product["id"] = 7_000_000_000 + number
    product["handle"] = title.lower().replace(" ", "-")
    product["title"] = title
    variant = product["variants"][0]
    variant["id"] = 6_000_000_000 + number
    variant["sku"] = f"HL-T{number:04d}-NP"
    variant["available"] = available
    variant["price"] = price
    if tags is not None:
        product["tags"] = tags
    if published:
        product["published_at"] = published
    return product


def seed(conn, extra=()):
    """The fixture feed plus `extra` products, applied in one sync."""
    apply(conn, [*load_feed(), *extra])


def shade_id(conn, handle):
    return conn.execute("select id from shade where handle = ?", (handle,)).fetchone()["id"]


def handles(page):
    """Handles in row order, read back through the title (handles equal slugged titles)."""
    return [row["title"] for row in page.rows]
