"""Domain dicts as response models. The domain modules answer with dicts shaped for templates;
this is the one place that turns them into the shapes of schemas.py."""

import sqlite3

from .. import shades, tips
from ..shades import _COLUMNS, FROM
from . import schemas
from .schemas import Bottle, Layer, ShadeRow, Tile, Tip, Wheel


def tip_model(shade: tips.TipShade) -> Tip:
    return Tip(
        id=shade.id,
        hex=shade.hex,
        hex2=shade.hex2,
        finishes=sorted(shade.finishes),
        topper=shade.topper,
        clear=shade.clear,
        coats=shade.coats,
        colours=sorted(shade.colours or ()),
        revision=tips.revision([shade]),
    )


def _extras(conn: sqlite3.Connection, ids: list[int]) -> dict[int, dict]:
    """What a ShadeRow needs that the list, picker and detail queries do not all carry: the release
    date, the official collection and the shop's colour tags (the tip renderer reads them)."""
    extras: dict[int, dict] = {}
    if not ids:
        return extras
    marks = ", ".join("?" * len(ids))
    for row in conn.execute(
        f"select id, released_on, official_collection from shade where id in ({marks})", ids
    ):
        extras[row["id"]] = {
            "released_on": row["released_on"],
            "official_collection": row["official_collection"],
            "colours": [],
        }
    for tag in conn.execute(
        "select shade_id, value from shade_tag where ns = 'color'"
        f" and shade_id in ({marks}) order by value",
        ids,
    ):
        extras[tag["shade_id"]]["colours"].append(tag["value"])
    return extras


def _status(status: shades.Status | None) -> schemas.Status | None:
    if status is None:
        return None
    return schemas.Status(key=status.key, label=status.label, buyable=status.buyable)


def shade_rows(conn: sqlite3.Connection, rows: list[dict]) -> list[ShadeRow]:
    """Shade dicts of shades.list_shades, shades.get_shade or rows_by_id as ShadeRows."""
    extras = _extras(conn, [row["id"] for row in rows])
    made = []
    for row in rows:
        row = {**row, **extras[row["id"]]}
        finishes = row["finishes"]
        if isinstance(finishes, str):
            finishes = [f for f in finishes.split(",") if f]
        made.append(
            ShadeRow(
                id=row["id"],
                title=row["title"],
                kind=row["kind"],
                source=row["source"],
                is_topper=bool(row["is_topper"]),
                price_cents=row["price_cents"],
                compare_at_cents=row["compare_at_cents"],
                status=_status(row["status"]),
                finishes=finishes,
                owned_count=row["owned_count"] or 0,
                wishlisted=bool(row["wishlisted"]),
                hero_image_url=row["hero_image_url"],
                released_on=row["released_on"],
                official_collection=row["official_collection"],
                marks=[list(span) for span in row.get("marks", ())],
                tip=tip_model(tips.tip_shade({**row, "finishes": finishes})),
            )
        )
    return made


def shade_row(conn: sqlite3.Connection, row: dict) -> ShadeRow:
    return shade_rows(conn, [row])[0]


def rows_by_id(conn: sqlite3.Connection, ids: list[int]) -> dict[int, ShadeRow]:
    """ShadeRows for known shade ids (bottles, wishlist items, identifiers point at shades by id)."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    marks = ", ".join("?" * len(ids))
    found = conn.execute(f"select {_COLUMNS} {FROM} where s.id in ({marks})", ids).fetchall()
    return {row.id: row for row in shade_rows(conn, shades._with_finishes(conn, found))}


def bottle(row: dict) -> Bottle:
    return Bottle(
        id=row["id"],
        shade_id=row["shade_id"],
        state=row["state"],
        bought_on=row["bought_on"],
        price_paid_cents=row["price_paid_cents"],
        opened_on=row["opened_on"],
        notes=row["notes"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def layer(row: dict) -> Layer:
    return Layer(
        id=row["id"],
        ord=row["ord"],
        shade_id=row["shade_id"],
        title=row["title"],
        coats=row["coats"],
        label=row["label"],
        tip=tip_model(tips.tip_shade(row)),
    )


def tile(row: dict) -> Tile:
    return Tile(
        position=row["position"],
        filled=row["filled"],
        has_draft=row["has_draft"],
        stack_id=row["stack_id"],
        draft_stack_id=row["draft_stack_id"],
        summary=row["summary"],
        layers=[layer(item) for item in row["layers"]],
        painted_on=row["painted_on"],
        note=row["note"],
    )


def wheel_fields(row: dict, public_url: str, tiles: list[dict] | None = None) -> dict:
    """The Wheel shape of a wheels.* dict; `filled` and `drafts` come from the dict when it has
    them (wheels.list_wheels) and are counted from `tiles` otherwise (wheels.get)."""
    if "filled" in row:
        filled, drafts = row["filled"], row["drafts"]
    else:
        filled = sum(t["filled"] for t in tiles or ())
        drafts = sum(t["has_draft"] for t in tiles or ())
    from .. import wheels

    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "slot_count": row["slot_count"],
        "archived": bool(row["archived"]),
        "filled": filled,
        "drafts": drafts,
        "tag_url": wheels.tag_url(public_url, row["slug"]),
        "created_at": row["created_at"],
    }


def wheel(row: dict, public_url: str, tiles: list[dict] | None = None) -> Wheel:
    return Wheel(**wheel_fields(row, public_url, tiles))
