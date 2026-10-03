"""Deterministic red-flag detection from the multilingual lexicons.

Every locale's lexicon (``data/lexicon/*.yaml``) runs on every input, on the normalized
text and on a de-obfuscated copy. Certainty is conservative:

- a "strong" pattern, or two *different* "weak" patterns for the same code -> ``likely``
- a single weak pattern -> ``possible``

The output is a list of signals. Ruko never concludes "this is a scam".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import data_dir, load_yaml
from ruko.guardrails.normalize import deobfuscate, normalize, strip_zero_width
from ruko.models.common import Certainty, EvidenceSpan, ReasonCode, SignalSource
from ruko.models.event import Signal

_FLAGS = re.IGNORECASE | re.UNICODE


@dataclass(frozen=True)
class LexiconPattern:
    """One compiled lexicon pattern."""

    pattern_id: str
    code: ReasonCode
    strong: bool
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Hint:
    """A compiled extraction hint (product class, holding intent or source type)."""

    field: str
    value: str
    regex: re.Pattern[str]


@lru_cache(maxsize=1)
def lexicon_files() -> tuple[dict, ...]:
    """Load every lexicon file (cached)."""
    paths = sorted((data_dir() / "lexicon").glob("*.yaml"))
    return tuple(load_yaml("lexicon", p.name) for p in paths)


@lru_cache(maxsize=1)
def load_patterns() -> tuple[LexiconPattern, ...]:
    """Compile all signal patterns from all locales (cached)."""
    patterns: list[LexiconPattern] = []
    for raw in lexicon_files():
        for code_name, groups in raw["signals"].items():
            for strength in ("strong", "weak"):
                for index, text in enumerate(groups.get(strength, [])):
                    patterns.append(
                        LexiconPattern(
                            pattern_id=f"{raw['locale']}:{code_name}:{strength}:{index}",
                            code=ReasonCode(code_name),
                            strong=strength == "strong",
                            regex=re.compile(strip_zero_width(text), _FLAGS),
                        )
                    )
    return tuple(patterns)


@lru_cache(maxsize=1)
def load_hints() -> tuple[Hint, ...]:
    """Compile all extraction hints from all locales (cached)."""
    hints: list[Hint] = []
    for raw in lexicon_files():
        for field, values in (raw.get("hints") or {}).items():
            for value, texts in values.items():
                hints.extend(
                    Hint(field, value, re.compile(strip_zero_width(t), _FLAGS)) for t in texts
                )
    return tuple(hints)


def _first_match(regex: re.Pattern[str], variants: tuple[str, ...]) -> re.Match[str] | None:
    for text in variants:
        match = regex.search(text)
        if match:
            return match
    return None


def detect_signals(text: str) -> list[Signal]:
    """Find red-flag patterns in (already redacted) text.

    Args:
        text: Redacted message text.

    Returns:
        One signal per reason code found, with certainty and an evidence span
        (offsets refer to the normalized text).
    """
    normalized = normalize(text)
    variants = (normalized, deobfuscate(normalized))
    hits: dict[ReasonCode, list[tuple[LexiconPattern, re.Match[str]]]] = {}
    for pattern in load_patterns():
        match = _first_match(pattern.regex, variants)
        if match:
            hits.setdefault(pattern.code, []).append((pattern, match))

    signals: list[Signal] = []
    for code, found in hits.items():
        strong = any(p.strong for p, _ in found)
        weak_ids = {p.pattern_id for p, _ in found if not p.strong}
        certainty = Certainty.LIKELY if strong or len(weak_ids) >= 2 else Certainty.POSSIBLE
        first = found[0][1]
        evidence = EvidenceSpan(start=first.start(), end=first.end(), text=first.group(0)[:200])
        signals.append(
            Signal(code=code, certainty=certainty, source=SignalSource.LEXICON, evidence=evidence)
        )
    return signals


def detect_hints(text: str) -> dict[str, list[str]]:
    """Return extraction hints found in text, e.g. ``{"product_class": ["derivative"]}``.

    Values are listed in data-file order without duplicates; the caller decides how to
    resolve several hints for the same field.
    """
    normalized = normalize(text)
    found: dict[str, list[str]] = {}
    for hint in load_hints():
        if hint.regex.search(normalized) and hint.value not in found.get(hint.field, []):
            found.setdefault(hint.field, []).append(hint.value)
    return found
