"""FastAPI application factory and the ASGI ``app`` object."""

from __future__ import annotations

from fastapi import FastAPI

from ruko import __version__
from ruko.api import health
from ruko.api.error_handlers import install_error_handlers
from ruko.config import Settings, get_settings
from ruko.observability import RequestContextMiddleware, configure_logging


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
    install_error_handlers(app)
    app.include_router(health.router)
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
