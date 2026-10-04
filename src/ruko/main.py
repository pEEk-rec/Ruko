"""FastAPI application factory and the ASGI ``app`` object."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ruko import __version__
from ruko.api import health, v1
from ruko.api.edge import BodyLimitMiddleware, RateLimitMiddleware
from ruko.api.error_handlers import install_error_handlers
from ruko.api.static import mount_frontend
from ruko.config import Settings, get_settings
from ruko.observability import RequestContextMiddleware, configure_logging
from ruko.orchestrator.services import Services


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the Ruko API application.

    Args:
        settings: Optional settings override (tests pass their own).

    Returns:
        A configured FastAPI app.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Ruko API",
        version=__version__,
        description=(
            "Decision-safety layer for Indian retail investors. Ruko never gives "
            "investment advice; it shows what a decision means for the user's own "
            "money, rules and exit plan."
        ),
    )
    app.state.settings = settings
    app.state.services = Services.from_settings(settings)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)
    mount_frontend(app, settings.static_dir)  # last: the API routes above always win
    # Middleware order: the last added runs first. Request IDs wrap everything, then CORS,
    # then rate limiting, then the body limit closest to the routes.
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["content-type", "x-request-id"],
        )
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
