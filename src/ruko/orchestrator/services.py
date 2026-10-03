"""External providers the workflows may use, built once per app from settings.

Tests replace ``Services`` fields with fakes; nothing else in the workflow changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.config import Settings
from ruko.errors import ErrorCode, RukoError
from ruko.providers.llm.base import LLMProvider
from ruko.providers.llm.factory import build_llm_provider
from ruko.providers.speech.factory import SpeechChain, build_speech_chain


@dataclass
class Services:
    """Settings plus the configured LLM provider and speech chain."""

    settings: Settings
    llm: LLMProvider | None
    speech: SpeechChain

    @classmethod
    def from_settings(cls, settings: Settings) -> Services:
        """Build providers from settings (missing keys mean 'not configured')."""
        return cls(settings, build_llm_provider(settings), build_speech_chain(settings))

    def response_locale(self, requested: str | None, detected: str | None = None) -> str:
        """Pick the response language: requested (must be enabled), detected, or default.

        Raises:
            RukoError: ``LOCALE_UNSUPPORTED`` if a requested locale is not enabled.
        """
        enabled = self.settings.enabled_locales
        if requested is not None:
            if requested not in enabled:
                raise RukoError(ErrorCode.LOCALE_UNSUPPORTED)
            return requested
        if detected in enabled:
            return str(detected)
        return self.settings.default_locale
