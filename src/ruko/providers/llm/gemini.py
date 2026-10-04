"""Google Gemini provider through the official Google Gen AI SDK (``google-genai``).

Checked against the installed SDK (2.28) on 2026-10-03: ``genai.Client(api_key=...)``,
``client.models.generate_content(model, contents, config)`` with a
``GenerateContentConfig`` (system instruction, temperature, JSON MIME type). The reply
text is the joined text of the first candidate's parts; parts marked ``thought`` are
skipped.

Transient failures (timeouts, network errors, HTTP 429/500/502/503/504) are retried with
exponential backoff here, so behaviour is the same for every provider. Anything else
raises ``LLMError`` at once. Exception messages are never logged or returned; only a short
reason label such as ``http_429``. If the main model is still out of quota (429) after its
retries, or the project may not use it (403/404), the request goes once more to
``fallback_model`` (if set) before giving up.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import SecretStr

from ruko.config import Settings
from ruko.errors import ErrorCode
from ruko.providers.http import RETRYABLE_STATUS
from ruko.providers.llm.base import LLMError, LLMProvider, LLMRequest, Message

FALLBACK_REASONS = frozenset({"http_429", "http_403", "http_404"})
"""Out of quota, or this project may not use the main model: try the fallback model."""
FALLBACK_STICKY_SECONDS = 600.0
"""After the main model runs out of quota, use the fallback directly for this long."""


class GeminiProvider(LLMProvider):
    """Calls Gemini ``generateContent`` through the Google Gen AI SDK."""

    name = "gemini"

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        *,
        backoff_seconds: float = 0.5,
        fallback_model: str | None = None,
        client: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.model = model
        self.fallback_model = fallback_model or None
        self._clock = clock
        self._fallback_until = 0.0
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep = sleep
        self._client = client or genai.Client(
            api_key=api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> GeminiProvider:
        """Build the provider from settings (the key must be present)."""
        if settings.gemini_api_key is None:
            raise ValueError("gemini_api_key is not set")
        return cls(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            fallback_model=settings.gemini_fallback_model,
        )

    def __repr__(self) -> str:
        """Never show the key."""
        return f"GeminiProvider(model={self.model!r})"

    def generate(self, request: LLMRequest) -> str:
        """Call Gemini, retrying transient failures, and return the reply text.

        Out of quota on the main model (429 after retries): one more try on the fallback model.
        """
        contents = [_content(m) for m in request.messages]
        config = build_config(request)
        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        if self.fallback_model and self._clock() < self._fallback_until:
            models = [self.fallback_model]  # the main model ran out of quota a moment ago
        reason = "unknown"
        for index, model in enumerate(models):
            retries = self._max_retries if index == 0 else 0
            reply, reason = self._try_model(model, contents, config, retries)
            if reply is not None:
                return parse_response(reply)
            if reason not in FALLBACK_REASONS:
                break
            if model == self.model:
                self._fallback_until = self._clock() + FALLBACK_STICKY_SECONDS
        raise LLMError(ErrorCode.LLM_UNAVAILABLE, reason)

    def _try_model(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
        retries: int,
    ) -> tuple[Any, str]:
        """One model with retries: (response, "") on success, else (None, reason label)."""
        reason = "unknown"
        for attempt in range(retries + 1):
            if attempt:
                self._sleep(self._backoff * 2 ** (attempt - 1))
            try:
                return (
                    self._client.models.generate_content(
                        model=model, contents=contents, config=config
                    ),
                    "",
                )
            except errors.APIError as error:
                reason = f"http_{error.code}"
                if error.code not in RETRYABLE_STATUS:
                    break
            except httpx.TimeoutException:
                reason = "timeout"
            except httpx.TransportError:
                reason = "network"
        return None, reason


def _content(message: Message) -> types.Content:
    parts = [types.Part.from_text(text=message.text)]
    if message.image is not None:
        parts.append(
            types.Part.from_bytes(data=message.image.data, mime_type=message.image.mime_type)
        )
    return types.Content(role=message.role, parts=parts)


def build_config(request: LLMRequest) -> types.GenerateContentConfig:
    """Build the generation config for a request (temperature 0, JSON when asked)."""
    return types.GenerateContentConfig(
        system_instruction=request.system,
        temperature=0,
        max_output_tokens=request.max_output_tokens,
        response_mime_type="application/json" if request.json_output else None,
        # Ruko gives the model no tools; automatic function calling stays off.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def parse_response(response: types.GenerateContentResponse) -> str:
    """Extract the reply text from a ``generate_content`` response.

    Raises:
        LLMError: ``LLM_INVALID_OUTPUT`` if the prompt was blocked or the reply is empty.
    """
    if not response.candidates:
        feedback = response.prompt_feedback
        blocked = feedback is not None and feedback.block_reason is not None
        raise LLMError(ErrorCode.LLM_INVALID_OUTPUT, "blocked" if blocked else "empty")
    content = response.candidates[0].content
    parts = (content.parts if content else None) or []
    text = "".join(p.text or "" for p in parts if not p.thought)
    if not text.strip():
        raise LLMError(ErrorCode.LLM_INVALID_OUTPUT, "empty")
    return text
