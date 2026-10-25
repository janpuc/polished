"""Layer stacks: the working draft behind a wheel slot's builder sheet, and the saved swatch it
becomes (DESIGN 10). Takes a connection; routes never write SQL.

A stack is edited only while it is a draft that some slot points at (`wheel_slot.draft_stack_id`);
every operation on any other stack raises NotADraft, which routes answer with 409. Functions that
write several rows run in one transaction, or join the caller's.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from .catalog.parse import fold
from .db import atomic

MAX_LAYERS = 8
MIN_COATS = 1
MAX_COATS = 5
NAME_LIMIT = 80
NOTE_LIMIT = 500
COPY_SOURCES_LIMIT = 20

# Milliseconds, so two stacks saved within a second still sort in the order they were saved
# ("same as last"). The column default has seconds only.
_NOW_MS = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"

# stack_layer sl join shade s: a layer and what a chip shows of its shade.
_LAYER_SELECT = (
    "select sl.id, sl.stack_id, sl.ord, sl.shade_id, sl.coats, s.title, s.handle,"
    " s.hero_image_url from stack_layer sl join shade s on s.id = sl.shade_id"
)


class StackError(Exception):
    """Base of the refusals below; routes map each subclass to a status code."""


class NotADraft(StackError):
    """The stack is not a draft that a slot points at (409)."""


class LayerNotFound(StackError):
    """The layer does not belong to the stack (404)."""


class ShadeNotFound(StackError):
    """No such shade (404)."""


class SlotNotFound(StackError):
    """No such wheel, or a position outside 1..slot_count (404)."""


class SourceNotFound(StackError):
    """The stack to copy from is not a saved stack (404)."""


class StackFull(StackError):
    """The stack already has MAX_LAYERS layers (422)."""


class EmptyStack(StackError):
    """Save needs at least one layer (422)."""


@dataclass(frozen=True)
class SlotRef:
    wheel_id: int
    position: int


@dataclass(frozen=True)
class OpenedDraft:
    stack_id: int
    resumed: bool  # True when the slot already had a draft ("Resumed your draft")


def default_coats(shade) -> int:
    """1 for top coats, base coats and toppers, 2 for other polish. `shade` needs kind and
    is_topper."""
    if shade["kind"] in ("topcoat", "basecoat") or shade["is_topper"]:
        return 1
    return 2


def layer_labels(count: int) -> list[str]:
    """Painting-order labels: none for one layer, then Base, 2nd, 3rd, ..., Top."""
    if count <= 1:
        return [""] * count
    middle = [f"{n}{'nd' if n == 2 else 'rd' if n == 3 else 'th'}" for n in range(2, count)]
    return ["Base", *middle, "Top"]


def summary(layers: list) -> str:
    """ "One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco": painting order, ×N above 1."""
    return " + ".join(
        f"{layer['title']} ×{layer['coats']}" if layer["coats"] > 1 else layer["title"]
        for layer in layers
    )


def layers_by_stack(conn: sqlite3.Connection, stack_ids: list[int]) -> dict[int, list[dict]]:
    """The layers of each stack in painting order, with their labels, in one query."""
    result: dict[int, list[dict]] = {stack_id: [] for stack_id in stack_ids}
    if not stack_ids:
        return result
    marks = ",".join("?" * len(stack_ids))
    rows = conn.execute(
        f"{_LAYER_SELECT} where sl.stack_id in ({marks}) order by sl.stack_id, sl.ord", stack_ids
    )
    for row in rows:
        result[row["stack_id"]].append(dict(row))
    for layers in result.values():
        for layer, label in zip(layers, layer_labels(len(layers)), strict=True):
            layer["label"] = label
    return result


def layers(conn: sqlite3.Connection, stack_id: int) -> list[dict]:
    return layers_by_stack(conn, [stack_id])[stack_id]


def _slot_of_draft(conn: sqlite3.Connection, stack_id: int) -> SlotRef:
    row = conn.execute(
        "select ws.wheel_id, ws.position from wheel_slot ws join stack st on st.id = ws.draft_stack_id"
        " where ws.draft_stack_id = ? and st.status = 'draft'",
        (stack_id,),
    ).fetchone()
    if row is None:
        raise NotADraft(stack_id)
    return SlotRef(row["wheel_id"], row["position"])


def _layer(conn: sqlite3.Connection, stack_id: int, layer_id: int) -> sqlite3.Row:
    row = conn.execute(
        "select id, ord, coats from stack_layer where id = ? and stack_id = ?", (layer_id, stack_id)
    ).fetchone()
    if row is None:
        raise LayerNotFound(layer_id)
    return row


def _count(conn: sqlite3.Connection, stack_id: int) -> int:
    return conn.execute(
        "select count(*) from stack_layer where stack_id = ?", (stack_id,)
    ).fetchone()[0]


def _clean(raw: str | None, limit: int) -> str | None:
    return (raw or "").strip()[:limit] or None


def slot_of(conn: sqlite3.Connection, stack_id: int) -> SlotRef:
    """The slot whose draft this is. Raises NotADraft: this is the 409 guard."""
    return _slot_of_draft(conn, stack_id)


def sheet(conn: sqlite3.Connection, stack_id: int) -> dict:
    """Everything the builder sheet shows for a draft: the slot, its wheel, the layers with
    labels, the live summary, and the saved note and date of the slot. Raises NotADraft."""
    ref = _slot_of_draft(conn, stack_id)
    row = conn.execute(
        "select w.name as wheel_name, w.slug as wheel_slug, ws.note, ws.painted_on, st.name"
        " from wheel_slot ws join wheel w on w.id = ws.wheel_id"
        " join stack st on st.id = ws.draft_stack_id"
        " where ws.wheel_id = ? and ws.position = ?",
        (ref.wheel_id, ref.position),
    ).fetchone()
    stack_layers = layers(conn, stack_id)
    return {
        "stack_id": stack_id,
        "wheel_id": ref.wheel_id,
        "position": ref.position,
        **dict(row),
        "layers": stack_layers,
        "summary": summary(stack_layers),
        "full": len(stack_layers) >= MAX_LAYERS,
    }


def open_draft(conn: sqlite3.Connection, wheel_id: int, position: int) -> OpenedDraft:
    """Open the builder on a slot: resume its draft, or start one holding a copy of the slot's
    saved layers (and name), or nothing. Creates the slot row when missing."""
    with atomic(conn):
        wheel = conn.execute("select slot_count from wheel where id = ?", (wheel_id,)).fetchone()
        if wheel is None or not 1 <= position <= wheel["slot_count"]:
            raise SlotNotFound((wheel_id, position))
        conn.execute(
            "insert or ignore into wheel_slot (wheel_id, position) values (?, ?)",
            (wheel_id, position),
        )
        slot = conn.execute(
            "select stack_id, draft_stack_id from wheel_slot where wheel_id = ? and position = ?",
            (wheel_id, position),
        ).fetchone()
        if slot["draft_stack_id"] is not None:
            return OpenedDraft(slot["draft_stack_id"], resumed=True)
        name = None
        if slot["stack_id"] is not None:
            name = conn.execute(
                "select name from stack where id = ?", (slot["stack_id"],)
            ).fetchone()["name"]
        draft_id = conn.execute("insert into stack (name) values (?)", (name,)).lastrowid
        if slot["stack_id"] is not None:
            _copy_layers(conn, slot["stack_id"], draft_id)
        conn.execute(
            "update wheel_slot set draft_stack_id = ? where wheel_id = ? and position = ?",
            (draft_id, wheel_id, position),
        )
        return OpenedDraft(draft_id, resumed=False)


def _copy_layers(conn: sqlite3.Connection, source_id: int, target_id: int) -> None:
    conn.execute(
        "insert into stack_layer (stack_id, ord, shade_id, coats)"
        " select ?, ord, shade_id, coats from stack_layer where stack_id = ? order by ord",
        (target_id, source_id),
    )


def append(conn: sqlite3.Connection, stack_id: int, shade_id: int) -> int:
    """Paint one more layer on top, with the shade's default coats. Returns the layer id."""
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        shade = conn.execute(
            "select kind, is_topper from shade where id = ?", (shade_id,)
        ).fetchone()
        if shade is None:
            raise ShadeNotFound(shade_id)
        count = _count(conn, stack_id)
        if count >= MAX_LAYERS:
            raise StackFull(stack_id)
        return conn.execute(
            "insert into stack_layer (stack_id, ord, shade_id, coats) values (?, ?, ?, ?)",
            (stack_id, count + 1, shade_id, default_coats(shade)),
        ).lastrowid


def move(conn: sqlite3.Connection, stack_id: int, layer_id: int, direction: str) -> bool:
    """Swap a layer with its neighbour: "up" is towards the base (the list shows Base first).
    False when it is already at that end. (stack_id, ord) is unique and ord >= 1, so the swap
    parks one layer on ord = count + 1 meanwhile."""
    if direction not in ("up", "down"):
        raise ValueError(f"direction must be up or down, got {direction!r}")
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        layer = _layer(conn, stack_id, layer_id)
        count = _count(conn, stack_id)
        other_ord = layer["ord"] - 1 if direction == "up" else layer["ord"] + 1
        if not 1 <= other_ord <= count:
            return False
        other = conn.execute(
            "select id from stack_layer where stack_id = ? and ord = ?", (stack_id, other_ord)
        ).fetchone()
        update = "update stack_layer set ord = ? where id = ?"
        conn.execute(update, (count + 1, layer_id))
        conn.execute(update, (layer["ord"], other["id"]))
        conn.execute(update, (other_ord, layer_id))
        return True


def change_coats(conn: sqlite3.Connection, stack_id: int, layer_id: int, delta: int) -> int:
    """Add or take off one coat, clamped to 1..5. Returns the new count."""
    if delta not in (-1, 1):
        raise ValueError(f"delta must be -1 or 1, got {delta!r}")
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        layer = _layer(conn, stack_id, layer_id)
        coats = min(MAX_COATS, max(MIN_COATS, layer["coats"] + delta))
        conn.execute("update stack_layer set coats = ? where id = ?", (coats, layer_id))
        return coats


def remove(conn: sqlite3.Connection, stack_id: int, layer_id: int) -> None:
    """Delete a layer and renumber the rest 1..n."""
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        layer = _layer(conn, stack_id, layer_id)
        conn.execute("delete from stack_layer where id = ?", (layer_id,))
        # One row at a time, lowest first: a single update could hit the unique (stack_id, ord)
        # midway, depending on the order SQLite visits the rows.
        later = conn.execute(
            "select id, ord from stack_layer where stack_id = ? and ord > ? order by ord",
            (stack_id, layer["ord"]),
        ).fetchall()
        for row in later:
            conn.execute("update stack_layer set ord = ? where id = ?", (row["ord"] - 1, row["id"]))


def over_black_shade(conn: sqlite3.Connection, handle: str) -> dict | None:
    """The shade the "Over black" template inserts, None when the catalog lacks the handle (the
    button is then hidden)."""
    row = conn.execute(
        "select id, title, kind, is_topper from shade where handle = ? order by id limit 1",
        (handle,),
    ).fetchone()
    return dict(row) if row else None


def over_black(conn: sqlite3.Connection, stack_id: int, handle: str) -> str:
    """Insert the black base at ord 1 with one coat. Returns "added", "already" (the first
    layer is that shade; nothing changes) or "unavailable" (no shade has the handle)."""
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        black = over_black_shade(conn, handle)
        if black is None:
            return "unavailable"
        first = conn.execute(
            "select shade_id from stack_layer where stack_id = ? and ord = 1", (stack_id,)
        ).fetchone()
        if first is not None and first["shade_id"] == black["id"]:
            return "already"
        count = _count(conn, stack_id)
        if count >= MAX_LAYERS:
            raise StackFull(stack_id)
        # Highest first, for the same reason as in remove().
        rows = conn.execute(
            "select id, ord from stack_layer where stack_id = ? order by ord desc", (stack_id,)
        ).fetchall()
        for row in rows:
            conn.execute("update stack_layer set ord = ? where id = ?", (row["ord"] + 1, row["id"]))
        conn.execute(
            "insert into stack_layer (stack_id, ord, shade_id, coats) values (?, 1, ?, 1)",
            (stack_id, black["id"]),
        )
        return "added"


def copy_from(conn: sqlite3.Connection, stack_id: int, source_stack_id: int) -> int:
    """Replace the draft's layers with copies of a saved stack's rows. Returns the layer count.
    The draft never shares the source: editing one slot leaves the other alone."""
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        source = conn.execute(
            "select 1 from wheel_slot ws join stack st on st.id = ws.stack_id"
            " where ws.stack_id = ? and st.status = 'saved'",
            (source_stack_id,),
        ).fetchone()
        if source is None:
            raise SourceNotFound(source_stack_id)
        conn.execute("delete from stack_layer where stack_id = ?", (stack_id,))
        _copy_layers(conn, source_stack_id, stack_id)
        return _count(conn, stack_id)


def last_saved_id(conn: sqlite3.Connection) -> int | None:
    """The saved stack held by a slot that was saved most recently, or None."""
    row = conn.execute(
        "select st.id from stack st join wheel_slot ws on ws.stack_id = st.id"
        " where st.status = 'saved' order by st.updated_at desc, st.id desc limit 1"
    ).fetchone()
    return row["id"] if row else None


def same_as_last(conn: sqlite3.Connection, stack_id: int) -> int | None:
    """copy_from() the most recently saved stack. Returns the layer count, None when nothing has
    been saved yet (the draft is left alone)."""
    with atomic(conn):
        _slot_of_draft(conn, stack_id)
        source_id = last_saved_id(conn)
        if source_id is None:
            return None
        return copy_from(conn, stack_id, source_id)


def copy_sources(
    conn: sqlite3.Connection, query: str = "", limit: int = COPY_SOURCES_LIMIT
) -> list[dict]:
    """Saved stacks to copy from, most recently saved first: stack_id, wheel_name, wheel_slug,
    position, name, painted_on, layers and summary. `query` keeps the stacks with a layer whose
    shade name contains it (accent- and case-insensitive)."""
    where = ["st.status = 'saved'"]
    args: list = []
    folded = fold(query).strip()
    if folded:
        where.append(
            "exists (select 1 from stack_layer sl join shade s on s.id = sl.shade_id"
            " where sl.stack_id = st.id and s.search_text like ? escape '\\')"
        )
        escaped = folded.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        args.append(f"%{escaped}%")
    rows = conn.execute(
        "select st.id as stack_id, st.name, ws.position, ws.painted_on, w.name as wheel_name,"
        " w.slug as wheel_slug, w.id as wheel_id"
        " from stack st join wheel_slot ws on ws.stack_id = st.id"
        " join wheel w on w.id = ws.wheel_id"
        f" where {' and '.join(where)} order by st.updated_at desc, st.id desc limit ?",
        [*args, limit],
    ).fetchall()
    found = [dict(r) for r in rows]
    by_stack = layers_by_stack(conn, [r["stack_id"] for r in found])
    for item in found:
        item["layers"] = by_stack[item["stack_id"]]
        item["summary"] = summary(item["layers"])
    return found


def save(
    conn: sqlite3.Connection,
    stack_id: int,
    name: str = "",
    note: str = "",
    painted_on: str = "",
    today: date | None = None,
) -> SlotRef:
    """Commit the draft to its slot: it replaces the slot's previous saved stack (deleted, its
    layers with it), the draft pointer clears, and the name, note and painted-on date are stored.
    A blank `painted_on` means `today` (default: the machine's date; routes pass the household's).
    Raises EmptyStack without layers and ValueError for a date that is not YYYY-MM-DD."""
    typed = painted_on.strip()
    day = date.fromisoformat(typed) if typed else today or date.today()
    with atomic(conn):
        ref = _slot_of_draft(conn, stack_id)
        if _count(conn, stack_id) == 0:
            raise EmptyStack(stack_id)
        old = conn.execute(
            "select stack_id from wheel_slot where wheel_id = ? and position = ?",
            (ref.wheel_id, ref.position),
        ).fetchone()["stack_id"]
        conn.execute(
            "update wheel_slot set stack_id = ?, draft_stack_id = null, painted_on = ?, note = ?"
            " where wheel_id = ? and position = ?",
            (stack_id, day.isoformat(), _clean(note, NOTE_LIMIT), ref.wheel_id, ref.position),
        )
        conn.execute(
            f"update stack set status = 'saved', name = ?, updated_at = {_NOW_MS} where id = ?",
            (_clean(name, NAME_LIMIT), stack_id),
        )
        if old is not None:
            conn.execute("delete from stack where id = ?", (old,))
        return ref


def cancel(conn: sqlite3.Connection, stack_id: int) -> SlotRef:
    """Discard the draft. The slot row goes too when it then holds no saved stack and no note."""
    with atomic(conn):
        ref = _slot_of_draft(conn, stack_id)
        conn.execute(
            "update wheel_slot set draft_stack_id = null where wheel_id = ? and position = ?",
            (ref.wheel_id, ref.position),
        )
        conn.execute("delete from stack where id = ?", (stack_id,))
        conn.execute(
            "delete from wheel_slot where wheel_id = ? and position = ?"
            " and stack_id is null and coalesce(note, '') = ''",
            (ref.wheel_id, ref.position),
        )
        return ref


def clear_slot(conn: sqlite3.Connection, wheel_id: int, position: int) -> None:
    """Remove a swatch: the saved stack, any draft and the slot row. Nothing happens for a slot
    without a row."""
    with atomic(conn):
        slot = conn.execute(
            "select stack_id, draft_stack_id from wheel_slot where wheel_id = ? and position = ?",
            (wheel_id, position),
        ).fetchone()
        if slot is None:
            return
        conn.execute(
            "delete from wheel_slot where wheel_id = ? and position = ?", (wheel_id, position)
        )
        for stack_id in (slot["stack_id"], slot["draft_stack_id"]):
            if stack_id is not None:
                conn.execute("delete from stack where id = ?", (stack_id,))
