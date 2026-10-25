"""Bottles: several per shade, each with a state, a printed P code and purchase details
(DESIGN 4.2). A shade is owned while one of its bottles is neither archived nor empty."""

import calendar
import re
import sqlite3
from dataclasses import dataclass
from datetime import date

from .identifiers import normalise_printed
from .tips import TIP_FIELDS

STATES = ("full", "half", "low", "empty")
STATE_LABELS = {"full": "Full", "half": "Half", "low": "Low", "empty": "Empty"}
NOTES_LIMIT = 500

_PRICE = re.compile(r"\$?\s*(\d{1,4})(?:[.,](\d{1,2}))?")

# bottle b join shade s: the bottle and what a card shows of its shade.
_SELECT = (
    f"select b.*, s.title, s.hero_image_url, {TIP_FIELDS}"
    " from bottle b join shade s on s.id = b.shade_id"
)


@dataclass
class BottleInput:
    """A validated add or edit form."""

    state: str = "full"
    printed_code: str | None = None
    bought_on: str | None = None
    price_paid_cents: int | None = None
    opened_on: str | None = None
    notes: str | None = None


def clean_printed_code(raw: str | None) -> str | None:
    """ "259" and "p259" are stored as "P259". A value that does not look like a P number is
    kept uppercase without spaces rather than refused: a bottle is never lost over its code."""
    text = (raw or "").strip()
    if not text:
        return None
    return normalise_printed(text) or "".join(text.split()).upper()


def parse_price(raw: str) -> int | None:
    """ "12.5", "12,50" or "$12.50" -> cents. Raises ValueError for anything else."""
    text = raw.strip()
    if not text:
        return None
    match = _PRICE.fullmatch(text)
    if match is None:
        raise ValueError(raw)
    whole, fraction = match.groups()
    return int(whole) * 100 + int((fraction or "0").ljust(2, "0"))


def _parse_date(raw: str) -> str | None:
    text = raw.strip()
    if not text:
        return None
    return date.fromisoformat(text).isoformat()


def parse_input(
    state: str = "full",
    printed_code: str = "",
    bought_on: str = "",
    price_paid: str = "",
    opened_on: str = "",
    notes: str = "",
) -> tuple[BottleInput, dict[str, str]]:
    """The form's strings as a BottleInput, and a message per field that is wrong."""
    errors: dict[str, str] = {}
    if state not in STATES:
        errors["state"] = "Pick full, half, low or empty."
    values = BottleInput(
        state=state if state in STATES else "full",
        printed_code=clean_printed_code(printed_code),
        notes=notes.strip()[:NOTES_LIMIT] or None,
    )
    for name, raw in (("bought_on", bought_on), ("opened_on", opened_on)):
        try:
            setattr(values, name, _parse_date(raw))
        except ValueError:
            errors[name] = "Use a date like 2026-10-25."
    try:
        values.price_paid_cents = parse_price(price_paid)
    except ValueError:
        errors["price_paid"] = "Use an amount like 15.50."
    return values, errors


def add(conn: sqlite3.Connection, shade_id: int, values: BottleInput) -> int:
    cursor = conn.execute(
        "insert into bottle (shade_id, printed_code, state, bought_on, price_paid_cents,"
        " opened_on, notes) values (?, ?, ?, ?, ?, ?, ?)",
        (
            shade_id,
            values.printed_code,
            values.state,
            values.bought_on,
            values.price_paid_cents,
            values.opened_on,
            values.notes,
        ),
    )
    return cursor.lastrowid


def update(conn: sqlite3.Connection, bottle_id: int, values: BottleInput) -> None:
    conn.execute(
        "update bottle set printed_code = ?, state = ?, bought_on = ?, price_paid_cents = ?,"
        " opened_on = ?, notes = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
        " where id = ?",
        (
            values.printed_code,
            values.state,
            values.bought_on,
            values.price_paid_cents,
            values.opened_on,
            values.notes,
            bottle_id,
        ),
    )


def set_state(conn: sqlite3.Connection, bottle_id: int, state: str) -> None:
    if state not in STATES:
        raise ValueError(f"unknown bottle state {state!r}")
    conn.execute(
        "update bottle set state = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
        " where id = ?",
        (state, bottle_id),
    )


def set_archived(conn: sqlite3.Connection, bottle_id: int, archived: bool) -> None:
    conn.execute(
        "update bottle set archived = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
        " where id = ?",
        (int(archived), bottle_id),
    )


def delete(conn: sqlite3.Connection, bottle_id: int) -> None:
    """Hard delete, for a bottle entered by mistake."""
    conn.execute("delete from bottle where id = ?", (bottle_id,))


def get(conn: sqlite3.Connection, bottle_id: int) -> dict | None:
    row = conn.execute(f"{_SELECT} where b.id = ?", (bottle_id,)).fetchone()
    return dict(row) if row else None


def is_owned(bottle: dict) -> bool:
    return not bottle["archived"] and bottle["state"] != "empty"


def for_shade(conn: sqlite3.Connection, shade_id: int) -> list[dict]:
    """Every bottle of a shade, newest first, archived ones last."""
    rows = conn.execute(
        f"{_SELECT} where b.shade_id = ? order by b.archived, b.id desc", (shade_id,)
    )
    return [dict(r) for r in rows]


def list_groups(conn: sqlite3.Connection, state: str = "", archived: bool = False) -> list[dict]:
    """The /bottles page: bottles grouped by shade (alphabetical), newest bottle first inside a
    group. `archived` picks archived bottles only; the default hides them. An unknown `state`
    means no filter."""
    where = ["b.archived = ?"]
    args: list = [int(archived)]
    if state in STATES:
        where.append("b.state = ?")
        args.append(state)
    rows = conn.execute(
        f"{_SELECT} where {' and '.join(where)} order by s.title collate nocase, s.id, b.id desc",
        args,
    )
    groups: list[dict] = []
    for row in map(dict, rows):
        if not groups or groups[-1]["shade_id"] != row["shade_id"]:
            groups.append(
                {
                    "shade_id": row["shade_id"],
                    "title": row["title"],
                    "hero_image_url": row["hero_image_url"],
                    "tip": row,
                    "bottles": [],
                }
            )
        groups[-1]["bottles"].append(row)
    return groups


def recent(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """The latest bottles that are not archived, for the home page."""
    rows = conn.execute(f"{_SELECT} where b.archived = 0 order by b.id desc limit ?", (limit,))
    return [dict(r) for r in rows]


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Bottles owned (not archived, not empty) and shades owned, for the home page."""
    bottles = conn.execute(
        "select count(*) from bottle where archived = 0 and state <> 'empty'"
    ).fetchone()[0]
    shades = conn.execute("select count(*) from shade_status where owned_count > 0").fetchone()[0]
    return {"bottles": bottles, "shades": shades}


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def group_history(rows: list[dict]) -> list[dict]:
    """Bottle rows (any order) as years -> months -> rows, newest first. A bottle is dated by
    `bought_on`, or by the date part of `created_at` when that is empty (`dated_by_entry`). Totals
    add `price_paid_cents`; a bottle without a price counts in `unpriced`, not in the total."""
    dated = []
    for row in rows:
        entry = dict(row)
        entry["dated_by_entry"] = not row["bought_on"]
        entry["date"] = row["bought_on"] or row["created_at"][:10]
        dated.append(entry)
    dated.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    years: list[dict] = []
    for entry in dated:
        year, month = entry["date"][:4], entry["date"][5:7]
        if not years or years[-1]["year"] != year:
            years.append({"year": year, "months": []})
        months = years[-1]["months"]
        if not months or months[-1]["month"] != month:
            name = calendar.month_name[int(month)]
            months.append({"month": month, "label": f"{name} {year}", "rows": []})
        months[-1]["rows"].append(entry)
    for year in years:
        for month in year["months"]:
            _totals(month, month["rows"])
        _totals(year, [r for m in year["months"] for r in m["rows"]])
    return years


def _totals(target: dict, rows: list[dict]) -> None:
    priced = [r["price_paid_cents"] for r in rows if r["price_paid_cents"] is not None]
    target["count"] = len(rows)
    target["total_cents"] = sum(priced)
    target["unpriced"] = len(rows) - len(priced)
    target["count_text"] = _plural(len(rows), "bottle")


def history(conn: sqlite3.Connection) -> list[dict]:
    """The purchase history: every bottle, archived and empty ones included, by month bought."""
    rows = conn.execute(f"{_SELECT} order by b.id")
    return group_history([dict(r) for r in rows])
