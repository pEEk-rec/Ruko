"""The ``LLMProvider`` interface and its request and error types.

A provider turns one ``LLMRequest`` (system instruction, a few messages, an optional
image) into the model's text reply. Providers know nothing about Ruko's schemas: the
understanding layer validates every reply itself. Requests carry redacted text only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from ruko.errors import ErrorCode, RukoError


@dataclass(frozen=True)
class ImagePart:
    """An image sent with a message (screenshots only). Held in memory, never stored."""

    mime_type: str
    data: bytes

    def __repr__(self) -> str:
        """Show the type and size only, never the bytes."""
        return f"ImagePart(mime_type={self.mime_type!r}, bytes={len(self.data)})"


@dataclass(frozen=True)
class Message:
    """One turn of the conversation sent to the model."""

    role: Literal["user", "model"]
    text: str
    image: ImagePart | None = None


@dataclass(frozen=True)
class LLMRequest:
    """Everything a provider needs for one call."""

    system: str
    messages: tuple[Message, ...]
    json_output: bool = True
    max_output_tokens: int = 4096


class LLMError(RukoError):
    """A provider call failed. ``reason`` is a short content-free label for the trace."""

    def __init__(self, code: ErrorCode, reason: str) -> None:
        super().__init__(code)
        self.reason = reason


class LLMProvider(ABC):
    """Interface every LLM provider implements."""

    name: str = "llm"

    @abstractmethod
    def generate(self, request: LLMRequest) -> str:
        """Return the model's text reply.

        Args:
            request: System instruction, messages and output options.

        Returns:
            The reply text (JSON text when ``request.json_output`` is true).

        Raises:
            LLMError: When the provider is unreachable, refuses, or returns nothing.
        """
