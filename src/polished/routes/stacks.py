"""The layer-stack builder: every edit is a round trip against a draft, answered with the layer
list and an out-of-band live summary (DESIGN 10, 13.5)."""

import sqlite3
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, Request
from starlette.responses import Response

from .. import stacks
from ..db import get_conn
from ..web import render
from ._builder import (
    PICKER_RESET,
    SHEET_CLOSE,
    fail,
    layers_context,
    picker,
    sheet_context,
    slot_swap,
    today,
)

router = APIRouter(prefix="/stacks")

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

FULL = f"A swatch holds up to {stacks.MAX_LAYERS} layers."


def layers_response(
    request: Request,
    conn: sqlite3.Connection,
    stack_id: int,
    *,
    status_code: int = 200,
    reset_picker: str | None = None,
    **extra,
) -> Response:
    """#stack-layers with the summary and the Save button out of band. `reset_picker` (a scope)
    also puts the results back to the empty query, for after a layer was added."""
    try:
        context = layers_context(request, conn, stack_id, oob=True, **extra)
    except stacks.StackError as exc:
        raise fail(exc) from None
    if reset_picker is not None:
        context["picker"] = picker(conn, stack_id, "", reset_picker)
    response = render(request, "_stack_layers.html", context, status_code)
    if reset_picker is not None:
        response.headers.update(PICKER_RESET)
    return response


@router.get("/{stack_id}/sheet")
def sheet(request: Request, conn: Conn, stack_id: int):
    try:
        context = sheet_context(request, conn, stack_id)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return render(request, "_stack_sheet.html", context)


@router.post("/{stack_id}/layers")
def append_layer(
    request: Request,
    conn: Conn,
    stack_id: int,
    shade_id: Annotated[int, Form()],
    filter: Annotated[str, Form()] = "owned",
):
    try:
        layer_id = stacks.append(conn, stack_id, shade_id)
    except stacks.StackFull:
        return layers_response(request, conn, stack_id, status_code=422, notice=FULL)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return layers_response(request, conn, stack_id, new_layer_id=layer_id, reset_picker=filter)


@router.post("/{stack_id}/layers/{layer_id}/move")
def move_layer(
    request: Request,
    conn: Conn,
    stack_id: int,
    layer_id: int,
    dir: Annotated[Literal["up", "down"], Form()],
):
    try:
        stacks.move(conn, stack_id, layer_id, dir)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return layers_response(request, conn, stack_id)


@router.post("/{stack_id}/layers/{layer_id}/coats")
def change_coats(
    request: Request,
    conn: Conn,
    stack_id: int,
    layer_id: int,
    delta: Annotated[Literal[-1, 1], Form()],
):
    try:
        stacks.change_coats(conn, stack_id, layer_id, delta)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return layers_response(request, conn, stack_id)


@router.post("/{stack_id}/layers/{layer_id}/delete")
def delete_layer(request: Request, conn: Conn, stack_id: int, layer_id: int):
    try:
        stacks.remove(conn, stack_id, layer_id)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return layers_response(request, conn, stack_id)


@router.post("/{stack_id}/template/over-black")
def over_black(request: Request, conn: Conn, stack_id: int):
    handle = request.app.state.settings.over_black_handle
    try:
        outcome = stacks.over_black(conn, stack_id, handle)
    except stacks.StackFull:
        return layers_response(request, conn, stack_id, status_code=422, notice=FULL)
    except stacks.StackError as exc:
        raise fail(exc) from None
    notice = {
        "already": "Already over black.",
        "unavailable": "There is no black base in the catalog.",
    }.get(outcome)
    status_code = 422 if outcome == "unavailable" else 200
    return layers_response(request, conn, stack_id, status_code=status_code, notice=notice)


@router.get("/{stack_id}/copy-sources")
def copy_sources(request: Request, conn: Conn, stack_id: int, q: str = ""):
    try:
        stacks.slot_of(conn, stack_id)
    except stacks.StackError as exc:
        raise fail(exc) from None
    context = {
        "stack_id": stack_id,
        "q": q.strip(),
        "sources": stacks.copy_sources(conn, q),
        "has_layers": bool(stacks.layers(conn, stack_id)),
    }
    return render(request, "_copy_sources.html", context)


@router.post("/{stack_id}/template/copy")
def copy_template(
    request: Request,
    conn: Conn,
    stack_id: int,
    source_stack_id: Annotated[int | None, Form()] = None,
    source: Annotated[str, Form()] = "",
    filter: Annotated[str, Form()] = "owned",
):
    notice = None
    try:
        if source_stack_id is not None:
            stacks.copy_from(conn, stack_id, source_stack_id)
        elif source == "last":
            if stacks.same_as_last(conn, stack_id) is None:
                notice = "Nothing is saved yet to copy."
        else:
            return Response("Give source_stack_id or source=last", status_code=422)
    except stacks.StackError as exc:
        raise fail(exc) from None
    return layers_response(request, conn, stack_id, notice=notice, reset_picker=filter)


@router.post("/{stack_id}/save")
def save(
    request: Request,
    conn: Conn,
    stack_id: int,
    name: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
    painted_on: Annotated[str, Form()] = "",
):
    try:
        ref = stacks.save(
            conn, stack_id, name, note, painted_on, today=date.fromisoformat(today(request))
        )
    except stacks.EmptyStack:
        return _save_error("Add at least one layer before saving.")
    except ValueError:
        return _save_error("Painted on needs a date like 2026-10-25.")
    except stacks.StackError as exc:
        raise fail(exc) from None
    response = render(
        request, "_slot_swap.html", slot_swap(conn, ref.wheel_id, ref.position, saved=True)
    )
    response.headers.update(SHEET_CLOSE)
    return response


def _save_error(message: str) -> Response:
    response = Response(message, status_code=422)
    response.headers.update({"HX-Retarget": "#save-error", "HX-Reswap": "innerHTML"})
    return response


@router.post("/{stack_id}/cancel")
def cancel(request: Request, conn: Conn, stack_id: int):
    try:
        ref = stacks.cancel(conn, stack_id)
    except stacks.StackError as exc:
        raise fail(exc) from None
    response = render(request, "_slot_swap.html", slot_swap(conn, ref.wheel_id, ref.position))
    response.headers.update(SHEET_CLOSE)
    return response
