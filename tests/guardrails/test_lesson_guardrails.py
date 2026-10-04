"""Lessons may report claims ("SEBI says be suspicious of ...") but never assert outcomes."""

import pytest

from ruko.guardrails.output_filter import find_violations

FORBIDDEN = [
    "You will get 12% a year if you stay invested.",
    "You will earn a lot from this plan.",
    "The expected return on this fund is high.",
    "This scheme is safe and guaranteed.",
    "This app is legit.",
    "You should buy this stock now.",
    "आपको हर साल अच्छा रिटर्न मिलेगा।",
    "ನಿಮಗೆ ಒಳ್ಳೆಯ ಲಾಭ ಸಿಗುತ್ತದೆ.",
]

ALLOWED = [
    "SEBI's guide says to be suspicious of anyone who promises assured returns.",
    "SEBI says registered investment advisers are prohibited from guaranteeing returns.",
    "Ruko can't vouch for any tip, app or person.",
    "In derivatives you may lose part or all of the margin, and the loss may exceed it.",
]


@pytest.mark.parametrize("text", FORBIDDEN)
def test_lesson_text_that_asserts_or_recommends_is_blocked(text):
    assert find_violations(text, "lesson")


@pytest.mark.parametrize("text", ALLOWED)
def test_lesson_text_that_reports_or_explains_is_allowed(text):
    assert find_violations(text, "lesson") == []
