"""Local PII redaction. Runs before any text leaves the server (LLM, OCR follow-ups).

Replaces phone numbers, UPI IDs, emails, PAN, card-like and account-like numbers, and
names after salutations with typed placeholders. Returns the redacted text and a count
per type; the original values are never returned or stored.

UPI IDs keep their *handle* (the part after ``@``) and a SEBI category suffix if present
(``.brk``, ``.mf`` ...), because those describe the kind of payee, not a person:
``ramesh.k@oksbi`` -> ``[UPI_USER]@oksbi``; ``98xxxxxx10@ybl`` -> ``[UPI_PHONE]@ybl``;
``abc.brk@validhdfc`` -> ``[UPI_USER].brk@validhdfc``.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from ruko.facts import upi_validated_handle
from ruko.guardrails.sensitive import luhn_valid

_EMAIL = re.compile(r"\b[\w.+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)+\b", re.IGNORECASE)
_UPI = re.compile(r"(?<![\w.\-])([\w.\-]{2,256})@([a-z][a-z0-9]{1,63})\b(?!\.[a-z])", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?|0)?[6-9]\d{4}[\s\-]?\d{5}(?!\d)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# Card/Aadhaar-style groups (4-4-4[-n]) or a plain run of 9-19 digits.
_LONG_NUMBER = re.compile(r"(?<![\d,])(?:\d{4}([ \-])\d{4}\1\d{4}(?:\1\d{1,7})?|\d{9,19})(?![\d,])")
_MONEY_BEFORE = re.compile(r"(₹|\brs\.?|\binr|\brupees?)\s*$", re.IGNORECASE)
_NAME_EN = re.compile(
    r"\b(Mr|Mrs|Ms|Miss|Dr|Shri|Sri|Smt|Kumari)\.?\s+([A-Z][a-z]+)(\s+[A-Z][a-z]+)?"
)
_NAME_INDIC = re.compile(r"(श्री|श्रीमती|सुश्री|डॉ\.?|ಶ್ರೀ|ಶ್ರೀಮತಿ|ಡಾ\.?)\s+(\S+)")
_PHONE_LIKE = re.compile(r"^(?:\+?91)?[6-9]\d{9}$")


@dataclass(frozen=True)
class Redaction:
    """Redacted text plus counts by type. Never contains the removed values."""

    text: str
    counts: dict[str, int]


def _upi_placeholder(username: str) -> str:
    if _PHONE_LIKE.match(re.sub(r"\D", "", username)) and username.replace("+", "").isdigit():
        return "[UPI_PHONE]"
    suffix = username.rsplit(".", 1)[-1].lower() if "." in username else ""
    _, suffixes = upi_validated_handle()
    return f"[UPI_USER].{suffix}" if suffix in suffixes else "[UPI_USER]"


def _replace_long_number(match: re.Match[str], counts: Counter[str]) -> str:
    preceding = match.string[max(0, match.start() - 8) : match.start()]
    if _MONEY_BEFORE.search(preceding):
        return match.group(0)  # an amount like "Rs 100000000" is not personal data
    digits = re.sub(r"\D", "", match.group(0))
    if luhn_valid(digits):
        counts["card"] += 1
        return "[CARD]"
    counts["account"] += 1
    return "[ACCOUNT]"


def redact(text: str) -> Redaction:
    """Redact personal data from text.

    Args:
        text: Original text (kept only in memory by the caller).

    Returns:
        A ``Redaction`` with the redacted text and counts by type.
    """
    counts: Counter[str] = Counter()

    def sub(pattern: re.Pattern[str], kind: str, replacement: str, value: str) -> str:
        def repl(_m: re.Match[str]) -> str:
            counts[kind] += 1
            return replacement

        return pattern.sub(repl, value)

    text = sub(_EMAIL, "email", "[EMAIL]", text)

    def upi_repl(match: re.Match[str]) -> str:
        counts["upi_id"] += 1
        return f"{_upi_placeholder(match.group(1))}@{match.group(2)}"

    text = _UPI.sub(upi_repl, text)
    text = sub(_PAN, "pan", "[PAN]", text)
    text = sub(_PHONE, "phone", "[PHONE]", text)
    text = _LONG_NUMBER.sub(lambda m: _replace_long_number(m, counts), text)

    def name_repl(match: re.Match[str]) -> str:
        counts["name"] += 1
        return f"{match.group(1)} [NAME]"

    text = _NAME_EN.sub(name_repl, text)
    text = _NAME_INDIC.sub(name_repl, text)
    return Redaction(text=text, counts=dict(counts))
