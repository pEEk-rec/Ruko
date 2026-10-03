"""Indian number formatting and rupee amounts in words (en, hi, kn).

- ``group_indian(150000)`` -> ``"1,50,000"`` (last three digits, then pairs).
- ``rupees(150000)`` -> ``"₹1,50,000"``.
- ``amount_in_words(150000, "en")`` -> ``"one lakh fifty thousand rupees"``.

Word tables live in ``data/language/numbers_{locale}.yaml``. A locale either lists all
words 0-99 (Hindi and Kannada, where they are irregular) or gives ``units`` (0-19) and
``tens`` that are joined by rule (English).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml

CRORE = 10_000_000
LAKH = 100_000
THOUSAND = 1_000


def group_indian(n: int) -> str:
    """Format an integer with Indian digit grouping, e.g. 15000000 -> '1,50,00,000'."""
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    pairs.insert(0, head)
    return sign + ",".join(pairs) + "," + tail


def rupees(n: int) -> str:
    """Format whole rupees with the ₹ sign and Indian grouping."""
    return ("-₹" if n < 0 else "₹") + group_indian(abs(n))


@dataclass(frozen=True)
class NumberWords:
    """Word tables for one locale."""

    words_0_99: tuple[str, ...]
    hundred: str | None
    hundreds: tuple[str | None, ...] | None
    hundreds_before_more: tuple[str | None, ...] | None
    thousand: str
    lakh: str
    crore: str
    currency_one: str
    currency_many: str


def _compose_0_99(raw: dict) -> tuple[str, ...]:
    units, tens, joiner = raw["units"], raw["tens"], raw.get("tens_joiner", " ")
    words = list(units)
    for n in range(20, 100):
        ten, unit = divmod(n, 10)
        words.append(tens[ten] if unit == 0 else f"{tens[ten]}{joiner}{units[unit]}")
    return tuple(words)


@lru_cache(maxsize=16)
def number_words(locale: str) -> NumberWords:
    """Load the number-word tables for a locale (cached)."""
    raw = load_yaml("language", f"numbers_{locale}.yaml")
    words = tuple(raw["words_0_99"]) if "words_0_99" in raw else _compose_0_99(raw)
    if len(words) != 100:
        raise ValueError(f"numbers_{locale}.yaml must define 100 words for 0-99")
    return NumberWords(
        words_0_99=words,
        hundred=raw.get("hundred"),
        hundreds=tuple(raw["hundreds"]) if "hundreds" in raw else None,
        hundreds_before_more=(
            tuple(raw["hundreds_before_more"]) if "hundreds_before_more" in raw else None
        ),
        thousand=raw["thousand"],
        lakh=raw["lakh"],
        crore=raw["crore"],
        currency_one=raw["currency_one"],
        currency_many=raw["currency_many"],
    )


def _below_thousand(n: int, words: NumberWords) -> list[str]:
    hundreds, rest = divmod(n, 100)
    parts: list[str] = []
    if hundreds:
        if words.hundreds:
            table = words.hundreds_before_more if rest and words.hundreds_before_more else None
            parts.append(str((table or words.hundreds)[hundreds]))
        else:
            parts.extend([words.words_0_99[hundreds], str(words.hundred)])
    if rest:
        parts.append(words.words_0_99[rest])
    return parts


def number_in_words(n: int, locale: str) -> str:
    """Spell a non-negative integer in the Indian system (thousand, lakh, crore).

    Args:
        n: The number (0 or more).
        locale: Locale with a numbers data file.

    Returns:
        The number in words, e.g. ``"one crore fifty lakh"``.

    Raises:
        ValueError: If ``n`` is negative.
    """
    if n < 0:
        raise ValueError("number_in_words expects a non-negative integer")
    words = number_words(locale)
    if n == 0:
        return words.words_0_99[0]
    crores, rest = divmod(n, CRORE)
    lakhs, rest = divmod(rest, LAKH)
    thousands, rest = divmod(rest, THOUSAND)
    parts: list[str] = []
    if crores:
        parts.extend([number_in_words(crores, locale), words.crore])
    if lakhs:
        parts.extend([words.words_0_99[lakhs], words.lakh])
    if thousands:
        parts.extend([words.words_0_99[thousands], words.thousand])
    parts.extend(_below_thousand(rest, words))
    return " ".join(parts)


def amount_in_words(n: int, locale: str) -> str:
    """Spell a whole-rupee amount, e.g. ``"one lakh fifty thousand rupees"``."""
    words = number_words(locale)
    currency = words.currency_one if n == 1 else words.currency_many
    return f"{number_in_words(n, locale)} {currency}"
