"""Typed error codes and the standard error contract.

Every error response has the same shape::

    {"error": {"code": "...", "message_key": "error....", "retryable": false}}

Error responses never echo user input. ``message_key`` is a template key that a
client renders in the user's language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    """Every error the API can return."""

    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    RATE_LIMITED = "RATE_LIMITED"
    LOCALE_UNSUPPORTED = "LOCALE_UNSUPPORTED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
    OCR_UNAVAILABLE = "OCR_UNAVAILABLE"
    SPEECH_UNAVAILABLE = "SPEECH_UNAVAILABLE"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_FORMAT_UNSUPPORTED = "AUDIO_FORMAT_UNSUPPORTED"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_FORMAT_UNSUPPORTED = "IMAGE_FORMAT_UNSUPPORTED"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    TOOL_FAILED = "TOOL_FAILED"
    OUTPUT_BLOCKED = "OUTPUT_BLOCKED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ErrorSpec:
    """Static facts about an error code: HTTP status and whether a retry may help."""

    http_status: int
    retryable: bool


ERROR_SPECS: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.INVALID_REQUEST: ErrorSpec(422, False),
    ErrorCode.NOT_FOUND: ErrorSpec(404, False),
    ErrorCode.METHOD_NOT_ALLOWED: ErrorSpec(405, False),
    ErrorCode.PAYLOAD_TOO_LARGE: ErrorSpec(413, False),
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: ErrorSpec(415, False),
    ErrorCode.RATE_LIMITED: ErrorSpec(429, True),
    ErrorCode.LOCALE_UNSUPPORTED: ErrorSpec(422, False),
    ErrorCode.LLM_UNAVAILABLE: ErrorSpec(503, True),
    ErrorCode.LLM_INVALID_OUTPUT: ErrorSpec(502, True),
    ErrorCode.OCR_UNAVAILABLE: ErrorSpec(503, True),
    ErrorCode.SPEECH_UNAVAILABLE: ErrorSpec(503, True),
    ErrorCode.AUDIO_TOO_LARGE: ErrorSpec(413, False),
    ErrorCode.AUDIO_TOO_LONG: ErrorSpec(413, False),
    ErrorCode.AUDIO_FORMAT_UNSUPPORTED: ErrorSpec(415, False),
    ErrorCode.IMAGE_TOO_LARGE: ErrorSpec(413, False),
    ErrorCode.IMAGE_FORMAT_UNSUPPORTED: ErrorSpec(415, False),
    ErrorCode.TOOL_NOT_ALLOWED: ErrorSpec(500, False),
    ErrorCode.TOOL_FAILED: ErrorSpec(502, True),
    ErrorCode.OUTPUT_BLOCKED: ErrorSpec(500, False),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(500, True),
}


def message_key_for(code: ErrorCode) -> str:
    """Return the localizable template key for an error code."""
    return f"error.{code.value.lower()}"


class ErrorBody(BaseModel):
    """The inner object of an error response."""

    code: ErrorCode
    message_key: str
    retryable: bool
    fields: list[str] | None = None


class ErrorResponse(BaseModel):
    """The full error response: ``{"error": {...}}``."""

    error: ErrorBody


class RukoError(Exception):
    """An expected, typed failure that maps onto the error contract.

    The exception message is never shown to clients or logged; only the code is.
    """

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.code = code

    @property
    def spec(self) -> ErrorSpec:
        """Return the static spec (status, retryable) for this error."""
        return ERROR_SPECS[self.code]


def build_error_response(code: ErrorCode, fields: list[str] | None = None) -> ErrorResponse:
    """Create the standard error response body for a code.

    Args:
        code: The error code.
        fields: Optional request field locations (never values) for validation errors.

    Returns:
        The error response model.
    """
    spec = ERROR_SPECS[code]
    return ErrorResponse(
        error=ErrorBody(
            code=code,
            message_key=message_key_for(code),
            retryable=spec.retryable,
            fields=fields,
        )
    )
