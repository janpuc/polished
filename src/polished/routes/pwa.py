"""Manifest, service worker and the offline page (DESIGN 11). All three are public."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ..web import render, templates

router = APIRouter()

THEME_COLOR = "#b02a78"
BACKGROUND_COLOR = "#fbf8fb"
# `curl -I` and browsers' freshness checks use HEAD.
PROBEABLE = ["GET", "HEAD"]


@router.api_route("/manifest.webmanifest", methods=PROBEABLE)
def manifest() -> JSONResponse:
    icons = "/static/icons"
    return JSONResponse(
        {
            "name": "Polished",
            "short_name": "Polished",
            "description": "The household's nail polish inventory",
            "start_url": "/?source=pwa",
            "scope": "/",
            "display": "standalone",
            "background_color": BACKGROUND_COLOR,
            "theme_color": THEME_COLOR,
            "icons": [
                {"src": f"{icons}/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": f"{icons}/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": f"{icons}/icon-maskable-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        },
        media_type="application/manifest+json",
    )


@router.api_route("/sw.js", methods=PROBEABLE)
def service_worker(request: Request) -> Response:
    """Served from the root so its scope is `/`; no-cache so a release reaches the phone."""
    body = templates.get_template("sw.js").render(version=request.app.state.settings.version)
    return Response(body, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@router.api_route("/offline", methods=PROBEABLE)
def offline(request: Request):
    return render(request, "offline.html")
