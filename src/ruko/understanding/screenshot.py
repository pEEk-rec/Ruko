"""Screenshot path: base64 image -> checked bytes -> text via the provider (OCR).

The image is decoded and kept in memory only for the provider call; it is never stored
or logged. The OCR text is treated exactly like typed text afterwards: it goes through
the sensitive-data check, redaction and the guardrail gate before anything else.

Privacy note: an image cannot be redacted locally before OCR, so the screenshot itself
reaches the OCR provider. The OCR prompt asks only for a transcription.
"""

from __future__ import annotations

import base64
import binascii
import json
import re

from ruko.errors import ErrorCode, RukoError
from ruko.providers.llm.base import ImagePart, LLMError, LLMProvider, LLMRequest, Message
from ruko.understanding.extract import Prompts, get_prompts

_DATA_URL = re.compile(r"^data:[\w/+.-]+;base64,", re.IGNORECASE)
_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def sniff_image_type(data: bytes) -> str | None:
    """Return the MIME type from the file's magic bytes (PNG, JPEG, WebP), else None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def decode_image(content: str, max_bytes: int) -> ImagePart:
    """Decode and check a base64 screenshot.

    Args:
        content: Base64 data, optionally with a ``data:image/...;base64,`` prefix.
        max_bytes: Size limit for the decoded image.

    Returns:
        The image bytes with their sniffed MIME type.

    Raises:
        RukoError: ``IMAGE_TOO_LARGE`` or ``IMAGE_FORMAT_UNSUPPORTED``.
    """
    encoded = re.sub(r"\s+", "", _DATA_URL.sub("", content.strip()))
    if len(encoded) * 3 // 4 > max_bytes + 3:
        raise RukoError(ErrorCode.IMAGE_TOO_LARGE)
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise RukoError(ErrorCode.IMAGE_FORMAT_UNSUPPORTED) from None
    if len(data) > max_bytes:
        raise RukoError(ErrorCode.IMAGE_TOO_LARGE)
    mime_type = sniff_image_type(data)
    if mime_type is None:
        raise RukoError(ErrorCode.IMAGE_FORMAT_UNSUPPORTED)
    return ImagePart(mime_type=mime_type, data=data)


def build_ocr_request(image: ImagePart, prompts: Prompts | None = None) -> LLMRequest:
    """Build the transcription request for one screenshot."""
    prompts = prompts or get_prompts()
    return LLMRequest(
        system=prompts.ocr_system,
        messages=(Message(role="user", text=prompts.ocr_user, image=image),),
    )


def image_to_text(image: ImagePart, provider: LLMProvider | None, max_chars: int) -> str:
    """Transcribe a screenshot through the provider.

    Args:
        image: Checked image bytes.
        provider: The LLM provider (OCR needs one; there is no local OCR).
        max_chars: The transcription is cut to the text-input limit.

    Returns:
        The visible text (may be empty).

    Raises:
        RukoError: ``OCR_UNAVAILABLE`` if there is no provider, it fails, or the reply
            is not the expected JSON.
    """
    if provider is None:
        raise RukoError(ErrorCode.OCR_UNAVAILABLE)
    try:
        reply = provider.generate(build_ocr_request(image))
        data = json.loads(_CODE_FENCE.sub("", reply))
    except (LLMError, json.JSONDecodeError):
        raise RukoError(ErrorCode.OCR_UNAVAILABLE) from None
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str):
        raise RukoError(ErrorCode.OCR_UNAVAILABLE)
    return text[:max_chars]
