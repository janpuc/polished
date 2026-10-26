"""GET /stacks/{id} (the builder sheet of a draft), /stacks/copy-sources and /stacks/pick."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from .. import shades, stacks
from ..routes import _builder
from . import rows, schemas
from .errors import ApiError
from .routing import ApiRoute, Conn

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
