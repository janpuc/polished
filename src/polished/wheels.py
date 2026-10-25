"""Swatch wheels: slugs for the NFC tag and QR code, CRUD, the slot grid and "swatched on"
(DESIGN 9). Takes a connection; routes never write SQL. The stack builder is stacks.py."""

import io
import secrets
import sqlite3
from collections.abc import Callable

import segno

from . import stacks
from .db import atomic

# Lowercase Crockford base32: 0-9 and a-z without i, l, o, u.
SLUG_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
SLUG_LENGTH = 6
SLUG_ATTEMPTS = 10
DEFAULT_SLOT_COUNT = 20
MAX_SLOT_COUNT = 40
NAME_LIMIT = 60


class WheelNotFound(LookupError):
    """No wheel has that id (404)."""


def new_slug() -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_LENGTH))


def clean_name(raw: str) -> str:
    """The trimmed name; ValueError when empty."""
    name = raw.strip()[:NAME_LIMIT]
    if not name:
        raise ValueError("A wheel needs a name.")
    return name


def _with_new_slug[T](write: Callable[[str], T]) -> T:
    """Runs write(slug) with fresh slugs until one is not taken (a unique violation on
    wheel.slug), then returns its result."""
    for _ in range(SLUG_ATTEMPTS):
        try:
            return write(new_slug())
        except sqlite3.IntegrityError as exc:
            if "wheel.slug" not in str(exc):
                raise
    raise RuntimeError(f"no free wheel slug after {SLUG_ATTEMPTS} attempts")


def create(conn: sqlite3.Connection, name: str, slot_count: int = DEFAULT_SLOT_COUNT) -> int:
    """A new wheel with a fresh slug. ValueError for an empty name or a slot count outside
    1..40."""
    name = clean_name(name)
    if not 1 <= slot_count <= MAX_SLOT_COUNT:
        raise ValueError(f"A wheel has 1 to {MAX_SLOT_COUNT} slots.")
    return _with_new_slug(
        lambda slug: (
            conn.execute(
                "insert into wheel (slug, name, slot_count) values (?, ?, ?)",
                (slug, name, slot_count),
            ).lastrowid
        )
    )


def get(conn: sqlite3.Connection, wheel_id: int) -> dict | None:
    row = conn.execute("select * from wheel where id = ?", (wheel_id,)).fetchone()
    return dict(row) if row else None


def get_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute("select * from wheel where slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def list_wheels(conn: sqlite3.Connection, archived: bool = False) -> list[dict]:
    """Wheels by name, each with `filled` (slots holding a swatch) and `drafts` (open drafts).
    `archived` picks archived wheels only; the default hides them."""
    rows = conn.execute(
        "select w.*,"
        " (select count(*) from wheel_slot ws where ws.wheel_id = w.id"
        "   and ws.stack_id is not null) as filled,"
        " (select count(*) from wheel_slot ws where ws.wheel_id = w.id"
        "   and ws.draft_stack_id is not null) as drafts"
        " from wheel w where w.archived = ? order by w.name collate nocase, w.id",
        (int(archived),),
    )
    return [dict(r) for r in rows]


def rename(conn: sqlite3.Connection, wheel_id: int, name: str) -> None:
    """Changes the name only; the slug, and with it the tag, stays."""
    conn.execute("update wheel set name = ? where id = ?", (clean_name(name), wheel_id))


def set_archived(conn: sqlite3.Connection, wheel_id: int, archived: bool) -> None:
    """Archive or restore. The slug stays, so the tag keeps opening the wheel."""
    conn.execute("update wheel set archived = ? where id = ?", (int(archived), wheel_id))


def regenerate_slug(conn: sqlite3.Connection, wheel_id: int) -> str:
    """Give the wheel a new slug (its old tag then 404s). Raises WheelNotFound."""

    def write(slug: str) -> str:
        cursor = conn.execute("update wheel set slug = ? where id = ?", (slug, wheel_id))
        if cursor.rowcount == 0:
            raise WheelNotFound(wheel_id)
        return slug

    return _with_new_slug(write)


def take_tag(conn: sqlite3.Connection, wheel_id: int, from_wheel_id: int) -> None:
    """Swap slugs, so the tag stuck on `from_wheel_id` opens `wheel_id` and the other way round.
    Raises WheelNotFound, or ValueError for the same wheel twice."""
    if wheel_id == from_wheel_id:
        raise ValueError("A wheel cannot take its own tag.")
    with atomic(conn):
        slugs = {
            r["id"]: r["slug"]
            for r in conn.execute(
                "select id, slug from wheel where id in (?, ?)", (wheel_id, from_wheel_id)
            )
        }
        for missing in (wheel_id, from_wheel_id):
            if missing not in slugs:
                raise WheelNotFound(missing)
        update = "update wheel set slug = ? where id = ?"
        # slug is unique, so one wheel parks on a value no slug can have (it contains "-").
        conn.execute(update, (f"swap-{wheel_id}", wheel_id))
        conn.execute(update, (slugs[wheel_id], from_wheel_id))
        conn.execute(update, (slugs[from_wheel_id], wheel_id))


def tag_url(public_url: str, slug: str) -> str:
    """What the NFC tag and the QR code carry: PUBLIC_URL/w/<slug>."""
    return f"{public_url.rstrip('/')}/w/{slug}"


def qr_svg(url: str) -> str:
    """The QR code of `url` as an SVG document without an XML declaration."""
    out = io.BytesIO()
    segno.make(url, error="m").save(out, kind="svg", scale=8, border=2, xmldecl=False, nl=False)
    return out.getvalue().decode()


def _tiles(conn: sqlite3.Connection, wheel: dict, positions: range) -> list[dict]:
    rows = {
        r["position"]: r
        for r in conn.execute("select * from wheel_slot where wheel_id = ?", (wheel["id"],))
    }
    saved = [rows[p]["stack_id"] for p in positions if p in rows and rows[p]["stack_id"]]
    stack_layers = stacks.layers_by_stack(conn, saved)
    tiles = []
    for position in positions:
        row = rows.get(position)
        stack_id = row["stack_id"] if row else None
        layers = stack_layers.get(stack_id, [])
        tiles.append(
            {
                "wheel_id": wheel["id"],
                "wheel_slug": wheel["slug"],
                "position": position,
                "stack_id": stack_id,
                "draft_stack_id": row["draft_stack_id"] if row else None,
                "filled": stack_id is not None,
                "has_draft": bool(row and row["draft_stack_id"] is not None),
                "note": row["note"] if row else None,
                "painted_on": row["painted_on"] if row else None,
                "layers": layers,
                "summary": stacks.summary(layers),
            }
        )
    return tiles


def slot_grid(conn: sqlite3.Connection, wheel: dict) -> list[dict]:
    """One tile per position 1..slot_count: position, filled, has_draft, the saved stack's
    summary and layers (with shade title, hero_image_url, swatch_image_url, coats, label), note and painted_on.
    Empty slots have no row and come back empty."""
    return _tiles(conn, wheel, range(1, wheel["slot_count"] + 1))


def slot_tile(conn: sqlite3.Connection, wheel: dict, position: int) -> dict:
    """The tile of slot_grid() for one position (the out-of-band swap after a save)."""
    return _tiles(conn, wheel, range(position, position + 1))[0]


def swatched_on(conn: sqlite3.Connection, shade_id: int) -> list[dict]:
    """Where a shade is used in a saved stack on a wheel that is not archived: wheel name, slug,
    position and stack_id, by wheel name then position. Drafts never count."""
    rows = conn.execute(
        "select w.slug, w.name, ws.position, ws.stack_id"
        " from stack_layer sl"
        " join wheel_slot ws on ws.stack_id = sl.stack_id"
        " join wheel w on w.id = ws.wheel_id and w.archived = 0"
        " where sl.shade_id = ?"
        " group by ws.wheel_id, ws.position"
        " order by w.name collate nocase, ws.position",
        (shade_id,),
    )
    return [dict(r) for r in rows]


def highlight_positions(conn: sqlite3.Connection, wheel_id: int, shade_id: int) -> list[int]:
    """Positions on one wheel whose saved stack contains the shade, ascending (`?hl=`). The
    first one is where the page scrolls to."""
    rows = conn.execute(
        "select distinct ws.position from stack_layer sl"
        " join wheel_slot ws on ws.stack_id = sl.stack_id"
        " where ws.wheel_id = ? and sl.shade_id = ? order by ws.position",
        (wheel_id, shade_id),
    )
    return [r["position"] for r in rows]
