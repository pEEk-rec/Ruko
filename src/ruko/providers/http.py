"""One small HTTP helper shared by the external providers (Gemini, Sarvam).

``post_with_retries`` sends one POST and retries transient failures (timeouts, network
errors, HTTP 429/500/502/503/504) with exponential backoff. It never logs anything and
never follows redirects. Callers map ``ProviderHTTPError`` to their own typed error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class ProviderHTTPError(Exception):
    """The request did not succeed. ``reason`` is a short label such as ``http_503``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def post_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None],
    transport: httpx.BaseTransport | None = None,
    **request: Any,
) -> httpx.Response:
    """POST with retries; return the first HTTP 200 response.

    Args:
        url: Target URL (never contains a secret).
        headers: Request headers (secrets go here).
        timeout_seconds: Per-attempt timeout.
        max_retries: Extra attempts after the first.
        backoff_seconds: First backoff; doubles on every retry.
        sleep: Sleep function (injected by tests).
        transport: Optional httpx transport (tests use a mock transport).
        **request: ``json=...`` or ``files=...``/``data=...`` passed to httpx.

    Returns:
        The successful response.

    Raises:
        ProviderHTTPError: After the last attempt, or at once for a non-retryable status.
    """
    reason = "unknown"
    with httpx.Client(timeout=timeout_seconds, transport=transport) as client:
        for attempt in range(max_retries + 1):
            if attempt:
                sleep(backoff_seconds * 2 ** (attempt - 1))
            try:
                response = client.post(url, headers=headers, **request)
            except httpx.TimeoutException:
                reason = "timeout"
                continue
            except httpx.TransportError:
                reason = "network"
                continue
            if response.status_code == 200:
                return response
            reason = f"http_{response.status_code}"
            if response.status_code not in RETRYABLE_STATUS:
                break
    raise ProviderHTTPError(reason)
