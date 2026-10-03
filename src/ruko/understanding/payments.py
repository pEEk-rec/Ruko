"""Classify payment destinations mentioned in (redacted) text.

Works on the placeholders left by ``language/redact.py``:

- ``[UPI_PHONE]@psp``: a UPI ID that is a phone number -> an individual's account.
- ``[UPI_USER].brk@validhdfc``: matches the SEBI ``@valid`` handle *pattern* for registered
  intermediaries. That is only a pattern; Ruko never calls it verified and points the
  user to SEBI Check.
- ``[UPI_USER]@psp``: another UPI ID; a signal only when the text asks for a payment.
- ``[ACCOUNT]`` near bank words (A/C, IFSC ...): bank details shared in chat.
- QR-code payment requests.

Payee type can be ambiguous, so certainty stays conservative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ruko.facts import upi_validated_handle
from ruko.guardrails.normalize import normalize
from ruko.models.common import Certainty, PaymentDestination, ReasonCode, SignalSource
from ruko.models.event import Signal

_UPI_PHONE = re.compile(r"\[upi_phone\]@[a-z0-9]+")
_UPI_USER = re.compile(r"\[upi_user\](?:\.([a-z]+))?@([a-z0-9]+)")
_ACCOUNT = re.compile(r"\[account\]")
_BANK_WORDS = re.compile(r"(\ba/?c\b|\bacc(oun)?t\b|\bifsc\b|\bkhata\b|खाता|खाते|ಖಾತೆ|ಅಕೌಂಟ್)")
_PAY_WORDS = re.compile(
    r"(\b(pay|paid|send|transfer|deposit|gpay|google pay|phonepe|paytm|bhejo|bhejein|"
    r"bhejiye|dalo|kalisi|haaki)\b|भेज|पेमेंट|डालें|ಕಳುಹಿಸಿ|ಪಾವತಿ|ಪೇ ಮಾಡಿ)"
)
_QR = re.compile(r"(\bqr\b|\bq\.r\.|क्यूआर|ಕ್ಯೂಆರ್)")


@dataclass(frozen=True)
class PaymentFindings:
    """Structural facts about payment instructions. Never contains IDs or numbers."""

    upi_phone: int
    upi_other: int
    upi_validated_pattern: int
    bank_details: bool
    qr_payment: bool
    pay_instruction: bool


def analyze_payments(redacted_text: str) -> PaymentFindings:
    """Find payment destinations in redacted text.

    Args:
        redacted_text: Output of ``redact()``.

    Returns:
        Counts and flags describing the payment instructions.
    """
    text = normalize(redacted_text)
    prefix, suffixes = upi_validated_handle()
    validated = other = 0
    for suffix, psp in _UPI_USER.findall(text):
        if psp.startswith(prefix) and suffix in suffixes:
            validated += 1
        else:
            other += 1
    return PaymentFindings(
        upi_phone=len(_UPI_PHONE.findall(text)),
        upi_other=other,
        upi_validated_pattern=validated,
        bank_details=bool(_ACCOUNT.search(text) and _BANK_WORDS.search(text)),
        qr_payment=bool(_QR.search(text)),
        pay_instruction=bool(_PAY_WORDS.search(text)),
    )


def payment_signals(findings: PaymentFindings) -> list[Signal]:
    """Turn payment findings into at most one ``PAY_TO_INDIVIDUAL_ACCOUNT`` signal."""
    if findings.upi_phone:
        certainty: Certainty | None = Certainty.LIKELY
    elif findings.pay_instruction and (
        findings.upi_other or findings.bank_details or findings.qr_payment
    ):
        certainty = Certainty.POSSIBLE
    else:
        certainty = None
    if certainty is None:
        return []
    return [
        Signal(
            code=ReasonCode.PAY_TO_INDIVIDUAL_ACCOUNT, certainty=certainty, source=SignalSource.RULE
        )
    ]


def payment_destination(findings: PaymentFindings) -> PaymentDestination:
    """Return ``individual_account`` only for clear cases; otherwise ``unknown``.

    Ruko never sets ``broker_or_exchange`` from text: only the user can declare that.
    """
    if findings.upi_phone:
        return PaymentDestination.INDIVIDUAL_ACCOUNT
    return PaymentDestination.UNKNOWN
