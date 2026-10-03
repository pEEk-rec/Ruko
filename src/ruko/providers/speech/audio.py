"""Checks on incoming audio: base64, size, format (magic bytes) and, for WAV, duration.

Only WAV duration can be measured without an audio-decoding library; other formats are
bounded by the size limit (and the provider's own short-audio limit). The declared
format must match the file's magic bytes.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
import wave
from collections.abc import Callable

from ruko.errors import ErrorCode, RukoError
from ruko.providers.speech.base import AudioClip


def _mp3(d: bytes) -> bool:
    return d.startswith(b"ID3") or (len(d) > 1 and d[0] == 0xFF and (d[1] & 0xE6) == 0xE2)


def _aac(d: bytes) -> bool:
    return len(d) > 1 and d[0] == 0xFF and (d[1] & 0xF6) == 0xF0


_SIGNATURES: dict[str, Callable[[bytes], bool]] = {
    "wav": lambda d: d[:4] == b"RIFF" and d[8:12] == b"WAVE",
    "mp3": _mp3,
    "ogg": lambda d: d.startswith(b"OggS"),
    "opus": lambda d: d.startswith(b"OggS") or d.startswith(b"\x1a\x45\xdf\xa3"),
    "webm": lambda d: d.startswith(b"\x1a\x45\xdf\xa3"),
    "m4a": lambda d: d[4:8] == b"ftyp",
    "aac": _aac,
    "flac": lambda d: d.startswith(b"fLaC"),
    "amr": lambda d: d.startswith(b"#!AMR"),
}

MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "webm": "audio/webm",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "amr": "audio/amr",
}


def wav_duration(data: bytes) -> float | None:
    """Return the duration of WAV audio in seconds, or None if it cannot be read."""
    try:
        with wave.open(io.BytesIO(data)) as reader:
            rate = reader.getframerate()
            return reader.getnframes() / rate if rate else None
    except (wave.Error, EOFError):
        return None


def decode_audio(content: str, audio_format: str, max_bytes: int, max_seconds: float) -> AudioClip:
    """Decode and check a base64 voice note.

    Args:
        content: Base64 audio (a ``data:audio/...;base64,`` prefix is allowed).
        audio_format: Declared format (``wav``, ``mp3``, ``ogg`` ...).
        max_bytes: Size limit of the decoded audio.
        max_seconds: Duration limit (checked when measurable).

    Returns:
        The checked clip.

    Raises:
        RukoError: ``AUDIO_TOO_LARGE``, ``AUDIO_TOO_LONG`` or ``AUDIO_FORMAT_UNSUPPORTED``.
    """
    encoded = re.sub(r"\s+", "", re.sub(r"^data:[\w/+.-]+;base64,", "", content.strip()))
    if len(encoded) * 3 // 4 > max_bytes + 3:
        raise RukoError(ErrorCode.AUDIO_TOO_LARGE)
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise RukoError(ErrorCode.AUDIO_FORMAT_UNSUPPORTED) from None
    if len(data) > max_bytes:
        raise RukoError(ErrorCode.AUDIO_TOO_LARGE)
    check = _SIGNATURES.get(audio_format)
    if check is None or not check(data):
        raise RukoError(ErrorCode.AUDIO_FORMAT_UNSUPPORTED)
    duration = wav_duration(data) if audio_format == "wav" else None
    if audio_format == "wav" and duration is None:
        raise RukoError(ErrorCode.AUDIO_FORMAT_UNSUPPORTED)
    if duration is not None and duration > max_seconds:
        raise RukoError(ErrorCode.AUDIO_TOO_LONG)
    return AudioClip(data=data, format=audio_format, duration_seconds=duration)
