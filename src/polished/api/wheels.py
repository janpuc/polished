"""GET /wheels, /wheels/{id} and /w/{slug} (what the NFC tag opens)."""

from fastapi import APIRouter

from .. import wheels
from . import rows, schemas
from .errors import not_found
from .routing import ApiRoute, AppSettings, Conn

router = APIRouter(route_class=ApiRoute, tags=["wheels"])


def _with_tiles(conn, settings, wheel: dict) -> schemas.WheelWithTiles:
    tiles = wheels.slot_grid(conn, wheel)
    fields = rows.wheel_fields(wheel, settings.public_url, tiles)
    return schemas.WheelWithTiles(**fields, tiles=[rows.tile(t) for t in tiles])


def _detail(conn, settings, wheel: dict) -> schemas.WheelDetail:
    tiles = wheels.slot_grid(conn, wheel)
    every = wheels.list_wheels(conn) + wheels.list_wheels(conn, archived=True)
    return schemas.WheelDetail(
        **rows.wheel_fields(wheel, settings.public_url, tiles),
        tiles=[rows.tile(t) for t in tiles],
        filled_count=sum(t["filled"] for t in tiles),
        others=[
            schemas.WheelRef(id=w["id"], name=w["name"], slug=w["slug"])
            for w in every
            if w["id"] != wheel["id"]
        ],
    )


@router.get("/wheels", response_model=schemas.Wheels, summary="Wheels with their tiles")
def wheel_list(conn: Conn, settings: AppSettings, archived: bool = False):
    """By name; `archived=true` lists the archived ones only."""
    return schemas.Wheels(
        items=[_with_tiles(conn, settings, w) for w in wheels.list_wheels(conn, archived)]
    )


@router.get(
    "/wheels/{wheel_id}",
    response_model=schemas.WheelDetail,
    summary="One wheel by id",
    responses={404: {"description": "`not_found`"}},
)
def wheel_by_id(conn: Conn, settings: AppSettings, wheel_id: int):
    wheel = wheels.get(conn, wheel_id)
    if wheel is None:
        raise not_found("There is no wheel with that address.")
    return _detail(conn, settings, wheel)


@router.get(
    "/w/{slug}",
    response_model=schemas.WheelDetail,
    summary="One wheel by its tag slug",
    responses={404: {"description": "`not_found`"}},
)
def wheel_by_slug(conn: Conn, settings: AppSettings, slug: str):
    """What `https://…/w/<slug>` on a sticker or QR code opens. An unknown slug is a 404 (after
    sign-in, as on the web)."""
    wheel = wheels.get_by_slug(conn, slug)
    if wheel is None:
        raise not_found("There is no wheel with that address. The tag may be old.")
    return _detail(conn, settings, wheel)
