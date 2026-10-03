"""Text normalization for pattern matching (never for display).

Two views of the same text are produced:

- ``normalize``: Unicode NFKC, lower-case, zero-width characters removed, curly quotes
  straightened, whitespace collapsed.
- ``deobfuscate``: the normalized text with common evasions undone, e.g. ``sh0uld 1 buy``
  becomes ``should i buy``, ``b-u-y`` becomes ``buy`` and Cyrillic look-alike letters
  become Latin ones.

Patterns are matched against both, so simple tricks do not slip past the guardrails.
"""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_WHITESPACE = re.compile(r"\s+")
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})

_CONFUSABLES = str.maketrans(
    {
        # Cyrillic and Greek letters that look like Latin ones.
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "ѕ": "s",
        "і": "i", "ј": "j", "һ": "h", "ԁ": "d", "ӏ": "l", "ο": "o", "α": "a", "ε": "e",
        "ι": "i", "κ": "k", "ν": "v", "ρ": "p", "τ": "t", "υ": "u",
    }
)  # fmt: skip
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_LEET_TOKEN = re.compile(r"[a-z0-9@$]*[a-z][a-z0-9@$]*")
# Runs of single letters joined by ONE kind of separator: "b.u.y", "b-u-y", "b u y".
_SPACED_LETTERS = re.compile(r"\b[a-z]([.\-_* ])(?:[a-z]\1)+[a-z]\b")
_SEPARATORS = re.compile(r"[.\-_* ]")


def normalize(text: str) -> str:
    """Return a canonical lower-case form of the text for matching."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = text.translate(_QUOTES)
    text = _WHITESPACE.sub(" ", text)
    return text.strip().lower()


def _undo_leet(match: re.Match[str]) -> str:
    token = match.group(0)
    # Only rewrite mixed tokens like "sh0uld"; leave plain numbers ("500") alone.
    if any(ch.isdigit() or ch in "@$" for ch in token) and any(ch.isalpha() for ch in token):
        return token.translate(_LEET)
    return token


def deobfuscate(normalized: str) -> str:
    """Undo leetspeak inside words and join s-p-a-c-e-d single letters.

    Args:
        normalized: Text already passed through ``normalize``.

    Returns:
        A de-obfuscated variant used as a second matching pass.
    """
    text = normalized.translate(_CONFUSABLES)
    text = _LEET_TOKEN.sub(_undo_leet, text)
    text = re.sub(r"(?<![a-z0-9])1(?![a-z0-9])", "i", text)
    return _SPACED_LETTERS.sub(lambda m: _SEPARATORS.sub("", m.group(0)), text)


def strip_zero_width(pattern: str) -> str:
    """Remove zero-width characters from a pattern so it matches normalized text."""
    return _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", pattern))
