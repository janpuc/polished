"""Jinja environment and page rendering."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"


def _context(request: Request) -> dict:
    return {
        "user": getattr(request.state, "user", None),
        "version": request.app.state.settings.version,
    }


templates = Jinja2Templates(directory=PACKAGE_DIR / "templates", context_processors=[_context])


def render(
    request: Request, name: str, context: dict | None = None, status_code: int = 200
) -> Response:
    return templates.TemplateResponse(request, name, context or {}, status_code=status_code)
