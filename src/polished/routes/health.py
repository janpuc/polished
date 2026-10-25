import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import connect, schema_version

router = APIRouter()


@router.get("/healthz")
def healthz(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    try:
        conn = connect(settings.db_path)
        try:
            schema = schema_version(conn)
        finally:
            conn.close()
    except sqlite3.Error:
        return JSONResponse({"status": "error"}, status_code=503)
    return JSONResponse({"status": "ok", "version": settings.version, "schema": schema})
