"""What every /api/v1 router shares: the route class that adds ETag and 304 to each GET, the
connection and settings dependencies."""

import hashlib
import sqlite3
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.routing import APIRoute

from ..config import Settings
from ..db import get_conn

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

CACHE_CONTROL = "private, no-cache"


def operation_id(route: APIRoute) -> str:
    """The function's name, which is what generated clients call the operation."""
    return route.name


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings)]


def _etag_matches(header: str, etag: str) -> bool:
    candidates = [part.strip().removeprefix("W/") for part in header.split(",")]
    return "*" in candidates or etag in candidates


class ApiRoute(APIRoute):
    """A GET that answers 200 gets `ETag` (a hash of the body) and `Cache-Control: private,
    no-cache`; `If-None-Match` with the same ETag gets 304 and no body."""

    def get_route_handler(self) -> Callable:
        handle = super().get_route_handler()

        async def handler(request: Request) -> Response:
            response = await handle(request)
            if request.method != "GET" or response.status_code != 200:
                return response
            etag = f'"{hashlib.sha256(response.body).hexdigest()[:24]}"'
            headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
            if _etag_matches(request.headers.get("if-none-match", ""), etag):
                return Response(status_code=304, headers=headers)
            response.headers.update(headers)
            return response

        return handler
