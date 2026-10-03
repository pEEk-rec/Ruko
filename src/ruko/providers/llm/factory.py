"""Choose the LLM provider from settings.

``llm_provider``:

- ``auto``: Gemini when a key is set, otherwise none (lexicon-only extraction).
- ``gemini``: Gemini; without a key, none (the system still works on the lexicon).
- ``fake``: the scripted fake (tests, offline demos).
- ``none``: no LLM at all.
"""

from __future__ import annotations

from ruko.config import Settings
from ruko.providers.llm.base import LLMProvider
from ruko.providers.llm.fake import FakeLLMProvider
from ruko.providers.llm.gemini import GeminiProvider


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Return the configured provider, or None for lexicon-only extraction."""
    if settings.llm_provider == "none":
        return None
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        return None
    return GeminiProvider.from_settings(settings)
