"""HTTP edge protections: body size limit, JSON-only bodies, and rate limiting.

Both are plain ASGI middlewares that answer with the standard error contract. Neither
reads, keeps or logs body content: the size check only counts bytes, and the rate limiter
keys clients by a salted hash of their address, held in memory for the current minute.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ruko.errors import ERROR_SPECS, ErrorCode, build_error_response

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


async def send_error(send: Send, code: ErrorCode) -> None:
    """Send a complete error response for ``code``."""
    body = json.dumps(
        build_error_response(code).model_dump(mode="json", exclude_none=True)
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": ERROR_SPECS[code].http_status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class BodyLimitMiddleware:
    """Reject non-JSON bodies (415) and bodies over ``max_bytes`` (413), counting bytes only."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check the request, then pass it on with the buffered body replayed."""
        if scope["type"] != "http" or scope.get("method") not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return
        content_type = (_header(scope, b"content-type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            await send_error(send, ErrorCode.UNSUPPORTED_MEDIA_TYPE)
            return
        declared = _header(scope, b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await send_error(send, ErrorCode.PAYLOAD_TOO_LARGE)
            return
        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                await send_error(send, ErrorCode.PAYLOAD_TOO_LARGE)
                return
            if message["type"] != "http.request" or not message.get("more_body", False):
                break

        async def replay() -> Message:
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        await self.app(scope, replay, send)


class RateLimitMiddleware:
    """Fixed one-minute window per client for ``/v1`` routes (0 disables it)."""

    def __init__(
        self, app: ASGIApp, per_minute: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.app = app
        self.per_minute = per_minute
        self.clock = clock
        self._salt = secrets.token_bytes(16)
        self._window = -1
        self._counts: dict[str, int] = {}

    def _client_key(self, scope: Scope) -> str:
        host = (scope.get("client") or ("unknown", 0))[0]
        return hashlib.sha256(self._salt + str(host).encode()).hexdigest()[:16]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Count the request and reject it with 429 when over the limit."""
        if (
            scope["type"] != "http"
            or self.per_minute <= 0
            or not str(scope.get("path", "")).startswith("/v1/")
        ):
            await self.app(scope, receive, send)
            return
        window = int(self.clock() // 60)
        if window != self._window:
            self._window, self._counts = window, {}
        key = self._client_key(scope)
        self._counts[key] = self._counts.get(key, 0) + 1
        if self._counts[key] > self.per_minute:
            await send_error(send, ErrorCode.RATE_LIMITED)
            return
        await self.app(scope, receive, send)
