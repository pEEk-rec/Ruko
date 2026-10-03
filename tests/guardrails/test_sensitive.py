"""Sensitive-data detection: refuse secrets, but analyze payee details in scam messages."""

import pytest

from ruko.guardrails.normalize import deobfuscate, normalize
from ruko.guardrails.sensitive import detect_sensitive, luhn_valid


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("My OTP is 482913", "otp"),
        ("482913 is your OTP for login", "otp"),
        ("ओटीपी 734512 है", "otp"),
        ("ಒಟಿಪಿ 123456", "otp"),
        ("upi pin 4821", "pin"),
        ("PIN 4821", "pin"),
        ("cvv 123", "cvv"),
        ("password: Tiger@2024", "password"),
        ("my password is hunter22", "password"),
        ("my bank account no 123456789012", "own_account_number"),
        ("मेरा खाता नंबर 123456789012", "own_account_number"),
        ("debit card 4111111111111111", "card_number"),
        ("4111 1111 1111 1111", "card_number"),
    ],
)
def test_detects_secrets(text, kind):
    assert kind in detect_sensitive(text)


@pytest.mark.parametrize(
    "text",
    [
        "Pin code 560001",
        "Pay to A/C 123456789012 IFSC SBIN0001234",
        "Call 9876543210 for VIP group",
        "Invest Rs 1,00,000 and get 5% monthly",
        "Order ID 4111111111111111 shipped",
        "SIP of Rs 5000 due on 5th",
    ],
)
def test_does_not_flag_ordinary_or_third_party_numbers(text):
    assert detect_sensitive(text) == []


def test_luhn():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")
    assert not luhn_valid("1234")


def test_normalize_and_deobfuscate():
    assert normalize("  Ｓhould\u200b  I\nBUY ") == "should i buy"
    assert deobfuscate("sh0uld 1 buy 500 shares") == "should i buy 500 shares"
    assert deobfuscate("b-u-y n.o.w") == "buy now"
