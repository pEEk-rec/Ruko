"""Language and script detection for en, hi, kn, romanized and code-mixed text.

Method (deterministic, explainable):

1. Count letters per script (Latin, and each Indian script range in the registry).
2. If an Indian script dominates, that is the language. If Latin letters are also a
   sizeable share, the text is code-mixed.
3. For Latin-only text, count marker words from ``data/language/languages.yaml``:
   frequent function words of English and of romanized Hindi / Kannada. Romanized
   markers win if they are frequent enough; English markers alongside them mean
   code-mixed.

Confidence is a number in 0..1 that reflects how clear the evidence was.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.models.inputs import Script

_LATIN_WORD = re.compile(r"[a-z]+")
_MIXED_SHARE = 0.2
_ROMANIZED_SHARE = 0.12


@dataclass(frozen=True)
class LanguageSpec:
    """Registry entry for one language."""

    code: str
    script: Script
    unicode_range: tuple[int, int] | None
    markers: frozenset[str]


@dataclass(frozen=True)
class Detection:
    """Result of language detection."""

    language: str
    script: Script
    confidence: float
    is_code_mixed: bool
    is_romanized: bool


@lru_cache(maxsize=1)
def language_registry() -> tuple[LanguageSpec, ...]:
    """Load the language registry (cached)."""
    raw = load_yaml("language", "languages.yaml")["languages"]
    specs = []
    for code, spec in raw.items():
        rng = spec.get("unicode_range")
        markers = spec.get("markers") or spec.get("romanized_markers") or []
        specs.append(
            LanguageSpec(
                code=code,
                script=Script(spec["script"]),
                unicode_range=(int(rng[0]), int(rng[1])) if rng else None,
                markers=frozenset(str(m).lower() for m in markers),
            )
        )
    return tuple(specs)


def _script_counts(text: str, specs: tuple[LanguageSpec, ...]) -> tuple[int, dict[str, int]]:
    latin = 0
    indic: dict[str, int] = {s.code: 0 for s in specs if s.unicode_range}
    for char in text:
        if char.isascii() and char.isalpha():
            latin += 1
            continue
        point = ord(char)
        for spec in specs:
            if spec.unicode_range and spec.unicode_range[0] <= point <= spec.unicode_range[1]:
                indic[spec.code] += 1
                break
    return latin, indic


def _detect_latin(text: str, specs: tuple[LanguageSpec, ...], default: str) -> Detection:
    words = _LATIN_WORD.findall(text.lower())
    if not words:
        return Detection(default, Script.UNKNOWN, 0.0, False, False)
    shares = {s.code: sum(w in s.markers for w in words) / len(words) for s in specs}
    english = shares.pop("en", 0.0)
    best_code, best_share = max(shares.items(), key=lambda kv: kv[1], default=("en", 0.0))
    if best_share >= _ROMANIZED_SHARE and best_share >= english * 0.5:
        mixed = english >= _ROMANIZED_SHARE
        confidence = min(0.95, 0.5 + best_share)
        return Detection(best_code, Script.LATIN, round(confidence, 2), mixed, True)
    confidence = min(0.95, 0.5 + english) if english else 0.4
    return Detection("en", Script.LATIN, round(confidence, 2), False, False)


def detect_language(text: str, default: str = "en") -> Detection:
    """Detect language, script, code-mixing and romanization.

    Args:
        text: Input text.
        default: Language returned when there is no evidence at all.

    Returns:
        A ``Detection``.
    """
    specs = language_registry()
    latin, indic = _script_counts(text, specs)
    indic_code, indic_count = max(indic.items(), key=lambda kv: kv[1], default=(default, 0))
    total = latin + sum(indic.values())
    if total == 0:
        return Detection(default, Script.UNKNOWN, 0.0, False, False)
    if indic_count == 0:
        return _detect_latin(text, specs, default)

    spec = next(s for s in specs if s.code == indic_code)
    other_indic = sum(indic.values()) - indic_count
    mixed = latin / total >= _MIXED_SHARE or other_indic / total >= _MIXED_SHARE
    script = Script.MIXED if mixed else spec.script
    confidence = round(min(0.99, 0.5 + indic_count / total / 2), 2)
    return Detection(indic_code, script, confidence, mixed, False)
