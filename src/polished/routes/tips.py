"""Generated nail tips as SVG: one shade, or a whole stack (DESIGN 9)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from .. import stacks, tips
from ..db import get_conn

router = APIRouter(prefix="/tips")

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

# The image URLs carry ?v=<revision>, so a changed colour is a new URL and the old one may be
# kept for good. The ETag answers a URL typed without it.
CACHE = "private, max-age=31536000, immutable"


def _svg(request: Request, layers: list[tips.TipShade]) -> Response:
    etag = f'"{tips.revision(layers)}"'
    headers = {"ETag": etag, "Cache-Control": CACHE}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(tips.render(layers), media_type="image/svg+xml", headers=headers)


@router.get("/shade/{shade_id:int}.svg")
def shade_tip(request: Request, conn: Conn, shade_id: int):
    row = conn.execute(
        f"select s.id as shade_id, {tips.TIP_FIELDS} from shade s where s.id = ?", (shade_id,)
    ).fetchone()
    if row is None:
        return Response(status_code=404)
    return _svg(request, [tips.tip_shade(row)])


@router.get("/stack/{stack_id:int}.svg")
def stack_tip(request: Request, conn: Conn, stack_id: int):
    layers = stacks.layers(conn, stack_id)
    if not layers:
        return Response(status_code=404)
    return _svg(request, [tips.tip_shade(layer) for layer in layers])
