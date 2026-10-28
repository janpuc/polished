"""Curated corrections to what the shop's feed says about a few shades (DESIGN 14, item 90).

The shop lists Matte Taco as a "Nail Polish" tagged only `color:clear`: no `finish:matte` tag
and not a top coat, so the tip renderer never learned it removes the gloss. An override is
applied when the shade is written and again on every sync (`apply_overrides`), because an
unchanged product is not written. Migration 011 backfills the shades synced before this."""

import sqlite3

# handle -> the finish tags the shop does not give it
FINISH_OVERRIDES: dict[str, tuple[str, ...]] = {"matte-taco": ("matte",)}
# handle -> the kind the shop does not give it
KIND_OVERRIDES: dict[str, str] = {"matte-taco": "topcoat"}


def override_kind(handle: str, kind: str | None) -> str | None:
    return KIND_OVERRIDES.get(handle, kind)


def override_pairs(handle: str, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """`pairs` (namespace, value) plus the curated finishes of `handle`."""
    extra = [("finish", value) for value in FINISH_OVERRIDES.get(handle, ())]
    return pairs + [pair for pair in extra if pair not in pairs]


def apply_overrides(conn: sqlite3.Connection) -> None:
    """Makes the stored shades of the shop match the overrides, whether or not their product changed."""
    for handle, kind in KIND_OVERRIDES.items():
        conn.execute(
            "update shade set kind = ?, is_topper = 1"
            " where handle = ? and source = 'holotaco' and (kind != ? or is_topper = 0)",
            (kind, handle, kind),
        )
    for handle, values in FINISH_OVERRIDES.items():
        for value in values:
            added = conn.execute(
                "insert or ignore into shade_tag (shade_id, ns, value)"
                " select id, 'finish', ? from shade where handle = ? and source = 'holotaco'",
                (value, handle),
            ).rowcount
            if added:
                conn.execute(
                    "update shade set search_text = search_text || ' ' || ?"
                    " where handle = ? and source = 'holotaco'",
                    (value, handle),
                )
