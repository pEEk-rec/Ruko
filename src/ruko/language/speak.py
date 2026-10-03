"""Build the text that text-to-speech reads: Ruko's own templates only.

Each ``TemplateRef`` is re-rendered on the server through the ``Renderer`` (so the
output filter runs again) instead of trusting text from the client. Slot values must
match ``data/policy/speech.yaml`` (numbers, rupee amounts, percentages), and items are
kept whole: if the next item would exceed the provider's limit, it and the rest are
left out and ``truncated`` is set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.errors import ErrorCode, RukoError
from ruko.language.templates import MissingSlotError, Renderer
from ruko.models.responses import TemplateRef


@dataclass(frozen=True)
class SpeechPolicy:
    """Limits on what can be spoken."""

    slot_value: re.Pattern[str]
    max_slots_per_item: int


@dataclass(frozen=True)
class SpeechText:
    """The text to speak and how many items made it in."""

    text: str
    item_count: int
    truncated: bool


@lru_cache(maxsize=1)
def get_speech_policy() -> SpeechPolicy:
    """Load ``data/policy/speech.yaml`` (cached)."""
    raw = load_yaml("policy", "speech.yaml")
    return SpeechPolicy(
        slot_value=re.compile(raw["slot_value_pattern"]),
        max_slots_per_item=int(raw["max_slots_per_item"]),
    )


def _render_item(item: TemplateRef, renderer: Renderer, policy: SpeechPolicy) -> str:
    if len(item.slots) > policy.max_slots_per_item or not all(
        policy.slot_value.match(value) for value in item.slots.values()
    ):
        raise RukoError(ErrorCode.INVALID_REQUEST)
    try:
        return renderer.text(item.key, **item.slots)
    except (KeyError, MissingSlotError):
        raise RukoError(ErrorCode.INVALID_REQUEST) from None


def build_speech_text(
    items: list[TemplateRef], renderer: Renderer, max_chars: int, policy: SpeechPolicy | None = None
) -> SpeechText:
    """Render template references into one filtered text for TTS.

    Args:
        items: Template references from a previous response's ``speak[]``.
        renderer: Renderer for the speech locale (runs the output filter).
        max_chars: The TTS provider's text limit.
        policy: Optional policy override.

    Returns:
        The text to speak.

    Raises:
        RukoError: ``INVALID_REQUEST`` for an unknown key, a missing slot or a slot value
            that is not a number-like string.
    """
    policy = policy or get_speech_policy()
    parts: list[str] = []
    length = 0
    truncated = False
    for item in items:
        rendered = _render_item(item, renderer, policy)
        added = len(rendered) + (1 if parts else 0)
        if length + added > max_chars:
            truncated = True
            break
        parts.append(rendered)
        length += added
    return SpeechText(text=" ".join(parts), item_count=len(parts), truncated=truncated)
