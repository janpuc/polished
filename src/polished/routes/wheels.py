"""Swatch wheels: the list, the wheel page, the tag page, the QR code and the two slot actions
that open and empty the builder (DESIGN 9, 10, 13.5)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from .. import shades, stacks, wheels
from ..db import get_conn
from ..web import is_partial_request, render
from ._builder import SHEET_CLOSE, fail, sheet_context, slot_swap

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

NO_WHEEL = {
    "message": "There is no wheel with that address. The tag may be old, or the link is wrong.",
    "cta_href": "/wheels",
    "cta_label": "See your wheels",
    "tab_key": "wheels",
}


def _wheel(conn: sqlite3.Connection, wheel_id: int) -> dict:
    wheel = wheels.get(conn, wheel_id)
    if wheel is None:
        raise HTTPException(404, "No such wheel")
    return wheel


def _wheel_or_page(request: Request, conn: sqlite3.Connection, wheel_id: int):
    wheel = wheels.get(conn, wheel_id)
    if wheel is None:
        return None, render(request, "not_found.html", NO_WHEEL, 404)
    return wheel, None


def _others(conn: sqlite3.Connection, wheel_id: int) -> list[dict]:
    """The wheels whose tag this one could take, archived ones last."""
    every = wheels.list_wheels(conn) + wheels.list_wheels(conn, True)
    return [w for w in every if w["id"] != wheel_id]


def _redirect(request: Request, url: str) -> Response:
    """A plain form gets a 302; a confirmed HTMX button gets HX-Redirect, since a swapped-in
    page would land in the wrong element."""
    if request.headers.get("hx-request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=302)


def _cards(conn: sqlite3.Connection, archived: bool) -> list[dict]:
    cards = wheels.list_wheels(conn, archived)
    for card in cards:
        card["tiles"] = wheels.slot_grid(conn, card)
    return cards


def _list_page(
    request: Request,
    conn: sqlite3.Connection,
    *,
    archived: bool = False,
    values: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    context = {
        "cards": _cards(conn, archived),
        "ghost": wheels.unpainted_ring(),
        "archived": archived,
        "archived_count": len(wheels.list_wheels(conn, True)),
        "values": values or {},
        "error": error,
        "default_slots": wheels.DEFAULT_SLOT_COUNT,
        "max_slots": wheels.MAX_SLOT_COUNT,
    }
    return render(request, "wheels.html", context, status_code)


@router.get("/wheels")
def wheel_list(request: Request, conn: Conn, archived: int = 0):
    return _list_page(request, conn, archived=bool(archived))


@router.post("/wheels")
def create_wheel(
    request: Request,
    conn: Conn,
    name: Annotated[str, Form()] = "",
    slot_count: Annotated[str, Form()] = "",
):
    values = {"name": name.strip()[: wheels.NAME_LIMIT], "slot_count": slot_count.strip()}
    try:
        count = int(values["slot_count"]) if values["slot_count"] else wheels.DEFAULT_SLOT_COUNT
    except ValueError:
        count = 0
    try:
        wheel_id = wheels.create(conn, name, count)
    except ValueError as exc:
        error = str(exc)
        return _list_page(request, conn, values=values, error=error, status_code=422)
    return RedirectResponse(f"/wheels/{wheel_id}/tag", status_code=302)


@router.get("/w/{slug}")
def wheel_page(request: Request, conn: Conn, slug: str, hl: str = ""):
    """The canonical page, and what the NFC tag and the QR code open. `hl` is a shade id: the
    slots whose stack contains it get the foil ring, the rest dim."""
    wheel = wheels.get_by_slug(conn, slug)
    if wheel is None:
        return render(request, "not_found.html", NO_WHEEL, 404)
    tiles = wheels.slot_grid(conn, wheel)
    filled = [t for t in tiles if t["filled"]]
    highlight = None
    if hl.isdecimal():
        shade = shades.get_shade(conn, int(hl))
        if shade is not None:
            positions = wheels.highlight_positions(conn, wheel["id"], shade["id"])
            highlight = {"shade": shade, "positions": positions}
    context = {
        "wheel": wheel,
        "tiles": tiles,
        "filled": filled,
        "filled_count": len(filled),
        "hl": highlight,
        "hl_positions": highlight["positions"] if highlight else [],
        "others": _others(conn, wheel["id"]),
        "oob": False,
        "saved": False,
    }
    return render(request, "wheel.html", context)


@router.get("/wheels/{wheel_id}/rename")
def rename_sheet(request: Request, conn: Conn, wheel_id: int):
    """The rename form as a sheet, opened from the wheel page."""
    return render(request, "_wheel_rename.html", {"wheel": _wheel(conn, wheel_id)})


@router.post("/wheels/{wheel_id}")
def rename_wheel(request: Request, conn: Conn, wheel_id: int, name: Annotated[str, Form()] = ""):
    wheel = _wheel(conn, wheel_id)
    try:
        wheels.rename(conn, wheel_id, name)
    except ValueError as exc:
        response = Response(str(exc), status_code=422)
        response.headers.update({"HX-Retarget": "#rename-status", "HX-Reswap": "innerHTML"})
        return response
    if not is_partial_request(request):
        return RedirectResponse(f"/w/{wheel['slug']}", status_code=302)
    response = render(request, "_wheel_name.html", {"wheel": _wheel(conn, wheel_id)})
    response.headers.update(SHEET_CLOSE)
    return response


@router.post("/wheels/{wheel_id}/archive")
def archive_wheel(
    request: Request, conn: Conn, wheel_id: int, archived: Annotated[int, Form()] = 1
):
    wheel = _wheel(conn, wheel_id)
    wheels.set_archived(conn, wheel_id, bool(archived))
    return _redirect(request, "/wheels" if archived else f"/w/{wheel['slug']}")


@router.get("/wheels/{wheel_id}/delete")
def delete_sheet(request: Request, conn: Conn, wheel_id: int):
    """The confirmation sheet for deleting a wheel, opened from the wheel page."""
    wheel = _wheel(conn, wheel_id)
    swatches = next(
        w["filled"]
        for w in wheels.list_wheels(conn, bool(wheel["archived"]))
        if w["id"] == wheel_id
    )
    return render(request, "_wheel_delete.html", {"wheel": wheel, "swatches": swatches})


@router.post("/wheels/{wheel_id}/delete")
def delete_wheel(request: Request, conn: Conn, wheel_id: int, confirm: Annotated[str, Form()] = ""):
    """Deletes the wheel with its swatches and drafts for good. Only the confirmation sheet sends
    `confirm=yes`; without it nothing is deleted (400)."""
    _wheel(conn, wheel_id)
    if confirm != "yes":
        raise HTTPException(400, "Confirm the deletion")
    try:
        wheels.delete(conn, wheel_id)
    except wheels.WheelNotFound:
        raise HTTPException(404, "No such wheel") from None
    return _redirect(request, "/wheels")


@router.get("/wheels/{wheel_id}/tag")
def tag_page(request: Request, conn: Conn, wheel_id: int):
    wheel, missing = _wheel_or_page(request, conn, wheel_id)
    if missing is not None:
        return missing
    settings = request.app.state.settings
    context = {
        "wheel": wheel,
        "tag_url": wheels.tag_url(settings.public_url, wheel["slug"]),
        "others": _others(conn, wheel_id),
    }
    return render(request, "wheel_tag.html", context)


@router.api_route("/wheels/{wheel_id}/qr.svg", methods=["GET", "HEAD"])
def qr_code(request: Request, conn: Conn, wheel_id: int):
    wheel = _wheel(conn, wheel_id)
    url = wheels.tag_url(request.app.state.settings.public_url, wheel["slug"])
    return Response(
        wheels.qr_svg(url),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.post("/wheels/{wheel_id}/slug/regenerate")
def regenerate_slug(request: Request, wheel_id: int, conn: Conn):
    try:
        wheels.regenerate_slug(conn, wheel_id)
    except wheels.WheelNotFound:
        raise HTTPException(404, "No such wheel") from None
    return _redirect(request, f"/wheels/{wheel_id}/tag")


@router.post("/wheels/{wheel_id}/slug/take")
def take_tag(request: Request, wheel_id: int, conn: Conn, from_wheel_id: Annotated[int, Form()]):
    try:
        wheels.take_tag(conn, wheel_id, from_wheel_id)
    except wheels.WheelNotFound:
        raise HTTPException(404, "No such wheel") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return _redirect(request, f"/wheels/{wheel_id}/tag")


@router.post("/wheels/{wheel_id}/slots/{position}/draft")
def open_draft(request: Request, conn: Conn, wheel_id: int, position: int):
    """The builder sheet for a slot, resuming its draft. The slot's tile comes along out of band,
    so a sheet dismissed without saving leaves the draft dot on the ring."""
    try:
        opened = stacks.open_draft(conn, wheel_id, position)
        context = sheet_context(request, conn, opened.stack_id, resumed=opened.resumed)
    except stacks.StackError as exc:
        raise fail(exc) from None
    context |= slot_swap(conn, wheel_id, position)
    return render(request, "_stack_sheet.html", context)


@router.post("/wheels/{wheel_id}/slots/{position}/clear")
def clear_slot(request: Request, conn: Conn, wheel_id: int, position: int):
    wheel = _wheel(conn, wheel_id)
    if not 1 <= position <= wheel["slot_count"]:
        raise HTTPException(404, "No such slot")
    stacks.clear_slot(conn, wheel_id, position)
    response = render(request, "_slot_swap.html", slot_swap(conn, wheel_id, position))
    response.headers.update(SHEET_CLOSE)
    return response
