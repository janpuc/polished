"""Wheels: GET /wheels, /wheels/{id} and /w/{slug} (what the NFC tag opens), and the writes
(create, rename, archive, delete, the tag's slug, the slots)."""

from fastapi import APIRouter, Response

from .. import stacks, wheels
from . import rows, schemas
from .errors import ApiError, invalid, not_found
from .routing import ApiRoute, AppSettings, Conn
from .stacks import sheet_body

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


def wheel_or_404(conn, wheel_id: int) -> dict:
    wheel = wheels.get(conn, wheel_id)
    if wheel is None:
        raise not_found("There is no wheel with that address.")
    return wheel


def wheel_body(conn, settings, wheel_id: int) -> schemas.Wheel:
    wheel = wheel_or_404(conn, wheel_id)
    return rows.wheel(wheel, settings.public_url, wheels.slot_grid(conn, wheel))


@router.post(
    "/wheels",
    status_code=201,
    response_model=schemas.Wheel,
    summary="Make a wheel",
    responses={422: {"description": "`validation`: `name` or `slot_count`."}},
)
def create_wheel(conn: Conn, settings: AppSettings, body: schemas.WheelRequest):
    try:
        wheel_id = wheels.create(conn, body.name, body.slot_count)
    except ValueError as exc:
        field = "slot_count" if "slots" in str(exc) else "name"
        raise invalid({field: str(exc)}) from None
    return wheel_body(conn, settings, wheel_id)


@router.patch(
    "/wheels/{wheel_id}",
    response_model=schemas.Wheel,
    summary="Rename, archive or restore a wheel",
    responses={404: {"description": "`not_found`"}, 422: {"description": "`validation`"}},
)
def edit_wheel(conn: Conn, settings: AppSettings, wheel_id: int, body: schemas.WheelPatch):
    """`name` and/or `archived`. The slug stays, so the tag keeps opening the wheel."""
    wheel_or_404(conn, wheel_id)
    sent = body.model_fields_set & {"name", "archived"}
    if not sent or (body.name is None and body.archived is None):
        raise invalid({"name": "Give a name or archived."})
    if body.name is not None:
        try:
            wheels.rename(conn, wheel_id, body.name)
        except ValueError as exc:
            raise invalid({"name": str(exc)}) from None
    if body.archived is not None:
        wheels.set_archived(conn, wheel_id, body.archived)
    return wheel_body(conn, settings, wheel_id)


@router.delete(
    "/wheels/{wheel_id}",
    response_model=schemas.WheelDeleted,
    summary="Delete a wheel with its swatches and drafts",
    responses={404: {"description": "`not_found`"}},
)
def delete_wheel(conn: Conn, wheel_id: int):
    """For good, no undo: the app asks first (the web's confirmation sheet). Shades and bottles
    are untouched; the tag then opens a 404."""
    try:
        deleted = wheels.delete(conn, wheel_id)
    except wheels.WheelNotFound:
        raise not_found("There is no wheel with that address.") from None
    return schemas.WheelDeleted(deleted_swatches=deleted)


@router.post(
    "/wheels/{wheel_id}/slug/regenerate",
    response_model=schemas.Wheel,
    summary="Give the wheel a new tag address",
    responses={404: {"description": "`not_found`"}},
)
def regenerate_slug(conn: Conn, settings: AppSettings, wheel_id: int):
    """The old sticker then opens a 404."""
    try:
        wheels.regenerate_slug(conn, wheel_id)
    except wheels.WheelNotFound:
        raise not_found("There is no wheel with that address.") from None
    return wheel_body(conn, settings, wheel_id)


@router.post(
    "/wheels/{wheel_id}/slug/take",
    response_model=schemas.Wheel,
    summary="Take the tag of another wheel",
    responses={
        404: {"description": "`not_found`: either wheel."},
        422: {"description": "`same_wheel`"},
    },
)
def take_tag(conn: Conn, settings: AppSettings, wheel_id: int, body: schemas.TakeTagRequest):
    """The two wheels swap slugs: the sticker on `from_wheel_id` now opens this wheel and the
    other way round."""
    try:
        wheels.take_tag(conn, wheel_id, body.from_wheel_id)
    except wheels.WheelNotFound:
        raise not_found("There is no wheel with that address.") from None
    except ValueError as exc:
        raise ApiError(422, "same_wheel", str(exc), "from_wheel_id") from None
    return wheel_body(conn, settings, wheel_id)


@router.post(
    "/wheels/{wheel_id}/slots/{position}/draft",
    response_model=schemas.StackOpened,
    summary="Open the builder on a slot",
    responses={
        404: {"description": "`not_found`: no such wheel, or a position outside the wheel."}
    },
)
def open_slot_draft(conn: Conn, wheel_id: int, position: int):
    """Resumes the slot's draft (`resumed` true), or starts one holding a copy of the saved
    swatch's layers."""
    try:
        opened = stacks.open_draft(conn, wheel_id, position)
    except stacks.SlotNotFound:
        raise not_found("There is no such slot.") from None
    return schemas.StackOpened(
        **sheet_body(conn, opened.stack_id).model_dump(), resumed=opened.resumed
    )


@router.delete(
    "/wheels/{wheel_id}/slots/{position}",
    status_code=204,
    summary="Clear a slot's swatch",
    responses={
        404: {"description": "`not_found`: no such wheel, or a position outside the wheel."}
    },
)
def clear_slot(conn: Conn, wheel_id: int, position: int) -> Response:
    """The saved swatch and any draft go. Clearing an empty slot is fine."""
    wheel = wheel_or_404(conn, wheel_id)
    if not 1 <= position <= wheel["slot_count"]:
        raise not_found("There is no such slot.")
    stacks.clear_slot(conn, wheel_id, position)
    return Response(status_code=204)
