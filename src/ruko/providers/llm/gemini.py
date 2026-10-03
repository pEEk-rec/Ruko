"""Google Gemini provider over plain HTTPS (httpx), no Google SDK.

Endpoint (checked against ai.google.dev on 2026-10-03):
``POST {base_url}/models/{model}:generateContent`` with the key in the
``x-goog-api-key`` header (never in the URL). The reply text is in
``candidates[0].content.parts[].text``; parts marked ``thought`` are skipped.

Transient failures (timeouts, network errors, HTTP 429/500/502/503/504) are retried
with exponential backoff. Anything else raises ``LLMError`` straight away.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from ruko.config import Settings
from ruko.errors import ErrorCode
from ruko.providers.http import ProviderHTTPError, post_with_retries
from ruko.providers.llm.base import LLMError, LLMProvider, LLMRequest, Message


class GeminiProvider(LLMProvider):
    """Calls the Gemini ``generateContent`` REST endpoint."""

    name = "gemini"

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        *,
        backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._transport = transport
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> GeminiProvider:
        """Build the provider from settings (the key must be present)."""
        if settings.gemini_api_key is None:
            raise ValueError("gemini_api_key is not set")
        return cls(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def __repr__(self) -> str:
        """Never show the key."""
        return f"GeminiProvider(model={self.model!r})"

    def generate(self, request: LLMRequest) -> str:
        """Call Gemini, retrying transient failures, and return the reply text."""
        try:
            response = post_with_retries(
                self._url,
                headers={"x-goog-api-key": self._api_key.get_secret_value()},
                timeout_seconds=self._timeout,
                max_retries=self._max_retries,
                backoff_seconds=self._backoff,
                sleep=self._sleep,
                transport=self._transport,
                json=build_body(request),
            )
        except ProviderHTTPError as failure:
            raise LLMError(ErrorCode.LLM_UNAVAILABLE, failure.reason) from None
        return parse_reply(response.json())


def _content(message: Message) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"text": message.text}]
    if message.image is not None:
        encoded = base64.b64encode(message.image.data).decode("ascii")
        parts.append({"inlineData": {"mimeType": message.image.mime_type, "data": encoded}})
    return {"role": message.role, "parts": parts}


def build_body(request: LLMRequest) -> dict[str, Any]:
    """Build the ``generateContent`` JSON body for a request."""
    config: dict[str, Any] = {"temperature": 0, "maxOutputTokens": request.max_output_tokens}
    if request.json_output:
        config["responseMimeType"] = "application/json"
    return {
        "systemInstruction": {"parts": [{"text": request.system}]},
        "contents": [_content(m) for m in request.messages],
        "generationConfig": config,
    }


def parse_reply(payload: dict[str, Any]) -> str:
    """Extract the reply text from a ``generateContent`` response.

    Raises:
        LLMError: ``LLM_INVALID_OUTPUT`` if the prompt was blocked or the reply is empty.
    """
    candidates = payload.get("candidates") or []
    if not candidates:
        blocked = (payload.get("promptFeedback") or {}).get("blockReason")
        raise LLMError(ErrorCode.LLM_INVALID_OUTPUT, "blocked" if blocked else "empty")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise LLMError(ErrorCode.LLM_INVALID_OUTPUT, "empty")
    return text
