"""Speech provider interfaces (``STTProvider``, ``TTSProvider``) and their value types.

Audio is held in memory for one call and never stored or logged. Reprs show sizes,
never bytes. Locales are Ruko's short codes (``kn``); providers map them to their own tags.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ruko.errors import ErrorCode, RukoError


@dataclass(frozen=True)
class AudioClip:
    """Checked audio from the user: bytes, declared format and duration if measurable."""

    data: bytes
    format: str
    duration_seconds: float | None = None

    def __repr__(self) -> str:
        """Show format and size only."""
        return f"AudioClip(format={self.format!r}, bytes={len(self.data)})"


@dataclass(frozen=True)
class Transcript:
    """Text heard in the audio. Raw user text: it still goes through the guardrail gate."""

    text: str
    locale: str | None
    provider: str

    def __repr__(self) -> str:
        """Never show the transcript itself."""
        return f"Transcript(chars={len(self.text)}, locale={self.locale!r})"


@dataclass(frozen=True)
class SynthesizedAudio:
    """Speech produced from Ruko's own rendered text."""

    data: bytes
    format: str
    provider: str

    def __repr__(self) -> str:
        """Show format and size only."""
        return f"SynthesizedAudio(format={self.format!r}, bytes={len(self.data)})"


class SpeechError(RukoError):
    """A speech call failed. ``reason`` is a short content-free label for the trace."""

    def __init__(self, reason: str, code: ErrorCode = ErrorCode.SPEECH_UNAVAILABLE) -> None:
        super().__init__(code)
        self.reason = reason


class STTProvider(ABC):
    """Speech-to-text."""

    name: str = "stt"

    @abstractmethod
    def transcribe(self, clip: AudioClip, locale_hint: str | None) -> Transcript:
        """Return the text spoken in ``clip``.

        Raises:
            SpeechError: When the provider fails or the language is unsupported.
        """


class TTSProvider(ABC):
    """Text-to-speech."""

    name: str = "tts"

    @abstractmethod
    def synthesize(self, text: str, locale: str) -> SynthesizedAudio:
        """Return speech for ``text`` (already rendered and output-filtered).

        Raises:
            SpeechError: When the provider fails, the text is too long or the language
                is unsupported.
        """


class SpeechProvider(STTProvider, TTSProvider):
    """A provider for both directions (Sarvam and the fake both are)."""
