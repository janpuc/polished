"""The FastAPI app: middleware order, routers, static files."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .auth import AuthGateMiddleware, build_oidc_client
from .catalog.scheduler import Scheduler, close_stale_runs_at_startup
from .catalog.sync import SyncRunner
from .config import Settings
from .routes import bottles, health, home, pwa, shades, sync, wishlist
from .security import OriginCheckMiddleware, SecurityHeadersMiddleware
from .web import STATIC_DIR

log = logging.getLogger("polished")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Closes sync runs a dead process left behind, then starts the daily scheduler."""
    runner: SyncRunner = app.state.sync_runner
    await asyncio.to_thread(close_stale_runs_at_startup, runner.settings, runner.now())
    task = None
    if runner.settings.sync_enabled:
        task = asyncio.create_task(Scheduler(runner).run_forever(), name="sync-scheduler")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app(settings: Settings) -> FastAPI:
    # Outermost first: security headers, Origin check, session, auth gate, routes.
    app = FastAPI(
        lifespan=lifespan,
        title="polished",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        middleware=[
            Middleware(SecurityHeadersMiddleware),
            Middleware(OriginCheckMiddleware, public_netloc=settings.public_netloc),
            Middleware(
                SessionMiddleware,
                secret_key=settings.session_secret.get_secret_value(),
                session_cookie=auth.SESSION_COOKIE,
                max_age=settings.session_days * 86400,
                same_site="lax",
                https_only=settings.auth_mode == "oidc",
            ),
            Middleware(AuthGateMiddleware, settings=settings),
        ],
    )
    app.state.settings = settings
    app.state.sync_runner = SyncRunner(settings)
    app.state.oidc = build_oidc_client(settings) if settings.auth_mode == "oidc" else None
    if settings.auth_mode == "none":
        log.warning("AUTH_MODE=none: authentication is off (local development only)")

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(home.router)
    app.include_router(shades.router)
    app.include_router(bottles.router)
    app.include_router(wishlist.router)
    app.include_router(pwa.router)
    app.include_router(sync.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def serve(settings: Settings) -> int:
    # One worker: the scheduler and the database assume a single process.
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
    return 0
