"""Stacks: GET /stacks/{id} (the builder sheet of a draft), /stacks/copy-sources and /stacks/pick,
and the builder's writes: layers, templates, save and cancel."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from .. import shades, stacks, wheels
from ..routes import _builder
from . import rows, schemas
from .errors import ApiError, invalid, not_found
from .routing import ApiRoute, AppSettings, Conn, household_today

router = APIRouter(prefix="/stacks", route_class=ApiRoute, tags=["stacks"])


def sheet_body(conn, stack_id: int) -> schemas.StackSheet:
    try:
        sheet = stacks.sheet(conn, stack_id)
    except stacks.NotADraft:
        raise ApiError(409, "not_a_draft", "That swatch is not being edited.") from None
    layers = [rows.layer(layer) for layer in sheet["layers"]]
    return schemas.StackSheet(
        stack_id=sheet["stack_id"],
        wheel=schemas.StackWheel(
            id=sheet["wheel_id"], slug=sheet["wheel_slug"], name=sheet["wheel_name"]
        ),
        position=sheet["position"],
        name=sheet["name"],
        note=sheet["note"],
        painted_on=sheet["painted_on"],
        layers=layers,
        summary=sheet["summary"],
        full=sheet["full"],
        tip=[layer.tip for layer in layers],
    )


@router.get("/copy-sources", response_model=schemas.CopySources, summary="Saved stacks to copy")
def copy_sources(conn: Conn, q: str = ""):
    """Most recently saved first; `q` keeps the stacks with a layer whose shade name contains it."""
    return schemas.CopySources(
        items=[
            schemas.CopySource(
                stack_id=s["stack_id"],
                wheel_name=s["wheel_name"],
                wheel_slug=s["wheel_slug"],
                position=s["position"],
                name=s["name"],
                painted_on=s["painted_on"],
                summary=s["summary"],
                layers=[rows.layer(layer) for layer in s["layers"]],
            )
            for s in stacks.copy_sources(conn, q)
        ]
    )


@router.get("/pick", response_model=schemas.Pick, summary="The builder's shade picker")
def stack_pick(
    conn: Conn,
    q: str = "",
    scope: Annotated[Literal["owned", "toppers", "all"], Query()] = "owned",
):
    """Shades matching `q`, owned ones first, narrowed by `scope`. A P code or barcode the
    household has taught the app comes back as `suggestion` (and no items), as in the web's builder."""
    picker = _builder.picker(conn, 0, q, scope)
    result: shades.ShadePage | None = picker["result"]
    suggestion = picker["suggestion"]
    return schemas.Pick(
        items=rows.shade_rows(conn, result.rows) if result else [],
        total=result.total if result else 0,
        suggestion=rows.shade_row(conn, suggestion.shade) if suggestion else None,
    )


@router.get(
    "/{stack_id:int}",
    response_model=schemas.StackSheet,
    summary="A draft being edited",
    responses={409: {"description": "`not_a_draft`"}},
)
def stack_sheet(conn: Conn, stack_id: int):
    """409 `not_a_draft` for a stack that is not the working draft of a slot."""
    return sheet_body(conn, stack_id)


def stack_failure(error: stacks.StackError) -> ApiError:
    """The refusal of a stacks.py function as the answer the web gives (routes/_builder.STATUS)."""
    match error:
        case stacks.NotADraft():
            return ApiError(409, "not_a_draft", "That swatch is not being edited.")
        case stacks.StackFull():
            return ApiError(422, "stack_full", f"A swatch holds up to {stacks.MAX_LAYERS} layers.")
        case stacks.EmptyStack():
            return ApiError(422, "empty_stack", "Add at least one layer before saving.")
        case stacks.LayerNotFound():
            return not_found("That layer is not in this swatch.")
        case stacks.ShadeNotFound():
            return not_found("No such shade.")
        case stacks.SlotNotFound():
            return not_found("There is no such slot.")
        case stacks.SourceNotFound():
            return not_found("That swatch is not saved, so it can't be copied.")
    return ApiError(409, "conflict", str(error))


@router.post(
    "/{stack_id:int}/layers",
    response_model=schemas.StackSheet,
    summary="Paint another layer on top",
    responses={
        404: {"description": "`not_found`: no such shade."},
        409: {"description": "`not_a_draft`"},
        422: {"description": "`stack_full`: a swatch holds 8 layers."},
    },
)
def layer_add(conn: Conn, stack_id: int, body: schemas.LayerRequest):
    """Appended with the shade's default coats: 2 for polish, 1 for toppers and coats."""
    try:
        stacks.append(conn, stack_id, body.shade_id)
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return sheet_body(conn, stack_id)


@router.patch(
    "/{stack_id:int}/layers/{layer_id}",
    response_model=schemas.StackSheet,
    summary="Add or take off a coat, or move a layer",
    responses={
        404: {"description": "`not_found`: the layer is not in this swatch."},
        409: {"description": "`not_a_draft`"},
        422: {"description": "`validation`: send `coats_delta` (-1 or 1) or `move` (up or down)."},
    },
)
def layer_edit(conn: Conn, stack_id: int, layer_id: int, body: schemas.LayerPatch):
    """Coats stay between 1 and 5 (a change past either end changes nothing). `up` is towards
    the base, which the list shows first; at the end of the list nothing changes."""
    if (body.coats_delta is None) == (body.move is None):
        raise invalid({"coats_delta": "Send coats_delta (-1 or 1) or move (up or down), not both."})
    if body.coats_delta is not None and body.coats_delta not in (-1, 1):
        raise invalid({"coats_delta": "coats_delta must be -1 or 1."})
    if body.move is not None and body.move not in ("up", "down"):
        raise invalid({"move": "move must be up or down."})
    try:
        if body.coats_delta is not None:
            stacks.change_coats(conn, stack_id, layer_id, body.coats_delta)
        else:
            stacks.move(conn, stack_id, layer_id, body.move)
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return sheet_body(conn, stack_id)


@router.delete(
    "/{stack_id:int}/layers/{layer_id}",
    response_model=schemas.StackSheet,
    summary="Take a layer off",
    responses={
        404: {"description": "`not_found`: the layer is not in this swatch."},
        409: {"description": "`not_a_draft`"},
    },
)
def layer_delete(conn: Conn, stack_id: int, layer_id: int):
    try:
        stacks.remove(conn, stack_id, layer_id)
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return sheet_body(conn, stack_id)


@router.post(
    "/{stack_id:int}/template",
    response_model=schemas.StackTemplated,
    summary="Over black, Copy from…, Same as last",
    responses={
        404: {"description": "`not_found`: `source_stack_id` is not a saved stack."},
        409: {"description": "`not_a_draft`"},
        422: {"description": "`stack_full` (over black on a full stack) or `validation`."},
    },
)
def stack_template(conn: Conn, settings: AppSettings, stack_id: int, body: schemas.TemplateRequest):
    """`over_black` puts the black base first with one coat; `copy` replaces the layers with a
    saved stack's (`source_stack_id`); `last` copies the stack saved most recently, or answers
    `nothing_saved` and leaves the draft alone."""
    if body.kind not in ("over_black", "copy", "last"):
        raise invalid({"kind": "Pick over_black, copy or last."})
    if body.kind == "copy" and body.source_stack_id is None:
        raise invalid({"source_stack_id": "Pick the swatch to copy."})
    try:
        match body.kind:
            case "over_black":
                result = stacks.over_black(conn, stack_id, settings.over_black_handle)
            case "copy":
                stacks.copy_from(conn, stack_id, body.source_stack_id)
                result = "copied"
            case _:
                result = (
                    "nothing_saved" if stacks.same_as_last(conn, stack_id) is None else "copied"
                )
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return schemas.StackTemplated(**sheet_body(conn, stack_id).model_dump(), result=result)


def slot_result(conn, ref: stacks.SlotRef) -> schemas.SlotResult:
    wheel = wheels.get(conn, ref.wheel_id)
    return schemas.SlotResult(
        wheel_id=ref.wheel_id,
        position=ref.position,
        tile=rows.tile(wheels.slot_tile(conn, wheel, ref.position)),
    )


@router.post(
    "/{stack_id:int}/save",
    response_model=schemas.SlotResult,
    summary="Save the draft as the slot's swatch",
    responses={
        409: {"description": "`not_a_draft`"},
        422: {"description": "`empty_stack`, or `validation` for `painted_on`."},
    },
)
def stack_save(conn: Conn, settings: AppSettings, stack_id: int, body: schemas.SaveRequest):
    """Replaces the slot's earlier swatch, in one transaction. `painted_on` defaults to today."""
    try:
        ref = stacks.save(
            conn,
            stack_id,
            body.name or "",
            body.note or "",
            body.painted_on or "",
            today=household_today(settings),
        )
    except stacks.FutureDate:
        raise invalid(
            {"painted_on": "Swatched on can't be in the future. Pick today or an earlier day."}
        ) from None
    except ValueError:
        raise invalid({"painted_on": "Painted on needs a date like 2026-10-25."}) from None
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return slot_result(conn, ref)


@router.post(
    "/{stack_id:int}/cancel",
    response_model=schemas.SlotResult,
    summary="Throw the draft away",
    responses={409: {"description": "`not_a_draft`"}},
)
def stack_cancel(conn: Conn, stack_id: int):
    """The slot keeps its saved swatch, if it has one; `tile` is the slot as it is now."""
    try:
        ref = stacks.cancel(conn, stack_id)
    except stacks.StackError as exc:
        raise stack_failure(exc) from None
    return slot_result(conn, ref)
