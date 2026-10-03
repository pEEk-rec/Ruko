"""Detects secrets the user must never share (OTP, PIN, CVV, password, card, own account).

Runs on the original text, in memory, before redaction. It returns only the *types*
found, never the values. If anything is found, Ruko refuses to process the input and
warns the user.

A payee's bank account inside a forwarded scam message is not the user's secret: it
is redacted and becomes a fraud signal instead (Stage 5). Only first-person account
numbers ("my account number ...") are treated as sensitive here.
"""

from __future__ import annotations

import re

from ruko.guardrails.normalize import normalize
from ruko.guardrails.policy import GuardrailPolicy, get_policy

_CARD_CONTEXT = re.compile(
    r"(card|debit|credit|visa|master ?card|rupay|amex|कार्ड|ಕಾರ್ಡ್)", re.IGNORECASE
)
_GROUPED_CARD = re.compile(r"(?<!\d)\d{4}([ -])\d{4}\1\d{4}\1\d{1,7}(?!\d)")


def luhn_valid(digits: str) -> bool:
    """Return True if a digit string passes the Luhn checksum used by payment cards."""
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _has_card_number(text: str, policy: GuardrailPolicy) -> bool:
    for match in policy.card_number_pattern.finditer(text):
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        if not luhn_valid(digits):
            continue
        window = text[max(0, match.start() - 40) : match.end() + 20]
        if _CARD_CONTEXT.search(window) or _GROUPED_CARD.fullmatch(candidate.strip()):
            return True
    return False


def detect_sensitive(text: str, policy: GuardrailPolicy | None = None) -> list[str]:
    """Return the sorted list of sensitive-data types found in the text.

    Args:
        text: Raw user input.
        policy: Optional policy override (defaults to the data file).

    Returns:
        Types such as ``["otp", "card_number"]``; empty when nothing is found.
    """
    policy = policy or get_policy()
    normalized = normalize(text)
    found = {
        kind
        for kind, patterns in policy.sensitive_patterns.items()
        if any(p.search(normalized) for p in patterns)
    }
    if _has_card_number(normalized, policy):
        found.add("card_number")
    return sorted(found)
