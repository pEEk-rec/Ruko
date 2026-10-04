"""Short quotes from the user's own message, so a signal can show *where* it came from.

A signal such as "the message contains a guaranteed-return claim" is only convincing if the
person can see the words. This module turns a signal's evidence span (offsets into the
**redacted** text) into one short clause of that same redacted text.

Rules, because this is the one place message text goes back to the user:

- the excerpt is a plain substring of the redacted message (no rewriting, no model output);
- at most ``MAX_QUOTE`` characters, cut at a clause boundary where possible;
- phone numbers, UPI IDs, account numbers and the like appear as the redaction placeholders;
- it travels only in ``SignalView.quote`` of the response to the person who sent the message;
  it is never logged, never spoken by text-to-speech, and never stored.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ruko.models.common import ReasonCode
from ruko.models.event import Signal

MAX_QUOTE = 140
"""Longest quote, in characters."""

_REACH = 90
"""How far from the matched words to look for the start and end of the clause."""

# A full stop ends a clause only before a space or the end, so "bit.ly/x" stays whole.
_BOUNDARY = re.compile(r"[.!?](?=\s|$)|[\n\r|•]")
_SPACES = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_PLACEHOLDER_ONLY = re.compile(r"^[\s\[\]A-Z_@.\-0-9]*$")


def _clause(redacted: str, start: int, end: int) -> str:
    """Expand a match to the clause around it, within ``_REACH`` characters either side."""
    left = redacted.rfind("\n", 0, start)
    window_start = max(0, start - _REACH)
    cut = max((m.end() for m in _BOUNDARY.finditer(redacted, window_start, start)), default=-1)
    first = max(window_start if left < 0 else left + 1, cut if cut >= 0 else 0)
    after = _BOUNDARY.search(redacted, end, min(len(redacted), end + _REACH))
    last = after.end() if after else min(len(redacted), end + _REACH)
    return redacted[first:last]


def _tidy(text: str) -> str:
    text = _SPACES.sub(" ", _CONTROL.sub("", text)).strip(" -–—:;,|•")
    if len(text) <= MAX_QUOTE:
        return text
    cut = text.rfind(" ", 0, MAX_QUOTE - 1)
    return text[: cut if cut > MAX_QUOTE // 2 else MAX_QUOTE - 1].rstrip(" ,;:") + "…"


def signal_quotes(signals: Iterable[Signal], redacted: str) -> dict[ReasonCode, str]:
    """Return one short quote per reason code that has evidence in the redacted message.

    Args:
        signals: The event's signals (their evidence offsets are into ``redacted``).
        redacted: The redacted message text the signals were found in.

    Returns:
        ``{reason code: quote}``. Codes without usable evidence are left out.
    """
    quotes: dict[ReasonCode, str] = {}
    for signal in signals:
        span = signal.evidence
        if span is None or signal.code in quotes or span.end > len(redacted):
            continue
        quote = _tidy(_clause(redacted, span.start, span.end))
        if len(quote) >= 3 and not _PLACEHOLDER_ONLY.match(quote):
            quotes[signal.code] = quote
    return quotes
