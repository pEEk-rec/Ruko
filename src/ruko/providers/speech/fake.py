"""A fake speech provider for tests and offline demos. Never calls the network."""

from __future__ import annotations

import io
import wave

from ruko.providers.speech.base import (
    AudioClip,
    SpeechError,
    SpeechProvider,
    SynthesizedAudio,
    Transcript,
)


def silent_wav(seconds: float = 0.1, rate: int = 8000) -> bytes:
    """Return a short silent mono 16-bit WAV file."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


class FakeSpeechProvider(SpeechProvider):
    """Returns a fixed transcript and silent WAV audio; can be told to fail."""

    def __init__(
        self,
        transcript: str = "",
        transcript_locale: str | None = None,
        *,
        fail: bool = False,
        name: str = "fake",
    ) -> None:
        self.name = name
        self._transcript = transcript
        self._locale = transcript_locale
        self._fail = fail
        self.transcribe_calls = 0
        self.spoken: list[tuple[str, str]] = []

    def transcribe(self, clip: AudioClip, locale_hint: str | None) -> Transcript:
        """Return the scripted transcript (or fail)."""
        self.transcribe_calls += 1
        if self._fail:
            raise SpeechError("fake_failure")
        return Transcript(self._transcript, self._locale or locale_hint, self.name)

    def synthesize(self, text: str, locale: str) -> SynthesizedAudio:
        """Record what would be spoken and return silence (or fail)."""
        if self._fail:
            raise SpeechError("fake_failure")
        self.spoken.append((locale, text))
        return SynthesizedAudio(data=silent_wav(), format="wav", provider=self.name)
