"""Applying the feed to the database (DESIGN 5.2), and running a sync (DESIGN 5.1).

apply_feed() is the algorithm, one transaction over pages already in memory. SyncRunner wraps it
with the single-flight lock, the sync_run row, the fetch and the cooldown, then reads the release
sheet (DESIGN 5.6) and the polish colours.
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from ..config import Settings
from ..db import connect, transaction
from .classify import classify
from .colour import fill_colours
from .fetch import Clock, FeedError, Sleep, fetch_feed
from .hashing import content_hash
from .parse import (
    RETIRED_TAG,
    RETIRING_TAG,
    hero_image_url,
    is_topper,
    parse_compare_at_cents,
    parse_price_cents,
    search_text,
    swatch_image_url,
    tag_pairs,
)
from .sheet import (
    SheetCounts,
    SheetError,
    SheetRow,
    apply_sheet,
    fetch_sheet,
    parse_sheet,
    refresh_retired,
)

log = logging.getLogger("polished.sync")

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ABSENT_SYNCS_MISSING = 3  # consecutive absent syncs before a product counts as not listed
TRUST_RATIO = 0.7  # a feed smaller than this share of the last one is not believed
STALE_RUNNING_S = 3600  # a `running` row older than this belongs to a dead process


def format_time(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(TIME_FORMAT)


def parse_time(text: str) -> datetime:
    return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class SyncCounts:
    products_seen: int = 0
    new_shades: int = 0
    changed_shades: int = 0
    newly_missing: int = 0
    returned: int = 0
    unresolved_aliases: int = 0


@dataclass(frozen=True)
class RunOutcome:
    run_id: int
    status: str  # ok | error
    error: str | None = None
    retryable: bool = False


class RunRefused(Exception):
    """A run was not started: 409 while another is running, 429 inside the manual cooldown."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class _Parsed:
    """The facts of one feed product that go into its product row."""

    product: dict
    variant: dict
    role: str
    content_hash: str
    raw_json: str
    kind: str | None


def _parse(product: dict) -> _Parsed | None:
    variants = product.get("variants") or []
    if not variants:
        log.warning(
            "product %s (%s) has no variants; skipped", product.get("id"), product.get("handle")
        )
        return None
    if len(variants) > 1:
        log.warning("product %s has %d variants; using the first", product["id"], len(variants))
    variant = variants[0]
    classification = classify(product)
    stored = {key: value for key, value in product.items() if key != "body_html"}
    return _Parsed(
        product=product,
        variant=variant,
        role=classification.role,
        content_hash=content_hash(product),
        raw_json=json.dumps(stored, ensure_ascii=False, separators=(",", ":")),
        kind=classification.kind,
    )


def _upsert_shade(conn: sqlite3.Connection, product_row_id: int, parsed: _Parsed) -> bool:
    """Writes the shade for a product, with its tags; True when the shade is new."""
    product, variant = parsed.product, parsed.variant
    kind, tags = parsed.kind, product["tags"]
    pairs = tag_pairs(tags)
    values = {
        "kind": kind,
        "title": product["title"],
        "handle": product["handle"],
        "sku": variant.get("sku"),
        "search_text": search_text(product["title"], product["handle"], [v for _, v in pairs]),
        "hero_image_url": hero_image_url(product.get("images", [])),
        "swatch_image_url": swatch_image_url(product.get("images", []), product["title"]),
        "price_cents": parse_price_cents(variant.get("price")),
        "compare_at_cents": parse_compare_at_cents(variant.get("compare_at_price")),
        "available": int(bool(variant.get("available"))),
        "published_at": product.get("published_at"),
        "is_topper": int(is_topper(kind, tags)),
        "retired": int(RETIRED_TAG in tags),
        "retiring": int(RETIRING_TAG in tags),
    }
    row = conn.execute("select id from shade where product_id = ?", (product_row_id,)).fetchone()
    if row is None:
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        shade_id = conn.execute(
            f"insert into shade (product_id, {columns}) values (?, {marks})",
            (product_row_id, *values.values()),
        ).lastrowid
    else:
        shade_id = row["id"]
        assignments = ", ".join(f"{column} = ?" for column in values)
        conn.execute(f"update shade set {assignments} where id = ?", (*values.values(), shade_id))
        conn.execute("delete from shade_tag where shade_id = ?", (shade_id,))
    conn.executemany(
        "insert into shade_tag (shade_id, ns, value) values (?, ?, ?)",
        [(shade_id, ns, value) for ns, value in pairs],
    )
    return row is None


def _resolve_aliases(conn: sqlite3.Connection) -> int:
    """Links alias products that have no shade_alias row yet; returns how many stay unresolved."""
    pending = conn.execute(
        "select p.id, p.handle, p.product_type, p.tags_json from product p"
        " left join shade_alias a on a.product_id = p.id"
        " where p.role = 'alias' and a.product_id is null"
    ).fetchall()
    unresolved = 0
    for row in pending:
        classification = classify(
            {
                "handle": row["handle"],
                "product_type": row["product_type"],
                "tags": json.loads(row["tags_json"]),
            }
        )
        target = conn.execute(
            "select id from shade where handle = ? and source = 'holotaco' order by id limit 1",
            (classification.alias_target,),
        ).fetchone()
        if target is None:
            log.warning(
                "alias %s: no shade with handle %s yet", row["handle"], classification.alias_target
            )
            unresolved += 1
            continue
        conn.execute(
            "insert into shade_alias (product_id, shade_id, source) values (?, ?, ?)",
            (row["id"], target["id"], classification.alias_source),
        )
    return unresolved


def apply_feed(
    conn: sqlite3.Connection, run_id: int, pages: list[list[dict]], now: datetime, tz: ZoneInfo
) -> SyncCounts:
    """Applies the whole feed in one transaction and closes the sync_run row as ok."""
    parsed_products: dict[int, _Parsed] = {}
    for page in pages:
        for product in page:
            parsed = _parse(product)
            if parsed is not None:
                parsed_products[product["id"]] = parsed
    if not parsed_products:
        raise FeedError("the feed has no products")

    now_text = format_time(now)
    today = now.astimezone(tz).date().isoformat()
    counts = SyncCounts(products_seen=len(parsed_products))

    with transaction(conn):
        existing = {
            row["shopify_product_id"]: row
            for row in conn.execute(
                "select id, shopify_product_id, role, content_hash, absent_syncs, missing_since"
                " from product"
            )
        }
        previous = conn.execute(
            "select products_seen from sync_run where status = 'ok' and id != ?"
            " order by id desc limit 1",
            (run_id,),
        ).fetchone()

        # Shades from before migration 005 have no swatch photo and an unchanged hash, so the loop
        # below fills them from the feed in memory.
        unswatched = {
            row["product_id"]
            for row in conn.execute(
                "select product_id from shade where swatch_image_url is null"
                " and product_id is not null"
            )
        }

        for shopify_id, parsed in parsed_products.items():
            product, variant = parsed.product, parsed.variant
            row = existing.get(shopify_id)
            values = {
                "variant_id": variant["id"],
                "handle": product["handle"],
                "title": product["title"],
                "product_type": product["product_type"],
                "role": parsed.role,
                "sku": variant.get("sku"),
                "price_cents": parse_price_cents(variant.get("price")),
                "compare_at_cents": parse_compare_at_cents(variant.get("compare_at_price")),
                "available": int(bool(variant.get("available"))),
                "published_at": product.get("published_at"),
                "tags_json": json.dumps(product["tags"], ensure_ascii=False),
                "raw_json": parsed.raw_json,
                "content_hash": parsed.content_hash,
            }
            if row is None:
                columns = ", ".join(values)
                marks = ", ".join("?" for _ in values)
                product_row_id = conn.execute(
                    f"insert into product (shopify_product_id, {columns}, first_seen, last_seen)"
                    f" values (?, {marks}, ?, ?)",
                    (shopify_id, *values.values(), now_text, now_text),
                ).lastrowid
                changed = True
            else:
                product_row_id = row["id"]
                changed = row["content_hash"] != parsed.content_hash or row["role"] != parsed.role
                if row["missing_since"] is not None:
                    counts.returned += 1
                if changed:
                    assignments = ", ".join(f"{column} = ?" for column in values)
                    conn.execute(
                        f"update product set {assignments}, last_seen = ?, absent_syncs = 0,"
                        f" missing_since = null where id = ?",
                        (*values.values(), now_text, product_row_id),
                    )
                else:
                    conn.execute(
                        "update product set last_seen = ?, absent_syncs = 0, missing_since = null"
                        " where id = ?",
                        (now_text, product_row_id),
                    )
            if parsed.role == "shade" and changed:
                if _upsert_shade(conn, product_row_id, parsed):
                    counts.new_shades += 1
                else:
                    counts.changed_shades += 1
            elif parsed.role == "shade" and product_row_id in unswatched:
                swatch = swatch_image_url(product.get("images", []), product["title"])
                if swatch is not None:
                    conn.execute(
                        "update shade set swatch_image_url = ? where product_id = ?",
                        (swatch, product_row_id),
                    )

        counts.unresolved_aliases = _resolve_aliases(conn)
        refresh_retired(conn)  # a changed product must not undo what the release sheet said

        trustworthy = (
            previous is None or len(parsed_products) >= TRUST_RATIO * previous["products_seen"]
        )
        if trustworthy:
            for shopify_id, row in existing.items():
                if shopify_id in parsed_products:
                    continue
                absent = row["absent_syncs"] + 1
                missing_since = row["missing_since"]
                if absent >= ABSENT_SYNCS_MISSING and missing_since is None:
                    missing_since = today
                    counts.newly_missing += 1
                conn.execute(
                    "update product set absent_syncs = ?, missing_since = ? where id = ?",
                    (absent, missing_since, row["id"]),
                )
        else:
            log.warning(
                "feed has %d products, last run saw %d: absence accounting skipped",
                len(parsed_products),
                previous["products_seen"],
            )

        conn.execute(
            "update sync_run set status = 'ok', finished_at = ?, pages_fetched = ?,"
            " products_seen = ?, new_shades = ?, changed_shades = ?, newly_missing = ?,"
            " returned = ?, unresolved_aliases = ? where id = ?",
            (
                now_text,
                len(pages),
                counts.products_seen,
                counts.new_shades,
                counts.changed_shades,
                counts.newly_missing,
                counts.returned,
                counts.unresolved_aliases,
                run_id,
            ),
        )
    return counts


def read_pages(files: list[Path]) -> list[list[dict]]:
    """Pages from local JSON files shaped like /products.json (for sync --from-files)."""
    pages = []
    for path in files:
        try:
            pages.append(json.loads(Path(path).read_text(encoding="utf-8"))["products"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise FeedError(f"{path}: not a products feed ({exc})") from exc
    return pages


def last_run_started(conn: sqlite3.Connection) -> datetime | None:
    row = conn.execute("select started_at from sync_run order by id desc limit 1").fetchone()
    return parse_time(row["started_at"]) if row else None


def running_run(conn: sqlite3.Connection, now: datetime) -> sqlite3.Row | None:
    """The `running` row that still counts (younger than STALE_RUNNING_S), if any."""
    cutoff = format_time(datetime.fromtimestamp(now.timestamp() - STALE_RUNNING_S, UTC))
    return conn.execute(
        "select * from sync_run where status = 'running' and started_at > ? order by id desc limit 1",
        (cutoff,),
    ).fetchone()


def cooldown_remaining_s(conn: sqlite3.Connection, settings: Settings, now: datetime) -> int:
    """Seconds until a manual run is allowed again, 0 when it is allowed now."""
    started = last_run_started(conn)
    if started is None:
        return 0
    wait = started.timestamp() + settings.sync_manual_cooldown_s - now.timestamp()
    return max(0, int(wait + 0.999))


class SyncRunner:
    """Starts and executes sync runs, one at a time. Clock, sleep, transport and now are
    injectable so tests need neither network nor real waiting."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Clock | None = None,
        sleep: Sleep | None = None,
        now: Callable[[], datetime] = utc_now,
        colour_transport: httpx.BaseTransport | None = None,
        colour_sleep: Callable[[float], None] | None = None,
        sheet_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        self.sheet_transport = sheet_transport
        self.colour_options = {
            key: value
            for key, value in (("transport", colour_transport), ("sleep", colour_sleep))
            if value is not None
        }
        self.transport = transport
        self.now = now
        self.fetch_options = {
            key: value for key, value in (("clock", clock), ("sleep", sleep)) if value is not None
        }
        self.tz = ZoneInfo(settings.timezone)
        self.lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self.lock.locked()

    async def begin(self, trigger: str) -> int:
        """Takes the lock and inserts the `running` row; raises RunRefused instead of waiting."""
        if self.lock.locked():
            raise RunRefused(409, "A sync is already running.")
        await self.lock.acquire()
        try:
            return await asyncio.to_thread(self._insert_running, trigger)
        except BaseException:
            self.lock.release()
            raise

    def _insert_running(self, trigger: str) -> int:
        conn = connect(self.settings.db_path)
        try:
            with transaction(conn):
                now = self.now()
                if running_run(conn, now) is not None:
                    raise RunRefused(409, "A sync is already running.")
                if trigger == "manual":
                    wait = cooldown_remaining_s(conn, self.settings, now)
                    if wait:
                        raise RunRefused(
                            429,
                            f"The last sync started recently; try again in {wait // 60 + 1} min.",
                        )
                return conn.execute(
                    "insert into sync_run (started_at, trigger, status) values (?, ?, 'running')",
                    (format_time(now), trigger),
                ).lastrowid
        finally:
            conn.close()

    async def execute(
        self,
        run_id: int,
        files: list[Path] | None = None,
        sheet: Path | None = None,
        colours: bool = True,
    ) -> RunOutcome:
        """Fetches (or reads files), applies, closes the row. Releases the lock taken by begin().
        Then the release sheet: read from the `sheet` file, else fetched, but not when the shop
        pages came from `files` (an offline run stays offline). Then the polish colours, which
        download shade photos from the image CDN, unless `colours` is False."""
        try:
            if files is None:
                pages = await fetch_feed(
                    self.settings.store_url,
                    version=self.settings.version,
                    min_interval_s=self.settings.sync_min_interval_s,
                    transport=self.transport,
                    **self.fetch_options,
                )
            else:
                pages = await asyncio.to_thread(read_pages, files)
            counts = await asyncio.to_thread(self._apply, run_id, pages)
            await self._read_sheet(sheet, offline=files is not None)
            if colours:
                await asyncio.to_thread(self._read_colours)
        except asyncio.CancelledError:
            self._record_error(run_id, "interrupted")
            raise
        except FeedError as exc:
            log.error("sync run %d failed: %s", run_id, exc)
            self._record_error(run_id, str(exc))
            return RunOutcome(run_id, "error", str(exc), exc.retryable)
        except Exception as exc:
            log.exception("sync run %d failed", run_id)
            message = f"{type(exc).__name__}: {exc}"
            self._record_error(run_id, message)
            return RunOutcome(run_id, "error", message)
        finally:
            self.lock.release()
        log.info("sync run %d ok: %s", run_id, counts)
        return RunOutcome(run_id, "ok")

    async def run(
        self,
        trigger: str,
        files: list[Path] | None = None,
        sheet: Path | None = None,
        colours: bool = True,
    ) -> RunOutcome:
        return await self.execute(await self.begin(trigger), files, sheet, colours)

    def _apply(self, run_id: int, pages: list[list[dict]]) -> SyncCounts:
        conn = connect(self.settings.db_path)
        try:
            return apply_feed(conn, run_id, pages, self.now(), self.tz)
        finally:
            conn.close()

    async def _read_sheet(self, sheet: Path | None, *, offline: bool) -> None:
        """After the shop is applied: the release dates, collections and retired flags (DESIGN 5.6).
        One request, or the `sheet` file. Never raises: a sheet that cannot be fetched or read, or
        whose layout changed, is logged as a warning and the data stays as it was."""
        url = self.settings.release_sheet_url
        if sheet is None and (offline or not url):
            return
        try:
            if sheet is not None:
                text = await asyncio.to_thread(sheet.read_text, "utf-8-sig")
            else:
                text = await fetch_sheet(
                    url, version=self.settings.version, transport=self.sheet_transport
                )
            rows = parse_sheet(text)
            counts = await asyncio.to_thread(self._apply_sheet, rows)
        except (SheetError, OSError, ValueError) as exc:
            log.warning("release sheet skipped: %s", exc)
        except Exception:
            log.exception("release sheet step failed")
        else:
            log.info("release sheet applied: %s", counts)

    def _apply_sheet(self, rows: list[SheetRow]) -> SheetCounts:
        conn = connect(self.settings.db_path)
        try:
            return apply_sheet(conn, rows)
        finally:
            conn.close()

    def _read_colours(self) -> None:
        """After the feed is applied and the run is closed: reads the polish colour of the shades
        that have none (DESIGN 5.5). Never raises, so it can never fail the run."""
        conn = connect(self.settings.db_path)
        try:
            stored = fill_colours(conn, **self.colour_options)
        except Exception:
            log.exception("colour step failed")
        else:
            if stored:
                log.info("polish colour read for %d shades", stored)
        finally:
            conn.close()

    def _record_error(self, run_id: int, message: str) -> None:
        conn = connect(self.settings.db_path)
        try:
            conn.execute(
                "update sync_run set status = 'error', finished_at = ?, error = ? where id = ?",
                (format_time(self.now()), message, run_id),
            )
        finally:
            conn.close()
