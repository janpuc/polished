"""Identifier lookup (DESIGN 7): the resolution order and learned barcode mappings. Takes a
connection; routes never write SQL.

Nothing is ever seeded from catalog data: `shade_identifier` holds only what the household
taught the app, so a learned mapping wins by construction."""

import sqlite3
from dataclasses import dataclass

from . import shades
from .gtin import is_numeric, normalise_gtin

KINDS = ("gtin",)
# A number of this many digits is meant as a barcode, so one that fails the check is "invalid".
BARCODE_DIGITS = range(8, 15)


def normalise(kind: str, raw: str) -> str | None:
    """The stored form of a code of `kind`, or None when it is not one."""
    if kind == "gtin":
        return normalise_gtin(raw)
    return None


@dataclass
class Resolution:
    """What `resolve` found. `outcome` is one of match, unknown_code, invalid_code, results
    (DESIGN 7.2). `code` is the normalised gtin or SKU, `kind` says what the match came from
    (gtin or sku), `identifier_id` is the learned row a gtin match can delete ("This isn't it")."""

    outcome: str
    q: str
    via: str = "typed"
    code: str | None = None
    kind: str | None = None
    shade: dict | None = None
    identifier_id: int | None = None
    results: shades.ShadePage | None = None


def result_shade(conn: sqlite3.Connection, shade_id: int) -> dict:
    """A shade as a result row: the detail record plus `finishes`, which the row template reads."""
    shade = shades.get_shade(conn, shade_id)
    shade["finishes"] = shade["tags"]["finish"]
    return shade


def find(conn: sqlite3.Connection, kind: str, value: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from shade_identifier where kind = ? and value = ?", (kind, value)
    ).fetchone()


def resolve(conn: sqlite3.Connection, q: str, via: str = "typed") -> Resolution:
    """Scanner text or whatever was typed, in the order of DESIGN 7.2: a barcode, a number that
    is not one, a SKU, then an ordinary name search."""
    q = q.strip()
    gtin = normalise_gtin(q)
    if gtin is not None:
        row = find(conn, "gtin", gtin)
        if row is None:
            return Resolution("unknown_code", q, via, code=gtin)
        conn.execute(
            "update shade_identifier set use_count = use_count + 1,"
            " last_used_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') where id = ?",
            (row["id"],),
        )
        return Resolution(
            "match",
            q,
            via,
            code=gtin,
            kind="gtin",
            shade=result_shade(conn, row["shade_id"]),
            identifier_id=row["id"],
        )
    if is_numeric(q) and len("".join(q.split())) in BARCODE_DIGITS:
        return Resolution("invalid_code", q, via)
    sku = conn.execute("select id from shade where lower(sku) = lower(?) limit 1", (q,)).fetchone()
    if sku is not None:
        return Resolution(
            "match", q, via, code=q.upper(), kind="sku", shade=result_shade(conn, sku["id"])
        )
    return Resolution(
        "results", q, via, results=shades.search(conn, q) if shades.tokens(q) else None
    )


@dataclass
class Learned:
    """A stored mapping. `created` is False when the code was already known; `shade_id` is then
    the shade it already points at, which may differ from the one asked for."""

    id: int
    kind: str
    value: str
    shade_id: int
    created: bool


def learn(conn: sqlite3.Connection, kind: str, raw: str, shade_id: int) -> Learned:
    """Remembers that `raw` is `shade_id`. An existing mapping is kept, never overwritten: the
    caller compares `Learned.shade_id` with what it asked for. Raises ValueError for a value that
    is not a code of `kind`."""
    value = normalise(kind, raw)
    if value is None:
        raise ValueError(f"not a valid {kind} code: {raw!r}")
    cursor = conn.execute(
        "insert into shade_identifier (kind, value, shade_id) values (?, ?, ?)"
        " on conflict (kind, value) do nothing",
        (kind, value, shade_id),
    )
    row = find(conn, kind, value)
    return Learned(row["id"], kind, value, row["shade_id"], created=cursor.rowcount == 1)


def list_all(conn: sqlite3.Connection) -> list[dict]:
    """Every learned mapping with its shade, newest first, for the /identifiers page."""
    rows = conn.execute(
        "select i.*, s.title, s.hero_image_url from shade_identifier i"
        " join shade s on s.id = i.shade_id order by i.id desc"
    )
    return [dict(r) for r in rows]


def get(conn: sqlite3.Connection, identifier_id: int) -> dict | None:
    row = conn.execute("select * from shade_identifier where id = ?", (identifier_id,)).fetchone()
    return dict(row) if row else None


def delete(conn: sqlite3.Connection, identifier_id: int) -> None:
    conn.execute("delete from shade_identifier where id = ?", (identifier_id,))
