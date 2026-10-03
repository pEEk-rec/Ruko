"""A scripted LLM provider for tests and offline runs. Never calls the network."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from ruko.providers.llm.base import LLMProvider, LLMRequest

FakeResponse = str | Exception | Callable[[LLMRequest], str]
"""A scripted reply: fixed text, an exception to raise, or a function of the request."""

NEUTRAL_EXTRACTION = json.dumps(
    {
        "is_financial_decision": False,
        "product_class": "unknown",
        "source_type": "unknown",
        "holding_intent": "unknown",
        "payment_destination": "unknown",
        "field_confidence": {},
        "signals": [],
        "request_classes": [],
    }
)
"""Default JSON reply: a valid extraction that adds nothing (the lexicon still runs)."""


class FakeLLMProvider(LLMProvider):
    """Returns scripted replies in order, then a default; records every request."""

    name = "fake"

    def __init__(
        self,
        responses: Iterable[FakeResponse] = (),
        *,
        default_json: str = NEUTRAL_EXTRACTION,
        default_text: str = '{"text": ""}',
    ) -> None:
        self._responses = list(responses)
        self._default_json = default_json
        self._default_text = default_text
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> str:
        """Return the next scripted reply (or raise it, if it is an exception)."""
        self.calls.append(request)
        if not self._responses:
            return self._default_json if request.json_output else self._default_text
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(request)
        return response
