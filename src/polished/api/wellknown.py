"""GET /.well-known/apple-app-site-association: lets iOS open /w/* and /shades/* in the app, and
lets the app claim /auth/app/callback as its sign-in callback (webcredentials)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .routing import operation_id

router = APIRouter(generate_unique_id_function=operation_id, tags=["app"])

BUNDLE_ID = "com.janpuc.polished"


@router.get(
    "/.well-known/apple-app-site-association",
    summary="Universal links for the iPhone app",
    responses={200: {"content": {"application/json": {}}}},
)
def apple_app_site_association(request: Request) -> JSONResponse:
    """Public, served as application/json with no redirect. Registered only when
    POLISHED_APPLE_TEAM_ID is set. `/shades/new` is excluded before `/shades/*` (first match wins).
    `applinks` has no `/auth/*` component: a tapped link never opens the sign-in callback in the
    app. The callback is claimed through `webcredentials` for ASWebAuthenticationSession alone."""
    team = request.app.state.settings.apple_team_id
    app_id = f"{team}.{BUNDLE_ID}"
    return JSONResponse(
        {
            "applinks": {
                "details": [
                    {
                        "appIDs": [app_id],
                        "components": [
                            {"/": "/w/*"},
                            {"/": "/shades/new", "exclude": True},
                            {"/": "/shades/*"},
                        ],
                    }
                ]
            },
            "webcredentials": {"apps": [app_id]},
        }
    )
