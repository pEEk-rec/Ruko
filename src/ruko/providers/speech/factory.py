"""Speech providers in a configurable fallback order (``settings.speech_providers``).

Each provider is tried in order; a failure moves on to the next. If none is configured
or all fail, ``SPEECH_UNAVAILABLE`` is raised and the text path keeps working.

Known names: ``sarvam`` (needs a key), ``fake``. ``bhashini`` is reserved but not built
(no credentials yet); unknown or unconfigured names are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ruko.config import Settings
from ruko.errors import ErrorCode, RukoError
from ruko.providers.speech.base import (
    AudioClip,
    SpeechError,
    SpeechProvider,
    SynthesizedAudio,
    Transcript,
)
from ruko.providers.speech.fake import FakeSpeechProvider
from ruko.providers.speech.sarvam import SarvamProvider


@dataclass
class SpeechChain:
    """Tries providers in order. ``failures`` records content-free failure labels."""

    providers: list[SpeechProvider]
    failures: list[str] = field(default_factory=list)

    def transcribe(self, clip: AudioClip, locale_hint: str | None) -> Transcript:
        """Return the first successful transcript.

        Raises:
            RukoError: ``SPEECH_UNAVAILABLE`` if no provider succeeds.
        """
        for provider in self.providers:
            try:
                return provider.transcribe(clip, locale_hint)
            except SpeechError as error:
                self.failures.append(f"{provider.name}:{error.reason}")
        raise RukoError(ErrorCode.SPEECH_UNAVAILABLE)

    def synthesize(self, text: str, locale: str) -> SynthesizedAudio:
        """Return the first successful synthesis.

        Raises:
            RukoError: ``SPEECH_UNAVAILABLE`` if no provider succeeds.
        """
        for provider in self.providers:
            try:
                return provider.synthesize(text, locale)
            except SpeechError as error:
                self.failures.append(f"{provider.name}:{error.reason}")
        raise RukoError(ErrorCode.SPEECH_UNAVAILABLE)


def _has_key(settings: Settings) -> bool:
    key = settings.sarvam_api_key
    return key is not None and bool(key.get_secret_value())


def build_speech_chain(settings: Settings) -> SpeechChain:
    """Build the provider chain from settings, skipping names that are not usable."""
    providers: list[SpeechProvider] = []
    for name in settings.speech_providers:
        if name == "fake":
            providers.append(FakeSpeechProvider())
        elif name == "sarvam" and _has_key(settings):
            providers.append(SarvamProvider.from_settings(settings))
    return SpeechChain(providers)
