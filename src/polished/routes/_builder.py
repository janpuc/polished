"""What the wheel and stack routes share: the slot tile, list and count that every swatch change
swaps out of band, the builder sheet's context and the picker's rows (DESIGN 10)."""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request

from .. import bottles, identifiers, shades, stacks, wheels
from ..gtin import is_numeric

PICKER_TARGET = {"HX-Retarget": "#picker-results", "HX-Reswap": "innerHTML"}
SHEET_CLOSE = {"HX-Trigger": "sheetClose"}
PICKER_RESET = {"HX-Trigger": "pickerReset"}

# StackError subclass -> status; the 422s are answered with a fragment by the routes that can
# produce them, the rest as plain errors.
STATUS = {
    stacks.NotADraft: 409,
    stacks.LayerNotFound: 404,
    stacks.ShadeNotFound: 404,
    stacks.SlotNotFound: 404,
    stacks.SourceNotFound: 404,
    stacks.StackFull: 422,
    stacks.EmptyStack: 422,
}


def fail(error: stacks.StackError) -> HTTPException:
    return HTTPException(STATUS.get(type(error), 409), type(error).__name__)


def today(request: Request) -> str:
    return datetime.now(ZoneInfo(request.app.state.settings.timezone)).date().isoformat()


def slot_swap(conn: sqlite3.Connection, wheel_id: int, position: int, *, saved: bool = False):
    """The tile of one slot, the list of filled slots and the count, rendered out of band by
    `_slot_swap.html` after a save, a cancel, a clear or the opening of a draft."""
    wheel = wheels.get(conn, wheel_id)
    tiles = wheels.slot_grid(conn, wheel)
    filled = [t for t in tiles if t["filled"]]
    return {
        "wheel": wheel,
        "tile": tiles[position - 1],
        "filled": filled,
        "filled_count": len(filled),
        "saved": saved,
        "oob": True,
    }


def default_scope(conn: sqlite3.Connection) -> str:
    """Owned shades first, unless the household owns none yet (then the picker would be empty)."""
    return "owned" if bottles.counts(conn)["shades"] else "all"


def picker(conn: sqlite3.Connection, stack_id: int, q: str, scope: str) -> dict:
    """The rows under the builder's search field. A P code or barcode that the resolver knows
    comes first as a suggestion (DESIGN 7.2); a name gives ordinary rows, owned shades first."""
    scope = scope if scope in shades.PICK_SCOPES else "owned"
    q = q.strip()
    context = {
        "stack_id": stack_id,
        "q": q,
        "scope": scope,
        "suggestion": None,
        "unknown_code": None,
        "result": None,
        "full": len(stacks.layers(conn, stack_id)) >= stacks.MAX_LAYERS,
    }
    if q and (is_numeric(q) or identifiers.normalise_printed(q)):
        resolution = identifiers.resolve(conn, q)
        if resolution.outcome in ("match", "suggestion"):
            context["suggestion"] = resolution
            return context
        if resolution.outcome in ("unknown_code", "unknown_printed", "invalid_code"):
            context["unknown_code"] = resolution
    if not q or shades.tokens(q):
        context["result"] = shades.pick(conn, q, scope)
    return context


def layers_context(request: Request, conn: sqlite3.Connection, stack_id: int, **extra) -> dict:
    """The layer list, the templates row and the live summary of a draft. `layers_oob` is for
    `_stack_layers.html` alone (the summary and the Save button ride along out of band); the slot
    swap has its own `oob`, which the opening of a draft sets for `_slot_swap.html`."""
    sheet = stacks.sheet(conn, stack_id)
    handle = request.app.state.settings.over_black_handle
    first = sheet["layers"][0] if sheet["layers"] else None
    return {
        "s": sheet,
        "has_black": stacks.over_black_shade(conn, handle) is not None,
        "black_first": bool(first and first["handle"] == handle),
        "can_copy": stacks.last_saved_id(conn) is not None,
        "notice": None,
        "new_layer_id": None,
        "layers_oob": False,
        "picker": None,
        **extra,
    }


def sheet_context(
    request: Request, conn: sqlite3.Connection, stack_id: int, *, resumed: bool = False
) -> dict:
    scope = default_scope(conn)
    context = layers_context(request, conn, stack_id, resumed=resumed)
    sheet = context["s"]
    context.update(
        scope=scope,
        picker_ctx=picker(conn, stack_id, "", scope),
        saved_slot=wheels.slot_tile(conn, wheels.get(conn, sheet["wheel_id"]), sheet["position"])[
            "filled"
        ],
        today=today(request),
        painted_on=sheet["painted_on"] or today(request),
    )
    return context
