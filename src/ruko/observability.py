"""Privacy-safe structured logging and request IDs.

Design rule: log lines are built only from an allow-list of field names
(request IDs, timings, route templates, status, error codes, reason codes).
Anything else passed to ``log_event`` is dropped before it reaches a handler,
so message text, audio, profiles or results cannot be logged by accident.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER_NAME = "ruko"
REQUEST_ID_HEADER = "x-request-id"

ALLOWED_LOG_FIELDS: frozenset[str] = frozenset(
    {
        "request_id",
        "method",
        "route",
        "status",
        "duration_ms",
        "error_code",
        "exception_type",
        "reason_codes",
        "level",
        "step",
        "steps",
        "tool",
        "provider",
        "attempt",
        "locale",
        "count",
    }
)

_request_id: ContextVar[str] = ContextVar("ruko_request_id", default="-")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def current_request_id() -> str:
    """Return the request ID of the request being handled (or ``-``)."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Format records as one JSON object per line, using allow-listed fields only."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as JSON without any non-allow-listed data."""
        payload: dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "event": record.msg if isinstance(record.msg, str) else "event",
            "request_id": current_request_id(),
        }
        fields = getattr(record, "ruko_fields", None)
        if isinstance(fields, dict):
            payload.update({k: v for k, v in fields.items() if k in ALLOWED_LOG_FIELDS})
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the ``ruko`` logger (idempotent)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not any(getattr(h, "ruko_handler", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.ruko_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    # Uvicorn's access log prints raw paths and query strings, and httpx logs full
    # request URLs at INFO. We log our own safe lines instead.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a named event with allow-listed fields only.

    Args:
        event: A short, constant event name such as ``request_completed``.
        level: Logging level.
        **fields: Extra fields; keys outside ``ALLOWED_LOG_FIELDS`` are dropped.
    """
    safe = {k: v for k, v in fields.items() if k in ALLOWED_LOG_FIELDS}
    logging.getLogger(LOGGER_NAME).log(level, event, extra={"ruko_fields": safe})


def _incoming_request_id(scope: Scope) -> str:
    """Accept a client request ID only if it is a plain token; else generate one."""
    for name, value in scope.get("headers", []):
        if name.decode("latin-1").lower() == REQUEST_ID_HEADER:
            candidate = value.decode("latin-1")
            if _VALID_REQUEST_ID.match(candidate):
                return candidate
    return uuid.uuid4().hex


def _route_template(scope: Scope) -> str:
    """Return the matched route template (never the raw path, which may hold content)."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"


class RequestContextMiddleware:
    """ASGI middleware: assigns a request ID, times the request, logs one safe line.

    It never reads or logs request or response bodies, query strings or raw paths.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope)
        token = _request_id.set(request_id)
        started = time.perf_counter()
        status_holder: dict[str, int] = {"status": 500}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            log_event(
                "request_completed",
                method=scope.get("method", "-"),
                route=_route_template(scope),
                status=status_holder["status"],
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            _request_id.reset(token)
