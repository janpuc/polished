"""Holo Taco's official release list: reading the public Google Sheet and applying it (DESIGN 5.6).

The sheet knows what the shop feed does not: the release date, the official collection name, the
retired flag, and a few shades the shop no longer (or never) lists. parse_sheet() is pure,
fetch_sheet() is one polite request, apply_sheet() writes. A sheet that cannot be read, or whose
layout changed, raises SheetError and the caller leaves the database as it was.
"""

import csv
import io
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin, urlsplit

import httpx

from ..db import transaction
from .fetch import MAX_REDIRECTS, TIMEOUT_S, user_agent
from .parse import RETIRED_TAG, fold

log = logging.getLogger("polished.sync")

MIN_ROWS = 300  # the sheet has 374 today; far fewer means the layout changed or the page is not it
MAX_NEW_SHEET_SHADES = 40  # more unmatched rows than this in one run is a naming mismatch, not news
MAX_BYTES = 2_000_000
MAX_TEXT = 100  # longest shade or collection name kept
RETIRED_WORD = "retired"  # the Retired? column also says "Seasonal", which is not retired
GOOGLE_SUFFIXES = ("google.com", "googleusercontent.com")  # where the CSV export may redirect

# A sheet name whose shop title differs by more than the normalisation removes -> that title's
# normalised form. None found on the 2026-10-25 snapshot: every sheet name matched or was a shade
# the shop does not list.
ALIASES: dict[str, str] = {}

HEADER_CELLS = {"date": "release date", "name": "shade name", "collection": "in collection"}
RETIRED_HEADER = "retired"
MONTHS = {
    month: number
    for number, month in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}
_DATE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_APOSTROPHES = re.compile(r"['\u2018\u2019\u02bc`]")
_NOT_ALNUM = re.compile(r"[^a-z0-9]+")


class SheetError(Exception):
    """The sheet could not be fetched or understood; nothing must be applied."""


@dataclass(frozen=True)
class SheetRow:
    key: str  # normalise_name(name)
    name: str
    released_on: str  # "2019-07-06"
    collection: str | None
    retired: bool


def normalise_name(text: str) -> str:
    """A shade name for matching: trademark signs and apostrophes dropped, accents folded, case
    folded, every other run of non-alphanumerics one space. "Flakie Holo Taco™" -> "flakie holo
    taco", "Play Rosé" -> "play rose"."""
    text = text.replace("\u2122", "").replace("\u00ae", "").replace("&", " and ")
    return _NOT_ALNUM.sub(" ", fold(_APOSTROPHES.sub("", text))).strip()


def is_topper_name(key: str) -> bool:
    """A sheet-only shade has no tags, so the name decides: the flakie, glow and glitter tacos
    (the word "taco") and the flakes. Checked against the shop's own tags on the 364 shades that
    match: no false positive, 14 toppers without the word missed (Halogen Glow and the like)."""
    words = key.split()
    return "taco" in words or "flake" in words or "flakie" in words


def parse_date(text: str) -> str | None:
    """ "Jul 6, 2019" (or "2019-07-06") -> "2019-07-06"; None for anything else."""
    text = text.strip()
    try:
        if match := _DATE.fullmatch(text):
            month = MONTHS.get(match[1][:3].lower())
            return date(int(match[3]), month, int(match[2])).isoformat() if month else None
        if match := _ISO_DATE.fullmatch(text):
            return date(int(match[1]), int(match[2]), int(match[3])).isoformat()
    except ValueError:
        return None
    return None


def _header(cell: str) -> str:
    return " ".join(cell.casefold().replace("?", " ").split())


def parse_sheet(text: str, min_rows: int | None = None) -> list[SheetRow]:
    """The shades of the sheet in sheet order. The columns are found by their header names, in the
    first row that has "Release date" and "Shade name"; rows above it (a preamble with quoted,
    multi-line cells) and rows without a name and a date (blank, or notes below the table) are
    skipped. A name that appears twice keeps its earliest date. SheetError when the header row is
    missing a column or fewer than `min_rows` (MIN_ROWS) shades remain."""
    needed = MIN_ROWS if min_rows is None else min_rows
    try:
        table = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise SheetError(f"not a CSV file ({exc})") from exc
    columns: dict[str, int] = {}
    start = 0
    for index, cells in enumerate(table):
        headers = [_header(c) for c in cells]
        if HEADER_CELLS["date"] in headers and HEADER_CELLS["name"] in headers:
            wanted = (*HEADER_CELLS.values(), RETIRED_HEADER)
            columns = {h: headers.index(h) for h in wanted if h in headers}
            start = index + 1
            break
    missing = [h for h in (*HEADER_CELLS.values(), RETIRED_HEADER) if h not in columns]
    if not columns:
        raise SheetError("the header row (Release date, Shade name) was not found")
    if missing:
        raise SheetError(f"the header row has no {', '.join(missing)} column")

    rows: dict[str, SheetRow] = {}
    skipped = 0
    for cells in table[start:]:
        cells = [*cells, *[""] * (max(columns.values()) + 1 - len(cells))]
        name = " ".join(cells[columns[HEADER_CELLS["name"]]].split())
        if not name:
            continue
        released_on = parse_date(cells[columns[HEADER_CELLS["date"]]])
        key = normalise_name(name)
        if released_on is None or not key or len(name) > MAX_TEXT:
            skipped += 1
            continue
        collection = " ".join(cells[columns[HEADER_CELLS["collection"]]].split())[:MAX_TEXT] or None
        retired = cells[columns[RETIRED_HEADER]].strip().casefold() == RETIRED_WORD
        row = SheetRow(key, name, released_on, collection, retired)
        earlier = rows.get(key)
        if earlier is None or released_on < earlier.released_on:
            rows[key] = row
        if earlier is not None:
            log.warning("release sheet lists %r twice; keeping the earliest", name)
    if skipped:
        log.warning("release sheet: %d row(s) without a readable date or name skipped", skipped)
    if len(rows) < needed:
        raise SheetError(f"only {len(rows)} shades found, expected at least {needed}")
    return list(rows.values())


def _allowed_host(host: str, own_host: str) -> bool:
    return host == own_host or any(host == s or host.endswith("." + s) for s in GOOGLE_SUFFIXES)


async def fetch_sheet(
    url: str, *, version: str, transport: httpx.AsyncBaseTransport | None = None
) -> str:
    """The CSV text: one GET with an identifying User-Agent and a timeout, no retry. Google answers
    the export URL with a redirect to googleusercontent.com, which is followed (at most
    MAX_REDIRECTS hops, only to Google or the configured host); a status other than 200, a
    transport error or an oversized body is a SheetError."""
    own_host = urlsplit(url).hostname or ""
    async with httpx.AsyncClient(
        transport=transport,
        headers={"User-Agent": user_agent(version), "Accept": "text/csv"},
        timeout=TIMEOUT_S,
        follow_redirects=False,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        target = urljoin(url, response.headers.get("location", ""))
                        parts = urlsplit(target)
                        if parts.scheme != "https" or not _allowed_host(
                            parts.hostname or "", own_host
                        ):
                            raise SheetError(f"redirected away to {parts.hostname}")
                        url = target
                        continue
                    if response.status_code != 200:
                        raise SheetError(f"HTTP {response.status_code}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise SheetError("the response is larger than expected")
            except httpx.HTTPError as exc:
                raise SheetError(f"request failed: {type(exc).__name__}: {exc}") from exc
            try:
                return bytes(body).decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise SheetError("the response is not UTF-8 text") from exc
    raise SheetError("too many redirects")


@dataclass
class SheetCounts:
    rows: int = 0
    matched: int = 0  # sheet rows that found a shop shade
    created: int = 0  # new sheet-only shades
    merged: int = 0  # sheet-only shades folded into a shop shade that has appeared
    sheet_only: int = 0  # sheet-only shades after this run
    unlisted: list[str] = field(default_factory=list)  # shop polishes with no sheet row


def refresh_retired(conn: sqlite3.Connection) -> None:
    """retired = the shop's collection:retirement tag, or the sheet's Retired. The shop sync writes
    it from the tag and the sheet step from both, so both call this last (manual shades have no
    retired state)."""
    tag, _, value = RETIRED_TAG.partition(":")
    conn.execute(
        "update shade set retired = (sheet_retired = 1 or exists ("
        " select 1 from shade_tag t where t.shade_id = shade.id and t.ns = ? and t.value = ?))"
        " where source != 'manual' and retired != (sheet_retired = 1 or exists ("
        " select 1 from shade_tag t where t.shade_id = shade.id and t.ns = ? and t.value = ?))",
        (tag, value, tag, value),
    )


def _shop_shades(conn: sqlite3.Connection) -> dict[str, int]:
    """Normalised title -> shade id for the shop's shades; a polish beats a top coat of the same
    name (the sheet leaves top and base coats out), then the older row wins (it is read last)."""
    shades: dict[str, int] = {}
    for row in conn.execute(
        "select id, title from shade where source = 'holotaco' order by kind = 'polish', id desc"
    ):
        shades[normalise_name(row["title"])] = row["id"]
    return shades


def _write_sheet_facts(conn: sqlite3.Connection, shade_id: int, row: SheetRow) -> None:
    conn.execute(
        "update shade set released_on = ?, official_collection = ?, sheet_retired = ?,"
        " sheet_key = ? where id = ?",
        (row.released_on, row.collection, int(row.retired), row.key, shade_id),
    )


def merge_sheet_shade(conn: sqlite3.Connection, sheet_id: int, shop_id: int) -> None:
    """Folds a sheet-only shade into the shop shade that now lists it: its bottles, stack layers,
    learned codes and aliases move over, a wishlist entry too (when both are wished, the more
    wanted priority and the note stay), the household's tip colour stays unless the shop shade
    has one, and the sheet-only row goes. shade_tag has no rows for a sheet-only shade."""
    for table in ("bottle", "stack_layer", "shade_identifier", "shade_alias"):
        conn.execute(f"update {table} set shade_id = ? where shade_id = ?", (shop_id, sheet_id))
    theirs = conn.execute("select * from wishlist_item where shade_id = ?", (sheet_id,)).fetchone()
    if theirs is not None:
        ours = conn.execute("select * from wishlist_item where shade_id = ?", (shop_id,)).fetchone()
        if ours is None:
            conn.execute(
                "update wishlist_item set shade_id = ? where shade_id = ?", (shop_id, sheet_id)
            )
        else:
            conn.execute(
                "update wishlist_item set priority = ?, note = ? where id = ?",
                (
                    min(ours["priority"], theirs["priority"]),
                    ours["note"] or theirs["note"],
                    ours["id"],
                ),
            )
            conn.execute("delete from wishlist_item where id = ?", (theirs["id"],))
    conn.execute(
        "update shade set swatch_override_hex = (select swatch_override_hex from shade"
        " where id = ?) where id = ? and swatch_override_hex is null",
        (sheet_id, shop_id),
    )
    conn.execute("delete from shade where id = ?", (sheet_id,))


def apply_sheet(conn: sqlite3.Connection, rows: list[SheetRow]) -> SheetCounts:
    """Writes the sheet's facts in one transaction: for each row the matching shop shade gets its
    release date, official collection and retired flag; a row with no shop shade becomes (or stays)
    a sheet-only shade; a sheet-only shade whose name the shop now lists is merged into the shop
    shade. Nothing is ever deleted but those merged rows. SheetError, with nothing written, when
    more than MAX_NEW_SHEET_SHADES rows would become new shades."""
    counts = SheetCounts(rows=len(rows))
    with transaction(conn):
        shop = _shop_shades(conn)
        sheet_only = {
            r["sheet_key"]: r["id"]
            for r in conn.execute("select id, sheet_key from shade where source = 'sheet'")
        }
        fresh = [
            r for r in rows if ALIASES.get(r.key, r.key) not in shop and r.key not in sheet_only
        ]
        if len(fresh) > MAX_NEW_SHEET_SHADES:
            raise SheetError(
                f"{len(fresh)} sheet shades have no shop shade (limit {MAX_NEW_SHEET_SHADES}); "
                "the shop's names probably changed"
            )
        matched_ids: set[int] = set()
        for row in rows:
            shop_id = shop.get(ALIASES.get(row.key, row.key))
            stale_id = sheet_only.pop(row.key, None)
            if shop_id is not None:
                _write_sheet_facts(conn, shop_id, row)
                matched_ids.add(shop_id)
                if stale_id is not None:
                    merge_sheet_shade(conn, stale_id, shop_id)
                    counts.merged += 1
            elif stale_id is not None:
                conn.execute(
                    "update shade set title = ?, search_text = ?, is_topper = ? where id = ?",
                    (row.name, row.key, int(is_topper_name(row.key)), stale_id),
                )
                _write_sheet_facts(conn, stale_id, row)
            else:
                shade_id = conn.execute(
                    "insert into shade (source, kind, title, search_text, is_topper)"
                    " values ('sheet', 'polish', ?, ?, ?)",
                    (row.name, row.key, int(is_topper_name(row.key))),
                ).lastrowid
                _write_sheet_facts(conn, shade_id, row)
                counts.created += 1
        counts.matched = len(matched_ids)
        refresh_retired(conn)
        counts.sheet_only = conn.execute(
            "select count(*) from shade where source = 'sheet'"
        ).fetchone()[0]
        counts.unlisted = [
            r["title"]
            for r in conn.execute(
                "select title from shade where source = 'holotaco' and kind = 'polish'"
                " and sheet_key is null order by title"
            )
        ]
    return counts
