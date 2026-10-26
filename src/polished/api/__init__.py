"""The JSON API of the native app, under /api/v1 (docs/NATIVE.md 3, DESIGN 17).

`router` is /api/v1 itself; `app_router` holds the routes outside it that belong to the app:
the universal-link file and the UI-test reset. `install` adds the error handlers."""

from fastapi import APIRouter, FastAPI

from . import (
    bottles,
    errors,
    home,
    lookup,
    shades,
    signin,
    stacks,
    sync,
    testing,
    wellknown,
    wishlist,
)
from . import wheels as wheel_routes
from .routing import ApiRoute, operation_id

router = APIRouter(prefix="/api/v1", route_class=ApiRoute, generate_unique_id_function=operation_id)
for module in (
    signin,
    home,
    shades,
    bottles,
    wishlist,
    wheel_routes,
    stacks,
    lookup,
    sync,
):
    router.include_router(module.router)


def install(app: FastAPI) -> None:
    """The error shape for /api/v1, and the routes the settings switch on."""
    settings = app.state.settings
    errors.install(app)
    app.include_router(router)
    if settings.apple_team_id:
        app.include_router(wellknown.router)
    if settings.auth_mode == "none" and settings.test_reset_from:
        app.include_router(testing.router)
