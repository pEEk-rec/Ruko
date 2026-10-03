"""Sarvam AI speech provider (STT + TTS) over plain HTTPS (httpx).

Checked against docs.sarvam.ai on 2026-10-03:

- STT: ``POST {base}/speech-to-text``, multipart ``file``, ``model`` (``saaras:v4``),
  ``language_code`` (``kn-IN`` / ``hi-IN`` / ``en-IN`` / ``unknown``). Reply: ``transcript``,
  ``language_code``. The REST endpoint is for short audio (about 30 s).
- TTS: ``POST {base}/text-to-speech``, JSON ``text`` (``bulbul:v3``: max 2500 chars),
  ``language_code``, ``speaker``, ``model``, ``output_audio_codec``. Reply: ``audios``
  (list of base64 strings).

The key goes in the ``api-subscription-key`` header, never in the URL.
"""

from __future__ import annotations

import base64
import binascii
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from ruko.config import Settings
from ruko.language.speech_codes import locale_for_speech_code, speech_code_for
from ruko.providers.http import ProviderHTTPError, post_with_retries
from ruko.providers.speech.audio import MIME_TYPES
from ruko.providers.speech.base import (
    AudioClip,
    SpeechError,
    SpeechProvider,
    SynthesizedAudio,
    Transcript,
)


class SarvamProvider(SpeechProvider):
    """Speech-to-text and text-to-speech through Sarvam's REST API."""

    name = "sarvam"

    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str,
        stt_model: str,
        tts_model: str,
        tts_speaker: str,
        tts_max_chars: int,
        timeout_seconds: float,
        max_retries: int = 1,
        backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self.stt_model = stt_model
        self.tts_model = tts_model
        self.tts_speaker = tts_speaker
        self.tts_max_chars = tts_max_chars
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._transport = transport
        self._sleep = sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> SarvamProvider:
        """Build the provider from settings (the key must be present)."""
        if settings.sarvam_api_key is None:
            raise ValueError("sarvam_api_key is not set")
        return cls(
            settings.sarvam_api_key,
            base_url=settings.sarvam_base_url,
            stt_model=settings.sarvam_stt_model,
            tts_model=settings.sarvam_tts_model,
            tts_speaker=settings.sarvam_tts_speaker,
            tts_max_chars=settings.sarvam_tts_max_chars,
            timeout_seconds=settings.speech_timeout_seconds,
        )

    def __repr__(self) -> str:
        """Never show the key."""
        return f"SarvamProvider(stt={self.stt_model!r}, tts={self.tts_model!r})"

    def _post(self, path: str, **request: Any) -> dict[str, Any]:
        try:
            response = post_with_retries(
                f"{self._base}/{path}",
                headers={"api-subscription-key": self._api_key.get_secret_value()},
                timeout_seconds=self._timeout,
                max_retries=self._max_retries,
                backoff_seconds=self._backoff,
                sleep=self._sleep,
                transport=self._transport,
                **request,
            )
            return response.json()
        except ProviderHTTPError as failure:
            raise SpeechError(failure.reason) from None
        except ValueError:
            raise SpeechError("bad_json") from None

    def transcribe(self, clip: AudioClip, locale_hint: str | None) -> Transcript:
        """Send the audio to Sarvam STT and return the transcript."""
        language = speech_code_for(locale_hint) if locale_hint else None
        payload = self._post(
            "speech-to-text",
            files={"file": (f"voice.{clip.format}", clip.data, MIME_TYPES[clip.format])},
            data={"model": self.stt_model, "language_code": language or "unknown"},
        )
        text = payload.get("transcript")
        if not isinstance(text, str):
            raise SpeechError("no_transcript")
        detected = payload.get("language_code")
        locale = locale_for_speech_code(detected) if isinstance(detected, str) else None
        return Transcript(text=text, locale=locale or locale_hint, provider=self.name)

    def synthesize(self, text: str, locale: str) -> SynthesizedAudio:
        """Send rendered text to Sarvam TTS and return WAV audio."""
        language = speech_code_for(locale)
        if language is None:
            raise SpeechError("unsupported_locale")
        if not text.strip() or len(text) > self.tts_max_chars:
            raise SpeechError("text_length")
        payload = self._post(
            "text-to-speech",
            json={
                "text": text,
                "language_code": language,
                "speaker": self.tts_speaker,
                "model": self.tts_model,
                "output_audio_codec": "wav",
            },
        )
        audios = payload.get("audios")
        if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
            raise SpeechError("no_audio")
        try:
            data = base64.b64decode(audios[0], validate=True)
        except (binascii.Error, ValueError):
            raise SpeechError("bad_audio") from None
        return SynthesizedAudio(data=data, format="wav", provider=self.name)
