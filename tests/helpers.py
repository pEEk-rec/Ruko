"""Shared helpers for API tests: an app with fake providers that tests can swap."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from ruko.config import Settings
from ruko.main import create_app
from ruko.providers.llm.base import LLMProvider
from ruko.providers.speech.factory import SpeechChain
from ruko.providers.speech.fake import FakeSpeechProvider, silent_wav

PROFILE = {
    "monthly_expenses_band": "25k_50k",
    "liquid_savings_band": "1l_3l",
    "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": True},
    "age_band": "lt_30",
}


def make_client(
    *,
    llm: LLMProvider | None | str = "default",
    speech: list[FakeSpeechProvider] | None = None,
    **settings: object,
) -> TestClient:
    """Build a test client; ``llm=None`` means no LLM, a provider replaces the fake."""
    base = {"environment": "test", "llm_provider": "fake", "speech_providers": ["fake"]}
    app = create_app(Settings(**{**base, **settings}))
    services = app.state.services
    if llm != "default":
        services.llm = llm
    if speech is not None:
        services.speech = SpeechChain(list(speech))
    return TestClient(app, raise_server_exceptions=False)


def analyze_body(content: str, **extra: object) -> dict:
    """Body for /v1/analyze with a text input."""
    return {"input": {"type": "text", "content": content}, **extra}


def wav_b64(seconds: float = 0.2) -> str:
    """A short silent WAV, base64-encoded."""
    return base64.b64encode(silent_wav(seconds)).decode()
