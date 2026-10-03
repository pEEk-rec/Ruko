"""What arrives at Ruko (``RawInput``) and what the language layer produces from it."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from ruko.models.common import LOCALE_PATTERN, StrictModel


class InputType(StrEnum):
    """The kind of content the user shared."""

    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    LINK = "link"


class Script(StrEnum):
    """Writing system detected in the text."""

    LATIN = "latin"
    DEVANAGARI = "devanagari"
    KANNADA = "kannada"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RawInput(StrictModel):
    """One piece of shared content, exactly as the device sent it.

    Never stored or logged. For ``image`` the content is base64; for ``voice`` the
    audio goes to the voice endpoint and only its transcript becomes a ``RawInput``.
    """

    type: InputType = Field(description="What kind of content this is.")
    content: str = Field(
        min_length=1,
        description="Text, a link string, or base64 image data. Max size is set by config.",
    )
    claimed_locale: str | None = Field(
        default=None,
        pattern=LOCALE_PATTERN,
        description="Language the device thinks this is in (a hint, not trusted).",
    )


class NormalizedInput(StrictModel):
    """Text after language detection and local PII redaction.

    ``redaction_counts`` says how many items of each type were removed; it never
    contains the removed values.
    """

    text: str = Field(description="Redacted text. The only form sent to any external service.")
    language: str = Field(pattern=LOCALE_PATTERN, description="Detected language code.")
    script: Script = Field(description="Detected writing system.")
    language_confidence: float = Field(ge=0.0, le=1.0, description="Detector confidence 0..1.")
    is_code_mixed: bool = Field(description="True if more than one language is mixed.")
    is_romanized: bool = Field(description="True if an Indian language is written in Latin script.")
    redaction_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of redacted items by type, e.g. {'phone': 1}. Never the values.",
    )
